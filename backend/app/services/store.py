from __future__ import annotations

import json
import os
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from app.core.config import settings


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json(value: Any) -> str:
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False)


class TradingStore:
    """Small SQLite-backed ledger for the prototype's virtual accounts and in-app events.

    It intentionally does not store exchange credentials and never sends real orders.
    Add user authentication/authorization before exposing this API to the public internet.
    """

    def __init__(self, db_path: str | None = None):
        configured = db_path or os.getenv("NEXTRADE_DB_PATH", settings.nextrade_db_path)
        if configured != ":memory:":
            Path(configured).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
        self.db_path = configured
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(configured, check_same_thread=False, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys=ON")
        if configured != ":memory:":
            self._conn.execute("PRAGMA journal_mode=WAL")
        self._initialize()

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                yield self._conn
                self._conn.execute("COMMIT")
            except Exception:
                self._conn.execute("ROLLBACK")
                raise

    def _initialize(self) -> None:
        with self._lock:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS demo_accounts (
                    id TEXT PRIMARY KEY,
                    initial_capital REAL NOT NULL,
                    realized_pnl REAL NOT NULL DEFAULT 0,
                    total_fees REAL NOT NULL DEFAULT 0,
                    auto_enabled INTEGER NOT NULL DEFAULT 0,
                    symbols_json TEXT NOT NULL DEFAULT '["BTCUSDT","ETHUSDT"]',
                    interval TEXT NOT NULL DEFAULT '15m',
                    risk_percent REAL NOT NULL DEFAULT 1.0,
                    fee_bps REAL NOT NULL DEFAULT 10.0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS demo_positions (
                    id TEXT PRIMARY KEY,
                    account_id TEXT NOT NULL REFERENCES demo_accounts(id) ON DELETE CASCADE,
                    symbol TEXT NOT NULL,
                    interval TEXT NOT NULL,
                    direction TEXT NOT NULL CHECK(direction IN ('LONG','SHORT')),
                    status TEXT NOT NULL CHECK(status IN ('OPEN','CLOSED')),
                    entry REAL NOT NULL,
                    stop_loss REAL NOT NULL,
                    tp1 REAL NOT NULL,
                    tp2 REAL NOT NULL,
                    tp3 REAL NOT NULL,
                    initial_qty REAL NOT NULL,
                    remaining_qty REAL NOT NULL,
                    current_price REAL NOT NULL,
                    realized_pnl REAL NOT NULL DEFAULT 0,
                    fees REAL NOT NULL DEFAULT 0,
                    tp1_hit INTEGER NOT NULL DEFAULT 0,
                    tp2_hit INTEGER NOT NULL DEFAULT 0,
                    tp3_hit INTEGER NOT NULL DEFAULT 0,
                    entry_fee_charged INTEGER NOT NULL DEFAULT 0,
                    signal_candle_time INTEGER,
                    opened_at TEXT NOT NULL,
                    closed_at TEXT,
                    metadata_json TEXT NOT NULL DEFAULT '{}'
                );
                CREATE INDEX IF NOT EXISTS idx_demo_positions_account_status ON demo_positions(account_id, status);
                CREATE INDEX IF NOT EXISTS idx_demo_positions_symbol_status ON demo_positions(symbol, status);
                CREATE TABLE IF NOT EXISTS demo_events (
                    id TEXT PRIMARY KEY,
                    account_id TEXT NOT NULL REFERENCES demo_accounts(id) ON DELETE CASCADE,
                    position_id TEXT REFERENCES demo_positions(id) ON DELETE SET NULL,
                    event_key TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    symbol TEXT,
                    price REAL,
                    quantity REAL,
                    pnl REAL NOT NULL DEFAULT 0,
                    fee REAL NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    details_json TEXT NOT NULL DEFAULT '{}',
                    UNIQUE(account_id, event_key)
                );
                CREATE INDEX IF NOT EXISTS idx_demo_events_account_time ON demo_events(account_id, created_at DESC);
                CREATE TABLE IF NOT EXISTS backtest_runs (
                    id TEXT PRIMARY KEY,
                    account_id TEXT,
                    symbol TEXT NOT NULL,
                    interval TEXT NOT NULL,
                    run_type TEXT NOT NULL,
                    config_json TEXT NOT NULL,
                    result_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS notification_preferences (
                    account_id TEXT PRIMARY KEY REFERENCES demo_accounts(id) ON DELETE CASCADE,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    enabled_events_json TEXT NOT NULL DEFAULT '["signal","trade_opened","tp_hit","stop_hit","trade_closed","calendar_high"]',
                    quiet_start TEXT,
                    quiet_end TEXT,
                    min_importance TEXT NOT NULL DEFAULT 'medium',
                    push_enabled INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS notifications (
                    id TEXT PRIMARY KEY,
                    account_id TEXT NOT NULL REFERENCES demo_accounts(id) ON DELETE CASCADE,
                    event_key TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    body TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    read_at TEXT,
                    payload_json TEXT NOT NULL DEFAULT '{}',
                    push_attempts INTEGER NOT NULL DEFAULT 0,
                    push_sent_at TEXT,
                    push_error TEXT,
                    UNIQUE(account_id, event_key)
                );
                CREATE INDEX IF NOT EXISTS idx_notifications_account_time ON notifications(account_id, created_at DESC);
                CREATE TABLE IF NOT EXISTS notification_devices (
                    account_id TEXT NOT NULL REFERENCES demo_accounts(id) ON DELETE CASCADE,
                    token TEXT NOT NULL,
                    platform TEXT NOT NULL DEFAULT 'android',
                    created_at TEXT NOT NULL,
                    PRIMARY KEY(account_id, token)
                );
                CREATE TABLE IF NOT EXISTS demo_executed_signals (
                    account_id TEXT NOT NULL REFERENCES demo_accounts(id) ON DELETE CASCADE,
                    symbol TEXT NOT NULL,
                    signal_candle_time INTEGER NOT NULL,
                    direction TEXT NOT NULL,
                    position_id TEXT,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY(account_id, symbol, signal_candle_time)
                );
                CREATE TABLE IF NOT EXISTS notification_push_deliveries (
                    notification_id TEXT NOT NULL REFERENCES notifications(id) ON DELETE CASCADE,
                    token TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0, sent_at TEXT, last_error TEXT, updated_at TEXT NOT NULL,
                    PRIMARY KEY(notification_id, token)
                );
                """
            )
            # Additive migrations keep older local databases usable.
            columns = {row[1] for row in self._conn.execute("PRAGMA table_info(notifications)").fetchall()}
            for name, declaration in (("push_attempts", "INTEGER NOT NULL DEFAULT 0"), ("push_sent_at", "TEXT"), ("push_error", "TEXT")):
                if name not in columns:
                    self._conn.execute(f"ALTER TABLE notifications ADD COLUMN {name} {declaration}")

    def create_account(self, initial_capital: float, symbols: list[str] | None = None,
                       interval: str = "15m", risk_percent: float = 1.0, fee_bps: float = 10.0) -> dict[str, Any]:
        now, account_id = utc_now(), str(uuid.uuid4())
        clean_symbols = list(dict.fromkeys((s.upper().replace("/", "") for s in (symbols or ["BTCUSDT", "ETHUSDT"]))))[:10]
        with self._transaction() as conn:
            conn.execute(
                "INSERT INTO demo_accounts(id,initial_capital,symbols_json,interval,risk_percent,fee_bps,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)",
                (account_id, initial_capital, _json(clean_symbols), interval, risk_percent, fee_bps, now, now),
            )
            conn.execute("INSERT INTO notification_preferences(account_id,updated_at) VALUES(?,?)", (account_id, now))
        return self.get_account(account_id) or {}

    def _account_row(self, account_id: str) -> sqlite3.Row | None:
        return self._conn.execute("SELECT * FROM demo_accounts WHERE id=?", (account_id,)).fetchone()

    def get_account(self, account_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._account_row(account_id)
            if row is None:
                return None
            open_positions = self._conn.execute("SELECT * FROM demo_positions WHERE account_id=? AND status='OPEN' ORDER BY opened_at DESC", (account_id,)).fetchall()
            closed_count = self._conn.execute("SELECT COUNT(*) AS n FROM demo_positions WHERE account_id=? AND status='CLOSED'", (account_id,)).fetchone()["n"]
            wins = self._conn.execute("SELECT COUNT(*) AS n FROM demo_positions WHERE account_id=? AND status='CLOSED' AND (realized_pnl-fees)>0", (account_id,)).fetchone()["n"]
            realized, fees = float(row["realized_pnl"]), float(row["total_fees"])
            cash_equity = float(row["initial_capital"]) + realized - fees
            unrealized = 0.0
            exposure = 0.0
            open_serialized = []
            for item in open_positions:
                position = self._position_dict(item)
                direction_sign = 1.0 if item["direction"] == "LONG" else -1.0
                unrealized += (float(item["current_price"]) - float(item["entry"])) * direction_sign * float(item["remaining_qty"])
                exposure += float(item["entry"]) * float(item["remaining_qty"])
                open_serialized.append(position)
            total_equity = cash_equity + unrealized
            return {
                "id": row["id"], "initial_capital": row["initial_capital"],
                "realized_pnl": realized, "total_fees": fees, "unrealized_pnl": unrealized,
                "equity": total_equity, "exposure": exposure, "available_balance": max(0.0, total_equity - exposure),
                "net_return_percent": ((total_equity / float(row["initial_capital"]) - 1) * 100) if row["initial_capital"] else 0,
                "auto_enabled": bool(row["auto_enabled"]), "symbols": json.loads(row["symbols_json"]),
                "interval": row["interval"], "risk_percent": row["risk_percent"], "fee_bps": row["fee_bps"],
                "open_positions": open_serialized, "open_count": len(open_serialized), "closed_count": closed_count,
                "win_rate_percent": (wins / closed_count * 100) if closed_count else None,
                "created_at": row["created_at"], "updated_at": row["updated_at"], "mode": "VIRTUAL/DEMO",
            }

    @staticmethod
    def _position_dict(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"], "account_id": row["account_id"], "symbol": row["symbol"], "interval": row["interval"],
            "direction": row["direction"], "status": row["status"], "entry": row["entry"], "stop_loss": row["stop_loss"],
            "tp1": row["tp1"], "tp2": row["tp2"], "tp3": row["tp3"], "initial_qty": row["initial_qty"],
            "remaining_qty": row["remaining_qty"], "current_price": row["current_price"], "realized_pnl": row["realized_pnl"],
            "fees": row["fees"], "tp1_hit": bool(row["tp1_hit"]), "tp2_hit": bool(row["tp2_hit"]),
            "tp3_hit": bool(row["tp3_hit"]), "signal_candle_time": row["signal_candle_time"],
            "opened_at": row["opened_at"], "closed_at": row["closed_at"], "metadata": json.loads(row["metadata_json"]),
        }

    def set_auto(self, account_id: str, enabled: bool) -> dict[str, Any] | None:
        with self._transaction() as conn:
            cur = conn.execute("UPDATE demo_accounts SET auto_enabled=?,updated_at=? WHERE id=?", (int(enabled), utc_now(), account_id))
            if cur.rowcount == 0:
                return None
        return self.get_account(account_id)

    def accounts_for_monitoring(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT a.id,a.symbols_json,a.interval,a.risk_percent,a.fee_bps,a.auto_enabled FROM demo_accounts a "
                "WHERE a.auto_enabled=1 OR EXISTS (SELECT 1 FROM demo_positions p WHERE p.account_id=a.id AND p.status='OPEN')"
            ).fetchall()
            return [{"id": r["id"], "symbols": json.loads(r["symbols_json"]), "interval": r["interval"],
                     "risk_percent": float(r["risk_percent"]), "fee_bps": float(r["fee_bps"]),
                     "auto_enabled": bool(r["auto_enabled"])} for r in rows]

    def get_open_positions(self, account_id: str, symbol: str | None = None) -> list[dict[str, Any]]:
        query = "SELECT * FROM demo_positions WHERE account_id=? AND status='OPEN'"
        params: list[Any] = [account_id]
        if symbol:
            query += " AND symbol=?"; params.append(symbol.upper())
        query += " ORDER BY opened_at DESC"
        with self._lock:
            return [self._position_dict(r) for r in self._conn.execute(query, params).fetchall()]

    def has_active_symbol(self, account_id: str, symbol: str) -> bool:
        with self._lock:
            return self._conn.execute("SELECT 1 FROM demo_positions WHERE account_id=? AND symbol=? AND status='OPEN' LIMIT 1", (account_id, symbol.upper())).fetchone() is not None

    def open_position(self, account_id: str, *, symbol: str, interval: str, direction: str,
                      entry: float, stop_loss: float, tp1: float, tp2: float, tp3: float,
                      signal_candle_time: int | None, risk_percent: float | None = None,
                      fee_bps: float | None = None, metadata: dict[str, Any] | None = None) -> dict[str, Any] | None:
        now, position_id = utc_now(), str(uuid.uuid4())
        if direction not in {"LONG", "SHORT"} or min(entry, stop_loss, tp1, tp2, tp3) <= 0:
            return None
        risk_distance = entry - stop_loss if direction == "LONG" else stop_loss - entry
        if risk_distance <= 0:
            return None
        with self._transaction() as conn:
            account = conn.execute("SELECT * FROM demo_accounts WHERE id=?", (account_id,)).fetchone()
            if account is None:
                return None
            if conn.execute("SELECT 1 FROM demo_positions WHERE account_id=? AND symbol=? AND status='OPEN'", (account_id, symbol.upper())).fetchone():
                return None
            cash_equity = max(0.0, float(account["initial_capital"]) + float(account["realized_pnl"]) - float(account["total_fees"]))
            open_exposure_rows = conn.execute("SELECT entry,remaining_qty,current_price,direction FROM demo_positions WHERE account_id=? AND status='OPEN'", (account_id,)).fetchall()
            reserved_exposure = sum(float(item["entry"]) * float(item["remaining_qty"]) for item in open_exposure_rows)
            unrealized = sum((float(item["current_price"]) - float(item["entry"])) * (1.0 if item["direction"] == "LONG" else -1.0) * float(item["remaining_qty"]) for item in open_exposure_rows)
            equity = max(0.0, cash_equity + unrealized)
            available_capital = max(0.0, equity - reserved_exposure)
            capital_cap = available_capital * 0.95 / entry
            risk_amount = equity * (risk_percent if risk_percent is not None else float(account["risk_percent"])) / 100
            quantity = min(risk_amount / risk_distance, capital_cap)
            if quantity <= 0:
                return None
            if signal_candle_time is not None:
                seen = conn.execute("INSERT OR IGNORE INTO demo_executed_signals(account_id,symbol,signal_candle_time,direction,position_id,created_at) VALUES(?,?,?,?,?,?)",
                                     (account_id, symbol.upper(), int(signal_candle_time), direction, position_id, now))
                if seen.rowcount == 0:
                    return None
            fee_rate = (fee_bps if fee_bps is not None else float(account["fee_bps"])) / 10_000
            entry_fee = entry * quantity * fee_rate
            conn.execute("UPDATE demo_accounts SET total_fees=total_fees+?,updated_at=? WHERE id=?", (entry_fee, now, account_id))
            conn.execute(
                "INSERT INTO demo_positions(id,account_id,symbol,interval,direction,status,entry,stop_loss,tp1,tp2,tp3,initial_qty,remaining_qty,current_price,fees,entry_fee_charged,signal_candle_time,opened_at,metadata_json) VALUES(?,?,?,?,?,'OPEN',?,?,?,?,?,?,?,?,?,1,?,?,?)",
                (position_id, account_id, symbol.upper(), interval, direction, entry, stop_loss, tp1, tp2, tp3,
                 quantity, quantity, entry, entry_fee, signal_candle_time, now, _json(metadata or {})),
            )
            self._insert_event(conn, account_id, position_id, f"open:{position_id}", "trade_opened", symbol.upper(), entry, quantity, 0.0, entry_fee, {"direction": direction})
        return self.get_position(position_id)

    def get_position(self, position_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute("SELECT * FROM demo_positions WHERE id=?", (position_id,)).fetchone()
            return self._position_dict(row) if row else None

    def _insert_event(self, conn: sqlite3.Connection, account_id: str, position_id: str | None,
                      event_key: str, event_type: str, symbol: str | None, price: float | None,
                      quantity: float | None, pnl: float, fee: float, details: dict[str, Any] | None = None) -> None:
        conn.execute(
            "INSERT OR IGNORE INTO demo_events(id,account_id,position_id,event_key,event_type,symbol,price,quantity,pnl,fee,created_at,details_json) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (str(uuid.uuid4()), account_id, position_id, event_key, event_type, symbol, price, quantity, pnl, fee, utc_now(), _json(details or {})),
        )
        if event_type in {"trade_opened", "tp_hit", "stop_hit", "trade_closed", "signal", "calendar_high"}:
            self._create_notification(conn, account_id, event_key, event_type, symbol or "NEXTRADE", price, details or {})

    def update_position_bar(self, position_id: str, *, high: float, low: float, close: float,
                            bar_key: str, fee_bps: float | None = None) -> dict[str, Any] | None:
        """Update an open paper position from one OHLC bar. If SL and TP touch together, SL wins."""
        events: list[tuple[str, str, float, float, float, dict[str, Any]]] = []
        with self._transaction() as conn:
            position = conn.execute("SELECT * FROM demo_positions WHERE id=?", (position_id,)).fetchone()
            if position is None:
                return None
            if position["status"] != "OPEN":
                return self._position_dict(position)
            account = conn.execute("SELECT * FROM demo_accounts WHERE id=?", (position["account_id"],)).fetchone()
            direction = position["direction"]
            entry, stop = float(position["entry"]), float(position["stop_loss"])
            initial_qty, remaining = float(position["initial_qty"]), float(position["remaining_qty"])
            current = float(close)
            targets = [float(position[f"tp{i}"]) for i in range(1, 4)]
            flags = [bool(position[f"tp{i}_hit"]) for i in range(1, 4)]
            fee_rate = (fee_bps if fee_bps is not None else float(account["fee_bps"])) / 10_000
            sign = 1.0 if direction == "LONG" else -1.0
            stop_touched = (low <= stop) if direction == "LONG" else (high >= stop)
            targets_touched = [high >= targets[i] if direction == "LONG" else low <= targets[i] for i in range(3)]
            any_target_touched = any(t and not flags[i] for i, t in enumerate(targets_touched))
            realized_delta = 0.0
            fee_delta = 0.0
            event_type_final = None
            # Since OHLC does not reveal intra-candle order, stop is conservatively first when both sides touch.
            if stop_touched and any_target_touched:
                exit_price = stop
                gross = (exit_price - entry) * sign * remaining
                fee = exit_price * remaining * fee_rate
                realized_delta += gross; fee_delta += fee
                events.append((f"{bar_key}:ambiguous-stop", "stop_hit", exit_price, remaining, gross, {"reason": "stop_and_target_touched_same_bar_conservative_stop_first"}))
                remaining = 0.0; event_type_final = "stop_hit"
            elif stop_touched:
                exit_price = stop
                gross = (exit_price - entry) * sign * remaining
                fee = exit_price * remaining * fee_rate
                realized_delta += gross; fee_delta += fee
                events.append((f"{bar_key}:stop", "stop_hit", exit_price, remaining, gross, {"reason": "stop_loss"}))
                remaining = 0.0; event_type_final = "stop_hit"
            else:
                allocations = [0.4, 0.3, 0.3]
                for index in range(3):
                    if targets_touched[index] and not flags[index] and remaining > 0:
                        # If a later target was reached in OHLC, prior targets must have been crossed too.
                        qty = min(remaining, initial_qty * allocations[index])
                        exit_price = targets[index]
                        gross = (exit_price - entry) * sign * qty
                        fee = exit_price * qty * fee_rate
                        realized_delta += gross; fee_delta += fee
                        remaining = max(0.0, remaining - qty)
                        flags[index] = True
                        events.append((f"{bar_key}:tp{index + 1}", "tp_hit", exit_price, qty, gross, {"target": index + 1, "allocation_percent": int(allocations[index] * 100)}))
                if remaining <= max(1e-12, initial_qty * 1e-10):
                    remaining = 0.0; event_type_final = "trade_closed"
            now = utc_now()
            conn.execute(
                "UPDATE demo_positions SET current_price=?,remaining_qty=?,realized_pnl=realized_pnl+?,fees=fees+?,tp1_hit=?,tp2_hit=?,tp3_hit=?,status=?,closed_at=? WHERE id=?",
                (current, remaining, realized_delta, fee_delta, int(flags[0]), int(flags[1]), int(flags[2]),
                 "CLOSED" if remaining <= 0 else "OPEN", now if remaining <= 0 else None, position_id),
            )
            conn.execute("UPDATE demo_accounts SET realized_pnl=realized_pnl+?,total_fees=total_fees+?,updated_at=? WHERE id=?",
                         (realized_delta, fee_delta, now, position["account_id"]))
            for key, kind, price, qty, pnl, details in events:
                fee_for_event = price * qty * fee_rate
                self._insert_event(conn, position["account_id"], position_id, f"{position_id}:{key}", kind,
                                   position["symbol"], price, qty, pnl, fee_for_event, details)
            if remaining <= 0 and event_type_final in {"trade_closed", "stop_hit"}:
                close_reason = "all_targets_completed" if event_type_final == "trade_closed" else "stop_loss"
                self._insert_event(conn, position["account_id"], position_id, f"{position_id}:{bar_key}:closed", "trade_closed",
                                   position["symbol"], current, 0, realized_delta, fee_delta, {"reason": close_reason})
        return self.get_position(position_id)

    def update_position_price(self, position_id: str, price: float, event_key: str, fee_bps: float | None = None) -> dict[str, Any] | None:
        return self.update_position_bar(position_id, high=price, low=price, close=price, bar_key=event_key, fee_bps=fee_bps)

    def list_positions(self, account_id: str, status: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
        query = "SELECT * FROM demo_positions WHERE account_id=?"
        params: list[Any] = [account_id]
        if status:
            query += " AND status=?"; params.append(status.upper())
        query += " ORDER BY opened_at DESC LIMIT ?"; params.append(max(1, min(limit, 1000)))
        with self._lock:
            return [self._position_dict(r) for r in self._conn.execute(query, params).fetchall()]

    def list_events(self, account_id: str, limit: int = 200) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute("SELECT * FROM demo_events WHERE account_id=? ORDER BY created_at DESC LIMIT ?", (account_id, max(1, min(limit, 1000)))).fetchall()
            return [{"id": r["id"], "account_id": r["account_id"], "position_id": r["position_id"], "event_key": r["event_key"],
                     "event_type": r["event_type"], "symbol": r["symbol"], "price": r["price"], "quantity": r["quantity"],
                     "pnl": r["pnl"], "fee": r["fee"], "created_at": r["created_at"], "details": json.loads(r["details_json"])} for r in rows]

    def save_backtest(self, account_id: str | None, symbol: str, interval: str, run_type: str,
                      config: dict[str, Any], result: dict[str, Any]) -> str:
        run_id = str(uuid.uuid4())
        with self._transaction() as conn:
            conn.execute("INSERT INTO backtest_runs(id,account_id,symbol,interval,run_type,config_json,result_json,created_at) VALUES(?,?,?,?,?,?,?,?)",
                         (run_id, account_id, symbol, interval, run_type, _json(config), _json(result), utc_now()))
        return run_id

    def list_backtests(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute("SELECT id,account_id,symbol,interval,run_type,config_json,result_json,created_at FROM backtest_runs ORDER BY created_at DESC LIMIT ?", (max(1, min(limit, 200)),)).fetchall()
            return [{"id": r["id"], "account_id": r["account_id"], "symbol": r["symbol"], "interval": r["interval"],
                     "run_type": r["run_type"], "config": json.loads(r["config_json"]), "result": json.loads(r["result_json"]), "created_at": r["created_at"]} for r in rows]

    def save_preferences(self, account_id: str, values: dict[str, Any]) -> dict[str, Any] | None:
        enabled_events = values.get("enabled_events", ["signal", "trade_opened", "tp_hit", "stop_hit", "trade_closed", "calendar_high"])
        with self._transaction() as conn:
            if conn.execute("SELECT 1 FROM demo_accounts WHERE id=?", (account_id,)).fetchone() is None:
                return None
            conn.execute("INSERT INTO notification_preferences(account_id,enabled,enabled_events_json,quiet_start,quiet_end,min_importance,push_enabled,updated_at) VALUES(?,?,?,?,?,?,?,?) "
                         "ON CONFLICT(account_id) DO UPDATE SET enabled=excluded.enabled,enabled_events_json=excluded.enabled_events_json,quiet_start=excluded.quiet_start,quiet_end=excluded.quiet_end,min_importance=excluded.min_importance,push_enabled=excluded.push_enabled,updated_at=excluded.updated_at",
                         (account_id, int(bool(values.get("enabled", True))), _json(enabled_events), values.get("quiet_start"), values.get("quiet_end"), values.get("min_importance", "medium"), int(bool(values.get("push_enabled", False))), utc_now()))
        return self.get_preferences(account_id)

    def get_preferences(self, account_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute("SELECT * FROM notification_preferences WHERE account_id=?", (account_id,)).fetchone()
            if not row: return None
            return {"account_id": row["account_id"], "enabled": bool(row["enabled"]), "enabled_events": json.loads(row["enabled_events_json"]),
                    "quiet_start": row["quiet_start"], "quiet_end": row["quiet_end"], "min_importance": row["min_importance"],
                    "push_enabled": bool(row["push_enabled"]), "updated_at": row["updated_at"]}

    def _create_notification(self, conn: sqlite3.Connection, account_id: str, event_key: str, event_type: str,
                             symbol: str, price: float | None, details: dict[str, Any]) -> None:
        pref = conn.execute("SELECT * FROM notification_preferences WHERE account_id=?", (account_id,)).fetchone()
        if pref and not pref["enabled"]: return
        if pref and event_type not in json.loads(pref["enabled_events_json"]): return
        title_map = {"trade_opened": "Demo trade opened", "tp_hit": "Demo target reached", "stop_hit": "Demo stop-loss reached",
                     "trade_closed": "Demo trade closed", "signal": "New signal", "calendar_high": "High-impact economic event"}
        body = f"{symbol} · {event_type.replace('_', ' ')}"
        if price is not None: body += f" · {price:.8g}"
        conn.execute("INSERT OR IGNORE INTO notifications(id,account_id,event_key,event_type,title,body,created_at,payload_json) VALUES(?,?,?,?,?,?,?,?)",
                     (str(uuid.uuid4()), account_id, event_key, event_type, title_map.get(event_type, event_type), body, utc_now(), _json({"symbol": symbol, "price": price, **details})))

    def list_notifications(self, account_id: str, limit: int = 100, unread_only: bool = False) -> list[dict[str, Any]]:
        query = "SELECT * FROM notifications WHERE account_id=?"
        params: list[Any] = [account_id]
        if unread_only:
            query += " AND read_at IS NULL"
        query += " ORDER BY created_at DESC LIMIT ?"; params.append(max(1, min(limit, 500)))
        with self._lock:
            rows = self._conn.execute(query, params).fetchall()
            return [{"id": r["id"], "account_id": r["account_id"], "event_key": r["event_key"], "event_type": r["event_type"],
                     "title": r["title"], "body": r["body"], "created_at": r["created_at"], "read_at": r["read_at"],
                     "payload": json.loads(r["payload_json"])} for r in rows]

    def mark_notification_read(self, account_id: str, notification_id: str) -> bool:
        with self._transaction() as conn:
            cur = conn.execute("UPDATE notifications SET read_at=? WHERE id=? AND account_id=?", (utc_now(), notification_id, account_id))
            return cur.rowcount > 0

    def notify_high_impact_calendar_events(self, events: list[dict[str, Any]]) -> int:
        created = 0
        with self._transaction() as conn:
            accounts = conn.execute("SELECT id FROM demo_accounts").fetchall()
            for event in events:
                if str(event.get("importance", "")).lower() != "high":
                    continue
                scheduled = str(event.get("scheduled_at") or "unknown-time")
                event_name = str(event.get("event") or "Economic event")
                country = str(event.get("country") or "Unknown")
                event_key = f"calendar:{scheduled}:{country}:{event_name}"
                for account in accounts:
                    before = conn.total_changes
                    self._create_notification(
                        conn, account["id"], event_key, "calendar_high", event_name, None,
                        {"event": event_name, "country": country, "scheduled_at": scheduled,
                         "importance": "high", "source": event.get("source", "Finnhub economic calendar")},
                    )
                    if conn.total_changes > before:
                        created += 1
        return created

    def add_device(self, account_id: str, token: str, platform: str = "android") -> bool:
        with self._transaction() as conn:
            if conn.execute("SELECT 1 FROM demo_accounts WHERE id=?", (account_id,)).fetchone() is None:
                return False
            conn.execute("INSERT OR REPLACE INTO notification_devices(account_id,token,platform,created_at) VALUES(?,?,?,?)", (account_id, token, platform, utc_now()))
        return True

    def account_ids_with_devices(self) -> list[tuple[str, str]]:
        with self._lock:
            rows = self._conn.execute("SELECT d.account_id,d.token FROM notification_devices d JOIN notification_preferences p ON p.account_id=d.account_id WHERE p.push_enabled=1 AND p.enabled=1").fetchall()
            return [(r["account_id"], r["token"]) for r in rows]

    def reset_account(self, account_id: str) -> bool:
        with self._transaction() as conn:
            account = conn.execute("SELECT id FROM demo_accounts WHERE id=?", (account_id,)).fetchone()
            if account is None: return False
            conn.execute("DELETE FROM demo_positions WHERE account_id=?", (account_id,))
            conn.execute("DELETE FROM demo_events WHERE account_id=?", (account_id,))
            conn.execute("DELETE FROM demo_executed_signals WHERE account_id=?", (account_id,))
            conn.execute("DELETE FROM notifications WHERE account_id=?", (account_id,))
            conn.execute("UPDATE demo_accounts SET realized_pnl=0,total_fees=0,auto_enabled=0,updated_at=? WHERE id=?", (utc_now(), account_id))
        return True

    def pending_push_deliveries(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._transaction() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO notification_push_deliveries(notification_id,token,updated_at) "
                "SELECT n.id,d.token,? FROM notifications n "
                "JOIN notification_devices d ON d.account_id=n.account_id "
                "JOIN notification_preferences p ON p.account_id=n.account_id "
                "WHERE p.enabled=1 AND p.push_enabled=1", (utc_now(),)
            )
            rows = conn.execute(
                "SELECT x.notification_id,x.token,n.title,n.body,n.payload_json,n.event_type,p.quiet_start,p.quiet_end "
                "FROM notification_push_deliveries x JOIN notifications n ON n.id=x.notification_id "
                "JOIN notification_preferences p ON p.account_id=n.account_id "
                "WHERE x.sent_at IS NULL AND x.attempts<3 ORDER BY n.created_at ASC LIMIT ?",
                (max(1, min(limit, 200)),)
            ).fetchall()
            now = datetime.now(timezone.utc).strftime("%H:%M")
            pending = []
            for r in rows:
                start, end = r["quiet_start"], r["quiet_end"]
                if start and end:
                    quiet = (start <= now < end) if start <= end else (now >= start or now < end)
                    if quiet:
                        continue
                pending.append({"notification_id": r["notification_id"], "token": r["token"], "title": r["title"],
                                "body": r["body"], "payload": json.loads(r["payload_json"])})
            return pending

    def mark_push_delivery(self, notification_id: str, token: str, success: bool, error: str | None = None) -> None:
        with self._transaction() as conn:
            conn.execute(
                "UPDATE notification_push_deliveries SET attempts=attempts+1,sent_at=?,last_error=?,updated_at=? "
                "WHERE notification_id=? AND token=?",
                (utc_now() if success else None, None if success else (error or "unknown error")[:300], utc_now(), notification_id, token),
            )

    def close(self) -> None:
        with self._lock:
            self._conn.close()
