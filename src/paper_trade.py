# -*- coding: utf-8 -*-
"""
paper_trade.py
5주차 산출물: 실시간 '모의매매(페이퍼 트레이딩)' 엔진.

매일 장 마감 후 한 번 실행하면:
  1) 최신 시세로 오늘의 신호를 계산
  2) 보유 종목 청산(손절/추세이탈) 점검
  3) 신규 진입 후보 매수
  4) 가상 계좌 상태(현금·보유)를 파일에 저장하고, 매매 로그를 남김
  5) 누적 성과를 출력

핵심 원칙: 페이퍼 트레이딩 동안 전략(파라미터)은 '동결'한다. 손대지 않는다.
           지금은 최적화가 아니라, 정해진 규칙을 현실에서 검증하는 단계다.
"""
import os
import json
import pandas as pd
from strategy import BreakoutParams, generate_signals
from backtest import CostModel


# ===================== 동결 설정 (페이퍼 기간 중 변경 금지) =====================
FROZEN_PARAMS = BreakoutParams(entry_high=20, exit_low=10, trend_ma=60, stop_pct=0.10)
# 선정 근거: 4주차 민감도에서 Sharpe 최상위(견고) 조합
COST = CostModel()
CAPITAL = 10_000_000       # 가상 초기자본 1천만 (KIS 모의계좌 예수금과 일치)
WEIGHT = 0.10             # 1종목당 10%
MAX_POSITIONS = 10
STATE_PATH = "data/paper_state.json"
LOG_PATH = "data/paper_log.csv"


# ===================== 상태 관리 =====================
def load_state(path: str, capital: float) -> dict:
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"cash": capital, "positions": {}, "last_date": None,
            "equity_history": []}  # [[date, equity], ...]


def save_state(path: str, state: dict):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


