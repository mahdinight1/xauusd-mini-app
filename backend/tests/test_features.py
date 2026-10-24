from __future__ import annotations

from datetime import date, datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.backtest import simulate_backtest, simulate_walk_forward
from app.services.economic_calendar import EconomicCalendarError, FinnhubEconomicCalendar
from app.services.store import TradingStore

client = TestClient(app)


def sample_candles(count: int = 320, rising: bool = True):
    now = int(datetime.now(timezone.utc).timestamp() * 1000)
    price = 100.0
    result = []
    for i in range(count):
        price *= 1.003 if rising else 0.997
        result.append({
            "open_time": now - (count - i) * 60_000,
            "open": price / (1.003 if rising else 0.997),
            "high": price + max(0.4, price * 0.001),
            "low": price - max(0.4, price * 0.001),
            "close": price,
            "volume": 1000 + (i % 17) * 40,
            "close_time": now - (count - i) * 60_000 + 59_999,
            "closed": True,
        })
    return result


def test_demo_ledger_deduplicates_signal_and_records_partial_exit():
    store = TradingStore(":memory:")
    account = store.create_account(10_000)
    first = store.open_position(account["id"], symbol="BTCUSDT", interval="15m", direction="LONG",
                                entry=100, stop_loss=90, tp1=110, tp2=120, tp3=130, signal_candle_time=123)
    assert first is not None
    duplicate = store.open_position(account["id"], symbol="BTCUSDT", interval="15m", direction="LONG",
                                    entry=100, stop_loss=90, tp1=110, tp2=120, tp3=130, signal_candle_time=123)
    assert duplicate is None
    updated = store.update_position_bar(first["id"], high=111, low=100, close=110, bar_key="bar-1")
    assert updated["tp1_hit"] is True
    assert updated["remaining_qty"] == pytest.approx(first["initial_qty"] * 0.6)
    events = store.list_events(account["id"])
    assert any(event["event_type"] == "tp_hit" for event in events)
    assert any(item["event_type"] == "tp_hit" for item in store.list_notifications(account["id"]))


def test_demo_stop_is_conservative_when_stop_and_target_hit_same_bar():
    store = TradingStore(":memory:")
    account = store.create_account(5_000)
    position = store.open_position(account["id"], symbol="ETHUSDT", interval="5m", direction="LONG",
                                  entry=100, stop_loss=95, tp1=105, tp2=110, tp3=115, signal_candle_time=555)
    closed = store.update_position_bar(position["id"], high=106, low=94, close=101, bar_key="ambiguous")
    assert closed["status"] == "CLOSED"
    stop_events = [event for event in store.list_events(account["id"]) if event["event_type"] == "stop_hit"]
    assert stop_events
    assert "conservative_stop_first" in stop_events[0]["details"]["reason"]


def test_demo_preferences_roundtrip_and_backtest_history():
    store = TradingStore(":memory:")
    account = store.create_account(1_000)
    prefs = store.save_preferences(account["id"], {"enabled": True, "enabled_events": ["tp_hit"],
        "quiet_start": "22:00", "quiet_end": "07:00", "min_importance": "high", "push_enabled": False})
    assert prefs["enabled_events"] == ["tp_hit"]
    assert prefs["quiet_start"] == "22:00"
    run_id = store.save_backtest(account["id"], "BTCUSDT", "1h", "backtest", {"limit": 200}, {"status": "completed"})
    assert store.list_backtests()[0]["id"] == run_id


def test_backtest_uses_next_open_and_returns_metrics():
    result = simulate_backtest(sample_candles(240), symbol="BTCUSDT", interval="1m", signal_start=80)
    assert result["status"] == "completed"
    assert result["candles_used"] == 240
    assert "intrabar_priority" in result["execution_assumptions"]
    assert result["sample_size"] == result["trade_count"]
    assert isinstance(result["trades"], list)
    if result["trades"]:
        assert result["trades"][0]["entry_time"] > result["trades"][0]["signal_time"]


def test_walk_forward_produces_separate_out_of_sample_folds():
    result = simulate_walk_forward(sample_candles(320), symbol="BTCUSDT", interval="1h", folds=3, train_fraction=0.55)
    assert result["status"] == "completed"
    assert result["fold_count"] == 3
    assert len(result["folds"]) == 3
    assert "No parameter optimization" in result["method"]


@pytest.mark.asyncio
async def test_calendar_requires_provider_key_instead_of_fabricating_events():
    calendar = FinnhubEconomicCalendar(api_key="")
    with pytest.raises(EconomicCalendarError):
        await calendar.fetch(date(2026, 10, 24), date(2026, 10, 25))


