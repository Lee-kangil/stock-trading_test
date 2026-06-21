# -*- coding: utf-8 -*-
"""
report.py
페이퍼 트레이딩 현황을 HTML 리포트로 생성한다.
- 로컬 5전략(multi_paper_state.json) + KIS 듀얼모멘텀(live_state.json)
- 종목별: 보유수량·진입가·현재가·등락률(전일대비)·평가손익·수익률
실행:  python src/report.py  → data/report_YYYYMMDD.html (+ report_latest.html)
"""
import os
import json
import datetime as dt
import FinanceDataReader as fdr

LOCAL_STATE = "data/multi_paper_state.json"
LIVE_STATE = "data/live_state.json"
CAP_LOCAL = 20_000_000
CAP_KIS = 100_000_000
OUT_DIR = "data"


def name_map():
    try:
        lst = fdr.StockListing("KRX")
        code = "Code" if "Code" in lst.columns else "Symbol"
        nm = "Name" if "Name" in lst.columns else None
        if nm is None:
            return {}
        return {str(c).zfill(6): str(n) for c, n in zip(lst[code], lst[nm])}
    except Exception:
        return {}


def latest_prices(tickers):
    res = {}
    start = (dt.date.today() - dt.timedelta(days=12)).strftime("%Y-%m-%d")
    for t in tickers:
        try:
            df = fdr.DataReader(t, start)
            if len(df) >= 2:
                cur, prev = float(df["Close"].iloc[-1]), float(df["Close"].iloc[-2])
                res[t] = (cur, (cur / prev - 1) * 100)
            elif len(df) == 1:
                res[t] = (float(df["Close"].iloc[-1]), 0.0)
        except Exception:
            pass
    return res


def strat_block(title, positions, prices, names, capital, cash):
    holdval = 0.0
    rows = ""
    for code, pos in sorted(positions.items()):
        cur, chg = prices.get(code, (pos["entry_price"], 0.0))
        shares = pos["shares"]
        val = shares * cur
        holdval += val
        pnl = (cur - pos["entry_price"]) * shares
        ret = (cur / pos["entry_price"] - 1) * 100
        cc = "pos" if ret >= 0 else "neg"
        gc = "pos" if chg >= 0 else "neg"
        rows += (f"<tr><td>{code}</td><td>{names.get(code, code)}</td>"
                 f"<td class='r'>{shares:,}</td><td class='r'>{pos['entry_price']:,.0f}</td>"
                 f"<td class='r'>{cur:,.0f}</td><td class='r {gc}'>{chg:+.2f}%</td>"
                 f"<td class='r'>{val:,.0f}</td><td class='r {cc}'>{pnl:+,.0f}</td>"
                 f"<td class='r {cc}'>{ret:+.2f}%</td></tr>")
    equity = cash + holdval
    tot_ret = (equity / capital - 1) * 100
    tc = "pos" if tot_ret >= 0 else "neg"
    head = (f"<h3>{title} <span class='sub'>총자산 {equity:,.0f} "
            f"<span class='{tc}'>({tot_ret:+.2f}%)</span> · 보유 {len(positions)}종목 · 현금 {cash:,.0f}</span></h3>")
    if not positions:
        return head + "<p class='muted'>보유 종목 없음</p>"
    return head + ("<table><tr><th>코드</th><th>종목명</th><th>수량</th><th>진입가</th>"
                   "<th>현재가</th><th>등락률</th><th>평가금액</th><th>평가손익</th><th>수익률</th></tr>"
                   + rows + "</table>")


def main():
    today = dt.date.today().strftime("%Y-%m-%d")
    local = json.load(open(LOCAL_STATE, encoding="utf-8")) if os.path.exists(LOCAL_STATE) else {}
    live = json.load(open(LIVE_STATE, encoding="utf-8")) if os.path.exists(LIVE_STATE) else None

    # 모든 보유 종목 수집
    tickers = set()
    for st in local.values():
        tickers |= set(st.get("positions", {}).keys())
    if live:
        tickers |= set(live.get("positions", {}).keys())

    print(f"[리포트] {len(tickers)}종목 시세 조회 중...")
    names = name_map()
    prices = latest_prices(tickers)

    blocks = ""
    if live:
        blocks += "<h2>KIS 모의계좌 (듀얼모멘텀, 1억)</h2>"
        blocks += strat_block("듀얼모멘텀(KIS)", live.get("positions", {}), prices, names,
                              CAP_KIS, live.get("cash", CAP_KIS))
    blocks += "<h2>로컬 5전략 비교 (각 2천만)</h2>"
    # 누적수익 순 정렬
    order = sorted(local.keys(),
                   key=lambda k: (local[k].get("equity_history", [[None, CAP_LOCAL]])[-1][1]),
                   reverse=True)
    for nm in order:
        st = local[nm]
        blocks += strat_block(nm, st.get("positions", {}), prices, names,
                              CAP_LOCAL, st.get("cash", CAP_LOCAL))

    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<title>페이퍼 트레이딩 리포트 {today}</title>
<style>
body{{font-family:'Malgun Gothic',sans-serif;margin:24px;color:#222;background:#fafafa}}
h1{{color:#1F3A5F}} h2{{color:#2E75B6;border-bottom:2px solid #2E75B6;padding-bottom:4px;margin-top:28px}}
h3{{margin:18px 0 6px}} .sub{{font-size:13px;font-weight:normal;color:#555}}
table{{border-collapse:collapse;width:100%;background:#fff;margin-bottom:8px;font-size:13px}}
th,td{{border:1px solid #ddd;padding:6px 8px}} th{{background:#1F3A5F;color:#fff}}
.r{{text-align:right}} .pos{{color:#c0392b}} .neg{{color:#1f6fb2}} .muted{{color:#999}}
</style></head><body>
<h1>페이퍼 트레이딩 현황 리포트</h1>
<p class="muted">생성: {today} · 등락률=전일대비 · 빨강=이익/상승, 파랑=손실/하락</p>
{blocks}
</body></html>"""

    os.makedirs(OUT_DIR, exist_ok=True)
    for fn in [f"{OUT_DIR}/report_{today}.html", f"{OUT_DIR}/report_latest.html"]:
        with open(fn, "w", encoding="utf-8") as f:
            f.write(html)
    print(f"[리포트] 저장 완료 -> {OUT_DIR}/report_{today}.html (및 report_latest.html)")


if __name__ == "__main__":
    main()