# ===================== 핵심 로직 (테스트 가능, 시세 fetch와 분리) =====================
def compute_actions(price_data: dict, state: dict,
                    params: BreakoutParams = FROZEN_PARAMS, cost: CostModel = COST,
                    weight: float = WEIGHT, max_positions: int = MAX_POSITIONS,
                    allow_entries: bool = True):
    """주어진 시세로 '최신 거래일' 기준 매매 결정을 내리고 상태를 갱신.
    allow_entries=False면 청산만 수행(킬스위치 작동 시)."""
    sig = {t: generate_signals(df, params) for t, df in price_data.items()}
    latest = max(df.index.max() for df in sig.values())

    cash = state["cash"]
    positions = {k: dict(v) for k, v in state["positions"].items()}
    actions = []

    # --- (1) 청산 점검 ---
    for t in list(positions.keys()):
        if t not in sig or latest not in sig[t].index:
            continue
        row = sig[t].loc[latest]
        if pd.isna(row["Low_N"]) or pd.isna(row["SMA_M"]):
            continue
        close = float(row["Close"])
        pos = positions[t]
        stop_hit = close <= pos["entry_price"] * (1 - params.stop_pct)
        trend_exit = close < row["Low_N"]
        if stop_hit or trend_exit:
            fill = cost.sell_fill(close)
            proceeds = pos["shares"] * fill * (1 - cost.sell_fee - cost.tax)
            buy_cost = pos["shares"] * cost.buy_fill(pos["entry_price"]) * (1 + cost.buy_fee)
            cash += proceeds
            actions.append({
                "action": "SELL", "ticker": t, "price": round(close, 1),
                "shares": pos["shares"], "reason": "손절" if stop_hit else "추세이탈",
                "net_return_%": round((proceeds / buy_cost - 1) * 100, 2),
            })
            del positions[t]

    # --- 현재 총자산(비중 산정용) ---
    def holdings_value():
        v = 0.0
        for t, pos in positions.items():
            if latest in sig[t].index:
                v += pos["shares"] * float(sig[t].loc[latest, "Close"])
            else:
                v += pos["shares"] * pos["entry_price"]
        return v

    total_equity = cash + holdings_value()

    # --- (2) 신규 진입 (킬스위치 작동 시 건너뜀) ---
    candidates = []
    for t in (sig if allow_entries else []):
        if t in positions or latest not in sig[t].index:
            continue
        row = sig[t].loc[latest]
        if pd.isna(row["High_N"]) or pd.isna(row["SMA_M"]):
            continue
        if bool(row["EntrySignal"]):
            candidates.append((float(row["Close"]) / float(row["High_N"]) - 1, t))
    candidates.sort(reverse=True)

    for _, t in candidates:
        if len(positions) >= max_positions:
            break
        close = float(sig[t].loc[latest, "Close"])
        alloc = min(weight * total_equity, cash)
        fill = cost.buy_fill(close)
        shares = int(alloc // (fill * (1 + cost.buy_fee)))
        if shares <= 0:
            continue
        cash -= shares * fill * (1 + cost.buy_fee)
        positions[t] = {"shares": shares, "entry_price": close,
                        "entry_date": str(latest.date())}
        actions.append({"action": "BUY", "ticker": t, "price": round(close, 1),
                        "shares": shares, "reason": "돌파진입", "net_return_%": None})

    equity = cash + holdings_value()
    state["cash"] = cash
    state["positions"] = positions
    state["last_date"] = str(latest.date())
    state.setdefault("equity_history", []).append([str(latest.date()), round(equity, 0)])
    return actions, state, equity, latest


# ===================== 일일 실행 (시세 fetch 포함) =====================
def run_daily(universe: list, lookback_days: int = 400):
    import FinanceDataReader as fdr
    import datetime as dt

    start = (dt.date.today() - dt.timedelta(days=lookback_days)).strftime("%Y-%m-%d")
    print(f"[1] 최신 시세 로드 (최근 {lookback_days}일)...")
    price_data = {}
    for t in universe:
        try:
            df = fdr.DataReader(t, start)
            if not df.empty and len(df) > 130:
                price_data[t] = df[["High", "Low", "Close"]]
        except Exception as e:
            print(f"  {t} 실패: {e}")
    if not price_data:
        print("  시세 로드 실패. 종료.")
        return

    state = load_state(STATE_PATH, CAPITAL)
    latest_date = str(max(df.index.max() for df in price_data.values()).date())

    if state.get("last_date") == latest_date:
        print(f"[!] 최신 거래일({latest_date})은 이미 처리됨. 새 데이터가 없습니다.")
        _print_portfolio(state, price_data)
        return

    print(f"[2] 신호 계산 및 모의매매 (기준일 {latest_date}, 파라미터 동결)")
    actions, state, equity, latest = compute_actions(price_data, state)

    # 로그 기록
    if actions:
        rows = [{"date": latest_date, **a} for a in actions]
        log_df = pd.DataFrame(rows)
        header = not os.path.exists(LOG_PATH)
        os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
        log_df.to_csv(LOG_PATH, mode="a", header=header, index=False, encoding="utf-8-sig")

    save_state(STATE_PATH, state)

    print("\n[3] 오늘의 매매:")
    if actions:
        for a in actions:
            extra = f" ({a['net_return_%']}%)" if a["action"] == "SELL" else ""
            print(f"   {a['action']:4s} {a['ticker']} {a['shares']}주 @ {a['price']:,}  [{a['reason']}]{extra}")
    else:
        print("   매매 없음 (조건 미충족).")

    _print_portfolio(state, price_data)


def _print_portfolio(state, price_data):
    latest = max(df.index.max() for df in price_data.values())
    cash = state["cash"]
    print("\n[4] 현재 가상 포트폴리오:")
    hold_val = 0.0
    for t, pos in state["positions"].items():
        px = float(price_data[t].loc[latest, "Close"]) if latest in price_data[t].index else pos["entry_price"]
        val = pos["shares"] * px
        hold_val += val
        ret = (px / pos["entry_price"] - 1) * 100
        print(f"   {t}  {pos['shares']}주  평가 {val:,.0f}  ({ret:+.1f}%, 진입 {pos['entry_date']})")
    equity = cash + hold_val
    print(f"\n   현금 {cash:,.0f} + 주식 {hold_val:,.0f} = 총자산 {equity:,.0f}")
    print(f"   누적수익률(초기 1억 대비): {(equity/CAPITAL-1)*100:+.2f}%")
    print("\n   * 페이퍼 기간 최소 6~8주 권장. 이 수익률을 백테스트 기대치와 비교하세요.")


if __name__ == "__main__":
    UNIVERSE = [
        "005930", "000660", "035420", "035720", "005380", "000270", "051910",
        "006400", "005490", "068270", "105560", "055550", "012330", "028260", "066570",
    ]
    run_daily(UNIVERSE)
