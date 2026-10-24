import asyncio
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.market.binance import BinancePublicMarketData, MarketDataError

client = TestClient(app)


def test_health_endpoint_is_ok():
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "nextrade-api"
    assert "timestamp" in body


def test_candles_validates_bad_interval(monkeypatch):
    response = client.get("/v1/market/candles?symbol=BTCUSDT&interval=10m&limit=100")
    assert response.status_code == 422


def test_candles_rejects_invalid_symbol(monkeypatch):
    response = client.get("/v1/market/candles?symbol=BTC%20USDT&interval=1m&limit=100")
    assert response.status_code == 422


def test_analysis_endpoint_uses_provider_and_returns_engine_output(monkeypatch):
    now = int(datetime.now(timezone.utc).timestamp() * 1000)
    candles = []
    price = 100.0
    for index in range(100):
        price *= 1.003
        candles.append({
            "open_time": now - (100 - index) * 60_000,
            "open": price - 0.1, "high": price + 0.4, "low": price - 0.4,
            "close": price, "volume": 100 + index,
            "close_time": now - (100 - index) * 60_000 + 59_000,
            "quote_volume": 1000, "trades": 50, "taker_buy_volume": 50,
            "closed": True,
        })

    async def fake_candles(symbol="BTCUSDT", interval="15m", limit=300):
        return {"symbol": symbol.upper(), "interval": interval, "source": "fixture", "received_at": datetime.now(timezone.utc).isoformat(), "candles": candles}

    monkeypatch.setattr("app.main.market_data.candles", fake_candles)
    response = client.post("/v1/analyze/BTCUSDT?interval=15m")
    assert response.status_code == 200
    payload = response.json()
    assert payload["direction"] in {"LONG", "SHORT", "NO_TRADE"}
    assert payload["strategy_status"] == "experimental_unvalidated"
    assert "indicators" in payload
    if payload["direction"] == "LONG":
        assert payload["levels"]["stop_loss"] < payload["levels"]["entry"] < payload["levels"]["tp1"] < payload["levels"]["tp2"] < payload["levels"]["tp3"]


def test_insufficient_candles_return_no_trade():
    from app.strategy.engine import analyze_candles
    result = analyze_candles("BTCUSDT", "1m", [{"close": 100, "high": 101, "low": 99, "closed": True} for _ in range(20)])
    assert result["direction"] == "NO_TRADE"
    assert result["levels"] is None
    assert result["status"] == "insufficient_data"


def test_indicator_output_contains_expected_indicators():
    from app.market.indicators import latest_indicators
    candles = []
    price = 100.0
    for index in range(100):
        price += 0.2
        candles.append({"open": price - 0.1, "high": price + 0.5, "low": price - 0.5, "close": price, "volume": 100 + index})
    values = latest_indicators(candles)
    for key in ("sma20", "ema20", "ema50", "rsi14", "macd_histogram", "atr14", "adx14", "bollinger_upper", "bollinger_lower", "vwap20"):
        assert values[key] is not None, key
    assert values["bollinger_upper"] >= values["bollinger_middle"] >= values["bollinger_lower"]


@pytest.mark.asyncio
async def test_binance_adapter_parses_kline_payload():
    import httpx
    fixture = [[1700000000000, "100", "103", "99", "102", "1000", 1700000059999, "100000", 321, "500", "50000", "0"]]
    fixture.append([1700000060000, "102", "104", "101", "103", "1100", 1700000119999, "110000", 222, "600", "60000", "0"])
    async def handler(request):
        return httpx.Response(200, json=fixture)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client_http:
        adapter = BinancePublicMarketData(base_url="https://unit.test", client=client_http)
        result = await adapter.candles("BTCUSDT", "1m", 100)
    assert result["symbol"] == "BTCUSDT"
    assert result["count"] == 2
    assert result["candles"][0]["close"] == 102.0


def test_advanced_indicators_are_computed_from_candles():
    from app.market.indicators import latest_indicators
    candles = []
    price = 50.0
    for index in range(120):
        price += 0.15 if index % 6 else -0.04
        candles.append({
            "open": price - 0.05, "high": price + 0.25, "low": price - 0.3,
            "close": price, "volume": 250 + (index % 13) * 7,
        })
    result = latest_indicators(candles)
    for key in (
        "stoch_rsi_k", "stoch_rsi_d", "ichimoku_tenkan_sen", "ichimoku_kijun_sen",
        "ichimoku_senkou_span_a_current", "ichimoku_senkou_span_b_current",
        "supertrend", "supertrend_direction", "donchian_upper20_prev",
        "donchian_lower20_prev", "donchian_mid20_prev", "obv",
    ):
        assert result[key] is not None, key
    assert result["supertrend_direction"] in {"BULLISH", "BEARISH"}


def test_long_analysis_has_ordered_entry_stop_and_three_targets():
    from app.strategy.engine import analyze_candles
    now = int(datetime.now(timezone.utc).timestamp() * 1000)
    candles = []
    price = 100.0
    for index in range(150):
        price *= 1.003
        candles.append({
            "open_time": now - (150 - index) * 60_000,
            "open": price - 0.1, "high": price + 0.4, "low": price - 0.4,
            "close": price, "volume": 100 + index,
            "close_time": now - (150 - index) * 60_000 + 59_000, "closed": True,
        })
    result = analyze_candles("BTCUSDT", "15m", candles)
    assert result["direction"] == "LONG"
    levels = result["levels"]
    assert levels["stop_loss"] < levels["entry"] < levels["tp1"] < levels["tp2"] < levels["tp3"]
    assert levels["risk_reward"] == {"tp1": 1.0, "tp2": 2.0, "tp3": 3.0}
    assert result["score"] <= 100


def test_short_analysis_has_ordered_entry_stop_and_three_targets():
    from app.strategy.engine import analyze_candles
    now = int(datetime.now(timezone.utc).timestamp() * 1000)
    candles = []
    price = 10000.0
    for index in range(200):
        price *= 0.997
        candles.append({
            "open_time": now - (200 - index) * 60_000,
            "open": price + 1, "high": price + 5, "low": price - 5,
            "close": price, "volume": 1000 + index,
            "close_time": now - (200 - index) * 60_000 + 59_999, "closed": True,
        })
    result = analyze_candles("BTCUSDT", "15m", candles)
    assert result["direction"] == "SHORT"
    levels = result["levels"]
    assert 0 < levels["tp3"] < levels["tp2"] < levels["tp1"] < levels["entry"] < levels["stop_loss"]
    assert levels["risk_reward"] == {"tp1": 1.0, "tp2": 2.0, "tp3": 3.0}
