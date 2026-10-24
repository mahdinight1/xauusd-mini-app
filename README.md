# NEXTRADE — Android / Flutter trading analytics

NEXTRADE is a bilingual Persian RTL / English LTR Flutter Android source project with a FastAPI backend. This revision includes public-market charting and indicators, a versioned experimental signal engine, a persistent virtual-trading ledger, time-ordered backtests and anchored walk-forward evaluation, an optional economic calendar adapter, and in-app notification history.

> **Build/status honesty:** backend tests pass in the authoring environment. Flutter, Dart and Android SDK are not installed here, so this source has **not** been compiled or tested on an Android emulator/device, and no APK is included. Live connections to market/calendar providers also need to be verified from your network after configuration. This is a development implementation, not a production-ready trading service.

## Implemented in this revision

### Market data, charts, and signals
- Public Binance Spot REST data for candles/tickers plus a public kline WebSocket for the forming candle; no exchange API key is required for these public data endpoints.
- Candlestick chart, volume, history pan/zoom, symbol/timeframe selection and overlays: EMA20/50, Bollinger Bands, Supertrend, Ichimoku lines, and Donchian channels.
- Indicator calculations: SMA/EMA, RSI, MACD, ATR, ADX, Bollinger Bands, volume average, rolling-window VWAP proxy, Stochastic RSI, Ichimoku values, Supertrend, Donchian channels, and OBV.
- Explainable `NEXTRADE Trend-Momentum-Confluence v1` assessment with LONG, SHORT or NO_TRADE, factor scores, reasons, and Entry/SL/TP1–TP3 where the setup passes the rules.

### Automatic demo trading and history
- SQLite-backed demo accounts, positions, closed trades, and an event ledger that persist between backend restarts when the configured database file is retained.
- Automatic scanner runs at `DEMO_POLL_SECONDS` for accounts with auto-demo enabled. Existing virtual positions continue to be monitored even after automatic entry is disabled.
- Manual one-time scan, per-symbol single active position guard, idempotency key on account/symbol/signal-candle, risk-based quantity bounded by available virtual capital, entry/exit fees, 40%/30%/30% partial exits at TP1/TP2/TP3, and account metrics.
- If an OHLC candle touches both SL and a target, the virtual engine applies SL first. This is conservative but cannot recreate the exact order of intrabar price movement.
- Resetting the demo account is destructive: it deletes the account's trade/event/notification history and disables auto-demo.

### Backtest and walk-forward
- Backtest retrieves historical market candles from the configured market provider, calculates signals only with candles available at each decision time, and enters at the **next candle open** with adverse modeled slippage.
- Supports risk-based position sizing, fees, slippage, partial target exits, deterministic OHLC execution, stop-first ambiguity handling, end-of-test liquidation, equity/drawdown metrics and stored run history.
- Walk-forward splits later unseen candle segments into folds using expanding historical context. The current strategy is **fixed and not parameter-fitted**; this evaluates temporal stability but is not a full strategy-training/optimization workflow. Each fold restarts with the same initial capital, so aggregate PnL is a sum of independent fold results, not one continuously compounded equity curve.

### Academy, accounts, certificates, and membership
- 12 modules with 36 lessons and 48 server-side questions; quiz answers are not sent to the client before grading. Module pass mark is 75%; final exam draws 20 random questions and requires 80%.
- Authenticated learning progress, single-use submitted attempts, per-user records, module unlocks by subscription tier, and server-side prerequisite checks.
- Access policy: Free modules 1-3; Pro modules 1-8; Premium all 12 modules plus the final exam and certificate.
- **Current billing mode is DEMO** (`NEXTRADE_BILLING_MODE=demo`): the signed-in user can activate Pro or Premium test access for 30 days without sending a payment to any service. Repeated activation of an already-active same/higher demo tier does not extend its expiry; choosing a higher tier is treated as a demo upgrade. The server marks these records as `store=demo` and `payment_collected=false`.
- A course certificate is issued only after all lessons, all 12 module quizzes, and the final exam are passed. It has a unique ID, an HMAC signature verified by the backend, a public online verification endpoint, and a printable HTML page that can be saved to PDF from a browser. It is a platform completion record, **not** a government licence or professional accreditation.
- Account registration/login uses Argon2 password hashing and revocable, expiring bearer sessions. The JWT signing key must be replaced with a unique random secret before use outside a local test environment.
- Binance Spot connection is read-only. The backend queries key restrictions, fails closed unless account reading is enabled and trading/withdrawals are explicitly disabled, then encrypts key material at rest using Fernet. The mobile UI clears the entry fields after submission. No real orders or withdrawals exist in this feature.
- Real Google Play billing is **disabled by default**. The app's membership page currently calls the authenticated demo-activation endpoint and shows a clear DEMO/no-real-payment label; the Google Play verification endpoint returns 403 while `NEXTRADE_BILLING_MODE=demo`. Actual billing is a future mode requiring configured Play products, a service account, purchase-token verification, and end-to-end store testing. Do not switch the environment to `google_play` until the mobile purchase flow is implemented and tested.

