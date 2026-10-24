# Strategy specification — NEXTRADE Trend-Momentum-Confluence v1

**Status:** experimental and unvalidated. It is an explicit rules engine for software testing and educational analysis, not an investment recommendation. No profitable outcome is promised.

## Input controls

- Symbol from the configured provider.
- One supported candle interval.
- At least 60 closed candles; recommended request size is 300.
- Current open candle is excluded from scoring and trade-level generation.

## Indicators

Backend calculates SMA20, EMA20/EMA50, RSI14, MACD(12,26,9), ATR14, ADX14, Bollinger Bands(20,2 standard deviations), rolling VWAP proxy over 20 candles, 20-candle volume SMA, Stochastic RSI(14,14,3,3), Ichimoku current Tenkan/Kijun/Span A/Span B values, Supertrend(10,3), previous-20-candle Donchian channels, and OBV.

The 20-candle VWAP is not session-anchored. The API returns current Ichimoku values without a forward plot shift. The chart draws current lines to avoid silently implying forward data points.

## Score factors (maximum nominal weight 100 per direction)

| Factor | Max weight | Rule summary |
|---|---:|---|
| EMA trend alignment | 18 | Price > EMA20 > EMA50 favors LONG; reverse favors SHORT. Partial EMA20 alignment contributes 7. |
| RSI14 | 12 | RSI 52–68 favors LONG; 32–48 favors SHORT; >70/<30 penalizes the corresponding direction by 5; neutral directional readings add 4. |
| MACD histogram | 12 | Positive favors LONG; negative favors SHORT. |
| ADX14 | 10 | ADX >=25 awards 10 to EMA trend direction; 18–25 awards 5. |
| Rolling VWAP proxy | 8 | Price above/below proxy favors LONG/SHORT. |
| Relative volume | 8 | Volume >=1.2× its 20-candle SMA awards points in the direction of the candle close. |
| Short-term close structure | 7 | Four or more up/down steps among the last five transitions awards points to the corresponding side. |
| Supertrend | 10 | Direction awards points to matching side. |
| Ichimoku cloud position | 10 | Price above both current spans favors LONG; below both favors SHORT. |
| Donchian breakout | 5 | Close above/below previous 20-candle channel favors LONG/SHORT. |

Scores are clamped to 0–100. They are heuristic confluence scores, not calibrated probabilities. Opposing score is also returned. A side is emitted only if its score is at least 60 and exceeds the opposing score by at least 10; otherwise the output is `NO_TRADE`. Quality labels: A+ >=85, A >=75, B >=65, C >=60; below threshold is `NO_TRADE`.

## Entry, stop-loss, and targets

For a qualifying LONG or SHORT:

- Entry: close of the latest completed candle.
- ATR: Wilder-style ATR14 from candle true ranges.
- LONG stop: `min(entry - 1.5 * ATR14, lowest low of last 10 candles - 0.15 * ATR14)`.
- SHORT stop: `max(entry + 1.5 * ATR14, highest high of last 10 candles + 0.15 * ATR14)`.
- `R = abs(entry - stop_loss)`.
- LONG targets: `entry + (1R, 2R, 3R)`.
- SHORT targets: `entry - (1R, 2R, 3R)`.
- Suggested risk percentage included in the response: 1%, as a configurable example guideline; there is no account-size-based position-sizing/execution engine yet.

The calculation excludes fees, spread, slippage, funding, depth, minimum order size, tick size, and execution gaps. If future backtesting observes both stop and target inside one candle, the simulator must use tick/order data or a documented conservative rule.

## Not implemented / not validated

No multi-timeframe filter, news filter, order book/whale-flow/liquidity-sweep detector, market-structure swing labeling, empirical probability calibration, backtest, out-of-sample validation, walk-forward optimization, or persisted signal history exists yet. A later release must validate indicators against a trusted library and evaluate the strategy with chronological data, modeled costs, and out-of-sample tests before any real-money use.
