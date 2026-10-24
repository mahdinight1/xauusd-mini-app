from __future__ import annotations

from statistics import pstdev
from typing import Any


def sma(values: list[float], period: int) -> list[float | None]:
    if period <= 0:
        raise ValueError("period must be positive")
    out: list[float | None] = [None] * len(values)
    for i in range(period - 1, len(values)):
        out[i] = sum(values[i - period + 1:i + 1]) / period
    return out


def ema(values: list[float], period: int) -> list[float | None]:
    if period <= 0:
        raise ValueError("period must be positive")
    out: list[float | None] = [None] * len(values)
    if len(values) < period:
        return out
    initial = sum(values[:period]) / period
    out[period - 1] = initial
    alpha = 2 / (period + 1)
    previous = initial
    for i in range(period, len(values)):
        previous = values[i] * alpha + previous * (1 - alpha)
        out[i] = previous
    return out


def rsi(values: list[float], period: int = 14) -> list[float | None]:
    out: list[float | None] = [None] * len(values)
    if period <= 0 or len(values) <= period:
        return out
    gains = [max(values[i] - values[i - 1], 0.0) for i in range(1, len(values))]
    losses = [max(values[i - 1] - values[i], 0.0) for i in range(1, len(values))]
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    out[period] = 100.0 if avg_loss == 0 and avg_gain > 0 else (50.0 if avg_loss == 0 else 100 - 100 / (1 + avg_gain / avg_loss))
    for i in range(period + 1, len(values)):
        gain, loss = gains[i - 1], losses[i - 1]
        avg_gain = ((period - 1) * avg_gain + gain) / period
        avg_loss = ((period - 1) * avg_loss + loss) / period
        out[i] = 100.0 if avg_loss == 0 and avg_gain > 0 else (50.0 if avg_loss == 0 else 100 - 100 / (1 + avg_gain / avg_loss))
    return out


def macd(values: list[float], fast: int = 12, slow: int = 26, signal_period: int = 9) -> tuple[list[float | None], list[float | None], list[float | None]]:
    fast_line, slow_line = ema(values, fast), ema(values, slow)
    line: list[float | None] = [None] * len(values)
    for i, (f, s) in enumerate(zip(fast_line, slow_line)):
        if f is not None and s is not None:
            line[i] = f - s
    valid_start = next((i for i, v in enumerate(line) if v is not None), len(values))
    compact = [v for v in line[valid_start:] if v is not None]
    signal_compact = ema(compact, signal_period)
    signal_line: list[float | None] = [None] * len(values)
    for j, value in enumerate(signal_compact):
        signal_line[valid_start + j] = value
    hist: list[float | None] = [None] * len(values)
    for i, (m, sig) in enumerate(zip(line, signal_line)):
        if m is not None and sig is not None:
            hist[i] = m - sig
    return line, signal_line, hist


def true_ranges(candles: list[dict[str, Any]]) -> list[float]:
    out: list[float] = []
    for i, candle in enumerate(candles):
        high, low = float(candle["high"]), float(candle["low"])
        prev_close = float(candles[i - 1]["close"]) if i else float(candle["close"])
        out.append(max(high - low, abs(high - prev_close), abs(low - prev_close)))
    return out


def atr(candles: list[dict[str, Any]], period: int = 14) -> list[float | None]:
    tr = true_ranges(candles)
    out: list[float | None] = [None] * len(tr)
    if len(tr) < period or period <= 0:
        return out
    previous = sum(tr[:period]) / period
    out[period - 1] = previous
    for i in range(period, len(tr)):
        previous = ((period - 1) * previous + tr[i]) / period
        out[i] = previous
    return out


def bollinger(values: list[float], period: int = 20, deviation: float = 2.0) -> dict[str, list[float | None]]:
    middle = sma(values, period)
    upper: list[float | None] = [None] * len(values)
    lower: list[float | None] = [None] * len(values)
    for i in range(period - 1, len(values)):
        window = values[i - period + 1:i + 1]
        spread = pstdev(window) * deviation
        upper[i] = middle[i] + spread if middle[i] is not None else None
        lower[i] = middle[i] - spread if middle[i] is not None else None
    return {"middle": middle, "upper": upper, "lower": lower}


