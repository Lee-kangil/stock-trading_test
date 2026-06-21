# -*- coding: utf-8 -*-
"""
multi_backtest.py
5개 전략을 같은 유니버스·같은 비용으로 과거 백테스트하여 '한 표'로 비교.
실행:  python src/multi_backtest.py
각 전략은 독립 1억 가상계좌 기준.
"""
import FinanceDataReader as fdr
import pandas as pd
from backtest import CostModel
from strategies import STRATEGIES
from engine import backtest_portfolio_generic

START = "2020-01-01"
CAPITAL = 100_000_000
TOP_N = 200   # 시총 상위 N (속도 위해 기본 200, 1000까지 가능하나 느려짐)
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


def main():
    print(f"[1] 데이터 로드 (시작 {START})...")
    data = load()
    print(f"    {len(data)}종목\n")

    print(f"[2] {len(STRATEGIES)}개 전략 비교 백테스트 (비용 반영, 각 1억):")
    cost = CostModel()
    rows = []
    equities = {}
    for s in STRATEGIES:
        res = backtest_portfolio_generic(data, s, cost, capital=CAPITAL, weight=0.10, max_positions=10)
        m = res["metrics"]
        equities[s.name] = res["equity"]
        rows.append({"전략": s.name, "CAGR_%": m.get("CAGR_%"), "MDD_%": m.get("MDD_%"),
                     "Sharpe": m.get("Sharpe"), "매매수": m.get("n_trades"),
                     "승률_%": m.get("win_rate_%"), "손익비": m.get("profit_factor")})
    table = pd.DataFrame(rows).sort_values("Sharpe", ascending=False)
    print(table.to_string(index=False))

    try:
        import matplotlib.pyplot as plt
        plt.rcParams["font.family"] = "Malgun Gothic"
        plt.rcParams["axes.unicode_minus"] = False
        plt.figure(figsize=(11, 6))
        for name, eq in equities.items():
            plt.plot(eq.index, eq.values / 1e8, label=name, linewidth=1.1)
        plt.title("전략별 자산곡선 비교 (초기 1억)")
        plt.ylabel("자산(억원)"); plt.legend(); plt.grid(alpha=0.3)
        plt.tight_layout()
        import os; os.makedirs("data", exist_ok=True)
        plt.savefig("data/multi_strategy_compare.png", dpi=120)
        print("\n[3] 비교 차트 저장 -> data/multi_strategy_compare.png")
    except Exception as e:
        print(f"\n[3] 차트 생략: {e}")

    print("\n해석: Sharpe(위험대비수익)와 MDD(낙폭)를 함께 보세요. CAGR만 높고 MDD가")
    print("      너무 크면 실제로 굴리기 어렵습니다. 페이퍼로 이어서 전진검증하세요.")


if __name__ == "__main__":
    main()
