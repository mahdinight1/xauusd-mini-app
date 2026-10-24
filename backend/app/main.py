from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone
import hashlib
import html
import random
import secrets
from urllib.parse import quote
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Query, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import SecretStr, EmailStr, field_validator
import sqlite3
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from app.core.config import settings
from app.domain.schemas import HealthResponse, MarketStatusResponse
from app.market.binance import BinancePublicMarketData, MarketDataError, DEFAULT_SYMBOLS
from app.market.indicators import latest_indicators
from app.strategy.engine import analyze_candles
from app.services.backtest import simulate_backtest, simulate_walk_forward
from app.services.economic_calendar import EconomicCalendarError, FinnhubEconomicCalendar
from app.services.notifications import fcm_is_configured, send_fcm
from app.services.store import TradingStore
from app.services.academy_content import MODULES, COURSE_TITLE, MODULE_PASS_PERCENT, FINAL_PASS_PERCENT, module_required_tier, public_module, public_question, grade
from app.services.product_security import (
    ProductStore, AuthService, auth_secret_configured, exchange_encryption_configured,
    encrypt_exchange_secret, decrypt_exchange_secret, certificate_signature, verify_certificate_signature, digest,
)
from app.services.integrations import BinanceReadOnlyConnector, ExchangeConnectionError, GooglePlaySubscriptionVerifier, GooglePlayVerificationError

logger = logging.getLogger("nextrade")
market_data = BinancePublicMarketData()
trading_store = TradingStore()
economic_calendar = FinnhubEconomicCalendar()
product_store = ProductStore()
auth_service = AuthService(product_store)
binance_connector = BinanceReadOnlyConnector()
google_play_verifier = GooglePlaySubscriptionVerifier()
bearer_scheme = HTTPBearer(auto_error=False)


class DemoAccountCreate(BaseModel):
    initial_capital: float = Field(gt=0, le=1_000_000_000)
    symbols: list[str] = Field(default_factory=lambda: ["BTCUSDT", "ETHUSDT"], min_length=1, max_length=10)
    interval: str = "15m"
    risk_percent: float = Field(default=1.0, gt=0, le=5)
    fee_bps: float = Field(default=10.0, ge=0, le=100)


class AutoTradingToggle(BaseModel):
    enabled: bool


class BacktestRequest(BaseModel):
    symbol: str = "BTCUSDT"
    interval: str = "1h"
    candles_limit: int = Field(default=500, ge=200, le=1000)
    initial_capital: float = Field(default=10_000, gt=0, le=1_000_000_000)
    risk_percent: float = Field(default=1.0, gt=0, le=5)
    fee_bps: float = Field(default=10, ge=0, le=100)
    slippage_bps: float = Field(default=2, ge=0, le=100)
    account_id: str | None = None


class WalkForwardRequest(BacktestRequest):
    candles_limit: int = Field(default=800, ge=300, le=1000)
    folds: int = Field(default=4, ge=2, le=6)
    train_fraction: float = Field(default=0.55, gt=0.35, lt=0.85)


class NotificationPreferences(BaseModel):
    enabled: bool = True
    enabled_events: list[str] = Field(default_factory=lambda: ["trade_opened", "tp_hit", "stop_hit", "trade_closed", "calendar_high"])
    quiet_start: str | None = None
    quiet_end: str | None = None
    min_importance: Literal["low", "medium", "high"] = "medium"
    push_enabled: bool = False


class DeviceRegistration(BaseModel):
    token: str = Field(min_length=20, max_length=4096)
    platform: Literal["android", "ios", "web"] = "android"


class RegisterRequest(BaseModel):
    display_name: str = Field(min_length=2, max_length=80)
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=10, max_length=256)


class LoginRequest(BaseModel):
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=1, max_length=256)


class LessonCompleteRequest(BaseModel):
    completed: bool = True


class QuizSubmission(BaseModel):
    answers: dict[str, int] = Field(min_length=1, max_length=30)


class ExchangeConnectRequest(BaseModel):
    api_key: SecretStr = Field(min_length=20, max_length=256)
    api_secret: SecretStr = Field(min_length=20, max_length=256)


class DemoSubscriptionActivateRequest(BaseModel):
    tier: Literal["pro", "premium"]


class GooglePlayVerifyRequest(BaseModel):
    product_id: str = Field(min_length=3, max_length=200)
    purchase_token: SecretStr = Field(min_length=20, max_length=8192)

    @field_validator("product_id")
    @classmethod
    def product_id_is_safe(cls, value: str) -> str:
        if not all(char.isalnum() or char in "._-" for char in value):
            raise ValueError("Invalid product ID")
        return value


def _auth_context(credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme)) -> dict[str, Any]:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Sign in is required", headers={"WWW-Authenticate": "Bearer"})
    validated = auth_service.validate(credentials.credentials)
    if not validated:
        raise HTTPException(status_code=401, detail="Session is invalid or expired; sign in again", headers={"WWW-Authenticate": "Bearer"})
    user, jti = validated
    return {"user": user, "jti": jti}


def current_user(context: dict[str, Any] = Depends(_auth_context)) -> dict[str, Any]:
    return context["user"]


_TIER_LEVEL = {"free": 0, "pro": 1, "premium": 2}


def _user_tier(user_id: str) -> str:
    return str(product_store.subscription_entitlement(user_id).get("tier", "free"))


def _require_tier(user_id: str, required_tier: str) -> None:
    if _TIER_LEVEL.get(_user_tier(user_id), 0) < _TIER_LEVEL[required_tier]:
        raise HTTPException(status_code=403, detail=f"This feature requires an active {required_tier.upper()} subscription. Open Profile → Membership to view plans.")


def _require_module_tier(user_id: str, module_id: int) -> None:
    _require_tier(user_id, module_required_tier(module_id))


def _certificate_link(request: Request, certificate_number: str, route: str) -> str:
    public_base = settings.public_base_url.strip().rstrip("/")
    if public_base:
        endpoint = "verify" if route == "verify_certificate" else "view"
        return f"{public_base}/v1/academy/certificates/{endpoint}/{quote(certificate_number, safe='')}"
    # Development fallback; configure NEXTRADE_PUBLIC_BASE_URL for shareable production URLs.
    return str(request.url_for(route, certificate_number=certificate_number))


