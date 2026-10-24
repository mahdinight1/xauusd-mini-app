"""Original beginner-to-advanced trading curriculum and server-side question bank.

Answers are server-only; API endpoints must strip answer/explanation before an attempt is graded.
"""
from __future__ import annotations

MODULES: list[dict] = [
    {
        "id": 1, "title": "Financial markets and basic concepts", "level": "beginner",
        "description": "Market types, trading pairs, liquidity, orders, spread, and execution basics.",
        "lessons": [
            {"id": "m1-l1", "title": "Markets, assets, and trading pairs", "minutes": 8,
             "content": "A financial market is a venue or network where participants exchange assets under a defined set of rules. Crypto spot markets match buyers and sellers of digital assets; a BTC/USDT pair quotes how many USDT are exchanged for one BTC. The first asset is the base asset and the second is the quote asset.\n\nA price is a record of a particular market and source, not a universal truth. Different exchanges can show small differences because their order books and participants differ. Always check the symbol, market type, exchange, and timestamp before comparing prices."},
            {"id": "m1-l2", "title": "Liquidity, spread, and volume", "minutes": 7,
             "content": "The bid is the best displayed buying price and the ask is the best displayed selling price. The spread is ask minus bid. A narrow spread often indicates a more competitive market, but it does not guarantee that a large order can be filled near the displayed price.\n\nVolume measures activity over a period. Liquidity also depends on how much size is available at nearby prices. Large orders can move through several levels of the order book, causing market impact and slippage."},
            {"id": "m1-l3", "title": "Order types and execution", "minutes": 9,
             "content": "A market order prioritizes immediate execution but the final fill price is not guaranteed. A limit order specifies the worst acceptable buying or selling price, but it may not execute. Stop orders can trigger after a condition is reached and may execute at a different price during fast markets.\n\nFees, spread, slippage, funding where applicable, and latency all affect the result. Record actual or modeled costs instead of evaluating a strategy only by its chart entry and target."},
        ],
        "questions": [
            {"id":"m1-q1","question":"In BTC/USDT, which asset is the quote asset?","options":["BTC","USDT","Both are base assets","Neither asset"],"answer":1,"explanation":"USDT is the quote asset; its units express the price of one BTC."},
            {"id":"m1-q2","question":"What does the bid-ask spread measure?","options":["Daily traded volume","The difference between best ask and best bid","The account's unrealized P&L","The number of open orders"],"answer":1,"explanation":"The spread is best ask minus best bid."},
            {"id":"m1-q3","question":"What is a primary limitation of a market order?","options":["It never executes","It guarantees the last traded price","Its final execution price may vary with available liquidity","It cannot incur a fee"],"answer":2,"explanation":"Market orders prioritize execution, not a guaranteed price."},
            {"id":"m1-q4","question":"Which statement about volume and liquidity is most accurate?","options":["They are identical measures","High volume guarantees zero slippage","Liquidity concerns executable size near prices; volume summarizes activity over time","Volume predicts the next candle direction"],"answer":2,"explanation":"Volume and depth/liquidity are related but not interchangeable, and neither guarantees direction."},
        ],
    },
    {
        "id": 2, "title": "Reading price charts", "level": "beginner",
        "description": "Candlestick anatomy, timeframes, trends, ranges, and chart context.",
        "lessons": [
            {"id":"m2-l1","title":"Candlestick anatomy","minutes":8,"content":"Each OHLC candle records open, high, low, and close for a defined interval. The body spans open to close; the wicks show the interval's extremes beyond the body. A candle is only final after its interval closes. A live candle can change its close, high, low, and apparent pattern until then.\n\nOne candle does not prove a reversal or continuation. Interpret it with surrounding structure, volume, volatility, and the time at which the observation became available."},
            {"id":"m2-l2","title":"Timeframes and sessions","minutes":7,"content":"A 5-minute candle summarizes five minutes; a 4-hour candle summarizes four hours. Higher timeframes compress more activity and can make broad structure easier to see, while lower timeframes show more detail and more noise. Signals from several timeframes can conflict.\n\nCrypto trades continuously, but liquidity and activity still vary during the day. Always retain the timezone and timestamp when studying a historical chart or economic event."},
            {"id":"m2-l3","title":"Trends and ranges","minutes":8,"content":"An uptrend commonly forms higher swing highs and higher swing lows; a downtrend commonly forms lower highs and lower lows. A range contains repeated reactions between areas of support and resistance without sustained directional progress. Markets can transition between these regimes.\n\nTrend labels are hypotheses based on a rule, not certainties. Define the swing lookback and confirmation rule before testing so that chart interpretation is repeatable."},
        ],
        "questions": [
            {"id":"m2-q1","question":"When is an OHLC candle final for its interval?","options":["As soon as it opens","After the interval closes","When its high is reached","When volume is nonzero"],"answer":1,"explanation":"A live candle can still change until its interval has closed."},
            {"id":"m2-q2","question":"What is a common structural description of an uptrend?","options":["Lower highs and lower lows","Equal highs only","Higher highs and higher lows","A fixed price with no swings"],"answer":2,"explanation":"Higher swing highs and higher swing lows commonly describe an uptrend."},
            {"id":"m2-q3","question":"What is the main trade-off of a lower timeframe?","options":["It eliminates noise","It provides more detail but often more noise","It makes a price source universal","It removes transaction costs"],"answer":1,"explanation":"Lower timeframes show detail but expose more short-term noise."},
            {"id":"m2-q4","question":"What should be kept when reviewing a historical candle?","options":["Only its color","Only a screenshot","Its source, timeframe, and timestamp","A prediction of the next candle"],"answer":2,"explanation":"Source and time context are needed to interpret the observation reproducibly."},
        ],
    },
    {
        "id": 3, "title": "Technical analysis foundations", "level": "beginner",
        "description": "Support/resistance, moving averages, momentum indicators, and volatility.",
        "lessons": [
            {"id":"m3-l1","title":"Support, resistance, and trendlines","minutes":9,"content":"Support and resistance are usually zones where price previously reacted, not infinitely precise lines. A level becomes more informative when it is defined from data available at the time, respected by price, and evaluated against volatility and nearby market structure.\n\nDrawing rules should be consistent. If the analysis allows changing a level after seeing the outcome, a backtest can accidentally use future knowledge."},
            {"id":"m3-l2","title":"Moving averages, RSI, and MACD","minutes":10,"content":"SMA averages a fixed number of closes; EMA gives greater weight to recent observations. RSI summarizes recent gains and losses; MACD compares moving averages and is often used to describe momentum changes. Each indicator is a transformation of past prices, so none independently guarantees a future move.\n\nIndicator periods, input price, and warm-up history affect results. Validate calculations against trusted examples and avoid treating multiple highly correlated indicators as independent evidence."},
            {"id":"m3-l3","title":"ATR, Bollinger Bands, and volume","minutes":8,"content":"ATR summarizes recent true range and is commonly used to scale stops or compare volatility. Bollinger Bands place bands around a moving average using a standard-deviation estimate. Volume can help contextualize a breakout, but exchange-specific volume may not represent the entire market.\n\nUse volatility-adjusted thresholds where possible. An indicator value is meaningful only with its units, lookback, source, and timestamp."},
        ],
        "questions": [
            {"id":"m3-q1","question":"What does ATR primarily describe?","options":["Direction with certainty","Recent price range/volatility","The exact fair value","The number of exchange users"],"answer":1,"explanation":"ATR measures recent true range and is used as a volatility estimate."},
            {"id":"m3-q2","question":"How does an EMA differ from an SMA?","options":["EMA weights recent observations more heavily","EMA uses future prices","SMA only works on crypto","SMA guarantees less lag in every case"],"answer":0,"explanation":"EMA assigns exponentially higher weights to more recent observations."},
            {"id":"m3-q3","question":"What is the safest interpretation of an RSI reading?","options":["It guarantees an imminent reversal","It is a momentum summary based on past prices","It measures exchange solvency","It replaces stop-loss planning"],"answer":1,"explanation":"RSI summarizes recent price momentum; it does not guarantee a reversal."},
            {"id":"m3-q4","question":"Why should correlated indicators not be counted as fully independent evidence?","options":["They always have opposite signals","They may repeat similar information from the same price data","They contain no data","They eliminate overfitting"],"answer":1,"explanation":"Several indicators can transform the same underlying prices and give redundant signals."},
        ],
    },
    {
        "id": 4, "title": "Market structure", "level": "intermediate",
        "description": "Swing structure, break of structure, change of character, liquidity, and zones.",
        "lessons": [
            {"id":"m4-l1","title":"Swings and structure rules","minutes":9,"content":"A swing high or low requires a stated detection rule, such as neighboring candles on both sides. A rule using right-side candles cannot confirm that swing until those candles exist. Backtests must delay availability until confirmation; otherwise they introduce look-ahead bias.\n\nBreak of Structure and Change of Character are discretionary terms unless the algorithm defines pivot windows, close-versus-wick rules, and invalidation conditions."},
            {"id":"m4-l2","title":"Liquidity and stop clusters","minutes":8,"content":"Stops and resting orders can cluster around obvious highs, lows, and round numbers, but a chart alone cannot reveal the full order book or the identity of a participant. A liquidity sweep rule should specify the level, required breach, reclaim/close condition, and timeout.\n\nAvoid claiming that a specific candle proves a whale acted. Describe only the observable pattern and the rule used to classify it."},
            {"id":"m4-l3","title":"Supply and demand zones","minutes":8,"content":"Supply and demand zones are areas inferred from previous reactions or fast departures. Define their boundaries mechanically, include age and number of prior touches where relevant, and track when price invalidates them. Wider zones may be less precise but can account for volatility.\n\nA zone is a context feature, not a prediction. Evaluate whether it adds value beyond simpler support/resistance rules in out-of-sample data."},
        ],
        "questions": [
            {"id":"m4-q1","question":"When can a pivot requiring candles to its right be confirmed?","options":["Before the pivot candle opens","Only after the required right-side candles exist","At an arbitrary future date","Only when a trade wins"],"answer":1,"explanation":"The detection rule needs the right-side observations, so confirmation occurs later."},
            {"id":"m4-q2","question":"What makes a liquidity-sweep rule testable?","options":["Calling every wick a whale","A defined level, breach/reclaim condition, and timing rule","A promise of reversal","Using future candle highs"],"answer":1,"explanation":"Explicit observable conditions make the label reproducible and testable."},
            {"id":"m4-q3","question":"What can a chart wick prove about a whale?","options":["Which wallet placed the order","That a whale certainly caused the move","Nothing about participant identity by itself","The exact size of hidden orders"],"answer":2,"explanation":"OHLC prices do not reveal the identity or intent of the participants."},
            {"id":"m4-q4","question":"How should a supply/demand zone be evaluated?","options":["As guaranteed support","With explicit boundaries and out-of-sample testing","By moving it after every result","Without invalidation rules"],"answer":1,"explanation":"Defined zones can be tested; they are not guaranteed price barriers."},
        ],
    },
    {
        "id": 5, "title": "Advanced strategy development", "level": "intermediate",
        "description": "Trend, range, breakout, momentum, and regime-specific strategies.",
        "lessons": [
            {"id":"m5-l1","title":"Write rules before coding","minutes":8,"content":"A strategy specification should state eligible instruments, data source, timeframe, entry condition, invalidation, stop, targets, sizing, fees, and no-trade conditions. Each rule should be observable at the decision time.\n\nSeparating a strategy from data access, risk sizing, and execution makes it easier to compare versions and isolate defects. Store a version identifier with every generated signal and simulated trade."},
            {"id":"m5-l2","title":"Choose strategy by regime","minutes":8,"content":"Trend-following rules seek continuation and often struggle in noisy ranges. Mean-reversion rules seek returns toward a reference and can fail during strong trends. Breakout rules need a precise range definition and rules for false breakouts.\n\nRegime classifiers are imperfect estimates. Test strategy behavior across different conditions rather than assuming a single approach works everywhere."},
            {"id":"m5-l3","title":"Confluence and robustness","minutes":9,"content":"Confluence combines distinct, documented evidence, but adding filters can overfit a finite history. Prefer a small number of justified features, predefine acceptable parameter ranges, and compare against a simple baseline.\n\nUse separate training and evaluation periods. Treat manual changes after seeing test results as new hypotheses requiring a fresh untouched evaluation set."},
        ],
        "questions": [
            {"id":"m5-q1","question":"Which belongs in a complete strategy specification?","options":["Only an entry indicator","Entry, invalidation, sizing, costs, and no-trade rules","A guaranteed win rate","A list of favorite assets only"],"answer":1,"explanation":"A strategy needs explicit entries, exits, sizing, costs, and rejection conditions."},
            {"id":"m5-q2","question":"Why may a mean-reversion strategy struggle in a strong trend?","options":["Price never changes in trends","Price may continue moving away from the reference","It has no parameters","It removes transaction fees"],"answer":1,"explanation":"Persistent directional movement can continue instead of reverting promptly."},
            {"id":"m5-q3","question":"What is a common warning sign of overfitting?","options":["Stable results across untouched periods","Many tuned filters improve historical results but fail out of sample","A versioned strategy","Using a fixed test period"],"answer":1,"explanation":"Excessive tuning can fit historical noise that does not generalize."},
            {"id":"m5-q4","question":"What should happen after a strategy is changed because of test results?","options":["Reuse the same test set as proof","Treat it as a new hypothesis and evaluate on fresh data","Assume profitability increased","Delete previous results"],"answer":1,"explanation":"The test set influenced the change, so fresh untouched data is needed for evaluation."},
        ],
    },
    {
        "id": 6, "title": "Risk and money management", "level": "intermediate",
        "description": "Position sizing, R multiples, partial exits, fees, drawdown, and leverage risk.",
        "lessons": [
            {"id":"m6-l1","title":"Position sizing and risk per trade","minutes":10,"content":"A basic risk-based size starts with account equity multiplied by a chosen risk fraction, then divides that cash risk by the entry-to-stop distance per unit. Fees, slippage, contract multipliers, and exchange quantity rules can change the executable size.\n\nA 1% risk setting is a budget estimate, not a guarantee that loss cannot exceed 1%. Gaps, liquidation, execution failure, or illiquid markets can produce larger losses."},
            {"id":"m6-l2","title":"R multiples and partial exits","minutes":8,"content":"R is the initial risk distance expressed in account-currency terms or per-unit price distance, depending on the stated convention. A target at 2R is twice the initial risk distance from entry. Partial exits change remaining quantity and the realized/unrealized mix.\n\nDo not call a position risk-free after moving a stop unless the execution, fees, and gap assumptions justify it. Record each fill separately to keep the ledger auditable."},
            {"id":"m6-l3","title":"Drawdown, fees, and leverage","minutes":9,"content":"Drawdown measures decline from a previous equity peak. Profit factor compares gross profits to gross losses under a specified convention; expectancy summarizes average outcome per trade. Each metric depends on sample definition and modeled costs.\n\nLeverage increases notional exposure relative to equity and can make liquidation occur before a distant chart stop is filled. Risk limits should account for correlated positions and total exposure, not only each trade in isolation."},
        ],
        "questions": [
            {"id":"m6-q1","question":"In a simple risk-based sizing model, what primarily determines quantity?","options":["Account risk budget divided by per-unit stop distance","The desired win rate","Only the asset name","The number of indicators shown"],"answer":0,"explanation":"Quantity scales with allowed cash risk relative to loss per unit at the stop."},
            {"id":"m6-q2","question":"What does a 2R target mean under a fixed initial-risk convention?","options":["Two percent win rate","Two times the initial entry-to-stop risk distance in the favorable direction","Two open trades","Double the leverage automatically"],"answer":1,"explanation":"R multiples measure target distance relative to the initial risk distance."},
            {"id":"m6-q3","question":"Which statement about a 1% risk setting is correct?","options":["It guarantees a maximum 1% loss in all conditions","It is a planned risk budget and losses may exceed it","It removes slippage","It guarantees positive expectancy"],"answer":1,"explanation":"Gaps, fees, slippage, and execution failure can exceed the planned risk budget."},
            {"id":"m6-q4","question":"How is profit factor commonly calculated?","options":["Winning trade count divided by all trades","Gross profits divided by absolute gross losses","Maximum equity divided by initial balance","Average hold time divided by fees"],"answer":1,"explanation":"Profit factor compares gross profits with absolute gross losses."},
        ],
    },
    {
        "id": 7, "title": "Trading psychology", "level": "intermediate",
        "description": "FOMO, revenge trading, discipline, journaling, and precommitted plans.",
        "lessons": [
            {"id":"m7-l1","title":"Recognize emotional triggers","minutes":7,"content":"FOMO can lead to late entries after a large move; revenge trading can encourage larger or more frequent positions after a loss. These patterns are easier to recognize when decisions and emotions are recorded consistently.\n\nA missed trade is not automatically a mistake. Skipping a setup that violates the written rules is part of disciplined execution."},
            {"id":"m7-l2","title":"Build a trading plan","minutes":8,"content":"A useful plan records instruments, times, setup rules, risk limits, daily stop conditions, and what to do when data is stale or the platform fails. It should be short enough to use before every trade.\n\nThe plan should define circumstances in which the right action is no trade, including ambiguous setups, missing inputs, or breached risk limits."},
            {"id":"m7-l3","title":"Journal decisions, not just outcomes","minutes":8,"content":"A trading journal records the information available at entry, planned exits, size, costs, rule compliance, and post-trade notes. An excellent decision can lose; a poor process can win by luck. Review behavior across many examples rather than judging only one outcome.\n\nUse predefined review intervals and avoid changing rules after every win or loss. Seek support if trading begins to affect sleep, finances, or relationships."},
        ],
        "questions": [
            {"id":"m7-q1","question":"What is a useful response to FOMO?","options":["Increase size immediately","Follow prewritten entry criteria and accept missed trades","Remove stops","Trade every breakout"],"answer":1,"explanation":"Rules-based execution avoids chasing moves that do not meet the plan."},
            {"id":"m7-q2","question":"Why record the information available at entry?","options":["To reconstruct the decision without relying on hindsight","To guarantee a winning trade","To hide losing trades","To replace a risk plan"],"answer":0,"explanation":"An entry-time record helps distinguish decision quality from hindsight."},
            {"id":"m7-q3","question":"A disciplined trade follows all rules but loses. What is the soundest conclusion?","options":["The process is necessarily invalid","The trade outcome alone cannot establish decision quality","The trader should double the next size","The strategy must be changed immediately"],"answer":1,"explanation":"A single outcome is noisy; review the rules and a meaningful sample."},
            {"id":"m7-q4","question":"Which is a legitimate no-trade condition?","options":["A signal lacks required data or violates a risk limit","The trader has a favorite asset","A previous trade won","The chart contains a moving average"],"answer":0,"explanation":"Missing required data or breached risk limits can justify rejecting a trade."},
        ],
    },
    {
        "id": 8, "title": "Advanced chart analysis", "level": "advanced",
        "description": "Fibonacci, VWAP, Ichimoku, volatility, volume, and confluence limits.",
        "lessons": [
            {"id":"m8-l1","title":"Fibonacci and VWAP","minutes":8,"content":"Fibonacci retracement levels are derived from a selected swing. The result depends on how the swing anchors are chosen, so define those anchors before testing. VWAP averages price weighted by volume over a specified session or window.\n\nVWAP can be ambiguous across venues and sessions, especially for 24/7 assets. Always state the data source, reset boundary, and formula."},
            {"id":"m8-l2","title":"Ichimoku and volatility regimes","minutes":9,"content":"Ichimoku combines several rolling midpoint calculations and projected spans to provide trend/context information. Some lines are plotted forward or backward visually; an algorithm must distinguish the value known at decision time from the displayed alignment.\n\nVolatility regime labels should rely on a defined measure and lookback. A high ATR relative to its own history means something different from a high raw ATR across two assets with different price scales."},
            {"id":"m8-l3","title":"Interpret confluence carefully","minutes":8,"content":"A chart may contain many agreeing indicators simply because they reuse the same price history. Confirmation should ideally add distinct evidence and improve out-of-sample results after realistic costs.\n\nAnnotate levels and assumptions; keep false positives and no-trade outcomes in the record. Visual elegance is not evidence of predictive value."},
        ],
        "questions": [
            {"id":"m8-q1","question":"Why must a Fibonacci swing-anchor rule be defined in advance?","options":["To remove transaction costs","To avoid changing anchors with hindsight","To guarantee a bounce","To ensure all retracements are traded"],"answer":1,"explanation":"Flexible hindsight-based anchors make historical tests biased and irreproducible."},
            {"id":"m8-q2","question":"What must be specified for a VWAP calculation?","options":["The user's favorite color","Source data and session/reset window","The next target price","Only the exchange logo"],"answer":1,"explanation":"Volume, price source, and reset boundary determine the VWAP calculation."},
            {"id":"m8-q3","question":"What is a common risk with visual forward-plotted indicators?","options":["They cannot be displayed","A backtest may accidentally use information unavailable at the time","They remove look-ahead bias automatically","They make all data tick-based"],"answer":1,"explanation":"The plotted alignment must not leak future information into earlier decisions."},
            {"id":"m8-q4","question":"When is confluence most useful?","options":["When it is defined and adds out-of-sample value after costs","When it adds as many indicators as possible","When it hides losing cases","When it guarantees direction"],"answer":0,"explanation":"Confluence should be justified by testable incremental value, not by indicator count."},
        ],
    },
    {
        "id": 9, "title": "Backtesting and strategy validation", "level": "advanced",
        "description": "Look-ahead bias, leakage, out-of-sample tests, costs, and uncertainty.",
        "lessons": [
            {"id":"m9-l1","title":"Data integrity and look-ahead bias","minutes":10,"content":"A simulation must only use data available at the simulated decision time. Using a future-confirmed swing, final candle value, or revised fundamental value too early produces look-ahead bias. Leakage can also happen when training and test windows overlap improperly.\n\nValidate timestamps, duplicate candles, gaps, symbol changes, and source consistency. Preserve a data-source label and record any cleaning or exclusions."},
            {"id":"m9-l2","title":"Out-of-sample and walk-forward tests","minutes":9,"content":"A holdout period should remain untouched while strategy choices are made. Walk-forward evaluation repeats chronological training and testing windows so that performance is observed on later data. It does not guarantee future success, but it can expose instability.\n\nIf the strategy is changed after reviewing a test fold, that fold is no longer a fully independent test of the revised strategy."},
            {"id":"m9-l3","title":"Costs, sample size, and metrics","minutes":9,"content":"Include fees, spread, slippage, funding if relevant, and execution ambiguity. With OHLC bars, a candle may touch both stop and target; if order is unknown, use tick data or a conservative rule such as stop-first.\n\nWin rate alone is insufficient. Report sample size, net expectancy, profit factor, drawdown, distribution, and uncertainty. A profitable backtest can still be due to chance or a regime that will not recur."},
        ],
        "questions": [
            {"id":"m9-q1","question":"What is look-ahead bias?","options":["Using only past information","Using information that was not yet available at the simulated decision time","Using a training window","Recording a losing trade"],"answer":1,"explanation":"Look-ahead bias occurs when future information influences a past decision."},
            {"id":"m9-q2","question":"Why is a walk-forward test chronological?","options":["Markets only move forward in price","It evaluates rules on data that follows the corresponding training window","It guarantees profitability","It removes every source of uncertainty"],"answer":1,"explanation":"Chronological separation tests the strategy on later observations."},
            {"id":"m9-q3","question":"A candle reaches both a stop and target, but tick order is unknown. What is a defensible rule?","options":["Always assume target first","Delete the trade","Use tick data or a documented conservative stop-first rule","Assume both are filled at the best price"],"answer":2,"explanation":"Unknown intrabar order must be handled explicitly; a conservative rule avoids favorable assumptions."},
            {"id":"m9-q4","question":"Why should backtest reports include sample size?","options":["To prove future profit","To help judge how much evidence supports the observed metrics","To replace cost modeling","To hide uncertainty"],"answer":1,"explanation":"The number of trades affects how much confidence can be placed in observed statistics."},
        ],
    },
    {
        "id": 10, "title": "Practical simulated trading", "level": "intermediate",
        "description": "Apply a written plan, simulate execution, and audit performance.",
        "lessons": [
            {"id":"m10-l1","title":"Configure a demo account","minutes":7,"content":"Set a starting virtual balance, permitted symbols, timeframe, risk fraction, and cost assumptions before trading. A virtual ledger must distinguish free balance, reserved exposure, realized P&L, unrealized P&L, and fees.\n\nResetting a demo should require confirmation and must not be confused with a real brokerage account. Keep the original starting balance and event records where auditability is required."},
            {"id":"m10-l2","title":"Review signal and execution lifecycle","minutes":8,"content":"A signal should have a timestamp, source, strategy version, direction, entry model, invalidation rule, stop, and targets. The demo engine should prevent duplicate execution for the same signal and account.\n\nOHLC simulation is an approximation. Live price polling may miss intrabar excursions, and actual execution can differ because of latency and liquidity."},
            {"id":"m10-l3","title":"Learn from the trade log","minutes":8,"content":"Review planned versus actual simulated fills, partial exits, costs, invalidation, and final net P&L. Compare trades by symbol, strategy, timeframe, and market regime with adequate sample sizes.\n\nTreat demo results as a test of the stated simulation model, not as a promise about real-money performance."},
        ],
        "questions": [
            {"id":"m10-q1","question":"Why should a demo ledger track fees separately?","options":["Fees never affect P&L","To calculate net performance and make assumptions auditable","To guarantee a win","To hide execution costs"],"answer":1,"explanation":"Fees are part of net results and should be transparent in the ledger."},
            {"id":"m10-q2","question":"What prevents duplicate simulated execution?","options":["Random delays only","An idempotency key/unique record for the signal and account","A different chart color","Ignoring signal timestamps"],"answer":1,"explanation":"A unique signal key prevents the same event from opening duplicate trades."},
            {"id":"m10-q3","question":"What do demo results directly measure?","options":["Guaranteed real-world profit","Performance under the configured simulation assumptions","The next market price","The exchange's solvency"],"answer":1,"explanation":"Simulated results are conditional on the execution and cost model."},
            {"id":"m10-q4","question":"Which is useful in a trade review?","options":["Delete the loss","Compare planned and simulated execution with fees and rule compliance","Keep only the best month","Change the rule before every entry"],"answer":1,"explanation":"A review should compare actual simulation events with the plan and its cost model."},
        ],
    },
    {
        "id": 11, "title": "Portfolio and operational risk", "level": "advanced",
        "description": "Correlation, exposure, key permissions, account security, and operational controls.",
        "lessons": [
            {"id":"m11-l1","title":"Correlation and exposure","minutes":8,"content":"Several positions can express nearly the same risk even when their symbols differ. Total portfolio risk depends on correlations, leverage, concentration, liquidity, and shared market drivers.\n\nCalculate exposure and scenario losses across the portfolio instead of assuming that several small positions are automatically diversified."},
            {"id":"m11-l2","title":"API permissions and secrets","minutes":9,"content":"An exchange API key can grant different capabilities such as read/account data, trading, and withdrawals. Use the narrowest permissions needed, disable trading and withdrawals for a read-only connection, and restrict IP addresses where supported.\n\nNever place API secrets in source code, mobile preferences, logs, crash reports, or analytics. A backend should encrypt credentials at rest, use HTTPS, limit access, and allow revocation/deletion."},
            {"id":"m11-l3","title":"Threats and incident response","minutes":8,"content":"Phishing, malicious apps, compromised devices, exposed API keys, and account takeover can cause financial harm. Use unique passwords, multi-factor authentication, key restrictions, and regular permission review.\n\nIf a key is exposed, revoke it at the exchange immediately, inspect account activity, and rotate related credentials. Audit logs should not contain secrets or private account data unnecessarily."},
        ],
        "questions": [
            {"id":"m11-q1","question":"What permission profile is appropriate for a read-only exchange integration?","options":["Withdrawal enabled","Trading and withdrawal enabled","Only necessary account-read permission, with trade/withdraw disabled","Administrator access for all endpoints"],"answer":2,"explanation":"Least privilege means enabling only the account-data access the integration needs."},
            {"id":"m11-q2","question":"Where should an exchange secret be stored?","options":["In Flutter source code","In a mobile shared-preferences file","Encrypted on the backend with access controls and managed keys","In analytics logs"],"answer":2,"explanation":"Sensitive credentials should be encrypted and restricted on the server, not embedded in the app."},
            {"id":"m11-q3","question":"Why can multiple different crypto positions still be concentrated risk?","options":["Symbols never correlate","They can share market drivers and move together","Diversification is automatic by symbol count","Risk depends only on the ticker text"],"answer":1,"explanation":"Correlation and shared market factors can make different assets behave similarly."},
            {"id":"m11-q4","question":"What is the first response to a leaked exchange API key?","options":["Wait for a trade","Revoke the key and inspect account activity","Publish it for review","Store it in the app securely"],"answer":1,"explanation":"Revoke a compromised key promptly and review the account for unauthorized activity."},
        ],
    },
    {
        "id": 12, "title": "Capstone assessment", "level": "advanced",
        "description": "Combine regime, levels, entry/no-trade reasoning, risk sizing, targets, and documentation.",
        "lessons": [
            {"id":"m12-l1","title":"Build a complete trade thesis","minutes":10,"content":"A useful thesis records the data source and time, market regime, relevant structure, evidence for and against the setup, and the condition that invalidates the idea. Select LONG, SHORT, or NO TRADE based on the written rules.\n\nThe absence of a valid setup is a legitimate analytical result. Do not invent an entry merely to complete a worksheet or satisfy a signal count."},
            {"id":"m12-l2","title":"Calculate the risk and targets","minutes":9,"content":"Choose a stop based on the setup's invalidation and account for volatility. Calculate position size from the risk budget and stop distance, then compute target distances relative to initial risk. Include costs and exchange quantity constraints.\n\nCheck that target order matches the direction, stop is on the correct side of entry, and no target is non-positive or otherwise invalid for the instrument."},
            {"id":"m12-l3","title":"Submit a reproducible review","minutes":8,"content":"A capstone report should include chart context, rules applied, calculations, uncertainty, and a conclusion. Another learner should be able to reproduce the decision from the supplied observations and rules.\n\nPassing the course certifies completion of this learning and assessment process only. It is not government accreditation, professional licensing, or a guarantee of trading expertise."},
        ],
        "questions": [
            {"id":"m12-q1","question":"When is NO TRADE the correct analytical output?","options":["Never; every analysis needs an entry","When no setup meets documented rules or required data is missing","Only after a loss","Whenever price is green"],"answer":1,"explanation":"NO TRADE is appropriate when the rules or required inputs do not support a valid setup."},
            {"id":"m12-q2","question":"What makes a capstone analysis reproducible?","options":["Hidden decision rules","Chart context, inputs, explicit rules, and calculations","Only a final score","A guaranteed prediction"],"answer":1,"explanation":"A reader needs the evidence and rules used to reach the decision."},
            {"id":"m12-q3","question":"What does a NEXTRADE course certificate establish?","options":["Government trading license","Guaranteed trading profits","Course completion and assessment result only","Authorization to manage client funds"],"answer":2,"explanation":"The certificate is platform-issued evidence of course completion, not professional licensing."},
            {"id":"m12-q4","question":"Before accepting a calculated setup, what must be checked?","options":["Only the chart color","Directionally correct stop/target ordering and valid size/cost assumptions","Whether the target number is attractive","Whether every indicator agrees"],"answer":1,"explanation":"Ordering and sizing checks help catch invalid or inconsistent trade levels."},
        ],
    },
]

