# -*- coding: utf-8 -*-
"""
run_validate.py
4주차 실행 러너: 민감도 → 학습/검증 분리 → Walk-forward 순으로 검증 리포트 출력.
실행:  python src/run_validate.py
※ 여러 파라미터 조합을 반복 실행하므로 수 분 걸릴 수 있습니다.
"""
import FinanceDataReader as fdr
from backtest import CostModel
from validate import grid_search, in_out_sample, walk_forward

# ---------- 설정 ----------
START = "2020-01-01"
SPLIT = "2024-01-01"   # 이 날짜 이전=학습, 이후=검증
UNIVERSE = [
    "005930","000660","035420","035720","005380","000270","051910","006400",
    "005490","068270","105560","055550","012330","028260","066570",
]
# 파라미터 탐색 그리드 (조합 수 = 각 길이의 곱)
GRID = {
    "entry_high": [10, 20, 40],
    "exit_low":   [5, 10, 20],
    "trend_ma":   [60, 120, 200],
    "stop_pct":   [0.07, 0.10],
}   # = 3*3*3*2 = 54 조합

# Walk-forward 구간: (학습시작, 학습끝, 검증시작, 검증끝)
FOLDS = [
    ("2020-01-01", "2022-12-31", "2023-01-01", "2023-12-31"),
    ("2021-01-01", "2023-12-31", "2024-01-01", "2024-12-31"),
    ("2022-01-01", "2024-12-31", "2025-01-01", "2025-12-31"),
    ("2023-01-01", "2025-12-31", "2026-01-01", "2026-12-31"),
]
cost = CostModel()
BT = dict(capital=100_000_000, weight=0.10, max_positions=10)
# --------------------------

def load():
    data = {}
    for t in UNIVERSE:
        try:
            df = fdr.DataReader(t, START)
            if not df.empty and len(df) > 100:
                data[t] = df[["High", "Low", "Close"]]
        except Exception as e:
            print(f"  {t} 실패: {e}")
    return data

def main():
    print(f"[1] 데이터 로드... (시작 {START})")
    data = load()
    print(f"    {len(data)}종목 로드 완료\n")

    # ---- (A) 파라미터 민감도 / 과최적화 점검 ----
    print("[2] 파라미터 민감도 (전체구간, 상위/하위 5개):")
    gdf = grid_search(data, GRID, cost, **BT)
    cols = ["entry_high","exit_low","trend_ma","stop_pct","CAGR_%","MDD_%","Sharpe","n_trades","profit_factor"]
    print("  --- 상위 5 ---")
    print(gdf[cols].head().to_string(index=False))
    print("  --- 하위 5 ---")
    print(gdf[cols].tail().to_string(index=False))
    valid = gdf[gdf["score"] > -999]
    if len(valid):
        print(f"\n  → 유효 조합 {len(valid)}개의 Sharpe 분포: "
              f"평균 {valid['Sharpe'].mean():.2f}, 최저 {valid['Sharpe'].min():.2f}, 최고 {valid['Sharpe'].max():.2f}")
        print("    (조합 대부분이 비슷하게 양호하면 '견고', 1~2개만 튀면 '과최적화 의심')")

    # ---- (B) 학습/검증 분리 ----
    print(f"\n[3] 학습/검증 분리 (기준일 {SPLIT}):")
    io = in_out_sample(data, SPLIT, GRID, cost, **BT)
    b = io["best"]
    print(f"  학습구간 최적 파라미터: H{b.entry_high}/L{b.exit_low}/MA{b.trend_ma}/Stop{b.stop_pct}")
    def line(tag, m):
        print(f"   {tag:10s} CAGR {m.get('CAGR_%')}% | MDD {m.get('MDD_%')}% | "
              f"Sharpe {m.get('Sharpe')} | 매매 {m.get('n_trades')} | PF {m.get('profit_factor')}")
    line("학습(IS)", io["in_sample"])
    line("검증(OOS)", io["out_sample"])
    print("    → 검증(OOS) 성과가 학습과 비슷하면 신뢰↑, 폭락하면 과최적화.")

    # ---- (C) Walk-forward ----
    print("\n[4] Walk-forward (구간을 굴리며 재최적화→검증, OOS 성과만):")
    wf = walk_forward(data, GRID, FOLDS, cost, **BT)
    print(wf.to_string(index=False))
    if len(wf):
        print(f"\n  → OOS 평균 CAGR {wf['OOS_CAGR_%'].mean():.2f}%, 평균 Sharpe {wf['OOS_Sharpe'].mean():.2f}")
        print("    매 구간 OOS가 꾸준히 +면 실전성↑. 들쭉날쭉하면 시장 상황에 민감한 전략.")

    print("\n[결론 읽는 법]")
    print(" - 민감도: 좋은 조합이 '넓게' 분포해야 안전")
    print(" - OOS:    학습 대비 성과 하락폭이 작아야 함")
    print(" - WF:     대부분 구간에서 플러스여야 실거래 후보")

if __name__ == "__main__":
    main()
