# Market data integration

## Source

Current adapter: Binance public Spot market data.

- REST base: `https://data-api.binance.vision`
- Historical/current candles: `GET /api/v3/klines`
- 24-hour ticker: `GET /api/v3/ticker/24hr`
- Connectivity: `GET /api/v3/ping`
- Public WebSocket: `wss://data-stream.binance.vision/ws/{symbol-lowercase}@kline_{interval}`

Official source references:

- Market-data-only endpoints: https://github.com/binance/binance-spot-api-docs/blob/master/faqs/market_data_only.md
- Spot REST API: https://github.com/binance/binance-spot-api-docs/blob/master/rest-api.md
- WebSocket streams: https://github.com/binance/binance-spot-api-docs/blob/master/web-socket-streams.md

These endpoints are unauthenticated public market data; account balances and user-data streams are not part of this adapter. Provider access, request limits, latency, regional restrictions, and availability remain external dependencies.

## Data handling

- Symbols are normalized to uppercase and validated.
- Intervals are checked against the supported provider interval set.
- Candle OHLCV and exchange timestamps are parsed from source payloads. Invalid rows are ignored, and an empty/malformed response fails closed.
- The `closed` flag is estimated by comparing exchange candle close time with local UTC time. Device clock skew is a known limitation; use exchange-server-time validation in a production version.
- Chart uses REST for initial history and a WebSocket stream for the current candle. The stream reconnects after errors or a no-update timeout. Missing data is displayed as missing, never replaced by generated values.
- Indicators and signal analysis use closed candles only. Indicator API snapshots refresh periodically, so values can lag the open chart candle.

## Operations still required before release

- Run uptime and latency monitoring against the selected endpoint from intended user regions.
- Add bounded retry/backoff and shared connection pooling on backend requests.
- Add provider response caching and endpoint-weight awareness for multi-user deployment.
- Compare indicator outputs against an independently trusted reference with deterministic fixtures.
- Review provider terms, applicable rules, and supported-market availability before public release.
