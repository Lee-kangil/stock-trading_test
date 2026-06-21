# -*- coding: utf-8 -*-
"""
engine.py
전략 함수(entry/exit 컬럼)를 받아 동작하는 '범용' 백테스트/페이퍼 엔진.
- backtest_portfolio_generic : 과거 백테스트 (비용 반영, 레짐 필터 옵션)
- step_latest                : 최신 거래일 1개 처리 (페이퍼용, 레짐 옵션)

레짐 필터: regime(또는 regime_ok)가 '하락장(False)'인 날은 신규 매수를 막는다(현금).
청산 우선순위: 손절 → 청산신호(exit) → 보유기간(max_hold_days).
"""
import pandas as pd
from backtest import CostModel, performance_metrics
from strategies import Strategy


def _signals(price_data, strat):
    return {t: strat.signal_fn(df) for t, df in price_data.items()}


def _holdings_value(positions, sig, date):
    v = 0.0
    for t, pos in positions.items():
        if date in sig[t].index and not pd.isna(sig[t].loc[date, "Close"]):
            v += pos["shares"] * float(sig[t].loc[date, "Close"])
        else:
            v += pos["shares"] * pos["entry_price"]
    return v


def _exit_reason(stop_hit, exit_sig, time_exit):
    if stop_hit:
        return "손절"
    if exit_sig:
        return "청산"
    return "기간"


def backtest_portfolio_generic(price_data, strat: Strategy, cost: CostModel = CostModel(),
                               capital=100_000_000, weight=0.10, max_positions=10,
                               regime=None):
    """regime: 날짜별 bool Series(True=매수허용). None이면 필터 미적용."""
    sig = _signals(price_data, strat)
    all_dates = sorted(set().union(*[s.index for s in sig.values()]))
    mh = strat.max_hold_days

    regime_ok = None
    if regime is not None:
        regime_ok = regime.reindex(all_dates).ffill().eq(True)

    cash = capital
    positions = {}
    trades = []
    equity_curve = []

    for date in all_dates:
        # 청산
        for t in list(positions.keys()):
            if date not in sig[t].index:
                continue
            row = sig[t].loc[date]
            if pd.isna(row["Close"]):
                continue
            close = float(row["Close"])
            pos = positions[t]
            pos["days_held"] += 1
            stop_hit = close <= pos["entry_price"] * (1 - strat.stop_pct)
            exit_sig = bool(row["exit"])
            time_exit = mh is not None and pos["days_held"] >= mh
            if stop_hit or exit_sig or time_exit:
                fill = cost.sell_fill(close)
                proceeds = pos["shares"] * fill * (1 - cost.sell_fee - cost.tax)
                buy_cost = pos["shares"] * cost.buy_fill(pos["entry_price"]) * (1 + cost.buy_fee)
                cash += proceeds
                trades.append({"ticker": t, "entry_date": pos["entry_date"], "exit_date": str(date.date()),
                               "net_return_%": round((proceeds / buy_cost - 1) * 100, 2),
                               "reason": _exit_reason(stop_hit, exit_sig, time_exit)})
                del positions[t]

        total = cash + _holdings_value(positions, sig, date)

        # 진입 (레짐이 하락장이면 신규 매수 차단)
        allow = True if regime_ok is None else bool(regime_ok.loc[date])
        if allow:
            cands = []
            for t in sig:
                if t in positions or date not in sig[t].index:
                    continue
                row = sig[t].loc[date]
                if pd.isna(row["Close"]):
                    continue
                if bool(row["entry"]):
                    cands.append(t)
            for t in cands:
                if len(positions) >= max_positions:
                    break
                close = float(sig[t].loc[date, "Close"])
                alloc = min(weight * total, cash)
                fill = cost.buy_fill(close)
                shares = int(alloc // (fill * (1 + cost.buy_fee)))
                if shares <= 0:
                    continue
                cash -= shares * fill * (1 + cost.buy_fee)
                positions[t] = {"shares": shares, "entry_price": close,
                                "entry_date": str(date.date()), "days_held": 0}

        equity_curve.append((date, cash + _holdings_value(positions, sig, date)))

    equity = pd.Series(dict(equity_curve)).sort_index()
    tdf = pd.DataFrame(trades)
    return {"equity": equity, "trades": tdf, "metrics": performance_metrics(equity, tdf)}


def step_latest(price_data, strat: Strategy, state: dict, cost: CostModel = CostModel(),
                weight=0.10, max_positions=10, regime_ok=True):
    """regime_ok=False면 신규 매수 차단(청산만)."""
    sig = _signals(price_data, strat)
    latest = max(df.index.max() for df in sig.values())
    mh = strat.max_hold_days
    cash = state["cash"]
    positions = {k: dict(v) for k, v in state["positions"].items()}
    actions = []

    for t in list(positions.keys()):
        if t not in sig or latest not in sig[t].index:
            continue
        row = sig[t].loc[latest]
        if pd.isna(row["Close"]):
            continue
        close = float(row["Close"])
        pos = positions[t]
        pos["days_held"] = pos.get("days_held", 0) + 1
        stop_hit = close <= pos["entry_price"] * (1 - strat.stop_pct)
        exit_sig = bool(row["exit"])
        time_exit = mh is not None and pos["days_held"] >= mh
        if stop_hit or exit_sig or time_exit:
            actions.append({"action": "SELL", "ticker": t, "shares": pos["shares"],
                            "price": round(close, 1), "reason": _exit_reason(stop_hit, exit_sig, time_exit)})
            fill = cost.sell_fill(close)
            cash += pos["shares"] * fill * (1 - cost.sell_fee - cost.tax)
            del positions[t]

    total = cash + _holdings_value(positions, sig, latest)

    if regime_ok:
        cands = [t for t in sig if t not in positions and latest in sig[t].index
                 and not pd.isna(sig[t].loc[latest, "Close"]) and bool(sig[t].loc[latest, "entry"])]
        for t in cands:
            if len(positions) >= max_positions:
                break
            close = float(sig[t].loc[latest, "Close"])
            alloc = min(weight * total, cash)
            fill = cost.buy_fill(close)
            shares = int(alloc // (fill * (1 + cost.buy_fee)))
            if shares <= 0:
                continue
            cash -= shares * fill * (1 + cost.buy_fee)
            positions[t] = {"shares": shares, "entry_price": close,
                            "entry_date": str(latest.date()), "days_held": 0}
            actions.append({"action": "BUY", "ticker": t, "shares": shares,
                            "price": round(close, 1), "reason": "진입"})

    equity = cash + _holdings_value(positions, sig, latest)
    state["cash"] = cash
    state["positions"] = positions
    state["last_date"] = str(latest.date())
    state.setdefault("equity_history", []).append([str(latest.date()), round(equity, 0)])
    return actions, state, equity, latest
