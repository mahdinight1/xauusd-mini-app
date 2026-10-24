# NEXTRADE API reference

Base URL example: `http://127.0.0.1:8000`. Interactive OpenAPI docs: `/docs`.

## System and market data

| Method | Path | Behavior |
|---|---|---|
| GET | `/health` | Service health and UTC timestamp. |
| GET | `/v1/market/status` | Requests provider status. |
| GET | `/v1/markets?symbols=BTCUSDT,ETHUSDT` | Public 24-hour tickers for default/requested symbols. |
| GET | `/v1/market/ticker/{symbol}` | Public 24-hour ticker. |
| GET | `/v1/market/candles?symbol=BTCUSDT&interval=1m&limit=300` | Historical/current klines, source and receive metadata. Limit 100–1000. |
| GET | `/v1/market/indicators/{symbol}?interval=15m` | Indicators computed from available closed candles; needs enough history. |
| GET | `/v1/signals?symbols=BTCUSDT,ETHUSDT&interval=15m` | Long/short/no-trade assessments; up to six symbols. Signal history is not persisted by this route. |
| POST | `/v1/analyze/{symbol}?interval=15m` | Detailed manual assessment, factor scores, reasons and levels when eligible. |

The adapter uses Binance's public Spot market-data REST and kline WebSocket endpoints. No private exchange API key is used. Source data can be rate-limited/unavailable; errors are returned rather than fabricated prices/candles.

## Demo trading and ledger

All orders here are **virtual**. No exchange order is placed.

| Method | Path | Behavior |
|---|---|---|
| POST | `/v1/demo/accounts` | Create a demo account. Body: `initial_capital`, optional `symbols`, `interval`, `risk_percent` (0–5), `fee_bps` (0–100). |
| GET | `/v1/demo/accounts/{account_id}` | Equity, realized/unrealized PnL, exposure, available balance, open/closed counts, and settings. |
| POST | `/v1/demo/accounts/{account_id}/auto` | Body `{ "enabled": true|false }`; enables/disables automatic *new entries*. Open positions continue to be monitored. |
| POST | `/v1/demo/accounts/{account_id}/scan` | One manual scan. It may open a virtual position if the current setup qualifies. |
| GET | `/v1/demo/accounts/{account_id}/positions?status=OPEN&limit=200` | Full position list; `status` can be `OPEN` or `CLOSED`, or omitted for all recent records. |
| GET | `/v1/demo/accounts/{account_id}/events?limit=200` | Event ledger: opens, partial target exits, stop loss, close, fees, and event details. |
| POST | `/v1/demo/accounts/{account_id}/reset` | Destructive reset: deletes positions, event history and notifications, and disables auto-demo. |

The background worker scans active demo accounts every `DEMO_POLL_SECONDS` (minimum effective loop delay is five seconds). Market updates are subject to provider response latency and polling cadence. A unique account/symbol/signal-candle key prevents the same signal candle from opening duplicate positions. Only one open position per symbol per account is permitted. Position size is bounded by risk-distance sizing and available notional capital. TP exits use 40% / 30% / 30%; if an OHLC bar touches SL and a target together, SL is conservatively applied first.

## Backtest and walk-forward

| Method | Path | Behavior |
|---|---|---|
| POST | `/v1/backtest` | Historical simulation. Body options include `symbol`, `interval`, `candles_limit` (200–1000), `initial_capital`, `risk_percent`, `fee_bps`, `slippage_bps`, optional `account_id`. |
| POST | `/v1/walk-forward` | Anchored expanding-context evaluation. Additional options: `folds` (2–6), `train_fraction` (0.35–0.85). At least 300 closed candles required. |
| GET | `/v1/backtest/history?limit=50` | Stored run records and configuration/results. `limit` 1–200. |

Execution assumptions:
- Signal evaluation is time-ordered and sees only data through the decision candle.
- Entries use the next candle's open with adverse slippage; exits model fee and slippage drag.
- Target exits are 40% / 30% / 30%. For ambiguous OHLC bars, stop-loss takes priority over targets.
- Positions remaining at the end of the evaluation are liquidated at the last close with modeled slippage/fee.
- Funding, spread, order-book liquidity, latency, lot-size constraints and venue-specific order behavior are not fully modeled.
- Walk-forward does not optimize/tune the strategy. Each fold uses the fixed rules over a later unseen candle segment and restarts with the same initial capital; summed PnL is not a continuous compounded equity curve.
- Results are exploratory; the strategy is experimental and not proven profitable.

## Economic calendar

| Method | Path | Behavior |
|---|---|---|
| GET | `/v1/calendar/economic?from=2026-10-24&to=2026-10-31&importance=high&country=US` | Fetches provider calendar; `importance` and `country` are optional. Date range cannot exceed 31 days. |

Requires `FINNHUB_API_KEY`. If missing or the provider fails, returns HTTP 503 with a clear reason rather than fabricated data. Source timestamps without timezone information are tagged `provider_timezone_unspecified` and are not silently treated as UTC.

## Notifications

| Method | Path | Behavior |
|---|---|---|
| GET | `/v1/notifications/status` | Reports whether in-app alerts, calendar and server FCM credentials are configured. |
| GET | `/v1/demo/accounts/{account_id}/notifications?limit=100&unread_only=false` | Persisted in-app notification records and unread count. |
| GET | `/v1/demo/accounts/{account_id}/notification-preferences` | Current notification preferences. |
| PUT | `/v1/demo/accounts/{account_id}/notification-preferences` | Saves `enabled`, `enabled_events`, `quiet_start`, `quiet_end`, `min_importance`, `push_enabled`. Quiet-hour values use `HH:MM` and are interpreted against UTC by this prototype. `min_importance` is persisted but not yet used to change dispatch; current background calendar notifications are high-impact only. |
| POST | `/v1/demo/accounts/{account_id}/notification-devices` | Registers an FCM token and platform, but Flutter client token collection/registration is not implemented yet. |
| POST | `/v1/demo/accounts/{account_id}/notifications/{notification_id}/read` | Marks one notification as read. |