def adx(candles: list[dict[str, Any]], period: int = 14) -> list[float | None]:
    n = len(candles)
    result: list[float | None] = [None] * n
    if period <= 0 or n < period * 2 + 1:
        return result
    plus_dm = [0.0] * n
    minus_dm = [0.0] * n
    for i in range(1, n):
        up = float(candles[i]["high"]) - float(candles[i - 1]["high"])
        down = float(candles[i - 1]["low"]) - float(candles[i]["low"])
        plus_dm[i] = up if up > down and up > 0 else 0.0
        minus_dm[i] = down if down > up and down > 0 else 0.0
    tr = true_ranges(candles)
    smooth_tr = sum(tr[1:period + 1])
    smooth_plus = sum(plus_dm[1:period + 1])
    smooth_minus = sum(minus_dm[1:period + 1])
    dx_values: list[float | None] = [None] * n
    for i in range(period, n):
        if i > period:
            smooth_tr = smooth_tr - smooth_tr / period + tr[i]
            smooth_plus = smooth_plus - smooth_plus / period + plus_dm[i]
            smooth_minus = smooth_minus - smooth_minus / period + minus_dm[i]
        if smooth_tr <= 0:
            continue
        plus_di = 100 * smooth_plus / smooth_tr
        minus_di = 100 * smooth_minus / smooth_tr
        denom = plus_di + minus_di
        dx_values[i] = 0.0 if denom <= 0 else 100 * abs(plus_di - minus_di) / denom
    valid = [i for i, v in enumerate(dx_values) if v is not None]
    if len(valid) < period:
        return result
    first = valid[period - 1]
    previous = sum(float(dx_values[i]) for i in valid[:period]) / period
    result[first] = previous
    for i in range(first + 1, n):
        if dx_values[i] is not None:
            previous = ((period - 1) * previous + float(dx_values[i])) / period
            result[i] = previous
    return result


def _rolling_midpoint(candles: list[dict[str, Any]], period: int) -> float | None:
    if len(candles) < period:
        return None
    window = candles[-period:]
    highest = max(float(c["high"]) for c in window)
    lowest = min(float(c["low"]) for c in window)
    return (highest + lowest) / 2.0


def _stochastic_rsi(values: list[float], rsi_period: int = 14, stoch_period: int = 14, smooth_k: int = 3, smooth_d: int = 3) -> tuple[float | None, float | None]:
    rsi_values = rsi(values, rsi_period)
    raw_stoch: list[float | None] = [None] * len(values)
    for i, current in enumerate(rsi_values):
        if current is None or i + 1 < stoch_period:
            continue
        window = [v for v in rsi_values[i - stoch_period + 1:i + 1] if v is not None]
        if len(window) < stoch_period:
            continue
        low, high = min(window), max(window)
        raw_stoch[i] = 50.0 if high == low else (float(current) - low) / (high - low) * 100.0
    k_line: list[float | None] = [None] * len(values)
    for i in range(smooth_k - 1, len(values)):
        window = raw_stoch[i - smooth_k + 1:i + 1]
        if all(value is not None for value in window):
            k_line[i] = sum(float(value) for value in window if value is not None) / smooth_k
    d_line: list[float | None] = [None] * len(values)
    for i in range(smooth_d - 1, len(values)):
        window = k_line[i - smooth_d + 1:i + 1]
        if all(value is not None for value in window):
            d_line[i] = sum(float(value) for value in window if value is not None) / smooth_d
    return (k_line[-1] if k_line else None, d_line[-1] if d_line else None)


def _supertrend(candles: list[dict[str, Any]], period: int = 10, multiplier: float = 3.0) -> tuple[float | None, str | None]:
    atr_values = atr(candles, period)
    n = len(candles)
    if n < period + 2 or atr_values[-1] is None:
        return None, None
    final_upper: list[float | None] = [None] * n
    final_lower: list[float | None] = [None] * n
    direction: list[int | None] = [None] * n
    line: list[float | None] = [None] * n
    for i, candle in enumerate(candles):
        atr_value = atr_values[i]
        if atr_value is None:
            continue
        midpoint = (float(candle["high"]) + float(candle["low"])) / 2.0
        basic_upper = midpoint + multiplier * atr_value
        basic_lower = midpoint - multiplier * atr_value
        prev_close = float(candles[i - 1]["close"]) if i > 0 else float(candle["close"])
        prev_upper = final_upper[i - 1] if i > 0 else None
        prev_lower = final_lower[i - 1] if i > 0 else None
        final_upper[i] = basic_upper if prev_upper is None or basic_upper < prev_upper or prev_close > prev_upper else prev_upper
        final_lower[i] = basic_lower if prev_lower is None or basic_lower > prev_lower or prev_close < prev_lower else prev_lower
        if i == 0 or direction[i - 1] is None:
            direction[i] = 1 if float(candle["close"]) >= midpoint else -1
        elif direction[i - 1] == -1 and float(candle["close"]) > float(prev_upper if prev_upper is not None else basic_upper):
            direction[i] = 1
        elif direction[i - 1] == 1 and float(candle["close"]) < float(prev_lower if prev_lower is not None else basic_lower):
            direction[i] = -1
        else:
            direction[i] = direction[i - 1]
        line[i] = final_lower[i] if direction[i] == 1 else final_upper[i]
    last_direction = direction[-1]
    return line[-1], ("BULLISH" if last_direction == 1 else "BEARISH" if last_direction == -1 else None)


