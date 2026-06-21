# -*- coding: utf-8 -*-
"""
multi_walkforward.py
5개 전략을 각 2천만으로 walk-forward(연도별 OOS 일관성) 검증.
고정 규칙 전략이라 재최적화는 없고, '시기를 바꿔도 견고한가'를 연도별로 본다.
실행:  python src/multi_walkforward.py

⚠️ 유니버스가 '현재 시총 상위'라 절대수익은 생존편향으로 부풀려져 있음.
   → 연도별 '일관성'(매년 +인가, 어느 해에 무너지나)만 신뢰할 것.
"""
import FinanceDataReader as fdr
import pandas as pd
from backtest import CostModel
from strategies import STRATEGIES
from engine import backtest_portfolio_generic

START = "2020-01-01"
CAPITAL = 20_000_000      # 전략당 2천만
TOP_N = 200
FALLBACK = ["005930","000660","035420","035720","005380","000270","051910",
            "006400","005490","068270","105560","055550","012330","028260","066570"]


def build_universe(top_n=TOP_N):
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


def load():
    data = {}
    for t in build_universe():
        try:
            df = fdr.DataReader(t, START)
            if not df.empty and len(df) > 260:
                data[t] = df[["Open", "High", "Low", "Close", "Volume"]]
        except Exception:
            pass
    return data


def yearly_returns(eq):
    """자산곡선을 연도별 수익률(%)로."""
    out = {}
    for y in sorted(set(eq.index.year)):
        e = eq[eq.index.year == y]
        if len(e) > 1:
            out[y] = round((e.iloc[-1] / e.iloc[0] - 1) * 100, 1)
    return out


def main():
    print(f"[1] 데이터 로드 (시작 {START})...")
    data = load()
    print(f"    {len(data)}종목\n")

    cost = CostModel()
    peryear, sharpe, mdd = {}, {}, {}
    print("[2] 5개 전략 연도별 OOS 성과 산출 중...")
    for s in STRATEGIES:
        res = backtest_portfolio_generic(data, s, cost, capital=CAPITAL, weight=0.10, max_positions=10)
        peryear[s.name] = yearly_returns(res["equity"])
        sharpe[s.name] = res["metrics"].get("Sharpe")
        mdd[s.name] = res["metrics"].get("MDD_%")

    allyears = sorted({y for d in peryear.values() for y in d})
    tbl = pd.DataFrame({nm: {str(y): peryear[nm].get(y) for y in allyears} for nm in peryear}).T
    tbl["전체Sharpe"] = [sharpe[nm] for nm in tbl.index]
    tbl["MDD%"] = [mdd[nm] for nm in tbl.index]
    tbl["양수연도"] = [f"{sum(1 for y in allyears if (peryear[nm].get(y) or 0) > 0)}/{len(allyears)}"
                    for nm in tbl.index]
    tbl = tbl.sort_values("전체Sharpe", ascending=False)

    print("\n[3] 연도별 수익률(%) — 일관성이 핵심 (절대값은 생존편향으로 부풀려짐):")
    print(tbl.to_string())
    print("\n해석: 어느 해에 마이너스로 무너지는지, 매년 꾸준히 +인지를 보세요.")
    print("     '양수연도'가 높고 어떤 해에도 크게 깨지지 않는 전략이 실전 후보입니다.")
    print("     (2020년은 지표 워밍업 구간이라 의미 적음)")


if __name__ == "__main__":
    main()