### Economic calendar and notifications
- Calendar adapter uses Finnhub economic-calendar data only when `FINNHUB_API_KEY` is configured. Missing/failed source returns an explicit error; it never fills the UI with invented events.
- In-app notifications and event history are persisted for demo trade opens, TP/SL events, trade close, and high-impact calendar events. Notification types can be enabled/disabled, and unread items can be marked read.
- High-impact calendar notifications are polled in the background when the Finnhub key is configured.
- Optional Firebase Admin / FCM server send code is present, but **end-to-end Android push is not finished**: Flutter Firebase initialization, permission request, token retrieval, and device-token registration UI are not implemented. The app labels Push as unavailable rather than pretending it works.

## Important limitations and safety

- The strategy is **experimental and unvalidated**. The new backtest and walk-forward tools have not established profitability; do not use the output as a proven real-money decision system. A strategy score is not a win probability.
- The backtest models fees/slippage and conservative OHLC exits, but not funding, bid/ask spread, liquidity, exchange order filters, latency, or all real execution behavior. Historical data/provider availability limits sample size.
- The current walk-forward mode does not tune parameters. It only evaluates fixed rules over successive out-of-sample time segments.
- The data layer and API need live-feed verification in the target region. Public endpoints can be rate-limited or unavailable.
- Authentication and owner checks exist for academy, certificates, exchange connections, and subscriptions. However, **legacy demo-account, notifications, backtest-history, and some older routes have not all been migrated to consistent authentication and owner-scoped authorization**. Run locally or behind a trusted private network only; do not expose the API publicly until every route is audited, HTTPS and rate limiting are configured, and the deployment receives a security review.
- SQLite is suitable for local development/single-process use, not a horizontally scaled production backend. Use managed PostgreSQL, migrations, backups and monitoring before multi-user release.
- Economic calendar requires a valid Finnhub API key. FCM requires Firebase credentials and additional mobile-side setup before push works.
- No real exchange orders are ever sent by this app. All execution in this module is virtual/demo only.

## Project layout

```text
lib/                       Flutter app (Persian / English)
  core/l10n/                strings and language direction
  core/services/            API client and local settings
  features/charts/           candlestick chart and overlays
  features/demo/             virtual account and trade history
  features/tools/            calendar, backtest, notifications
backend/app/main.py         FastAPI routes and background worker
backend/app/market/         Binance adapter and indicator calculations
backend/app/strategy/       signal engine
backend/app/services/       SQLite ledger, backtest, calendar, FCM, academy content, identity and entitlement security
backend/tests/              backend tests
scripts/                    platform bootstrap scripts
docs/                       API, strategy, security and status notes
```

## 1. Build Android (on a computer with Flutter installed)

If you do not want to install Flutter locally, see [`BUILD_APK_FA.md`](BUILD_APK_FA.md) for the included GitHub Actions cloud-build workflow. This environment itself has not generated an APK.

Install Flutter stable and Android Studio / Android SDK, then open a terminal in this directory.

### Windows PowerShell
```powershell
.\scripts\bootstrap_android.ps1
flutter build apk --release
```

### Linux / macOS
```bash
chmod +x scripts/bootstrap_android.sh
./scripts/bootstrap_android.sh
flutter build apk --release
```

The bootstrap script generates the Android platform wrapper, sets Android `minSdk` to 24 (required by the selected secure-storage package), enables Internet permission, fetches Dart packages, and runs Flutter analysis/tests on that machine. This repository has not been compiled here. The default backend URL is `http://10.0.2.2:8000` for an Android emulator calling a backend on the host. A physical device needs a reachable LAN/server URL; use HTTPS for any deployment outside development.