In-app notifications are generated for selected demo trade events and high-impact calendar events. Calendar alerts are only generated when the calendar key is configured and the background worker runs. Server-side FCM sender code is present, but push is not end-to-end until Firebase is configured on the Android client and device tokens are registered. Required backend environment: `FCM_PROJECT_ID` and `FCM_SERVICE_ACCOUNT_PATH`; keep the service-account file outside version control.


## Identity, academy, assessment, and certificates

All `/v1/auth/*`, `/v1/academy/*` (except public certificate verification/view), `/v1/exchanges/*`, and `/v1/subscriptions/me` routes require `Authorization: Bearer <access_token>`. Sessions are expiring and logout revokes the current session. Passwords are hashed server-side.

| Method | Path | Behavior |
|---|---|---|
| POST | `/v1/auth/register` | Create account; body `display_name`, `email`, `password` (10+ chars). Returns a bearer token. |
| POST | `/v1/auth/login` | Verify credentials and issue a new session token. |
| GET | `/v1/auth/me` | Current profile and server-computed subscription entitlement. |
| POST | `/v1/auth/logout` | Revoke the current bearer session. |
| GET | `/v1/academy/modules` | Authenticated course modules and lock state for the current tier. Free: modules 1-3; Pro: modules 1-8; Premium: all 12. Locked lesson content is not sent. |
| GET | `/v1/academy/progress` | Per-user lesson completion, module quiz history, final-exam status, and a safe certificate summary. Internal signatures/user IDs are not returned. |
| POST | `/v1/academy/modules/{module_id}/lessons/{lesson_id}/complete` | Persist completion after the required subscription tier has been checked. |
| POST | `/v1/academy/modules/{module_id}/quiz/start` | Start a module quiz only after its lessons are completed and tier allows the module. |
| POST | `/v1/academy/quiz/{attempt_id}/submit` | Submit exactly one answer per question; the backend grades answers and records attempts. |
| POST | `/v1/academy/final-exam/start` | Premium only; requires every lesson and module quiz to be complete. Returns 20 random questions, with answer keys kept server-side. |
| POST | `/v1/academy/final-exam/{attempt_id}/submit` | Grades final attempt; passing threshold is 80%. A certificate is issued only when every prerequisite is fulfilled. |
| GET | `/v1/academy/certificates/me` | Current user's certificate status and verification/printable URLs. |
| GET | `/v1/academy/certificates/verify/{certificate_number}` | Public HMAC-signature verification. |
| GET | `/v1/academy/certificates/view/{certificate_number}` | Printable HTML certificate; browser print can save it as PDF. |

The course has 12 modules, 36 lessons and a server-side question bank of 48 questions. Module quiz pass mark is 75%; the final exam selects 20 randomized questions and uses an 80% threshold. Certificates are platform-issued course-completion records, not official accreditation or a guarantee of trading expertise.

## Exchange connections and subscriptions

| Method | Path | Behavior |
|---|---|---|
| GET | `/v1/exchanges/connections` | Current user's exchange connections; secrets are never returned. |
| POST | `/v1/exchanges/binance/connect` | Validates Binance key permissions and encrypts key/secret at rest. Requires account-read enabled and trading/withdrawals explicitly disabled. HTTPS is required when `ENVIRONMENT=production`. |
| POST | `/v1/exchanges/binance/test` | Re-checks private-key permissions using the stored encrypted credential. |
| DELETE | `/v1/exchanges/binance` | Removes current user's stored Binance connection. Revoke the key at Binance too if it may have been exposed. |
| GET | `/v1/subscriptions/plans` | Returns tier features and current billing mode. The default `demo` mode has no store product IDs or real prices. |
| GET | `/v1/subscriptions/me` | Returns the signed-in user's server-computed subscription entitlement. |
| POST | `/v1/subscriptions/demo/activate` | **Demo mode only**. Authenticated JSON body `{ "tier": "pro" }` or `{ "tier": "premium" }`; grants 30 days of test access without collecting money. Same/higher active demo tier is idempotent and does not extend expiry. |
| POST | `/v1/subscriptions/google-play/verify` | Future real-billing endpoint; returns 403 while `NEXTRADE_BILLING_MODE=demo`. When real mode is deliberately enabled and configured, verifies purchase token server-side. |

Set `NEXTRADE_BILLING_MODE=demo` for the current no-payment membership flow. Set `NEXTRADE_JWT_SECRET`, the independent `NEXTRADE_CERTIFICATE_SIGNING_KEY`, `NEXTRADE_CREDENTIAL_ENCRYPTION_KEY`, and `NEXTRADE_PUBLIC_BASE_URL` (public HTTPS API origin for shareable certificate URLs). Google Play variables are not needed in demo mode. The encryption key must be a valid Fernet key. A lost key makes stored encrypted credential/token material unreadable. Product IDs must match Google Play Console.

## Status codes and security

- `422`: invalid inputs/unsupported symbol or interval.
- `502`: market provider request/response failure.
- `503`: market provider disabled, calendar key missing, or external provider unavailable/configuration missing.
- `404`: requested local demo account/position/notification not found.

**Security warning:** identity/academy/exchange/subscription routes enforce authentication and ownership. Legacy demo-account, notification, backtest-history and some routes do not yet all enforce account ownership consistently. Treat the service as local/private until every route is audited, HTTPS and rate limiting are configured, and deployment receives a security review. Never expose it publicly as-is.