def _public_certificate(certificate: dict[str, Any], request: Request, verified: bool = True) -> dict[str, Any]:
    number = certificate["certificate_number"]
    return {
        "certificate_number": number,
        "learner_name": certificate["learner_name"],
        "course_title": certificate["course_title"],
        "final_score": float(certificate["final_score"]),
        "issued_at": certificate["issued_at"],
        "status": "valid" if verified and not certificate.get("revoked_at") else "invalid",
        "verification_url": _certificate_link(request, number, "verify_certificate"),
        "printable_url": _certificate_link(request, number, "view_certificate"),
        "scope_notice": "Platform-issued course-completion certificate; not a government license or professional accreditation.",
    }


def _academy_progress(user_id: str) -> dict[str, Any]:
    completed = product_store.completed_lessons(user_id)
    attempts = product_store.quiz_attempts(user_id)
    passed_modules = sorted(module["id"] for module in MODULES if product_store.has_passed_module_quiz(user_id, module["id"]))
    certificate_row = product_store.get_certificate_for_user(user_id)
    certificate = None
    if certificate_row:
        try:
            cert_valid = verify_certificate_signature(certificate_row)
        except RuntimeError:
            cert_valid = False
        # Never leak the HMAC signature or internal user ID in the progress payload.
        certificate = {
            "certificate_number": certificate_row["certificate_number"],
            "learner_name": certificate_row["learner_name"],
            "course_title": certificate_row["course_title"],
            "final_score": float(certificate_row["final_score"]),
            "issued_at": certificate_row["issued_at"],
            "status": "valid" if cert_valid and not certificate_row.get("revoked_at") else "invalid",
        }
    total_lessons = sum(len(module["lessons"]) for module in MODULES)
    return {
        "course_title": COURSE_TITLE,
        "completed_lessons": completed,
        "completed_lesson_count": len(completed),
        "total_lesson_count": total_lessons,
        "completed_percent": round(len(completed) / total_lessons * 100, 2) if total_lessons else 0,
        "passed_module_quizzes": passed_modules,
        "quiz_attempts": attempts,
        "final_exam_passed": product_store.has_passed_final_exam(user_id),
        "certificate": certificate,
    }


@asynccontextmanager
async def lifespan(_: FastAPI):
    task = asyncio.create_task(_background_worker(), name="nextrade-background-worker")
    try:
        yield
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


app = FastAPI(
    title=settings.app_name,
    version="0.4.0",
    description=(
        "NEXTRADE API with read-only market data, virtual trading, learning assessments, verifiable course certificates, "
        "read-only exchange credential validation, and server-verified subscription entitlements. No real exchange orders are sent. "
        "Deploy with HTTPS, strong secrets, ownership authorization, and rate limiting."
    ),
    lifespan=lifespan,
)