## 2. Run backend locally

Python 3.11+ recommended.

### Windows PowerShell
```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

### Linux / macOS
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

`MARKET_PROVIDER=binance_public` enables public market data. `MARKET_PROVIDER=none` disables it and returns HTTP 503. The public Binance endpoints do not require an API key.

### Required identity and credential secrets
Before using accounts or storing exchange credentials, replace the example values in `backend/.env` with real random secrets:

```powershell
# Generate a Fernet key (copy the printed value into NEXTRADE_CREDENTIAL_ENCRYPTION_KEY)
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Set `NEXTRADE_JWT_SECRET` and `NEXTRADE_CERTIFICATE_SIGNING_KEY` to different unique random values of at least 32 characters. Keep all secrets outside source control and back them up securely: losing the encryption key makes stored exchange credentials and encrypted purchase tokens unreadable, and losing the certificate signing key prevents verification of existing certificates. Set `NEXTRADE_PUBLIC_BASE_URL` to the public HTTPS API origin so certificate URLs can be shared. Do not use any example placeholders in a deployed environment.

### Demo subscriptions (current mode)
Keep `NEXTRADE_BILLING_MODE=demo` in the backend environment. The membership screen lets a signed-in user activate Pro or Premium demo access for 30 days. No payment processor/store is contacted and no money is collected. Demo entitlements are recorded server-side and expire. The `/v1/subscriptions/google-play/verify` endpoint is blocked while demo mode is enabled.

### Real Google Play subscriptions (future mode, not wired into the current app UI)
Only after implementing and testing the mobile store-purchase flow, create `nextrade_pro_monthly` and `nextrade_premium_monthly` in Google Play Console. Set `GOOGLE_PLAY_PACKAGE_NAME` and `GOOGLE_PLAY_SERVICE_ACCOUNT_PATH` to the final app package and a securely stored service-account file. Grant least-privilege access, configure billing products, and verify purchases through a Play test track before considering a switch to `NEXTRADE_BILLING_MODE=google_play`. Do not switch the mode now: the Flutter UI deliberately uses the demo endpoint.

### Binance read-only connection
In the profile/membership screen, connect a key created with account-reading only; explicitly disable Spot/Margin trading and withdrawals and restrict the key by IP when supported. The backend rejects permission responses that do not explicitly prove trading and withdrawals are disabled. Use HTTPS whenever not on a local development machine, and never give the app a withdrawal-enabled key. The integration does not place real orders.

### Optional economic calendar
Set `FINNHUB_API_KEY` in `backend/.env`. The calendar screen queries the next seven days from that provider. Review Finnhub's current plan, usage limits, permitted use and data licensing before deployment. No key means a visible configuration error, not fake calendar rows.

### Optional Firebase push (server-side only; mobile setup still pending)
Set `FCM_PROJECT_ID` and `FCM_SERVICE_ACCOUNT_PATH` in the backend environment. Keep the service-account JSON outside the repo and do not commit it. Push will not work end-to-end until the Flutter app is configured for the same Firebase project and registers its FCM device token; that mobile integration is not implemented in this revision. In-app notifications do work from persisted demo/calendar events.

## 3. Test backend

```bash
cd backend
python -m pip install -r requirements.txt
pytest -q
```

Latest backend result in this environment: **40 passed**. Tests use deterministic fixtures, mock store verifiers and mocked exchange responses; they do not prove that live Google Play, Binance private-key verification, calendar APIs, Flutter UI, or an Android APK work in production. Run the Flutter bootstrap script on a Flutter-enabled machine to execute `flutter analyze`, widget tests and an APK build.

## 4. Main API routes

See [`docs/API.md`](docs/API.md) for the complete route list and payload descriptions. FastAPI's interactive docs are available at `http://127.0.0.1:8000/docs` while the backend is running.

## 5. Release requirements

Before public or real users release: finish backend authorization/ownership checks across legacy routes, HTTPS and managed secrets; finish and test the future Google Play purchase flow before switching billing mode, and validate a read-only exchange key; finish Firebase client token registration if push is required; run Flutter analyzer/widget tests and Android build/device tests; verify provider access in the target region; validate indicators and strategy against independent references; conduct reproducible out-of-sample testing; document privacy, retention and provider terms; and configure release signing. Never claim a successful APK build until that command completes successfully.
