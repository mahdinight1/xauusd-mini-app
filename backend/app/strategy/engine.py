from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.market.indicators import latest_indicators

STRATEGY_NAME = "NEXTRADE Trend-Momentum-Confluence v1"
STRATEGY_STATUS = "experimental_unvalidated"


def _latest_valid(values: list[float | None], offset: int = 0) -> float | None:
    index = len(values) - 1 - offset
    return values[index] if 0 <= index < len(values) else None


def analyze_candles(symbol: str, interval: str, candles: list[dict[str, Any]]) -> dict[str, Any]:
    """Deterministic rule-based assessment; not a calibrated probability or profit guarantee."""
    closed = [c for c in candles if c.get("closed", True)]
    if len(closed) < 60:
        return {
            "symbol": symbol, "interval": interval, "direction": "NO_TRADE", "quality": "NO_TRADE",
            "score": 0, "reasons": ["At least 60 closed candles are required."],
            "status": "insufficient_data", "strategy": STRATEGY_NAME, "strategy_status": STRATEGY_STATUS,
            "created_at": datetime.now(timezone.utc).isoformat(), "indicators": {}, "levels": None,
        }

    indicators = latest_indicators(closed)
    closes = [float(c["close"]) for c in closed]
    price = closes[-1]
    e20, e50 = indicators["ema20"], indicators["ema50"]
    rsi_v, macd_h = indicators["rsi14"], indicators["macd_histogram"]
    adx_v, atr_v = indicators["adx14"], indicators["atr14"]
    vwap_v, volume_sma = indicators["vwap20"], indicators["volume_sma20"]
    if any(value is None for value in (e20, e50, rsi_v, macd_h, atr_v)) or float(atr_v) <= 0:
        return {
            "symbol": symbol, "interval": interval, "direction": "NO_TRADE", "quality": "NO_TRADE",
            "score": 0, "reasons": ["Indicator warm-up is incomplete."], "status": "insufficient_indicators",
            "strategy": STRATEGY_NAME, "strategy_status": STRATEGY_STATUS,
            "created_at": datetime.now(timezone.utc).isoformat(), "indicators": indicators, "levels": None,
        }

    long_score, short_score = 0.0, 0.0
    long_reasons: list[str] = []
    short_reasons: list[str] = []
    if price > float(e20) > float(e50):
        long_score += 18; long_reasons.append("Price > EMA20 > EMA50 (bullish alignment).")
    elif price < float(e20) < float(e50):
        short_score += 18; short_reasons.append("Price < EMA20 < EMA50 (bearish alignment).")
    elif price > float(e20):
        long_score += 7; long_reasons.append("Price is above EMA20, but EMA trend is not fully aligned.")
    elif price < float(e20):
        short_score += 7; short_reasons.append("Price is below EMA20, but EMA trend is not fully aligned.")

    if 52 <= float(rsi_v) <= 68:
        long_score += 12; long_reasons.append("RSI14 supports positive momentum without an extreme reading.")
    elif float(rsi_v) >= 70:
        long_score -= 5; long_reasons.append("RSI14 is overbought; long entries are penalized.")
    elif 32 <= float(rsi_v) <= 48:
        short_score += 12; short_reasons.append("RSI14 supports negative momentum without an extreme reading.")
    elif float(rsi_v) <= 30:
        short_score -= 5; short_reasons.append("RSI14 is oversold; short entries are penalized.")
    elif float(rsi_v) > 50:
        long_score += 4
    elif float(rsi_v) < 50:
        short_score += 4

    if float(macd_h) > 0:
        long_score += 12; long_reasons.append("MACD histogram is positive.")
    elif float(macd_h) < 0:
        short_score += 12; short_reasons.append("MACD histogram is negative.")

    if adx_v is not None and float(adx_v) >= 25:
        if float(e20) > float(e50):
            long_score += 10; long_reasons.append("ADX14 >= 25 confirms a stronger directional trend.")
        elif float(e20) < float(e50):
            short_score += 10; short_reasons.append("ADX14 >= 25 confirms a stronger directional trend.")
    elif adx_v is not None and float(adx_v) >= 18:
        if float(e20) > float(e50): long_score += 5
        elif float(e20) < float(e50): short_score += 5

    if vwap_v is not None and price > float(vwap_v):
        long_score += 8; long_reasons.append("Price is above the recent 20-candle VWAP proxy.")
    elif vwap_v is not None and price < float(vwap_v):
        short_score += 8; short_reasons.append("Price is below the recent 20-candle VWAP proxy.")

    if volume_sma is not None and float(volume_sma) > 0 and float(indicators["volume"]) >= float(volume_sma) * 1.2:
        if closes[-1] > closes[-2]:
            long_score += 8; long_reasons.append("Current volume is at least 1.2x its 20-candle average on an up candle.")
        elif closes[-1] < closes[-2]:
            short_score += 8; short_reasons.append("Current volume is at least 1.2x its 20-candle average on a down candle.")

    # Small structure check based only on closed historical candles.
    recent = closes[-6:]
    up_steps = sum(recent[i] > recent[i - 1] for i in range(1, len(recent)))
    down_steps = sum(recent[i] < recent[i - 1] for i in range(1, len(recent)))
    if up_steps >= 4:
        long_score += 7; long_reasons.append("Short-term closes show upward persistence.")
    if down_steps >= 4:
        short_score += 7; short_reasons.append("Short-term closes show downward persistence.")

    supertrend_direction = indicators.get("supertrend_direction")
    if supertrend_direction == "BULLISH":
        long_score += 10; long_reasons.append("Supertrend is bullish.")
    elif supertrend_direction == "BEARISH":
        short_score += 10; short_reasons.append("Supertrend is bearish.")

    cloud_a = indicators.get("ichimoku_senkou_span_a_current")
    cloud_b = indicators.get("ichimoku_senkou_span_b_current")
    if cloud_a is not None and cloud_b is not None:
        cloud_top, cloud_bottom = max(float(cloud_a), float(cloud_b)), min(float(cloud_a), float(cloud_b))
        if price > cloud_top:
            long_score += 10; long_reasons.append("Price is above the current Ichimoku cloud levels.")
        elif price < cloud_bottom:
            short_score += 10; short_reasons.append("Price is below the current Ichimoku cloud levels.")

    if indicators.get("donchian_breakout_up"):
        long_score += 5; long_reasons.append("Close broke above the previous 20-candle Donchian channel.")
    if indicators.get("donchian_breakout_down"):
        short_score += 5; short_reasons.append("Close broke below the previous 20-candle Donchian channel.")

    long_score, short_score = max(0.0, min(100.0, long_score)), max(0.0, min(100.0, short_score))
    direction = "NO_TRADE"
    score = max(long_score, short_score)
    reasons = ["Signal rejected: directional evidence is weak or conflicting."]
    chosen_score = 0.0
    if long_score >= 60 and long_score - short_score >= 10:
        direction, chosen_score, reasons = "LONG", long_score, long_reasons
    elif short_score >= 60 and short_score - long_score >= 10:
        direction, chosen_score, reasons = "SHORT", short_score, short_reasons
    if direction == "NO_TRADE":
        score = max(long_score, short_score)
        quality = "NO_TRADE"
        levels = None
    else:
        score = chosen_score
        quality = "A+" if score >= 85 else "A" if score >= 75 else "B" if score >= 65 else "C"
        atr_value = float(atr_v)
        entry = price
        if direction == "LONG":
            recent_swing_low = min(float(c["low"]) for c in closed[-10:])
            stop = min(entry - 1.5 * atr_value, recent_swing_low - 0.15 * atr_value)
            risk = entry - stop
            targets = [entry + risk * r for r in (1.0, 2.0, 3.0)]
        else:
            recent_swing_high = max(float(c["high"]) for c in closed[-10:])
            stop = max(entry + 1.5 * atr_value, recent_swing_high + 0.15 * atr_value)
            risk = stop - entry
            targets = [entry - risk * r for r in (1.0, 2.0, 3.0)]
        if direction == "SHORT" and targets[-1] <= 0:
            direction = "NO_TRADE"
            quality = "NO_TRADE"
            levels = None
            reasons = ["Setup rejected because the calculated 3R target is non-positive."]
        else:
            levels = {
                "entry": entry, "stop_loss": stop, "tp1": targets[0], "tp2": targets[1], "tp3": targets[2],
                "risk_distance": risk, "risk_reward": {"tp1": 1.0, "tp2": 2.0, "tp3": 3.0},
                "suggested_risk_percent": 1.0,
                "method": "Entry=last closed close; stop=max(1.5x ATR14, recent 10-candle swing plus 0.15x ATR); targets=1R/2R/3R.",
            }
    return {
        "symbol": symbol, "interval": interval, "direction": direction, "quality": quality,
        "score": round(score, 2), "long_score": round(long_score, 2), "short_score": round(short_score, 2),
        "market_regime": "TRENDING" if adx_v is not None and float(adx_v) >= 25 else "RANGING_OR_WEAK_TREND",
        "reasons": reasons, "strategy": STRATEGY_NAME, "strategy_status": STRATEGY_STATUS,
        "status": "assessment_only", "created_at": datetime.now(timezone.utc).isoformat(),
        "last_candle_open_time": closed[-1].get("open_time"), "indicators": indicators, "levels": levels,
        "limitations": [
            "Experimental rule set; it has not been backtested or statistically calibrated.",
            "Score is a confluence score, not a probability of winning.",
            "Spot market short selling may not be available; direction labels do not execute trades.",
            "Fees, slippage, funding, spread, and order-book depth are not included in these levels.",
        ],
    }