origins = [item.strip() for item in settings.allowed_origins.split(",") if item.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


def _require_market_provider() -> None:
    if not settings.market_configured:
        raise HTTPException(status_code=503, detail="Set MARKET_PROVIDER=binance_public to enable public market data.")


def _validate_symbol_interval(symbol: str, interval: str) -> tuple[str, str]:
    try:
        return BinancePublicMarketData.validate_symbol(symbol), BinancePublicMarketData.validate_interval(interval)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


async def _scan_account_once(account_id: str, allow_open_new: bool | None = None) -> dict[str, Any]:
    account = trading_store.get_account(account_id)
    if account is None:
        raise HTTPException(status_code=404, detail="Demo account not found")
    _require_market_provider()
    results: list[dict[str, Any]] = []
    for symbol in account["symbols"]:
        try:
            payload = await market_data.candles(symbol, account["interval"], 180)
            all_candles = payload["candles"]
            closed = [item for item in all_candles if item.get("closed")]
            if not closed:
                results.append({"symbol": symbol, "status": "waiting_for_closed_candle"})
                continue
            # Monitor existing positions using the latest candle's accumulated OHLC values.
            live_bar = all_candles[-1]
            updated_positions = []
            for position in trading_store.get_open_positions(account_id, symbol):
                bar_open_time = live_bar.get("open_time")
                metadata = position.get("metadata") if isinstance(position.get("metadata"), dict) else {}
                entry_bar_time = metadata.get("entry_bar_time")
                signal_time = position.get("signal_candle_time")
                if isinstance(bar_open_time, int) and isinstance(signal_time, int) and bar_open_time > signal_time:
                    if isinstance(entry_bar_time, int) and bar_open_time == entry_bar_time:
                        # Do not use the entry candle's earlier high/low; only the current observed close
                        # is known to be after the simulated fill. Excursions between polls may be missed.
                        updated = trading_store.update_position_price(
                            position["id"], float(live_bar["close"]), f"{bar_open_time}:price", fee_bps=account["fee_bps"],
                        )
                    else:
                        # Full OHLC bars after the entry candle can be processed with conservative stop-first priority.
                        updated = trading_store.update_position_bar(
                            position["id"], high=float(live_bar["high"]), low=float(live_bar["low"]),
                            close=float(live_bar["close"]), bar_key=str(bar_open_time), fee_bps=account["fee_bps"],
                        )
                    if updated:
                        updated_positions.append(updated)
            assessment = analyze_candles(symbol, account["interval"], closed)
            may_open_new = bool(account["auto_enabled"]) if allow_open_new is None else allow_open_new
            if may_open_new and assessment.get("direction") in {"LONG", "SHORT"} and assessment.get("levels") and not trading_store.has_active_symbol(account_id, symbol):
                last_closed = closed[-1]
                levels = assessment["levels"]
                # Simulated fill uses the latest observed provider close, then recalculates 1R/2R/3R
                # around that fill. The signal itself still uses only closed candles.
                entry_price = float(live_bar["close"])
                stop_price = float(levels["stop_loss"])
                risk_distance = entry_price - stop_price if assessment["direction"] == "LONG" else stop_price - entry_price
                if entry_price <= 0 or risk_distance <= 0:
                    results.append({"symbol": symbol, "assessment": assessment, "status": "setup_invalidated_before_simulated_fill"})
                    continue
                if assessment["direction"] == "LONG":
                    targets = [entry_price + risk_distance * value for value in (1, 2, 3)]
                else:
                    targets = [entry_price - risk_distance * value for value in (1, 2, 3)]
                if targets[-1] <= 0:
                    results.append({"symbol": symbol, "assessment": assessment, "status": "invalid_non_positive_target"})
                    continue
                opened = trading_store.open_position(
                    account_id, symbol=symbol, interval=account["interval"], direction=assessment["direction"],
                    entry=entry_price, stop_loss=stop_price, tp1=targets[0], tp2=targets[1], tp3=targets[2],
                    signal_candle_time=int(last_closed.get("open_time", last_closed.get("close_time", 0))),
                    risk_percent=float(account["risk_percent"]), fee_bps=float(account["fee_bps"]),
                    metadata={"score": assessment.get("score"), "strategy": assessment.get("strategy"),
                              "strategy_status": assessment.get("strategy_status"), "source": payload.get("source"),
                              "execution_model": "latest observed provider close; virtual execution only",
                              "entry_bar_time": int(live_bar.get("open_time", 0))},
                )
                results.append({"symbol": symbol, "assessment": assessment, "opened_position": opened,
                                "status": "position_opened" if opened else "signal_already_processed_or_size_too_small"})
            else:
                results.append({"symbol": symbol, "assessment": assessment, "updated_positions": updated_positions,
                                "status": "no_new_position"})
        except (ValueError, MarketDataError) as exc:
            results.append({"symbol": symbol, "status": "data_error", "error": str(exc)})
    return {"account_id": account_id, "mode": "VIRTUAL/DEMO", "results": results,
            "account": trading_store.get_account(account_id), "checked_at": datetime.now(timezone.utc).isoformat()}


async def _background_worker() -> None:
    calendar_last_run = 0.0
    while True:
        await asyncio.sleep(max(5, int(settings.demo_poll_seconds)))
        if settings.market_configured:
            for account in trading_store.accounts_for_monitoring():
                try:
                    await _scan_account_once(account["id"])
                except Exception as exc:  # Background monitor must survive a failed account/provider request.
                    logger.warning("Demo monitor failed for account %s: %s", account.get("id"), type(exc).__name__)
        if fcm_is_configured():
            for delivery in trading_store.pending_push_deliveries():
                ok, error = await send_fcm(delivery["token"], delivery["title"], delivery["body"], delivery.get("payload"))
                trading_store.mark_push_delivery(delivery["notification_id"], delivery["token"], ok, error)
        now = asyncio.get_running_loop().time()
        if settings.economic_calendar_api_key and now - calendar_last_run >= max(60, int(settings.calendar_poll_seconds)):
            calendar_last_run = now
            today = datetime.now(timezone.utc).date()
            try:
                calendar = await economic_calendar.fetch(today, today + timedelta(days=7), importance="high")
                trading_store.notify_high_impact_calendar_events(calendar["items"])
            except Exception as exc:
                logger.info("Calendar polling unavailable: %s", type(exc).__name__)


@app.get("/health", response_model=HealthResponse, tags=["system"])
def health() -> HealthResponse:
    return HealthResponse()


@app.get("/v1/market/status", response_model=MarketStatusResponse, tags=["market"])
async def market_status() -> MarketStatusResponse:
    if not settings.market_configured:
        return MarketStatusResponse(configured=False, provider=settings.market_provider, prices_available=False,
                                    message="Market-data provider is disabled; no prices or signals are available.")
    try:
        await market_data.ping()
        return MarketStatusResponse(configured=True, provider="Binance Spot public market data", prices_available=True,
                                    message="Provider connectivity verified. Prices may be delayed by network/device conditions.",
                                    last_update=datetime.now(timezone.utc))
    except MarketDataError:
        return MarketStatusResponse(configured=True, provider="Binance Spot public market data", prices_available=False,
                                    message="Provider selected but currently unreachable. No market values are fabricated.")


@app.get("/v1/markets", tags=["market"])
async def list_markets(symbols: str | None = Query(default=None, description="Comma-separated symbols, e.g. BTCUSDT,ETHUSDT")) -> dict:
    _require_market_provider()
    selected = [s.strip() for s in symbols.split(",") if s.strip()] if symbols else DEFAULT_SYMBOLS
    try:
        return await market_data.tickers(selected)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except MarketDataError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/v1/market/ticker/{symbol}", tags=["market"])
async def market_ticker(symbol: str) -> dict:
    _require_market_provider()
    try:
        return await market_data.ticker(symbol)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except MarketDataError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/v1/market/candles", tags=["market"])
async def market_candles(symbol: str = Query(default="BTCUSDT"), interval: str = Query(default="1m"),
                         limit: int = Query(default=300, ge=100, le=1000)) -> dict:
    _require_market_provider()
    try:
        return await market_data.candles(symbol, interval, limit)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except MarketDataError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/v1/market/indicators/{symbol}", tags=["analysis"])
async def market_indicators(symbol: str, interval: str = Query(default="15m")) -> dict:
    _require_market_provider()
    try:
        result = await market_data.candles(symbol, interval, 300)
        closed = [c for c in result["candles"] if c["closed"]]
        if len(closed) < 60:
            raise HTTPException(status_code=422, detail="At least 60 closed candles are required for indicator calculations.")
        return {"symbol": result["symbol"], "interval": interval, "source": result["source"],
                "received_at": result["received_at"], "closed_candles_used": len(closed), "indicators": latest_indicators(closed)}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except MarketDataError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/v1/signals", tags=["signals"])
async def list_signals(symbols: str = Query(default="BTCUSDT,ETHUSDT,SOLUSDT"), interval: str = Query(default="15m")) -> dict:
    _require_market_provider()
    selected = [s.strip() for s in symbols.split(",") if s.strip()]
    assessments, failures = [], []
    for symbol in selected[:6]:
        try:
            payload = await market_data.candles(symbol, interval, 300)
            assessments.append(analyze_candles(payload["symbol"], interval, payload["candles"]))
        except (ValueError, MarketDataError) as exc:
            failures.append({"symbol": symbol, "error": str(exc)})
    return {"items": assessments, "source": "Binance Spot public market data", "strategy_status": "experimental_unvalidated",
            "failures": failures, "message": "Scores are rule-based confluence scores, not calibrated win probabilities."}


@app.post("/v1/analyze/{symbol}", tags=["signals"])
async def analyze_symbol(symbol: str, interval: str = Query(default="15m")) -> dict:
    _require_market_provider()
    try:
        payload = await market_data.candles(symbol, interval, 300)
        assessment = analyze_candles(payload["symbol"], interval, payload["candles"])
        assessment["source"] = payload["source"]
        assessment["received_at"] = payload["received_at"]
        return assessment
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except MarketDataError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


# -- Persistent demo trading -------------------------------------------------
@app.post("/v1/demo/accounts", tags=["demo"])
def create_demo_account(request: DemoAccountCreate) -> dict:
    try:
        symbols = [BinancePublicMarketData.validate_symbol(symbol) for symbol in request.symbols]
        interval = BinancePublicMarketData.validate_interval(request.interval)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return trading_store.create_account(request.initial_capital, symbols, interval, request.risk_percent, request.fee_bps)


@app.get("/v1/demo/accounts/{account_id}", tags=["demo"])
def get_demo_account(account_id: str) -> dict:
    result = trading_store.get_account(account_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Demo account not found")
    return result


@app.post("/v1/demo/accounts/{account_id}/auto", tags=["demo"])
def toggle_demo_auto(account_id: str, request: AutoTradingToggle) -> dict:
    result = trading_store.set_auto(account_id, request.enabled)
    if result is None:
        raise HTTPException(status_code=404, detail="Demo account not found")
    return result


@app.post("/v1/demo/accounts/{account_id}/scan", tags=["demo"])
async def scan_demo_account(account_id: str) -> dict:
    return await _scan_account_once(account_id, allow_open_new=True)


@app.get("/v1/demo/accounts/{account_id}/positions", tags=["demo"])
def demo_positions(account_id: str, status: Literal["OPEN", "CLOSED"] | None = None,
                   limit: int = Query(default=200, ge=1, le=1000)) -> dict:
    if trading_store.get_account(account_id) is None:
        raise HTTPException(status_code=404, detail="Demo account not found")
    return {"items": trading_store.list_positions(account_id, status, limit), "mode": "VIRTUAL/DEMO"}


@app.get("/v1/demo/accounts/{account_id}/events", tags=["demo"])
def demo_events(account_id: str, limit: int = Query(default=200, ge=1, le=1000)) -> dict:
    if trading_store.get_account(account_id) is None:
        raise HTTPException(status_code=404, detail="Demo account not found")
    return {"items": trading_store.list_events(account_id, limit)}


@app.post("/v1/demo/accounts/{account_id}/reset", tags=["demo"])
def reset_demo_account(account_id: str) -> dict:
    if not trading_store.reset_account(account_id):
        raise HTTPException(status_code=404, detail="Demo account not found")
    return trading_store.get_account(account_id) or {}


# -- Backtesting and walk-forward -------------------------------------------
def _fetch_backtest_candles(symbol: str, interval: str, limit: int) -> tuple[str, str]:
    try:
        return BinancePublicMarketData.validate_symbol(symbol), BinancePublicMarketData.validate_interval(interval)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/v1/backtest", tags=["backtesting"])
async def run_backtest(request: BacktestRequest) -> dict:
    _require_market_provider()
    symbol, interval = _fetch_backtest_candles(request.symbol, request.interval, request.candles_limit)
    if request.account_id and trading_store.get_account(request.account_id) is None:
        raise HTTPException(status_code=404, detail="Demo account not found")
    try:
        candles = await market_data.candles(symbol, interval, request.candles_limit)
        result = await run_in_threadpool(
            simulate_backtest, candles["candles"], symbol=symbol, interval=interval,
            initial_capital=request.initial_capital, risk_percent=request.risk_percent,
            fee_bps=request.fee_bps, slippage_bps=request.slippage_bps,
        )
    except (ValueError, MarketDataError) as exc:
        raise HTTPException(status_code=502 if isinstance(exc, MarketDataError) else 422, detail=str(exc)) from exc
    run_id = trading_store.save_backtest(request.account_id, symbol, interval, "backtest", request.model_dump(), result)
    return {"run_id": run_id, "source": candles.get("source"), "data_received_at": candles.get("received_at"), **result}


@app.post("/v1/walk-forward", tags=["backtesting"])
async def run_walk_forward(request: WalkForwardRequest) -> dict:
    _require_market_provider()
    symbol, interval = _fetch_backtest_candles(request.symbol, request.interval, request.candles_limit)
    if request.account_id and trading_store.get_account(request.account_id) is None:
        raise HTTPException(status_code=404, detail="Demo account not found")
    try:
        candles = await market_data.candles(symbol, interval, request.candles_limit)
        result = await run_in_threadpool(
            simulate_walk_forward, candles["candles"], symbol=symbol, interval=interval,
            initial_capital=request.initial_capital, risk_percent=request.risk_percent,
            fee_bps=request.fee_bps, slippage_bps=request.slippage_bps,
            folds=request.folds, train_fraction=request.train_fraction,
        )
    except (ValueError, MarketDataError) as exc:
        raise HTTPException(status_code=502 if isinstance(exc, MarketDataError) else 422, detail=str(exc)) from exc
    run_id = trading_store.save_backtest(request.account_id, symbol, interval, "walk_forward", request.model_dump(), result)
    return {"run_id": run_id, "source": candles.get("source"), "data_received_at": candles.get("received_at"), **result}


@app.get("/v1/backtest/history", tags=["backtesting"])
def backtest_history(limit: int = Query(default=50, ge=1, le=200)) -> dict:
    return {"items": trading_store.list_backtests(limit)}


# -- Economic calendar and notifications -----------------------------------
@app.get("/v1/calendar/economic", tags=["calendar"])
async def get_economic_calendar(
    from_date: date = Query(alias="from", description="YYYY-MM-DD, UTC date"),
    to_date: date = Query(alias="to", description="YYYY-MM-DD, UTC date"),
    importance: Literal["low", "medium", "high"] | None = None,
    country: str | None = None,
) -> dict:
    try:
        return await economic_calendar.fetch(from_date, to_date, importance, country)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except EconomicCalendarError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/v1/notifications/status", tags=["notifications"])
def notification_status() -> dict:
    return {
        "in_app_notifications": True,
        "push_configured": fcm_is_configured(),
        "push_provider": "Firebase Cloud Messaging HTTP v1 via Firebase Admin SDK" if fcm_is_configured() else None,
        "calendar_configured": bool(settings.economic_calendar_api_key),
        "requirements": {
            "calendar": "Set FINNHUB_API_KEY to enable live economic calendar data.",
            "push": "Set FCM_SERVICE_ACCOUNT_PATH and FCM_PROJECT_ID, add Firebase messaging config to Flutter, and register device tokens.",
        },
    }


@app.get("/v1/demo/accounts/{account_id}/notifications", tags=["notifications"])
def list_notifications(account_id: str, limit: int = Query(default=100, ge=1, le=500), unread_only: bool = False) -> dict:
    if trading_store.get_account(account_id) is None:
        raise HTTPException(status_code=404, detail="Demo account not found")
    items = trading_store.list_notifications(account_id, limit, unread_only)
    return {"items": items, "unread_count": sum(item["read_at"] is None for item in trading_store.list_notifications(account_id, 500, True))}


@app.get("/v1/demo/accounts/{account_id}/notification-preferences", tags=["notifications"])
def get_notification_preferences(account_id: str) -> dict:
    result = trading_store.get_preferences(account_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Demo account not found")
    return result


@app.put("/v1/demo/accounts/{account_id}/notification-preferences", tags=["notifications"])
def update_notification_preferences(account_id: str, request: NotificationPreferences) -> dict:
    for time_value in (request.quiet_start, request.quiet_end):
        if time_value is not None:
            try:
                datetime.strptime(time_value, "%H:%M")
            except ValueError as exc:
                raise HTTPException(status_code=422, detail="Quiet hours must use HH:MM 24-hour format") from exc
    result = trading_store.save_preferences(account_id, request.model_dump())
    if result is None:
        raise HTTPException(status_code=404, detail="Demo account not found")
    return result


@app.post("/v1/demo/accounts/{account_id}/notification-devices", tags=["notifications"])
def register_notification_device(account_id: str, request: DeviceRegistration) -> dict:
    if not trading_store.add_device(account_id, request.token, request.platform):
        raise HTTPException(status_code=404, detail="Demo account not found")
    return {"registered": True, "platform": request.platform, "note": "Push delivery requires Firebase server credentials and an app configured with the same Firebase project."}


@app.post("/v1/demo/accounts/{account_id}/notifications/{notification_id}/read", tags=["notifications"])
def mark_notification_read(account_id: str, notification_id: str) -> dict:
    if not trading_store.mark_notification_read(account_id, notification_id):
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"marked_read": True}


# ----- Identity and sessions -----
@app.post("/v1/auth/register", status_code=201, tags=["identity"])
def register_user(request: RegisterRequest) -> dict:
    try:
        user, token, _ = auth_service.register(request.email, request.display_name, request.password)
    except sqlite3.IntegrityError as exc:
        raise HTTPException(status_code=409, detail="An account with this email already exists") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"user": user, "access_token": token, "token_type": "bearer", "expires_in": 43200}


@app.post("/v1/auth/login", tags=["identity"])
def login_user(request: LoginRequest) -> dict:
    try:
        result = auth_service.login(request.email, request.password)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if not result:
        raise HTTPException(status_code=401, detail="Email or password is incorrect", headers={"WWW-Authenticate": "Bearer"})
    user, token, _ = result
    return {"user": user, "access_token": token, "token_type": "bearer", "expires_in": 43200}


@app.get("/v1/auth/me", tags=["identity"])
def get_me(user: dict[str, Any] = Depends(current_user)) -> dict:
    return {"user": user, "entitlement": product_store.subscription_entitlement(user["id"])}


@app.post("/v1/auth/logout", tags=["identity"])
def logout_user(context: dict[str, Any] = Depends(_auth_context)) -> dict:
    auth_service.revoke(context["jti"], product_store)
    return {"logged_out": True}


# ----- Academy, scored assessments and signed course certificates -----
@app.get("/v1/academy/modules", tags=["academy"])
def academy_modules(user: dict[str, Any] = Depends(current_user)) -> dict:
    tier = _user_tier(user["id"])
    modules = []
    for module in MODULES:
        required_tier = module_required_tier(module["id"])
        locked = _TIER_LEVEL.get(tier, 0) < _TIER_LEVEL[required_tier]
        item = public_module(module, include_content=not locked)
        item["required_tier"] = required_tier
        item["locked"] = locked
        modules.append(item)
    return {"course_title": COURSE_TITLE, "modules": modules, "active_tier": tier,
            "module_pass_percent": MODULE_PASS_PERCENT, "final_pass_percent": FINAL_PASS_PERCENT,
            "certificate_scope": "Course completion only; not professional licensing or government accreditation."}


@app.get("/v1/academy/progress", tags=["academy"])
def academy_progress(user: dict[str, Any] = Depends(current_user)) -> dict:
    return _academy_progress(user["id"])


@app.post("/v1/academy/modules/{module_id}/lessons/{lesson_id}/complete", tags=["academy"])
def complete_academy_lesson(module_id: int, lesson_id: str, user: dict[str, Any] = Depends(current_user)) -> dict:
    module = next((item for item in MODULES if item["id"] == module_id), None)
    if not module or not any(lesson["id"] == lesson_id for lesson in module["lessons"]):
        raise HTTPException(status_code=404, detail="Lesson not found")
    _require_module_tier(user["id"], module_id)
    completed = product_store.complete_lesson(user["id"], module_id, lesson_id)
    return {"completed": True, "lesson": completed, "progress": _academy_progress(user["id"])}


@app.post("/v1/academy/modules/{module_id}/quiz/start", tags=["academy"])
def start_module_quiz(module_id: int, user: dict[str, Any] = Depends(current_user)) -> dict:
    module = next((item for item in MODULES if item["id"] == module_id), None)
    if not module:
        raise HTTPException(status_code=404, detail="Module not found")
    _require_module_tier(user["id"], module_id)
    completed_ids = {item["lesson_id"] for item in product_store.completed_lessons(user["id"]) if item["module_id"] == module_id}
    if not {lesson["id"] for lesson in module["lessons"]}.issubset(completed_ids):
        raise HTTPException(status_code=409, detail="Complete all lessons in this module before taking its quiz")
    question_ids = [item["id"] for item in module["questions"]]
    attempt_id = product_store.create_quiz_attempt(user["id"], "module", module_id, question_ids)
    return {"attempt_id": attempt_id, "module_id": module_id, "pass_percent": MODULE_PASS_PERCENT,
            "questions": [public_question(item) for item in module["questions"]]}


def _question_map() -> dict[str, dict[str, Any]]:
    return {question["id"]: question for module in MODULES for question in module["questions"]}


def _submit_academy_quiz(attempt_id: str, answers: dict[str, int], user_id: str) -> dict[str, Any]:
    attempt = product_store.get_quiz_attempt(attempt_id, user_id)
    if attempt is None:
        raise HTTPException(status_code=404, detail="Quiz attempt not found")
    if attempt["kind"] == "module" and attempt["module_id"] is not None:
        _require_module_tier(user_id, int(attempt["module_id"]))
    elif attempt["kind"] == "final":
        _require_tier(user_id, "premium")
    if attempt["submitted_at"]:
        raise HTTPException(status_code=409, detail="This quiz attempt has already been submitted")
    expected_ids = set(attempt["question_ids"])
    if set(answers) != expected_ids:
        raise HTTPException(status_code=422, detail="Submit exactly one answer for every question in this attempt")
    if any(not isinstance(value, int) or value not in range(4) for value in answers.values()):
        raise HTTPException(status_code=422, detail="Answers must be option indexes from 0 to 3")
    qmap = _question_map()
    questions = [qmap[qid] for qid in attempt["question_ids"]]
    result = grade(questions, answers)
    is_final = attempt["kind"] == "final"
    threshold = FINAL_PASS_PERCENT if is_final else MODULE_PASS_PERCENT
    passed = result["percent"] >= threshold
    if not product_store.submit_quiz_attempt(attempt_id, user_id, answers, result["percent"], passed):
        raise HTTPException(status_code=409, detail="This quiz attempt has already been submitted")
    response = {"attempt_id": attempt_id, "kind": attempt["kind"], "module_id": attempt["module_id"],
                "passed": passed, "pass_percent": threshold, **result, "progress": _academy_progress(user_id)}
    if is_final and passed:
        # Every lesson and every module quiz must be complete before a certificate is issued.
        progress = _academy_progress(user_id)
        all_modules_passed = len(progress["passed_module_quizzes"]) == len(MODULES)
        all_lessons_complete = progress["completed_lesson_count"] == progress["total_lesson_count"]
        if all_modules_passed and all_lessons_complete:
            try:
                cert = product_store.create_certificate(
                    user_id, progress_user_name := str(product_store.get_user(user_id)["display_name"]), result["percent"], certificate_signature
                )
                response["certificate"] = {
                    "certificate_number": cert["certificate_number"], "learner_name": cert["learner_name"],
                    "course_title": cert["course_title"], "final_score": cert["final_score"], "issued_at": cert["issued_at"],
                }
            except RuntimeError as exc:
                response["certificate_error"] = str(exc)
    response["progress"] = _academy_progress(user_id)
    return response


@app.post("/v1/academy/quiz/{attempt_id}/submit", tags=["academy"])
def submit_academy_quiz(attempt_id: str, request: QuizSubmission, user: dict[str, Any] = Depends(current_user)) -> dict:
    return _submit_academy_quiz(attempt_id, request.answers, user["id"])


@app.post("/v1/academy/final-exam/start", tags=["academy"])
def start_final_exam(user: dict[str, Any] = Depends(current_user)) -> dict:
    _require_tier(user["id"], "premium")
    progress = _academy_progress(user["id"])
    if progress["completed_lesson_count"] != progress["total_lesson_count"] or len(progress["passed_module_quizzes"]) != len(MODULES):
        raise HTTPException(status_code=409, detail="Complete all lessons and pass every module quiz before the final exam")
    pool = [question for module in MODULES for question in module["questions"]]
    chosen = random.SystemRandom().sample(pool, 20)
    attempt_id = product_store.create_quiz_attempt(user["id"], "final", None, [item["id"] for item in chosen])
    return {"attempt_id": attempt_id, "course_title": COURSE_TITLE, "pass_percent": FINAL_PASS_PERCENT,
            "question_count": len(chosen), "questions": [public_question(item) for item in chosen]}


@app.post("/v1/academy/final-exam/{attempt_id}/submit", tags=["academy"])
def submit_final_exam(attempt_id: str, request: QuizSubmission, user: dict[str, Any] = Depends(current_user)) -> dict:
    _require_tier(user["id"], "premium")
    attempt = product_store.get_quiz_attempt(attempt_id, user["id"])
    if attempt is None or attempt["kind"] != "final":
        raise HTTPException(status_code=404, detail="Final exam attempt not found")
    return _submit_academy_quiz(attempt_id, request.answers, user["id"])


@app.get("/v1/academy/certificates/me", tags=["academy"])
def my_certificate(request: Request, user: dict[str, Any] = Depends(current_user)) -> dict:
    certificate = product_store.get_certificate_for_user(user["id"])
    if not certificate:
        return {"issued": False, "message": "Complete all lessons, pass all module quizzes, and score at least 80% on the final exam."}
    verified = verify_certificate_signature(certificate)
    return {"issued": True, **_public_certificate(certificate, request, verified)}


@app.get("/v1/academy/certificates/verify/{certificate_number}", name="verify_certificate", tags=["academy"])
def verify_certificate(certificate_number: str, request: Request) -> dict:
    certificate = product_store.get_certificate_by_number(certificate_number)
    if not certificate:
        return {"certificate_number": certificate_number.upper(), "status": "not_found", "verified": False}
    signature_ok = False
    try:
        signature_ok = verify_certificate_signature(certificate)
    except RuntimeError:
        signature_ok = False
    result = _public_certificate(certificate, request, signature_ok)
    result["verified"] = result["status"] == "valid"
    return result


@app.get("/v1/academy/certificates/view/{certificate_number}", response_class=HTMLResponse, tags=["academy"])
def view_certificate(certificate_number: str, request: Request) -> HTMLResponse:
    """Printable certificate page; use the browser's print dialog to save a PDF copy."""
    certificate = product_store.get_certificate_by_number(certificate_number)
    if not certificate:
        raise HTTPException(status_code=404, detail="Certificate not found")
    try:
        signature_ok = verify_certificate_signature(certificate)
    except RuntimeError:
        signature_ok = False
    status = "VALID" if signature_ok and not certificate.get("revoked_at") else "INVALID / REVOKED"
    color = "#167d65" if status == "VALID" else "#b42318"
    number = html.escape(str(certificate["certificate_number"]))
    learner = html.escape(str(certificate["learner_name"]))
    course = html.escape(str(certificate["course_title"]))
    issued = html.escape(str(certificate["issued_at"]))
    score = html.escape(f"{float(certificate['final_score']):.1f}%")
    verify_url = html.escape(_certificate_link(request, str(certificate["certificate_number"]), "verify_certificate"), quote=True)
    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>NEXTRADE Course Certificate {number}</title>
<style>body{{margin:0;background:#eef2f6;color:#17212b;font-family:Arial,Helvetica,sans-serif}}.sheet{{max-width:900px;margin:36px auto;padding:56px;background:white;border:10px double #c7a44d;text-align:center;box-sizing:border-box}}.brand{{letter-spacing:6px;color:#187b95;font-weight:800}}h1{{font-size:38px;margin:28px 0 10px}}.name{{font-size:32px;color:#142638;margin:25px 0}}.course{{font-size:21px;font-weight:700}}.meta{{display:flex;justify-content:space-around;gap:24px;margin:34px 0;flex-wrap:wrap}}.meta div{{min-width:140px}}.label{{font-size:12px;text-transform:uppercase;letter-spacing:2px;color:#657384}}.value{{font-weight:700;margin-top:7px}}.status{{display:inline-block;padding:10px 18px;border:1px solid {color};color:{color};font-weight:800;letter-spacing:2px}}a{{color:#146e8a;overflow-wrap:anywhere}}.notice{{font-size:12px;color:#586575;max-width:680px;margin:24px auto 0;line-height:1.6}}button{{margin:22px auto;padding:12px 20px;border:0;border-radius:8px;background:#142638;color:white;font-weight:700;cursor:pointer}}@media print{{body{{background:white}}.sheet{{margin:0;max-width:none;border-width:8px;min-height:95vh;break-inside:avoid}}button{{display:none}}}}</style></head><body><main class="sheet"><div class="brand">NEXTRADE</div><h1>Certificate of Course Completion</h1><p>This certificate is awarded to</p><div class="name">{learner}</div><p>for completing the learning modules and passing the required assessments for</p><div class="course">{course}</div><div class="meta"><div><div class="label">Final score</div><div class="value">{score}</div></div><div><div class="label">Issued at (UTC)</div><div class="value">{issued}</div></div><div><div class="label">Certificate number</div><div class="value">{number}</div></div></div><div class="status">{status}</div><p>Verify this certificate online: <a href="{verify_url}">{verify_url}</a></p><p class="notice">This is a platform-issued record of course completion and assessment results. It is not a government license, regulated qualification, professional accreditation, financial credential, or guarantee of trading performance. The online verification endpoint is the authoritative status check.</p><button onclick="window.print()">Print / Save as PDF</button></main></body></html>"""
    return HTMLResponse(page, status_code=200)


# ----- Read-only exchange connection management -----
@app.get("/v1/exchanges/connections", tags=["exchanges"])
def list_exchange_connections(user: dict[str, Any] = Depends(current_user)) -> dict:
    return {"items": product_store.list_exchanges(user["id"]), "real_orders_enabled": False,
            "note": "This release permits read-only account access only; no order endpoints are implemented."}


@app.post("/v1/exchanges/binance/connect", tags=["exchanges"])
async def connect_binance(request: Request, body: ExchangeConnectRequest, user: dict[str, Any] = Depends(current_user)) -> dict:
    if settings.environment.lower() == "production" and request.url.scheme != "https":
        raise HTTPException(status_code=400, detail="Exchange credentials may only be submitted over HTTPS")
    if not exchange_encryption_configured():
        raise HTTPException(status_code=503, detail="Server-side credential encryption is not configured")
    api_key = body.api_key.get_secret_value().strip()
    api_secret = body.api_secret.get_secret_value().strip()
    try:
        validation = await binance_connector.validate_read_only(api_key, api_secret)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ExchangeConnectionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    fingerprint = hashlib.sha256(api_key.encode("utf-8")).hexdigest()[:12]
    try:
        connection = product_store.upsert_exchange(
            user["id"], "binance", encrypt_exchange_secret(api_key), encrypt_exchange_secret(api_secret), fingerprint,
            "connected", validation["permission_profile"], None,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"connection": connection, "real_orders_enabled": False, "verified_at": validation["verified_at"]}


@app.post("/v1/exchanges/binance/test", tags=["exchanges"])
async def test_binance_connection(user: dict[str, Any] = Depends(current_user)) -> dict:
    encrypted = product_store.get_exchange_secrets(user["id"], "binance")
    if not encrypted:
        raise HTTPException(status_code=404, detail="No Binance connection is stored for this account")
    try:
        api_key = decrypt_exchange_secret(encrypted["api_key_encrypted"])
        api_secret = decrypt_exchange_secret(encrypted["api_secret_encrypted"])
        result = await binance_connector.validate_read_only(api_key, api_secret)
    except ExchangeConnectionError as exc:
        product_store.update_exchange_check(user["id"], "binance", "error", str(exc))
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except (RuntimeError, ValueError) as exc:
        product_store.update_exchange_check(user["id"], "binance", "error", str(exc))
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    product_store.update_exchange_check(user["id"], "binance", "connected", None)
    return {"connected": True, "permission_profile": result["permission_profile"], "verified_at": result["verified_at"]}


@app.delete("/v1/exchanges/binance", tags=["exchanges"])
def disconnect_binance(user: dict[str, Any] = Depends(current_user)) -> dict:
    if not product_store.delete_exchange(user["id"], "binance"):
        raise HTTPException(status_code=404, detail="No Binance connection is stored for this account")
    return {"disconnected": True, "exchange": "binance"}


# ----- Server-verified subscriptions and entitlement checks -----
@app.get("/v1/subscriptions/plans", tags=["subscriptions"])
def subscription_plans() -> dict:
    mode = settings.billing_mode.strip().lower()
    is_demo = mode == "demo"
    return {"billing_mode": "demo" if is_demo else "google_play",
        "demo_duration_days": 30 if is_demo else None,
        "plans": [
        {"tier": "free", "product_id": None, "benefits": ["Basic market overview", "Core indicators", "Demo trading", "Academy modules 1-3"]},
        {"tier": "pro", "product_id": None if is_demo else settings.google_play_pro_product_id, "benefits": ["Academy modules 1-8", "Module quizzes through module 8", "Learning progress sync"]},
        {"tier": "premium", "product_id": None if is_demo else settings.google_play_premium_product_id, "benefits": ["All 12 academy modules", "All module quizzes", "Final examination", "Verifiable course certificate"]},
    ], "prices": ("Demo mode: no payment is collected; Pro/Premium demo access is granted for 30 days. No price is hardcoded or charged." if is_demo else "Loaded from Google Play at runtime; no price is hardcoded by the app."),
       "purchase_verification": ("DEMO ONLY: server-granted demo entitlements; no payment is collected." if is_demo else "Server-side Google Play Developer API only; client-side flags never grant premium.")}


@app.post("/v1/subscriptions/demo/activate", tags=["subscriptions"])
def activate_demo_subscription(request: DemoSubscriptionActivateRequest, user: dict[str, Any] = Depends(current_user)) -> dict:
    """Grant a clearly labeled, time-limited test entitlement without accepting money."""
    if settings.billing_mode.strip().lower() != "demo":
        raise HTTPException(status_code=403, detail="Demo subscription activation is disabled when billing mode is not demo")

    current = product_store.subscription_entitlement(user["id"])
    order = {"free": 0, "pro": 1, "premium": 2}
    if current.get("active") and current.get("store") == "demo" and order.get(str(current.get("tier")), 0) >= order[request.tier]:
        return {"activated": True, "demo": True, "already_active": True, "payment_collected": False,
                "payment_status": "not_charged", "entitlement": current,
                "message": "This demo entitlement is already active; expiry was not extended."}

    now = datetime.now(timezone.utc)
    expires_at = (now + timedelta(days=30)).isoformat()
    # These are stable internal demo references, not store purchase tokens or payment credentials.
    demo_reference = f"nextrade-demo-subscription:{user['id']}:{request.tier}"
    entitlement = product_store.upsert_subscription(
        user["id"], "demo", f"demo_{request.tier}_30d", digest(demo_reference),
        "DEMO_NO_PAYMENT_TOKEN", request.tier, "active", expires_at,
    )
    return {"activated": True, "demo": True, "already_active": False,
            "duration_days": 30, "payment_collected": False, "payment_status": "not_charged",
            "checkout_status": "simulated_success", "entitlement": entitlement,
            "message": "Demo subscription activated for 30 days. No money was charged."}


@app.get("/v1/subscriptions/me", tags=["subscriptions"])
async def my_subscription(user: dict[str, Any] = Depends(current_user)) -> dict:
    # Re-check known purchases with Google Play to pick up renewals, expirations, and cancellations.
    # If the provider is temporarily unreachable, retain the previously verified expiry but expose the warning.
    warnings: list[str] = []
    if settings.billing_mode.strip().lower() == "google_play" and getattr(google_play_verifier, "configured", False) and exchange_encryption_configured():
        for record in product_store.subscription_records_for_user(user["id"]):
            if record["store"] != "google_play" or not record.get("purchase_token_encrypted"):
                continue
            try:
                purchase_token = decrypt_exchange_secret(record["purchase_token_encrypted"])
                verified = await run_in_threadpool(google_play_verifier.verify, record["product_id"], purchase_token)
                product_store.upsert_subscription(user["id"], "google_play", record["product_id"], record["token_hash"],
                                                  record["purchase_token_encrypted"], verified["tier"], verified["status"], verified["expires_at"])
            except ValueError:
                product_store.update_subscription_status(record["id"], user["id"], "expired")
            except (GooglePlayVerificationError, RuntimeError) as exc:
                warnings.append(str(exc))
    entitlement = product_store.subscription_entitlement(user["id"])
    if warnings:
        entitlement["refresh_warning"] = "Google Play revalidation could not be completed; stored expiry is still enforced."
    return entitlement


@app.post("/v1/subscriptions/google-play/verify", tags=["subscriptions"])
async def verify_google_play_subscription(request: GooglePlayVerifyRequest, user: dict[str, Any] = Depends(current_user)) -> dict:
    if settings.billing_mode.strip().lower() != "google_play":
        raise HTTPException(status_code=403, detail="Real store purchases are disabled while NEXTRADE_BILLING_MODE=demo")
    product_id = request.product_id
    purchase_token = request.purchase_token.get_secret_value()
    if not exchange_encryption_configured():
        raise HTTPException(status_code=503, detail="Configure NEXTRADE_CREDENTIAL_ENCRYPTION_KEY before activating subscriptions")
    try:
        verified = await run_in_threadpool(google_play_verifier.verify, product_id, purchase_token)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except GooglePlayVerificationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    try:
        entitlement = product_store.upsert_subscription(user["id"], "google_play", product_id,
                                                        digest(purchase_token), encrypt_exchange_secret(purchase_token),
                                                        verified["tier"], verified["status"], verified["expires_at"])
    except PermissionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"verified": True, "verified_at": verified["verified_at"], "entitlement": entitlement}
