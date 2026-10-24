from __future__ import annotations

import asyncio
import re
import time
from datetime import datetime, timezone
from typing import Any

import httpx

BASE_URL = "https://data-api.binance.vision"
SUPPORTED_INTERVALS = {
    "1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h", "1d", "3d", "1w", "1M"
}
DEFAULT_SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "ADAUSDT"]
_SYMBOL_RE = re.compile(r"^[A-Z0-9]{5,20}$")


class MarketDataError(RuntimeError):
    """Raised when the upstream provider cannot return trustworthy market data."""


class BinancePublicMarketData:
    """Unauthenticated read-only adapter for Binance public spot market data."""

    def __init__(self, base_url: str = BASE_URL, timeout: float = 8.0, client: httpx.AsyncClient | None = None):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._client = client

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        try:
            if self._client is not None:
                response = await self._client.get(f"{self.base_url}{path}", params=params, timeout=self.timeout)
            else:
                async with httpx.AsyncClient(timeout=self.timeout, headers={"User-Agent": "NEXTRADE/0.2"}) as client:
                    response = await client.get(f"{self.base_url}{path}", params=params)
            response.raise_for_status()
            return response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise MarketDataError(f"Market provider request failed: {type(exc).__name__}") from exc

    @staticmethod
    def validate_symbol(symbol: str) -> str:
        normalized = symbol.upper().replace("/", "").strip()
        if not _SYMBOL_RE.fullmatch(normalized):
            raise ValueError("Invalid symbol. Use a symbol such as BTCUSDT.")
        return normalized

    @staticmethod
    def validate_interval(interval: str) -> str:
        if interval not in SUPPORTED_INTERVALS:
            raise ValueError(f"Unsupported interval: {interval}")
        return interval

    async def candles(self, symbol: str = "BTCUSDT", interval: str = "1m", limit: int = 300) -> dict[str, Any]:
        symbol = self.validate_symbol(symbol)
        interval = self.validate_interval(interval)
        if not 100 <= limit <= 1000:
            raise ValueError("limit must be between 100 and 1000")
        raw = await self._get("/api/v3/klines", {"symbol": symbol, "interval": interval, "limit": limit})
        if not isinstance(raw, list) or not raw:
            raise MarketDataError("Provider returned no candles")
        items = []
        for row in raw:
            if not isinstance(row, list) or len(row) < 11:
                continue
            try:
                items.append({
                    "open_time": int(row[0]),
                    "open": float(row[1]),
                    "high": float(row[2]),
                    "low": float(row[3]),
                    "close": float(row[4]),
                    "volume": float(row[5]),
                    "close_time": int(row[6]),
                    "quote_volume": float(row[7]),
                    "trades": int(row[8]),
                    "taker_buy_volume": float(row[9]),
                    "closed": int(row[6]) < int(time.time() * 1000),
                })
            except (TypeError, ValueError, OverflowError):
                continue
        if len(items) < 2:
            raise MarketDataError("Provider returned malformed candle data")
        return {
            "symbol": symbol,
            "interval": interval,
            "source": "Binance Spot public market data",
            "source_url": self.base_url,
            "received_at": datetime.now(timezone.utc).isoformat(),
            "candles": items,
            "count": len(items),
        }

    async def ticker(self, symbol: str) -> dict[str, Any]:
        normalized = self.validate_symbol(symbol)
        data = await self._get("/api/v3/ticker/24hr", {"symbol": normalized})
        try:
            return {
                "symbol": normalized,
                "last_price": float(data["lastPrice"]),
                "change_24h_percent": float(data["priceChangePercent"]),
                "volume_24h": float(data["volume"]),
                "high_24h": float(data["highPrice"]),
                "low_24h": float(data["lowPrice"]),
                "source": "Binance Spot public market data",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        except (KeyError, TypeError, ValueError) as exc:
            raise MarketDataError("Provider returned malformed ticker data") from exc

    async def tickers(self, symbols: list[str] | None = None) -> dict[str, Any]:
        selected = [self.validate_symbol(s) for s in (symbols or DEFAULT_SYMBOLS)]
        # Calls are intentionally bounded to a small explicit watchlist.
        results = await asyncio.gather(*(self.ticker(symbol) for symbol in selected[:20]))
        return {"items": results, "source": "Binance Spot public market data", "received_at": datetime.now(timezone.utc).isoformat()}

    async def ping(self) -> bool:
        await self._get("/api/v3/ping")
        return True
