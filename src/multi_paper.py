# -*- coding: utf-8 -*-
"""
multi_paper.py
5개 전략을 '각각 독립된 2천만 가상계좌'로 동시에 페이퍼 트레이딩(총 1억 균등배분).
매 영업일 마감 후 한 번 실행하면 5개 계좌가 동시에 갱신되고, 성과를 비교 출력한다.
실행:  python src/multi_paper.py

상태: data/multi_paper_state.json  (전략별 계좌)
로그: data/multi_paper_log.csv
"""
import os
import json
import datetime as dt
import FinanceDataReader as fdr
import pandas as pd

from backtest import CostModel
from strategies import STRATEGIES
from engine import step_latest

CAPITAL = 20_000_000      # 전략당 2천만 (총 1억을 5전략에 균등 배분)
WEIGHT = 0.10
MAX_POSITIONS = 10
TOP_N = 200               # 시총 상위 N (1000까지 가능하나 느려짐)
STATE_PATH = "data/multi_paper_state.json"
LOG_PATH = "data/multi_paper_log.csv"
FALLBACK = [
    "005930", "000660", "035420", "035720", "005380", "000270", "051910",
    "006400", "005490", "068270", "105560", "055550", "012330", "028260", "066570",
]


def build_universe(top_n=TOP_N):
    """FinanceDataReader 종목목록에서 시총 상위 top_n 추출(현재 기준 근사)."""
    try:
        lst = fdr.StockListing("KRX")
        code_col = "Code" if "Code" in lst.columns else ("Symbol" if "Symbol" in lst.columns else lst.columns[0])
        if "Marcap" in lst.columns:
            lst = lst.dropna(subset=["Marcap"]).sort_values("Marcap", ascending=False)
        tickers = [str(c).zfill(6) for c in lst[code_col].tolist()][:top_n]
        if not tickers:
            raise RuntimeError("목록 비어있음")
        print(f"    시총 상위 {len(tickers)}종목 로드(FDR 기준)")
        return tickers
    except Exception as e:
        print(f"    유니버스 빌드 실패({e}) → 기본 15종목")
        return FALLBACK


def build_regime(start):
    """코스피(KS11)가 200일선 위면 True(매수허용). 미래참조 방지로 shift(1)."""
    try:
        idx = fdr.DataReader("KS11", start)
        ma200 = idx["Close"].rolling(200).mean()
        regime = (idx["Close"] > ma200).shift(1)
        regime.index = pd.to_datetime(regime.index)
        return regime.ffill()
    except Exception as e:
        print(f"    레짐 계산 실패({e}) → 필터 미적용(항상 매수허용)")
        return None


def load_all_states():
    if os.path.exists(STATE_PATH):
        with open(STATE_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_all_states(states):
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(states, f, ensure_ascii=False, indent=2)


def main():
    start = (dt.date.today() - dt.timedelta(days=500)).strftime("%Y-%m-%d")
    print(f"[1] 시세 로드 (최근 500일)...")
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
    latest = str(max(df.index.max() for df in data.values()).date())

    # 시장 레짐 점검 (하락장이면 신규 매수 차단)
    regime = build_regime(start)
    regime_ok_today = True
    if regime is not None:
        rr = regime.loc[regime.index <= pd.Timestamp(latest)]
        regime_ok_today = bool(rr.iloc[-1]) if len(rr) else True
    print(f"    시장 레짐: {'상승장(매수 허용)' if regime_ok_today else '하락장(신규 매수 차단)'}")

    states = load_all_states()
    cost = CostModel()
    all_logs = []
    summary = []

    print(f"[2] 기준일 {latest} — 5개 전략 동시 갱신\n")
    for s in STRATEGIES:
        st = states.get(s.name) or {"cash": CAPITAL, "positions": {}, "last_date": None, "equity_history": []}
        if st.get("last_date") == latest:
            print(f"   [{s.name}] 이미 처리된 거래일 — 건너뜀")
        else:
            actions, st, equity, _ = step_latest(data, s, st, cost, WEIGHT, MAX_POSITIONS, regime_ok=regime_ok_today)
            states[s.name] = st
            for a in actions:
                all_logs.append({"date": latest, "strategy": s.name, **a})
            if actions:
                acts = ", ".join(f"{a['action']} {a['ticker']}" for a in actions)
                print(f"   [{s.name}] {acts}")
            else:
                print(f"   [{s.name}] 매매 없음")

        st = states[s.name]
        eq = st["equity_history"][-1][1] if st.get("equity_history") else st["cash"]
        summary.append({"전략": s.name, "보유종목": len(st["positions"]),
                        "총자산": f"{eq:,.0f}", "누적수익_%": round((eq / CAPITAL - 1) * 100, 2)})

    save_all_states(states)
    if all_logs:
        header = not os.path.exists(LOG_PATH)
        os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
        pd.DataFrame(all_logs).to_csv(LOG_PATH, mode="a", header=header, index=False, encoding="utf-8-sig")

    print("\n[3] 전략별 성과 비교:")
    print(pd.DataFrame(summary).sort_values("누적수익_%", ascending=False).to_string(index=False))
    print("\n   * 매 영업일 실행해 누적하세요. 6~8주 뒤 가장 견고한 전략을 데이터로 고릅니다.")


if __name__ == "__main__":
    main()
