from __future__ import annotations

import time
from datetime import date, datetime, timezone
from typing import Any

import httpx

from app.core.config import settings


class EconomicCalendarError(RuntimeError):
    pass


class FinnhubEconomicCalendar:
    """Optional Finnhub economic calendar adapter; never fabricates events."""

    BASE_URL = "https://finnhub.io/api/v1"

    def __init__(self, api_key: str | None = None, timeout: float = 8.0):
        self.api_key = api_key if api_key is not None else getattr(settings, "economic_calendar_api_key", "")
        self.timeout = timeout
        self._cache: dict[tuple[str, str], tuple[float, dict[str, Any]]] = {}

    async def fetch(self, start_date: date, end_date: date, importance: str | None = None,
                    country: str | None = None) -> dict[str, Any]:
        if not self.api_key:
            raise EconomicCalendarError("Economic calendar is not configured. Set FINNHUB_API_KEY; no events are fabricated.")
        if end_date < start_date:
            raise ValueError("end date must be on or after start date")
        if (end_date - start_date).days > 31:
            raise ValueError("calendar date range must not exceed 31 days")
        cache_key = (start_date.isoformat(), end_date.isoformat())
        cached = self._cache.get(cache_key)
        if cached and time.monotonic() - cached[0] < 300:
            payload = dict(cached[1])
        else:
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.get(f"{self.BASE_URL}/calendar/economic", params={
                        "from": start_date.isoformat(), "to": end_date.isoformat(), "token": self.api_key,
                    })
                    response.raise_for_status()
                    raw = response.json()
            except (httpx.HTTPError, ValueError) as exc:
                raise EconomicCalendarError(f"Finnhub calendar request failed: {type(exc).__name__}") from exc
            events = raw.get("economicCalendar", []) if isinstance(raw, dict) else None
            if not isinstance(events, list):
                raise EconomicCalendarError("Finnhub returned an unexpected calendar response")
            normalized = []
            for item in events:
                if not isinstance(item, dict):
                    continue
                event_time = item.get("time")
                time_zone_status = "unknown"
                try:
                    parsed_time = datetime.fromisoformat(str(event_time).replace("Z", "+00:00"))
                    if parsed_time.tzinfo is None:
                        # Do not silently label a provider-local timestamp as UTC.
                        time_zone_status = "provider_timezone_unspecified"
                    else:
                        parsed_time = parsed_time.astimezone(timezone.utc)
                        time_zone_status = "UTC"
                except (TypeError, ValueError):
                    parsed_time = None
                level = str(item.get("impact") or "unknown").lower()
                if level not in {"low", "medium", "high"}:
                    level = "unknown"
                normalized.append({
                    "event": str(item.get("event") or "Unnamed event"),
                    "country": str(item.get("country") or "Unknown"),
                    "currency": item.get("currency"),
                    "importance": level,
                    "scheduled_at": parsed_time.isoformat() if parsed_time else event_time,
                    "time_zone_status": time_zone_status,
                    "actual": item.get("actual"), "forecast": item.get("estimate"),
                    "previous": item.get("prev"), "unit": item.get("unit"),
                    "source": "Finnhub economic calendar",
                })
            payload = {
                "source": "Finnhub economic calendar", "from": start_date.isoformat(), "to": end_date.isoformat(),
                "retrieved_at": datetime.now(timezone.utc).isoformat(), "stale": False, "items": normalized,
            }
            self._cache[cache_key] = (time.monotonic(), payload)
        items = payload["items"]
        if importance:
            wanted = importance.lower()
            if wanted not in {"low", "medium", "high"}:
                raise ValueError("importance must be low, medium, or high")
            items = [event for event in items if event["importance"] == wanted]
        if country:
            items = [event for event in items if event["country"].lower() == country.lower()]
        result = dict(payload)
        result["items"] = sorted(items, key=lambda e: str(e.get("scheduled_at") or ""))
        result["count"] = len(result["items"])
        return result
