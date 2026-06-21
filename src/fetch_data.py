# -*- coding: utf-8 -*-
"""
fetch_data.py
1주차 실습용: 종목 1개의 일봉을 받아와 기본 지표를 계산하고 저장/시각화한다.

실행:  python src/fetch_data.py
바꿔볼 것: TICKER, START 값을 바꿔가며 여러 종목을 확인해 보세요.
  - 삼성전자 005930 / SK하이닉스 000660 / 카카오 035720 / NAVER 035420
  - 미국: AAPL, MSFT, TSLA 등도 같은 코드로 동작합니다.
"""
import os
import pandas as pd
import FinanceDataReader as fdr

# ---------- 설정 ----------
TICKER = "005930"      # 삼성전자
START  = "2022-01-01"  # 조회 시작일
# --------------------------

def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """RSI(상대강도지수) 계산. 30 이하 과매도 / 70 이상 과매수."""
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def main():
    print(f"[1] {TICKER} 데이터 다운로드 중... (시작일 {START})")
    df = fdr.DataReader(TICKER, START)
    if df.empty:
        print("데이터가 비었습니다. 티커/네트워크를 확인하세요.")
        return

    # ---------- 지표 계산 ----------
    df["SMA20"] = df["Close"].rolling(20).mean()      # 20일 이동평균
    df["SMA60"] = df["Close"].rolling(60).mean()      # 60일 이동평균
    df["High20"] = df["High"].rolling(20).max()       # 20일 신고가(돌파 전략 기준선)
    df["RSI14"] = rsi(df["Close"], 14)

    # ---------- 가장 단순한 신호 예시 ----------
    # "오늘 종가가 직전 20일 최고가를 돌파" = 돌파 매수 후보 (1주차 맛보기용)
    df["BreakoutSignal"] = df["Close"] > df["High20"].shift(1)

    print("\n[2] 최근 5일 미리보기:")
    cols = ["Close", "SMA20", "SMA60", "High20", "RSI14", "BreakoutSignal"]
    print(df[cols].tail().round(1))

    # ---------- 저장 ----------
    os.makedirs("data", exist_ok=True)
    out_csv = f"data/{TICKER}.csv"
    df.to_csv(out_csv, encoding="utf-8-sig")
    print(f"\n[3] 저장 완료 -> {out_csv}  (총 {len(df)}행)")

    # ---------- 시각화 (선택) ----------
    try:
        import matplotlib.pyplot as plt
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(11, 7), sharex=True,
                                       gridspec_kw={"height_ratios": [3, 1]})
        ax1.plot(df.index, df["Close"], label="Close", linewidth=1)
        ax1.plot(df.index, df["SMA20"], label="SMA20", linewidth=0.9)
        ax1.plot(df.index, df["SMA60"], label="SMA60", linewidth=0.9)
        # 돌파 신호 표시
        sig = df[df["BreakoutSignal"]]
        ax1.scatter(sig.index, sig["Close"], marker="^", s=20, label="Breakout")
        ax1.legend(); ax1.set_title(f"{TICKER}  price & signals")
        ax2.plot(df.index, df["RSI14"], linewidth=0.9)
        ax2.axhline(70, linestyle="--", linewidth=0.7)
        ax2.axhline(30, linestyle="--", linewidth=0.7)
        ax2.set_title("RSI(14)")
        plt.tight_layout()
        out_png = f"data/{TICKER}.png"
        plt.savefig(out_png, dpi=120)
        print(f"[4] 차트 저장 -> {out_png}")
    except Exception as e:
        print(f"[4] 차트 생략(matplotlib 오류): {e}")

if __name__ == "__main__":
    main()
