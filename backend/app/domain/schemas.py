from datetime import datetime, timezone
from typing import Literal
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    service: str = "nextrade-api"
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class MarketStatusResponse(BaseModel):
    configured: bool
    provider: str
    prices_available: bool = False
    message: str
    last_update: datetime | None = None


class MarketQuote(BaseModel):
    symbol: str
    last_price: float
    change_24h_percent: float | None = None
    volume_24h: float | None = None
    source: str
    timestamp: datetime


class SignalSummary(BaseModel):
    id: str
    symbol: str
    direction: Literal["LONG", "SHORT", "NO_TRADE"]
    quality: Literal["A+", "A", "B", "C", "NO_TRADE"]
    score: float = Field(ge=0, le=100)
    reason: str
    created_at: datetime