COURSE_TITLE = "NEXTRADE Trading Foundations and Risk-Aware Analysis"
MODULE_PASS_PERCENT = 75
FINAL_PASS_PERCENT = 80

def module_required_tier(module_id: int) -> str:
    """Access policy: introductory modules are free, intermediate modules are Pro, capstone is Premium."""
    if module_id <= 3:
        return "free"
    if module_id <= 8:
        return "pro"
    return "premium"


def public_module(module: dict, include_content: bool = True) -> dict:
    return {
        "id": module["id"], "title": module["title"], "level": module["level"],
        "description": module["description"],
        "lessons": [
            {key: lesson[key] for key in (("id", "title", "minutes", "content") if include_content else ("id", "title", "minutes"))}
            for lesson in module["lessons"]
        ],
        "question_count": len(module["questions"]),
        "pass_percent": MODULE_PASS_PERCENT,
    }

def public_question(question: dict) -> dict:
    return {"id": question["id"], "question": question["question"],
            "options": [{"value": i, "label": option} for i, option in enumerate(question["options"])]}

def grade(questions: list[dict], answers: dict[str, int]) -> dict:
    correct = 0
    review = []
    for question in questions:
        selected = answers.get(question["id"])
        is_correct = selected == question["answer"]
        correct += int(is_correct)
        review.append({"question_id": question["id"], "selected": selected,
                       "correct_answer": question["answer"], "correct": is_correct,
                       "explanation": question["explanation"]})
    total = len(questions)
    percent = round((correct / total) * 100, 2) if total else 0.0
    return {"correct_count": correct, "total": total, "percent": percent, "review": review}