def _obv(candles: list[dict[str, Any]]) -> float | None:
    if not candles:
        return None
    total = 0.0
    for i in range(1, len(candles)):
        volume = float(candles[i].get("volume", 0.0))
        if float(candles[i]["close"]) > float(candles[i - 1]["close"]):
            total += volume
        elif float(candles[i]["close"]) < float(candles[i - 1]["close"]):
            total -= volume
    return total


def latest_indicators(candles: list[dict[str, Any]]) -> dict[str, Any]:
    if not candles:
        raise ValueError("At least one candle is required")
    closes = [float(c["close"]) for c in candles]
    ema20, ema50 = ema(closes, 20), ema(closes, 50)
    sma20 = sma(closes, 20)
    rsi14 = rsi(closes, 14)
    macd_line, macd_signal, macd_hist = macd(closes)
    atr14 = atr(candles, 14)
    adx14 = adx(candles, 14)
    bands = bollinger(closes, 20)
    volumes = [float(c.get("volume", 0.0)) for c in candles]
    volume_sma20 = sma(volumes, 20)
    idx = len(candles) - 1
    take = lambda arr: arr[idx] if idx < len(arr) else None
    price = closes[idx]
    vwap_start = max(0, idx - 19)
    vwap_volume = sum(volumes[vwap_start:idx + 1])
    vwap_value = (
        sum(((float(c["high"]) + float(c["low"]) + float(c["close"])) / 3) * float(c.get("volume", 0.0)) for c in candles[vwap_start:idx + 1]) / vwap_volume
        if vwap_volume > 0 else None
    )
    latest_volume_sma = take(volume_sma20)
    stoch_k, stoch_d = _stochastic_rsi(closes)
    supertrend_value, supertrend_direction = _supertrend(candles)
    tenkan = _rolling_midpoint(candles, 9)
    kijun = _rolling_midpoint(candles, 26)
    senkou_b = _rolling_midpoint(candles, 52)
    senkou_a = (tenkan + kijun) / 2.0 if tenkan is not None and kijun is not None else None
    donchian_window = candles[max(0, idx - 20):idx]  # previous 20 bars, excluding the active comparison bar
    donchian_upper = max((float(c["high"]) for c in donchian_window), default=None)
    donchian_lower = min((float(c["low"]) for c in donchian_window), default=None)
    donchian_mid = (donchian_upper + donchian_lower) / 2.0 if donchian_upper is not None and donchian_lower is not None else None
    return {
        "close": price,
        "sma20": take(sma20), "ema20": take(ema20), "ema50": take(ema50),
        "rsi14": take(rsi14), "macd": take(macd_line), "macd_signal": take(macd_signal),
        "macd_histogram": take(macd_hist), "atr14": take(atr14), "adx14": take(adx14),
        "bollinger_upper": take(bands["upper"]), "bollinger_middle": take(bands["middle"]),
        "bollinger_lower": take(bands["lower"]), "vwap20": vwap_value,
        "volume": volumes[idx], "volume_sma20": latest_volume_sma,
        "stoch_rsi_k": stoch_k, "stoch_rsi_d": stoch_d,
        "ichimoku_tenkan_sen": tenkan, "ichimoku_kijun_sen": kijun,
        "ichimoku_senkou_span_a_current": senkou_a, "ichimoku_senkou_span_b_current": senkou_b,
        "supertrend": supertrend_value, "supertrend_direction": supertrend_direction,
        "donchian_upper20_prev": donchian_upper, "donchian_lower20_prev": donchian_lower,
        "donchian_mid20_prev": donchian_mid, "obv": _obv(candles),
        "donchian_breakout_up": donchian_upper is not None and price > donchian_upper,
        "donchian_breakout_down": donchian_lower is not None and price < donchian_lower,
    }
