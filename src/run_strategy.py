# -*- coding: utf-8 -*-
"""
run_strategy.py
2주차 실행 러너: 종목 1개에 돌파 전략을 적용해 '매매 내역'과 '간이 성과'를 출력.
실행:  python src/run_strategy.py
※ 비용 미반영. 규칙이 실제로 매매를 만들어내는지 눈으로 확인하는 단계.
"""
import FinanceDataReader as fdr
from strategy import BreakoutParams, backtest_single

# ---------- 설정 ----------
TICKER = "005930"
START = "2020-01-01"
params = BreakoutParams(entry_high=20, exit_low=10, trend_ma=60, stop_pct=0.07)
# --------------------------

def main():
    print(f"[1] {TICKER} 데이터 로드 (시작 {START})")
    df = fdr.DataReader(TICKER, START)
    if df.empty:
        print("데이터 없음. 티커/네트워크 확인.")
        return

    print(f"[2] 돌파 전략 적용 (파라미터: {params})")
    result = backtest_single(df, params)
    trades, summary = result["trades"], result["summary"]

    print("\n[3] 매매 내역 (최근 10건):")
    if len(trades):
        print(trades.tail(10).to_string(index=False))
    else:
        print("  해당 기간 매매 없음 (조건/기간을 바꿔보세요).")

    print("\n[4] 간이 성과 요약  ※비용 미반영:")
    for k, v in summary.items():
        print(f"   {k:18s}: {v}")
    print("\n해석 팁: win_rate(승률)와 avg_return(평균수익)을 함께 보세요.")
    print("        승률이 낮아도 손익비가 크면 수익이 날 수 있습니다. 정밀 평가는 3~4주차.")

if __name__ == "__main__":
    main()