def test_calendar_endpoint_reports_missing_configuration(monkeypatch):
    monkeypatch.setattr("app.main.economic_calendar", FinnhubEconomicCalendar(api_key=""))
    response = client.get("/v1/calendar/economic?from=2026-10-24&to=2026-10-25")
    assert response.status_code == 503
    assert "not configured" in response.json()["detail"].lower()


def test_demo_api_creates_persistent_account_and_preferences(monkeypatch):
    store = TradingStore(":memory:")
    monkeypatch.setattr("app.main.trading_store", store)
    response = client.post("/v1/demo/accounts", json={"initial_capital": 2500, "symbols": ["BTCUSDT"], "interval": "15m"})
    assert response.status_code == 200, response.text
    account = response.json()
    assert account["mode"] == "VIRTUAL/DEMO"
    assert account["initial_capital"] == 2500
    preference_response = client.get(f"/v1/demo/accounts/{account['id']}/notification-preferences")
    assert preference_response.status_code == 200
    toggle = client.post(f"/v1/demo/accounts/{account['id']}/auto", json={"enabled": True})
    assert toggle.status_code == 200
    assert toggle.json()["auto_enabled"] is True


def test_auto_demo_scan_opens_once_per_closed_signal_candle(monkeypatch):
    store = TradingStore(":memory:")
    monkeypatch.setattr("app.main.trading_store", store)
    account = store.create_account(10000, ["BTCUSDT"], "15m", 1.0, 10.0)
    candles = sample_candles(180, rising=True)
    candles[-1]["closed"] = False

    async def fake_candles(symbol="BTCUSDT", interval="15m", limit=300):
        return {"symbol": symbol, "interval": interval, "source": "test fixture", "received_at": datetime.now(timezone.utc).isoformat(), "candles": candles, "count": len(candles)}

    monkeypatch.setattr("app.main.market_data.candles", fake_candles)
    first = client.post(f"/v1/demo/accounts/{account['id']}/scan")
    assert first.status_code == 200, first.text
    assert first.json()["mode"] == "VIRTUAL/DEMO"
    second = client.post(f"/v1/demo/accounts/{account['id']}/scan")
    assert second.status_code == 200, second.text
    assert len(store.list_positions(account["id"], "OPEN")) <= 1
    assert len(store.list_positions(account["id"])) <= 1


def test_backtest_api_persists_completed_run(monkeypatch):
    store = TradingStore(":memory:")
    monkeypatch.setattr("app.main.trading_store", store)

    async def fake_candles(symbol="BTCUSDT", interval="1h", limit=300):
        candles = sample_candles(limit, rising=True)
        return {"symbol": symbol, "interval": interval, "source": "fixture only", "received_at": datetime.now(timezone.utc).isoformat(), "candles": candles}

    monkeypatch.setattr("app.main.market_data.candles", fake_candles)
    response = client.post("/v1/backtest", json={"symbol": "BTCUSDT", "interval": "1h", "candles_limit": 200, "initial_capital": 5000})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["run_id"]
    assert body["source"] == "fixture only"
    history = client.get("/v1/backtest/history")
    assert history.status_code == 200
    assert history.json()["items"][0]["id"] == body["run_id"]


def test_demo_equity_tracks_reserved_exposure_and_notification_read_state():
    store = TradingStore(":memory:")
    account = store.create_account(10_000)
    position = store.open_position(
        account["id"], symbol="BTCUSDT", interval="15m", direction="LONG",
        entry=100, stop_loss=90, tp1=110, tp2=120, tp3=130, signal_candle_time=999,
    )
    assert position is not None
    refreshed = store.get_account(account["id"])
    assert refreshed["exposure"] > 0
    assert refreshed["available_balance"] == pytest.approx(refreshed["equity"] - refreshed["exposure"])
    assert refreshed["net_return_percent"] < 0  # Entry fee is charged immediately.
    notification = store.list_notifications(account["id"])[0]
    assert notification["read_at"] is None
    assert store.mark_notification_read(account["id"], notification["id"])
    assert store.list_notifications(account["id"])[0]["read_at"] is not None


def test_notification_api_marks_notification_as_read(monkeypatch):
    store = TradingStore(":memory:")
    monkeypatch.setattr("app.main.trading_store", store)
    account = store.create_account(2_000)
    position = store.open_position(
        account["id"], symbol="ETHUSDT", interval="5m", direction="SHORT",
        entry=100, stop_loss=105, tp1=95, tp2=90, tp3=85, signal_candle_time=1001,
    )
    assert position is not None
    notification = store.list_notifications(account["id"])[0]
    response = client.post(f"/v1/demo/accounts/{account['id']}/notifications/{notification['id']}/read")
    assert response.status_code == 200
    assert response.json()["marked_read"] is True
    listed = client.get(f"/v1/demo/accounts/{account['id']}/notifications")
    assert listed.json()["items"][0]["read_at"] is not None
