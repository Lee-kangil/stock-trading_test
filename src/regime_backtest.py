# -*- coding: utf-8 -*-
"""
regime_backtest.py
시장 레짐 필터(코스피 200일선) 적용 전/후를 비교한다.
- 지수(KS11)가 200일선 위 = 상승장(매수 허용), 아래 = 하락장(신규 매수 차단)
실행:  python src/regime_backtest.py

⚠️ 유니버스가 '현재 시총 상위'라 절대수익은 생존편향으로 부풀려져 있음.
   레짐 필터의 효과는 'MDD 감소'와 '2022년 손실 축소'로 판단하세요.
"""
import FinanceDataReader as fdr
import pandas as pd
from backtest import CostModel
from strategies import STRATEGIES
from engine import backtest_portfolio_generic

START = "2020-01-01"
CAPITAL = 20_000_000
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


def build_regime():
    """코스피 지수가 200일선 위면 True(매수허용). 미래참조 방지로 shift(1)."""
    idx = fdr.DataReader("KS11", START)
    ma200 = idx["Close"].rolling(200).mean()
    regime = (idx["Close"] > ma200).shift(1)
    regime.index = pd.to_datetime(regime.index)
    return regime


def yr2022(eq):
    e = eq[eq.index.year == 2022]
    return round((e.iloc[-1] / e.iloc[0] - 1) * 100, 1) if len(e) > 1 else None


def main():
    print(f"[1] 데이터 로드 (시작 {START})...")
    data = {}
    for t in build_universe():
        try:
            df = fdr.DataReader(t, START)
            if not df.empty and len(df) > 260:
                data[t] = df[["Open", "High", "Low", "Close", "Volume"]]
        except Exception:
            pass
    print(f"    {len(data)}종목")
    regime = build_regime()
    print("[2] 레짐 필터 전/후 비교 백테스트 (각 2천만)...\n")

    cost = CostModel()
    rows = []
    for s in STRATEGIES:
        base = backtest_portfolio_generic(data, s, cost, capital=CAPITAL, regime=None)
        filt = backtest_portfolio_generic(data, s, cost, capital=CAPITAL, regime=regime)
        rows.append({
            "전략": s.name,
            "CAGR_무": base["metrics"].get("CAGR_%"), "CAGR_레짐": filt["metrics"].get("CAGR_%"),
            "MDD_무": base["metrics"].get("MDD_%"), "MDD_레짐": filt["metrics"].get("MDD_%"),
            "Sharpe_무": base["metrics"].get("Sharpe"), "Sharpe_레짐": filt["metrics"].get("Sharpe"),
            "2022_무": yr2022(base["equity"]), "2022_레짐": yr2022(filt["equity"]),
        })
    tbl = pd.DataFrame(rows)
    print(tbl.to_string(index=False))
    print("\n해석: MDD와 2022 수익률이 '레짐' 쪽에서 얼마나 개선되는지가 핵심입니다.")
    print("     보통 MDD가 줄고 2022 손실이 작아지는 대신, 강세장 CAGR은 약간 깎입니다(트레이드오프).")


if __name__ == "__main__":
    main()
