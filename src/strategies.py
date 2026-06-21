# -*- coding: utf-8 -*-
"""
strategies.py
동시 비교/관찰할 스윙 전략들을 '동일한 인터페이스'로 정의한다.

각 전략 함수: 가격 DataFrame(Open/High/Low/Close)을 받아
  'Close', 'entry'(bool), 'exit'(bool) 컬럼을 가진 DataFrame을 반환.
미래참조 방지를 위해 비교 기준은 shift 처리.
손절(stop_pct)·보유기간(max_hold_days)은 엔진이 처리한다.
"""
from dataclasses import dataclass
from typing import Callable, Optional
import pandas as pd


def _sma(s, n):
    return s.rolling(n).mean()


def _adx(df, n=14):
    """ADX·+DI·-DI (Wilder 평활 근사). 추세 '강도'를 0~100으로."""
    high, low, close = df["High"], df["Low"], df["Close"]
    up = high.diff()
    down = -low.diff()
    plus_dm = ((up > down) & (up > 0)) * up
    minus_dm = ((down > up) & (down > 0)) * down
    tr = pd.concat([(high - low),
                    (high - close.shift()).abs(),
                    (low - close.shift()).abs()], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1 / n, adjust=False).mean()
    plus_di = 100 * plus_dm.ewm(alpha=1 / n, adjust=False).mean() / atr
    minus_di = 100 * minus_dm.ewm(alpha=1 / n, adjust=False).mean() / atr
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di)
    adx = dx.ewm(alpha=1 / n, adjust=False).mean()
    return adx, plus_di, minus_di


def _heikin_ashi(df):
    """하이킨아시 시가/종가 계산. (HA_Open은 전일 HA값에 의존하는 재귀식)"""
    ha_close = (df["Open"] + df["High"] + df["Low"] + df["Close"]) / 4
    o = df["Open"].values
    c = ha_close.values
    ha_open = [(o[0] + df["Close"].values[0]) / 2]
    for i in range(1, len(c)):
        ha_open.append((ha_open[i - 1] + c[i - 1]) / 2)
    return pd.Series(ha_open, index=df.index), ha_close


def _frame(df):
    out = pd.DataFrame(index=df.index)
    out["Close"] = df["Close"]
    return out


# ===================== 1) 골든크로스 (중기 추세) =====================
def golden_cross(df):
    out = _frame(df)
    sma20 = _sma(df["Close"], 20)
    sma60 = _sma(df["Close"], 60)
    out["entry"] = ((sma20 > sma60) & (sma20.shift(1) <= sma60.shift(1))).fillna(False)
    out["exit"] = (sma20 < sma60).fillna(False)
    return out


# ===================== 2) 돌파 (보관용, 현재 미사용) =====================
def breakout(df):
    out = _frame(df)
    high20 = df["High"].rolling(20).max().shift(1)
    low10 = df["Low"].rolling(10).min().shift(1)
    sma60 = _sma(df["Close"], 60)
    out["entry"] = ((df["Close"] > high20) & (df["Close"] > sma60)).fillna(False)
    out["exit"] = (df["Close"] < low10).fillna(False)
    return out


# ===================== 3) ADX 추세강도 추종 =====================
def adx_trend(df):
    out = _frame(df)
    adx, pdi, mdi = _adx(df, 14)
    sma20 = _sma(df["Close"], 20)
    out["entry"] = ((adx > 25) & (pdi > mdi) & (df["Close"] > sma20)).fillna(False)
    out["exit"] = ((adx < 20) | (df["Close"] < sma20)).fillna(False)
    return out


# ===================== 4) 듀얼 모멘텀 (방어형) =====================
def dual_momentum(df):
    """절대모멘텀: 종가가 200일선 위 + 최근 6개월(120일) 수익률 양수일 때만 보유.
    200일선 아래로 내려가면 청산(=하락장엔 현금). 신호가 드물어 과매매 없음."""
    out = _frame(df)
    sma200 = df["Close"].rolling(200).mean()
    mom6 = df["Close"] / df["Close"].shift(120) - 1
    out["entry"] = ((df["Close"] > sma200) & (mom6 > 0)).fillna(False)
    out["exit"] = (df["Close"] < sma200).fillna(False)
    return out


