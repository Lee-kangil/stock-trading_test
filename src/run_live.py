# -*- coding: utf-8 -*-
"""
run_live.py
KIS 모의계좌(1억)에 '듀얼모멘텀 1개 전략'을 레짐 필터와 함께 실제 모의주문으로 굴린다.
(로컬 5전략 비교는 multi_paper.py가 따로 담당. 이건 KIS 체결 현실성 확인용.)

[!] 안전 원칙
  - 기본 KIS_ENV=paper(모의투자). 기본 DRY_RUN(전송 안 함, KIS_LIVE=1일 때만 전송).
  - 레짐 하락장 또는 킬스위치(누적손실 -15%) 시 신규 매수 차단(청산만).
  - 평일 정규장(09:00~15:30)에 실행해야 체결됩니다.
"""
import os
import datetime as dt
import FinanceDataReader as fdr
import pandas as pd

import kis_api
from backtest import CostModel
from strategies import Strategy, dual_momentum
from engine import step_latest
from paper_trade import load_state, save_state

# ---------- 설정 ----------
LIVE = os.getenv("KIS_LIVE", "0") == "1"
DRY_RUN = not LIVE
CAPITAL = 100_000_000          # KIS 모의계좌 예수금과 일치(1억)
WEIGHT = 0.10
MAX_POSITIONS = 10
MAX_DD_PCT = 15.0              # 누적손실 한도(킬스위치)
TOP_N = 200
STRAT = Strategy("듀얼모멘텀", dual_momentum, 0.12)   # KIS로 굴릴 대표 전략
LIVE_STATE = "data/live_state.json"
FALLBACK = ["005930","000660","035420","035720","005380","000270","051910",
            "006400","005490","068270","105560","055550","012330","028260","066570"]


def build_universe(top_n=TOP_N):
    try:
        lst = fdr.StockListing("KRX")
        code_col = "Code" if "Code" in lst.columns else ("Symbol" if "Symbol" in lst.columns else lst.columns[0])
        if "Marcap" in lst.columns:
            lst = lst.dropna(subset=["Marcap"]).sort_values("Marcap", ascending=False)
        t = [str(c).zfill(6) for c in lst[code_col].tolist()][:top_n]
        return t if t else FALLBACK
    except Exception as e:
        print(f"    유니버스 빌드 실패({e}) → 기본 15종목")
        return FALLBACK


def build_regime(start):
    try:
        idx = fdr.DataReader("KS11", start)
        ma200 = idx["Close"].rolling(200).mean()
        reg = (idx["Close"] > ma200).shift(1)
        reg.index = pd.to_datetime(reg.index)
        return reg.ffill()
    except Exception:
        return None


def main():
    print("=" * 56)
    print("[KIS 연동] 듀얼모멘텀 + 레짐 필터")
    print(kis_api.config_summary())
    print(f"DRY_RUN={DRY_RUN} (실제전송={'예' if LIVE else '아니오'}) | 자본 {CAPITAL:,} | 킬스위치 -{MAX_DD_PCT}%")
    print("=" * 56)
    if not kis_api.APP_KEY:
        print("[!] .env에 KIS 키가 없습니다. 종료.")
        return

    start = (dt.date.today() - dt.timedelta(days=500)).strftime("%Y-%m-%d")
    print("[1] 시세 로드...")
    data = {}
    for t in build_universe():
        try:
            df = fdr.DataReader(t, start)
            if not df.empty and len(df) > 130:
                data[t] = df[["Open", "High", "Low", "Close", "Volume"]]
        except Exception:
            pass
    if not data:
        print("시세 로드 실패. 종료.")
        return
    latest = max(df.index.max() for df in data.values())

    # 레짐
    regime = build_regime(start)
    regime_ok = True
    if regime is not None:
        rr = regime.loc[regime.index <= latest]
        regime_ok = bool(rr.iloc[-1]) if len(rr) else True

    # 킬스위치: 현재 평가자산 기준 누적손익
    state = load_state(LIVE_STATE, CAPITAL)

    # 중복 실행 방지(멱등성): 같은 거래일을 이미 처리했으면 주문하지 않고 종료.
    # → 안정성을 위해 하루에 cron을 여러 번 잡아도 실제 주문은 한 번만 일어난다.
    if state.get("last_date") == str(latest.date()):
        print(f"[i] 기준일 {latest.date()}는 이미 처리됨 — 중복 주문 방지로 종료.")
        return

    holdings = sum(pos["shares"] * float(data[t].loc[latest, "Close"])
                   for t, pos in state["positions"].items() if latest in data[t].index)
    equity = state["cash"] + holdings
    dd = (equity / CAPITAL - 1) * 100
    kill = dd <= -MAX_DD_PCT
    print(f"    레짐: {'상승장' if regime_ok else '하락장'} | 누적손익 {dd:+.1f}%{' | [KILL]킬스위치' if kill else ''}")

    allow_buy = regime_ok and not kill

    # 신호 계산(로컬 상태 기준) → 주문
    actions, state, equity, _ = step_latest(data, STRAT, state, CostModel(),
                                            WEIGHT, MAX_POSITIONS, regime_ok=allow_buy)
    save_state(LIVE_STATE, state)

    print(f"\n[2] 기준일 {latest.date()} - 주문 {'시뮬레이션' if DRY_RUN else '전송'}:")
    if not actions:
        print("   주문 없음.")
    for a in actions:
        try:
            res = kis_api.order_cash(code=a["ticker"], qty=a["shares"], side=a["action"].lower(),
                                     price=0, ord_dvsn="01", dry_run=DRY_RUN)
            tag = "DRY" if res.get("dry_run") else "SENT"
            print(f"   [{tag}] {a['action']} {a['ticker']} {a['shares']}주 [{a['reason']}]")
            if not res.get("dry_run"):
                print(f"          응답: {res.get('response', {}).get('msg1','')}")
        except Exception as e:
            print(f"   [ERROR] {a['ticker']} 주문 실패: {e}")

    print(f"\n[3] 가상 총자산(로컬 추정): {equity:,.0f}  ({(equity/CAPITAL-1)*100:+.2f}%)")
    if DRY_RUN:
        print("   * 시뮬레이션입니다. 실제 모의주문은 .env에서 KIS_LIVE=1 (평일 장중 실행).")
    print("   * 로컬 추정이라 실제 KIS 잔고와 다를 수 있음(체결·거부 차이). 정식은 잔고조회로 대조.")


if __name__ == "__main__":
    main()
