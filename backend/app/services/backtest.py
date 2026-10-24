from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.strategy.engine import analyze_candles


def _closed(candles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [c for c in candles if c.get("closed", True) and all(k in c for k in ("open", "high", "low", "close"))]


def _trade_metrics(trades: list[dict[str, Any]], initial_capital: float, equity_curve: list[float], total_fees: float) -> dict[str, Any]:
    net_values = [float(t["net_pnl"]) for t in trades]
    wins = [v for v in net_values if v > 0]
    losses = [v for v in net_values if v < 0]
    net_profit_from_winners = sum(wins)
    net_loss_from_losers = abs(sum(losses))
    gross_values = [float(t.get("gross_pnl") or 0.0) for t in trades]
    gross_profit = sum(v for v in gross_values if v > 0)
    gross_loss_abs = abs(sum(v for v in gross_values if v < 0))
    peak = initial_capital
    max_dd_abs = 0.0
    max_dd_pct = 0.0
    for equity in equity_curve:
        peak = max(peak, equity)
        drawdown = peak - equity
        max_dd_abs = max(max_dd_abs, drawdown)
        if peak > 0:
            max_dd_pct = max(max_dd_pct, drawdown / peak * 100)
    final_equity = equity_curve[-1] if equity_curve else initial_capital
    return {
        "trade_count": len(trades),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate_percent": round(len(wins) / len(trades) * 100, 4) if trades else None,
        "initial_capital": round(initial_capital, 8),
        "final_equity": round(final_equity, 8),
        "net_pnl": round(final_equity - initial_capital, 8),
        "net_return_percent": round((final_equity / initial_capital - 1) * 100, 6) if initial_capital else 0,
        "gross_profit_before_costs": round(gross_profit, 8),
        "gross_loss_before_costs": round(gross_loss_abs, 8),
        "profit_factor": round(net_profit_from_winners / net_loss_from_losers, 6) if net_loss_from_losers > 0 else (None if net_profit_from_winners == 0 else "unbounded_no_losses"),
        "profit_factor_method": "Net winning-trade PnL divided by absolute net losing-trade PnL, after modeled fees and adverse fills.",
        "expectancy_per_trade": round(sum(net_values) / len(net_values), 8) if net_values else None,
        "total_fees_and_slippage": round(total_fees, 8),
        "max_drawdown": round(max_dd_abs, 8),
        "max_drawdown_percent": round(max_dd_pct, 6),
        "sample_size": len(trades),
    }


def simulate_backtest(
    candles: list[dict[str, Any]], *, symbol: str, interval: str, initial_capital: float = 10_000.0,
    risk_percent: float = 1.0, fee_bps: float = 10.0, slippage_bps: float = 2.0,
    signal_start: int = 80, signal_end: int | None = None,
) -> dict[str, Any]:
    """Deterministic single-position OHLC backtest with next-open entries and conservative intrabar exits.

    At every decision point, the strategy only sees candles up to that point. Entries happen at
    the next bar's open, adjusted for modeled slippage. If SL and any TP are touched in one OHLC
    bar, the stop is applied first. No real orders are sent.
    """
    bars = _closed(candles)
    n = len(bars)
    upper = min(n - 1, signal_end if signal_end is not None else n - 1)
    start = max(60, signal_start)
    if n < 100 or upper <= start:
        return {
            "status": "insufficient_data", "symbol": symbol, "interval": interval, "candles_used": n,
            "message": "At least 100 closed candles and a non-empty evaluation window are required.",
            **_trade_metrics([], initial_capital, [initial_capital], 0.0), "trades": [],
        }

    equity = float(initial_capital)
    equity_curve = [equity]
    total_costs = 0.0
    trades: list[dict[str, Any]] = []
    active: dict[str, Any] | None = None
    fee_rate = fee_bps / 10_000
    slip_rate = slippage_bps / 10_000

    def record_trade(position: dict[str, Any], exit_time: Any, exit_reason: str) -> None:
        nonlocal trades
        net = float(position["net_pnl"])
        trades.append({
            "symbol": symbol, "interval": interval, "direction": position["direction"],
            "signal_time": position["signal_time"], "entry_time": position["entry_time"],
            "exit_time": exit_time, "entry": round(position["entry"], 10),
            "stop_loss": round(position["stop_loss"], 10), "tp1": round(position["targets"][0], 10),
            "tp2": round(position["targets"][1], 10), "tp3": round(position["targets"][2], 10),
            "exit_reason": exit_reason, "net_pnl": round(net, 8), "gross_pnl": round(position["gross_pnl"], 8),
            "fees": round(position["fees"], 8), "slippage_drag": round(position["slippage_cost"], 8),
            "fees_and_slippage": round(position["costs"], 8), "initial_quantity": round(position["initial_qty"], 12),
            "score": position["score"],
        })

    # This starts at the requested out-of-sample signal boundary; prior bars are only context.
    for i in range(start, upper):
        bar = bars[i]
        if active is not None:
            direction = active["direction"]
            stop = active["stop_loss"]
            targets = active["targets"]
            stop_touched = float(bar["low"]) <= stop if direction == "LONG" else float(bar["high"]) >= stop
            remaining = active["remaining_qty"]
            targets_touched = [float(bar["high"]) >= target if direction == "LONG" else float(bar["low"]) <= target for target in targets]
            if stop_touched:
                # OHLC cannot reveal price sequence: conservatively apply SL before any TP.
                exit_price = stop * (1 - slip_rate if direction == "LONG" else 1 + slip_rate)
                gross = (exit_price - active["entry"]) * (1 if direction == "LONG" else -1) * remaining
                exit_cost = exit_price * remaining * fee_rate
                slippage_drag = abs(exit_price - stop) * remaining
                active["gross_pnl"] += gross
                active["net_pnl"] += gross - exit_cost
                active["fees"] += exit_cost
                active["slippage_cost"] += slippage_drag
                active["costs"] += exit_cost + slippage_drag
                equity += gross - exit_cost
                total_costs += exit_cost + slippage_drag
                equity_curve.append(equity)
                record_trade(active, bar.get("close_time", bar.get("open_time")), "stop_loss")
                active = None
                continue

            allocations = [0.4, 0.3, 0.3]
            for target_index, target_hit in enumerate(targets_touched):
                if target_hit and not active["target_hits"][target_index] and active["remaining_qty"] > 0:
                    qty = min(active["remaining_qty"], active["initial_qty"] * allocations[target_index])
                    exit_price = targets[target_index] * (1 - slip_rate if direction == "LONG" else 1 + slip_rate)
                    gross = (exit_price - active["entry"]) * (1 if direction == "LONG" else -1) * qty
                    exit_cost = exit_price * qty * fee_rate
                    slippage_drag = abs(exit_price - targets[target_index]) * qty
                    active["gross_pnl"] += gross
                    active["net_pnl"] += gross - exit_cost
                    active["fees"] += exit_cost
                    active["slippage_cost"] += slippage_drag
                    active["costs"] += exit_cost + slippage_drag
                    active["remaining_qty"] = max(0.0, active["remaining_qty"] - qty)
                    active["target_hits"][target_index] = True
                    equity += gross - exit_cost
                    total_costs += exit_cost + slippage_drag
                    equity_curve.append(equity)
            if active["remaining_qty"] <= max(1e-12, active["initial_qty"] * 1e-10):
                record_trade(active, bar.get("close_time", bar.get("open_time")), "tp3")
                active = None
            continue

        # Signal is calculated using candles through i. Entry is at the next bar's open.
        assessment = analyze_candles(symbol, interval, bars[: i + 1])
        direction = assessment.get("direction")
        levels = assessment.get("levels")
        if direction not in {"LONG", "SHORT"} or not isinstance(levels, dict) or i + 1 >= n:
            continue
        next_bar = bars[i + 1]
        raw_entry = float(next_bar["open"])
        entry = raw_entry * (1 + slip_rate if direction == "LONG" else 1 - slip_rate)
        stop = float(levels["stop_loss"])
        # Reject gaps where entry is on the wrong side of the stop; do not invent a better fill.
        risk_distance = entry - stop if direction == "LONG" else stop - entry
        if risk_distance <= 0 or entry <= 0:
            continue
        targets = [entry + risk_distance * r for r in (1, 2, 3)] if direction == "LONG" else [entry - risk_distance * r for r in (1, 2, 3)]
        if targets[-1] <= 0:
            continue
        risk_amount = max(0.0, equity) * risk_percent / 100
        qty = min(risk_amount / risk_distance, max(0.0, equity) * 0.95 / entry)
        if qty <= 0:
            continue
        entry_cost = entry * qty * fee_rate
        entry_slippage_drag = abs(entry - raw_entry) * qty
        equity -= entry_cost
        total_costs += entry_cost + entry_slippage_drag
        equity_curve.append(equity)
        active = {
            "direction": direction, "entry": entry, "stop_loss": stop, "targets": targets,
            "initial_qty": qty, "remaining_qty": qty, "target_hits": [False, False, False],
            "signal_time": bar.get("close_time", bar.get("open_time")),
            "entry_time": next_bar.get("open_time"), "score": assessment.get("score"),
            "gross_pnl": 0.0, "net_pnl": -entry_cost, "costs": entry_cost + entry_slippage_drag,
            "fees": entry_cost, "slippage_cost": entry_slippage_drag,
        }

    # End-of-test liquidation makes open trades comparable across folds.
    if active is not None:
        last = bars[min(upper, n - 1)]
        direction = active["direction"]
        exit_price = float(last["close"]) * (1 - slip_rate if direction == "LONG" else 1 + slip_rate)
        qty = active["remaining_qty"]
        gross = (exit_price - active["entry"]) * (1 if direction == "LONG" else -1) * qty
        exit_cost = exit_price * qty * fee_rate
        slippage_drag = abs(exit_price - float(last["close"])) * qty
        active["gross_pnl"] += gross
        active["net_pnl"] += gross - exit_cost
        active["fees"] += exit_cost
        active["slippage_cost"] += slippage_drag
        active["costs"] += exit_cost + slippage_drag
        equity += gross - exit_cost
        total_costs += exit_cost + slippage_drag
        equity_curve.append(equity)
        record_trade(active, last.get("close_time", last.get("open_time")), "end_of_test")

    metrics = _trade_metrics(trades, initial_capital, equity_curve, total_costs)
    return {
        "status": "completed", "symbol": symbol, "interval": interval, "strategy_status": "experimental_unvalidated",
        "candles_used": n, "evaluation_start_index": start, "evaluation_end_index": upper,
        "execution_assumptions": {
            "entry": "next candle open after signal candle, with adverse slippage",
            "intrabar_priority": "stop-loss first whenever stop and any target touch in the same OHLC candle",
            "partial_exits": {"tp1": 0.4, "tp2": 0.3, "tp3": 0.3},
            "sizing": "risk-based sizing capped at 95% of equity notional; no leverage modeled",
            "short_positions": "hypothetical paper positions; not spot exchange order availability",
            "costs": "fees are deducted; adverse slippage is reflected in fill prices and also reported as an estimated drag without subtracting it twice",
            "lookahead": "signals use only candles through the decision candle; fills begin on the next candle",
        },
        **metrics, "trades": trades[-500:],
        "limitations": ["Experimental fixed rules; no profitability claim.", "OHLC data cannot establish the exact order of intrabar price movements.", "Funding, spread, liquidity, and exchange-specific lot constraints are not modeled."],
    }


def simulate_walk_forward(candles: list[dict[str, Any]], *, symbol: str, interval: str,
                          initial_capital: float = 10_000.0, risk_percent: float = 1.0,
                          fee_bps: float = 10.0, slippage_bps: float = 2.0,
                          folds: int = 4, train_fraction: float = 0.55) -> dict[str, Any]:
    bars = _closed(candles)
    n = len(bars)
    if n < 300:
        return {"status": "insufficient_data", "symbol": symbol, "interval": interval, "candles_used": n,
                "message": "Walk-forward needs at least 300 closed candles."}
    folds = max(2, min(int(folds), 6))
    train_end = max(150, min(n - folds * 30, int(n * train_fraction)))
    test_span = (n - train_end) // folds
    if test_span < 30:
        return {"status": "insufficient_data", "message": "Not enough candles for the chosen fold count.", "candles_used": n}

    results = []
    all_trades: list[dict[str, Any]] = []
    total_costs = 0.0
    for fold_index in range(folds):
        test_start = train_end + fold_index * test_span
        test_end = n if fold_index == folds - 1 else min(n, test_start + test_span)
        fold_bars = bars[:test_end]
        metrics = simulate_backtest(
            fold_bars, symbol=symbol, interval=interval, initial_capital=initial_capital,
            risk_percent=risk_percent, fee_bps=fee_bps, slippage_bps=slippage_bps,
            signal_start=test_start, signal_end=test_end - 1,
        )
        results.append({
            "fold": fold_index + 1, "train_context_candles": test_start, "test_start_index": test_start,
            "test_end_index": test_end - 1, "test_candles": test_end - test_start,
            "metrics": {k: metrics.get(k) for k in ("trade_count", "win_rate_percent", "net_pnl", "net_return_percent", "profit_factor", "expectancy_per_trade", "max_drawdown_percent", "total_fees_and_slippage")},
            "trades": metrics.get("trades", []),
        })
        all_trades.extend(metrics.get("trades", []))
        total_costs += float(metrics.get("total_fees_and_slippage") or 0)

    net_pnl = sum(float(t.get("net_pnl") or 0) for t in all_trades)
    wins = sum(float(t.get("net_pnl") or 0) > 0 for t in all_trades)
    losses = sum(float(t.get("net_pnl") or 0) < 0 for t in all_trades)
    gross_profit = sum(float(t.get("net_pnl") or 0) for t in all_trades if float(t.get("net_pnl") or 0) > 0)
    gross_loss_abs = abs(sum(float(t.get("net_pnl") or 0) for t in all_trades if float(t.get("net_pnl") or 0) < 0))
    return {
        "status": "completed", "symbol": symbol, "interval": interval, "candles_used": n,
        "method": "Anchored expanding-context walk-forward; fixed strategy rules are tested on later, unseen candle segments. No parameter optimization is performed.",
        "fold_count": len(results), "train_fraction": train_fraction,
        "aggregate_out_of_sample": {
            "trade_count": len(all_trades), "wins": wins, "losses": losses,
            "win_rate_percent": round(wins / len(all_trades) * 100, 4) if all_trades else None,
            "net_pnl_sum_across_folds": round(net_pnl, 8),
            "net_return_percent_sum_of_independent_folds": round(net_pnl / initial_capital * 100, 6) if initial_capital else 0,
            "profit_factor": round(gross_profit / gross_loss_abs, 6) if gross_loss_abs > 0 else (None if gross_profit == 0 else "unbounded_no_losses"),
            "total_fees_and_slippage": round(total_costs, 8),
        },
        "folds": results,
        "limitations": ["Every fold starts from the same initial capital; aggregate PnL is a sum of independent fold runs, not a continuous compounded portfolio.",
                        "The strategy is not fitted on training data; this evaluates temporal stability only.",
                        "Backtest results do not establish future profitability."],
    }
