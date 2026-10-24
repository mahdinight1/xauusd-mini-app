# Security and deployment checklist

- [ ] Deploy the API with HTTPS and a restricted CORS origin list.
- [x] Add authentication, server-side authorization and session revocation for identity, academy, certificate, exchange, and subscription routes.
- [ ] Audit every legacy demo, notification, backtest and related route for authentication and owner-scoped authorization; do not expose publicly until complete.
- [ ] Never place exchange secrets or privileged API keys in Flutter, local preferences, logs, or analytics.
- [x] Encrypt Binance API key/secret and Google Play purchase tokens at rest using a server-side Fernet key.
- [ ] Move production secrets into a managed secret store and define key rotation/recovery procedures; restrict exchange permissions to account read access.
- [ ] Validate and normalize all upstream market feed data; track source and timestamps.
- [ ] Reject stale candles before evaluating actionable signals.
- [ ] Add PostgreSQL migrations, backups, audit logs, and idempotency constraints before cloud demo trading.
- [ ] Make financial arithmetic deterministic and covered by unit/integration tests.
- [ ] Treat provider terms, data licensing, jurisdiction, privacy, and financial promotion obligations as release requirements.
- [ ] Use a release signing key held outside source control; do not commit keystores or passwords.
- [ ] Do not enable real order execution without separate opt-in, an order preview, risk limits, audit trail, and explicit disable control.

- [x] Validate a Google Play purchase token server-side before granting Pro/Premium entitlement; verify the token cannot be claimed by another account.
- [x] Gate academy modules/final exam/certificate progression by Free/Pro/Premium entitlement on the backend.
- [x] Sign course certificates with a separate HMAC signing secret and expose a public verification endpoint and printable view. The credential is platform-issued only, not official accreditation.
- [ ] Configure `NEXTRADE_PUBLIC_BASE_URL` to the public HTTPS API origin before issuing shareable certificates in production.
- [ ] Configure actual Play Console subscriptions, service-account permissions and production package ID; perform end-to-end test-track purchase, renewal, cancellation, refund and expiry tests.
- [ ] Perform a real Binance permission test using a dedicated read-only key with trading and withdrawal disabled, then revoke it after verification.
- [ ] Install Flutter/Android SDK, run `flutter analyze`, widget tests, Android build and device security testing; these were not run in the current environment.
