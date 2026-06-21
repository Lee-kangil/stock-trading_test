# -*- coding: utf-8 -*-
"""
strategy.py
2주차 산출물: 돌파 전략(연습용)을 '함수'로 구현한다.
- 지표 계산 함수
- 신호 생성 함수 (진입/청산 규칙을 코드로)
- 간이 매매 시뮬레이션 (비용 미반영 — 비용/세금/슬리피지는 3주차에서 추가)

규칙 정의는 '전략규칙_돌파형.md' 참고.
"""
from dataclasses import dataclass
import pandas as pd


# ===================== 지표 함수 =====================
def sma(series: pd.Series, period: int) -> pd.Series:
    """단순 이동평균."""
    return series.rolling(period).mean()


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """RSI(상대강도지수)."""
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))


# ===================== 전략 파라미터 =====================
@dataclass
class BreakoutParams:
    entry_high: int = 20    # 진입: 직전 N일 최고가 돌파
    exit_low: int = 10      # 청산: 직전 N일 최저가 이탈
    trend_ma: int = 60      # 추세 필터: M일 이동평균 위에서만 매수
    stop_pct: float = 0.07  # 손절: 매수가 대비 -7%


# ===================== 신호 생성 =====================
def generate_signals(df: pd.DataFrame, p: BreakoutParams = BreakoutParams()) -> pd.DataFrame:
    """
    가격 DataFrame(High/Low/Close 포함)에 지표와 진입신호 컬럼을 추가해 반환.
    - High_N  : 직전 entry_high일 최고가 (shift로 '어제까지' 기준 → 미래참조 방지)
    - Low_N   : 직전 exit_low일 최저가
    - SMA_M   : 추세 필터선
    - EntrySignal : 진입 조건 충족 여부 (보유 여부는 시뮬레이션에서 판단)
    """
    out = df.copy()
    out["High_N"] = out["High"].rolling(p.entry_high).max().shift(1)
    out["Low_N"] = out["Low"].rolling(p.exit_low).min().shift(1)
    out["SMA_M"] = sma(out["Close"], p.trend_ma)

    out["EntrySignal"] = (out["Close"] > out["High_N"]) & (out["Close"] > out["SMA_M"])
    return out


# ===================== 간이 매매 시뮬레이션 =====================
def backtest_single(df: pd.DataFrame, p: BreakoutParams = BreakoutParams()) -> dict:
    """
    단일 종목, 1포지션 가정의 간이 시뮬레이션.
    ※ 비용/세금/슬리피지 미반영 (3주차에서 추가). 규칙이 매매를 만들어내는지 확인이 목적.
    반환: {'trades': DataFrame, 'summary': dict}
    """
    d = generate_signals(df, p)
    in_pos = False
    entry_price = entry_date = None
    trades = []

    for date, row in d.iterrows():
        close = row["Close"]
        if pd.isna(row["SMA_M"]) or pd.isna(row["Low_N"]):
            continue  # 지표가 아직 안 채워진 초기 구간 건너뜀

        if not in_pos:
            if bool(row["EntrySignal"]):
                in_pos = True
                entry_price, entry_date = close, date
        else:
            stop_hit = close <= entry_price * (1 - p.stop_pct)
            trend_exit = close < row["Low_N"]
            if stop_hit or trend_exit:
                ret = close / entry_price - 1
                trades.append({
                    "entry_date": entry_date, "entry": round(entry_price, 1),
                    "exit_date": date, "exit": round(close, 1),
                    "return_%": round(ret * 100, 2),
                    "reason": "손절" if stop_hit else "추세이탈",
                })
                in_pos = False
                entry_price = entry_date = None

    tdf = pd.DataFrame(trades)
    if len(tdf) == 0:
        summary = {"trades": 0}
    else:
        wins = (tdf["return_%"] > 0).sum()
        summary = {
            "trades": len(tdf),
            "win_rate_%": round(wins / len(tdf) * 100, 1),
            "avg_return_%": round(tdf["return_%"].mean(), 2),
            "best_%": round(tdf["return_%"].max(), 2),
            "worst_%": round(tdf["return_%"].min(), 2),
            "total_compound_%": round((( (tdf["return_%"]/100 + 1).prod() ) - 1) * 100, 2),
        }
    return {"trades": tdf, "summary": summary}