# ===================== 5) 추세 눌림목 (중기) =====================
def pullback_trend(df):
    """상승추세(종가>60일선) 중 20일선까지 눌렸다가 그 위에서 마감하면 매수,
    60일선 이탈 시 청산."""
    out = _frame(df)
    sma20 = _sma(df["Close"], 20)
    sma60 = _sma(df["Close"], 60)
    uptrend = df["Close"] > sma60
    out["entry"] = (uptrend & (df["Low"] <= sma20) & (df["Close"] > sma20)).fillna(False)
    out["exit"] = (df["Close"] < sma60).fillna(False)
    return out


# ===================== 6) 하이킨아시 추세 (신규) =====================
def heikin_ashi(df):
    """하이킨아시 양봉(HA_Close>HA_Open)이 2일 연속 + 20일선 위면 매수,
    첫 음봉(HA_Close<HA_Open) 전환 시 청산. 노이즈를 줄여 추세를 타는 기법."""
    out = _frame(df)
    ha_open, ha_close = _heikin_ashi(df)
    ha_bull = ha_close > ha_open
    ha_bear = ha_close < ha_open
    sma20 = _sma(df["Close"], 20)
    sma60 = _sma(df["Close"], 60)
    # 진입: HA 양봉 2연속 + 중기 상승추세(60일선 위)
    out["entry"] = (ha_bull & ha_bull.shift(1) & (df["Close"] > sma60)).fillna(False)
    # 청산: 20일선 하향 이탈(추세 종료). HA 색 변화는 너무 잦아 과매매라 제외
    out["exit"] = (df["Close"] < sma20).fillna(False)
    return out


# ===================== 7) Minervini SEPA (사용자 조건식) =====================
def minervini_sepa(df):
    """Mark Minervini SEPA 기반 8개 조건 동시 충족 시 매수.
    1)당일등락률>=3% 2)종가>20MA*1.05 3)거래량>=20일평균*1.5
    4)종가>=20일최고가*0.95 5)종가>60MA 6)종가>120MA 7)5MA>10MA 8)10MA>20MA
    청산: 사용자 미지정 → 20일선 이탈로 가정(+손절 8%는 엔진)."""
    out = _frame(df)
    chg = df["Close"].pct_change() * 100
    sma5 = _sma(df["Close"], 5)
    sma10 = _sma(df["Close"], 10)
    sma20 = _sma(df["Close"], 20)
    sma60 = _sma(df["Close"], 60)
    sma120 = _sma(df["Close"], 120)
    volavg20 = df["Volume"].rolling(20).mean()
    high20 = df["High"].rolling(20).max()
    cond = ((chg >= 3) &
            (df["Close"] > sma20 * 1.05) &
            (df["Volume"] >= volavg20 * 1.5) &
            (df["Close"] >= high20 * 0.95) &
            (df["Close"] > sma60) &
            (df["Close"] > sma120) &
            (sma5 > sma10) &
            (sma10 > sma20))
    out["entry"] = cond.fillna(False)
    # 청산: 10일선 이탈(타이트). 손절 7%는 엔진(stop_pct)
    out["exit"] = (df["Close"] < sma10).fillna(False)
    return out


@dataclass
class Strategy:
    name: str
    signal_fn: Callable
    stop_pct: float = 0.10
    max_hold_days: Optional[int] = None


STRATEGIES = [
    Strategy("골든크로스", golden_cross, 0.10),
    Strategy("ADX추세", adx_trend, 0.08),
    Strategy("듀얼모멘텀", dual_momentum, 0.12),
    Strategy("하이킨아시", heikin_ashi, 0.08),
    Strategy("Minervini", minervini_sepa, 0.07),
]
