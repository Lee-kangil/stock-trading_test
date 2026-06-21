# -*- coding: utf-8 -*-
"""
backtest.py
3주차 산출물: '비용을 반영한' 다종목 포트폴리오 백테스트 엔진 + 성과지표.

비용 모델 (2026년 기준):
  - 매수 수수료: 0.015% (증권사별 상이, 조정 가능)
  - 매도 수수료: 0.015%
  - 증권거래세 : 0.20% (매도 시, 코스피/코스닥 2026년 적용)
  - 슬리피지   : 0.10% (체결 미끄러짐, 매수/매도 각각)

단순화 가정: 신호 발생일 '종가'에 체결(슬리피지 가산). 실거래는 익일 시가 등으로
            보정 필요 — 4주차 이후 정밀화.
"""
from dataclasses import dataclass
import numpy as np
import pandas as pd
from strategy import BreakoutParams, generate_signals


# ===================== 비용 모델 =====================
@dataclass
class CostModel:
    buy_fee: float = 0.00015     # 매수 수수료 0.015%
    sell_fee: float = 0.00015    # 매도 수수료 0.015%
    tax: float = 0.0020          # 거래세 0.20% (매도 시)
    slippage: float = 0.0010     # 슬리피지 0.10% (편도)

    def buy_fill(self, price: float) -> float:
        return price * (1 + self.slippage)

    def sell_fill(self, price: float) -> float:
        return price * (1 - self.slippage)


# ===================== 성과지표 =====================
def performance_metrics(equity: pd.Series, trades: pd.DataFrame) -> dict:
    """자산곡선(equity)과 매매내역(trades)에서 핵심 지표 산출."""
    eq = equity.dropna()
    if len(eq) < 2:
        return {"error": "데이터 부족"}

    total_return = eq.iloc[-1] / eq.iloc[0] - 1
    years = len(eq) / 252
    cagr = (eq.iloc[-1] / eq.iloc[0]) ** (1 / years) - 1 if years > 0 else np.nan

    # 최대낙폭(MDD)
    roll_max = eq.cummax()
    drawdown = eq / roll_max - 1
    mdd = drawdown.min()

    # 샤프지수(무위험수익률 0 가정, 일간→연환산)
    daily_ret = eq.pct_change().dropna()
    sharpe = (daily_ret.mean() / daily_ret.std() * np.sqrt(252)) if daily_ret.std() > 0 else np.nan

    m = {
        "total_return_%": round(total_return * 100, 2),
        "CAGR_%": round(cagr * 100, 2),
        "MDD_%": round(mdd * 100, 2),
        "Sharpe": round(sharpe, 2),
        "n_trades": int(len(trades)),
    }
    if len(trades):
        wins = trades[trades["net_return_%"] > 0]["net_return_%"]
        losses = trades[trades["net_return_%"] <= 0]["net_return_%"]
        gross_win = wins.sum()
        gross_loss = abs(losses.sum())
        m.update({
            "win_rate_%": round(len(wins) / len(trades) * 100, 1),
            "avg_win_%": round(wins.mean(), 2) if len(wins) else 0.0,
            "avg_loss_%": round(losses.mean(), 2) if len(losses) else 0.0,
            "profit_factor": round(gross_win / gross_loss, 2) if gross_loss > 0 else np.inf,
        })
    return m


# ===================== 포트폴리오 백테스트 =====================
def backtest_portfolio(
    price_data: dict,
    params: BreakoutParams = BreakoutParams(),
    cost: CostModel = CostModel(),
    capital: float = 100_000_000,   # 초기 자본 1억
    weight: float = 0.10,           # 1종목당 비중 10%
    max_positions: int = 10,        # 최대 동시 보유 종목 수
) -> dict:
    """
    price_data: { '종목코드': DataFrame(High/Low/Close) , ... }
    반환: { 'equity': Series, 'trades': DataFrame, 'metrics': dict }
    """
    # 1) 종목별 신호 미리 계산
    sig = {t: generate_signals(df, params) for t, df in price_data.items()}

    # 2) 전체 거래일(달력) 만들기 — 모든 종목 날짜의 합집합
    all_dates = sorted(set().union(*[df.index for df in sig.values()]))

    cash = capital
    positions = {}   # 종목 -> {'shares', 'entry_price', 'entry_date'}
    trades = []
    equity_curve = []

    for date in all_dates:
        # ---- (a) 보유 종목 청산 점검 ----
        for t in list(positions.keys()):
            if date not in sig[t].index:
                continue
            row = sig[t].loc[date]
            if pd.isna(row["Low_N"]) or pd.isna(row["SMA_M"]):
                continue
            close = row["Close"]
            pos = positions[t]
            stop_hit = close <= pos["entry_price"] * (1 - params.stop_pct)
            trend_exit = close < row["Low_N"]
            if stop_hit or trend_exit:
                fill = cost.sell_fill(close)
                proceeds = pos["shares"] * fill * (1 - cost.sell_fee - cost.tax)
                cash += proceeds
                # 순수익률(비용 포함): 실수령 / 실매수금액 - 1
                buy_cost = pos["shares"] * cost.buy_fill(pos["entry_price"]) * (1 + cost.buy_fee)
                net_ret = proceeds / buy_cost - 1
                trades.append({
                    "ticker": t,
                    "entry_date": pos["entry_date"], "exit_date": date,
                    "entry": round(pos["entry_price"], 1), "exit": round(close, 1),
                    "net_return_%": round(net_ret * 100, 2),
                    "reason": "손절" if stop_hit else "추세이탈",
                })
                del positions[t]

        # ---- (b) 신규 진입 점검 ----
        # 현재 총자산(현금 + 보유평가액) 계산
        holdings_val = 0.0
        for t, pos in positions.items():
            if date in sig[t].index:
                holdings_val += pos["shares"] * sig[t].loc[date, "Close"]
            else:
                holdings_val += pos["shares"] * pos["entry_price"]
        total_equity = cash + holdings_val

        # 진입 후보: 신호 발생 + 미보유 + 슬롯 여유
        candidates = []
        for t in sig:
            if t in positions or date not in sig[t].index:
                continue
            row = sig[t].loc[date]
            if pd.isna(row["High_N"]) or pd.isna(row["SMA_M"]):
                continue
            if bool(row["EntrySignal"]):
                strength = row["Close"] / row["High_N"] - 1   # 돌파 강도
                candidates.append((strength, t))
        candidates.sort(reverse=True)   # 강한 돌파 우선

        for _, t in candidates:
            if len(positions) >= max_positions:
                break
            row = sig[t].loc[date]
            close = row["Close"]
            alloc = min(weight * total_equity, cash)
            fill = cost.buy_fill(close)
            shares = int(alloc // (fill * (1 + cost.buy_fee)))
            if shares <= 0:
                continue
            spend = shares * fill * (1 + cost.buy_fee)
            cash -= spend
            positions[t] = {"shares": shares, "entry_price": close, "entry_date": date}

        # ---- (c) 일별 총자산 기록 ----
        holdings_val = 0.0
        for t, pos in positions.items():
            if date in sig[t].index:
                holdings_val += pos["shares"] * sig[t].loc[date, "Close"]
            else:
                holdings_val += pos["shares"] * pos["entry_price"]
        equity_curve.append((date, cash + holdings_val))

    equity = pd.Series(dict(equity_curve)).sort_index()
    tdf = pd.DataFrame(trades)
    metrics = performance_metrics(equity, tdf)
    return {"equity": equity, "trades": tdf, "metrics": metrics}
