# -*- coding: utf-8 -*-
"""
run_backtest.py
3주차 실행 러너: 여러 종목(유니버스)에 돌파 전략을 비용 반영하여 백테스트.
실행:  python src/run_backtest.py

- 기본은 시가총액 상위 대형주 15개로 빠르게 검증.
- 코스피200 전체로 돌리려면 아래 USE_KOSPI200 = True 로 바꾸세요(시간 더 걸림).
"""
import FinanceDataReader as fdr
from strategy import BreakoutParams
from backtest import CostModel, backtest_portfolio

# ---------- 설정 ----------
START = "2020-01-01"
USE_KOSPI200 = False   # True 로 바꾸면 코스피200 전체 (pykrx 필요, 느림)

UNIVERSE = [
    "005930",  # 삼성전자
    "000660",  # SK하이닉스
    "035420",  # NAVER
    "035720",  # 카카오
    "005380",  # 현대차
    "000270",  # 기아
    "051910",  # LG화학
    "006400",  # 삼성SDI
    "005490",  # POSCO홀딩스
    "068270",  # 셀트리온
    "105560",  # KB금융
    "055550",  # 신한지주
    "012330",  # 현대모비스
    "028260",  # 삼성물산
    "066570",  # LG전자
]

params = BreakoutParams(entry_high=20, exit_low=10, trend_ma=60, stop_pct=0.07)
cost = CostModel()  # 수수료 0.015%, 거래세 0.20%, 슬리피지 0.10%
# --------------------------

def load_universe():
    tickers = UNIVERSE
    if USE_KOSPI200:
        try:
            from pykrx import stock
            import datetime
            today = datetime.datetime.now().strftime("%Y%m%d")
            tickers = stock.get_index_portfolio_deposit_file("1028")  # 코스피200
            print(f"  코스피200 {len(tickers)}종목 로드")
        except Exception as e:
            print(f"  코스피200 로드 실패({e}) → 기본 15종목 사용")
            tickers = UNIVERSE

    data = {}
    for t in tickers:
        try:
            df = fdr.DataReader(t, START)
            if not df.empty and len(df) > 100:
                data[t] = df[["High", "Low", "Close"]]
        except Exception as e:
            print(f"  {t} 로드 실패: {e}")
    return data

def main():
    print(f"[1] 유니버스 데이터 로드 중... (시작 {START})")
    data = load_universe()
    print(f"    로드 완료: {len(data)}종목")

    print("[2] 비용 반영 포트폴리오 백테스트 실행...")
    res = backtest_portfolio(data, params, cost,
                             capital=100_000_000, weight=0.10, max_positions=10)

    m = res["metrics"]
    print("\n[3] 성과 지표 (비용 반영):")
    for k, v in m.items():
        print(f"   {k:16s}: {v}")

    trades = res["trades"]
    print(f"\n[4] 매매 내역 (최근 10건 / 총 {len(trades)}건):")
    if len(trades):
        print(trades.tail(10).to_string(index=False))

    # ---- 자산곡선 차트 ----
    try:
        import matplotlib.pyplot as plt
        # 한글 폰트 설정 (Windows 기본 'Malgun Gothic')
        plt.rcParams["font.family"] = "Malgun Gothic"
        plt.rcParams["axes.unicode_minus"] = False
        eq = res["equity"]
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(11, 7), sharex=True,
                                       gridspec_kw={"height_ratios": [3, 1]})
        ax1.plot(eq.index, eq.values / 1e8, linewidth=1.2)
        ax1.set_title("Portfolio Equity (억원)"); ax1.grid(alpha=0.3)
        dd = (eq / eq.cummax() - 1) * 100
        ax2.fill_between(dd.index, dd.values, 0, alpha=0.4)
        ax2.set_title("Drawdown (%)"); ax2.grid(alpha=0.3)
        plt.tight_layout()
        import os; os.makedirs("data", exist_ok=True)
        plt.savefig("data/portfolio_equity.png", dpi=120)
        print("\n[5] 자산곡선 차트 저장 -> data/portfolio_equity.png")
    except Exception as e:
        print(f"\n[5] 차트 생략: {e}")

    print("\n해석 가이드: MDD(최대낙폭)와 Sharpe(위험 대비 수익)를 수익률만큼 중요하게 보세요.")
    print("           다음(4주차)은 이 결과가 '우연이 아닌지' out-of-sample로 검증합니다.")

if __name__ == "__main__":
    main()
