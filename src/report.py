# -*- coding: utf-8 -*-
"""
report.py
페이퍼 트레이딩 현황을 HTML 리포트로 생성한다.
- KIS 실제 모의계좌 잔고(잔고조회 API) + 로컬 5전략(multi_paper_state.json)
- 종목별: 보유수량·진입가/매입가·현재가·등락률·평가손익·수익률
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


def _cls(x):
    return "pos" if x >= 0 else "neg"


def kis_real_block(bal, names, prices):
    cash = bal.get("cash", 0.0)
    rows = ""
    hold = 0.0
    for p in sorted(bal.get("positions", []), key=lambda x: -x["eval_amt"]):
        hold += p["eval_amt"]
        chg = prices.get(p["code"], (p["cur_price"], 0.0))[1]
        rows += (f"<tr><td>{p['code']}</td><td>{p['name'] or names.get(p['code'], p['code'])}</td>"
                 f"<td class='r'>{p['qty']:,}</td><td class='r'>{p['avg_price']:,.0f}</td>"
                 f"<td class='r'>{p['cur_price']:,.0f}</td><td class='r {_cls(chg)}'>{chg:+.2f}%</td>"
                 f"<td class='r'>{p['eval_amt']:,.0f}</td><td class='r {_cls(p['pnl'])}'>{p['pnl']:+,.0f}</td>"
                 f"<td class='r {_cls(p['ret_pct'])}'>{p['ret_pct']:+.2f}%</td></tr>")
    equity = cash + hold
    ret = (equity / CAP_KIS - 1) * 100
    head = (f"<h3>듀얼모멘텀 (KIS 실제 모의계좌) "
            f"<span class='sub'>총평가 {equity:,.0f} <span class='{_cls(ret)}'>({ret:+.2f}%)</span> "
            f"· 보유 {len(bal.get('positions', []))}종목 · 예수금 {cash:,.0f}</span></h3>")
    if not bal.get("positions"):
        return head + "<p class='muted'>보유 종목 없음(현금 보유)</p>"
    return head + ("<table><tr><th>코드</th><th>종목명</th><th>수량</th><th>매입가</th>"
                   "<th>현재가</th><th>등락률</th><th>평가금액</th><th>평가손익</th><th>수익률</th></tr>"
                   + rows + "</table>")


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
        rows += (f"<tr><td>{code}</td><td>{names.get(code, code)}</td>"
                 f"<td class='r'>{shares:,}</td><td class='r'>{pos['entry_price']:,.0f}</td>"
                 f"<td class='r'>{cur:,.0f}</td><td class='r {_cls(chg)}'>{chg:+.2f}%</td>"
                 f"<td class='r'>{val:,.0f}</td><td class='r {_cls(pnl)}'>{pnl:+,.0f}</td>"
                 f"<td class='r {_cls(ret)}'>{ret:+.2f}%</td></tr>")
    equity = cash + holdval
    tot_ret = (equity / capital - 1) * 100
    head = (f"<h3>{title} <span class='sub'>총자산 {equity:,.0f} "
            f"<span class='{_cls(tot_ret)}'>({tot_ret:+.2f}%)</span> · 보유 {len(positions)}종목 · 현금 {cash:,.0f}</span></h3>")
    if not positions:
        return head + "<p class='muted'>보유 종목 없음</p>"
    return head + ("<table><tr><th>코드</th><th>종목명</th><th>수량</th><th>진입가</th>"
                   "<th>현재가</th><th>등락률</th><th>평가금액</th><th>평가손익</th><th>수익률</th></tr>"
                   + rows + "</table>")


def main():
    today = dt.date.today().strftime("%Y-%m-%d")
    local = json.load(open(LOCAL_STATE, encoding="utf-8")) if os.path.exists(LOCAL_STATE) else {}

    tickers = set()
    for st in local.values():
        tickers |= set(st.get("positions", {}).keys())

    # KIS 실제 잔고 시도
    kis_bal = None
    try:
        import kis_api
        if kis_api.APP_KEY:
            kis_bal = kis_api.get_balance_parsed()
            tickers |= {p["code"] for p in kis_bal.get("positions", [])}
            print(f"[리포트] KIS 실제 잔고 조회 성공: 보유 {len(kis_bal['positions'])}종목")
    except Exception as e:
        print(f"[리포트] KIS 실잔고 조회 실패({e}) → 로컬 추정으로 대체")

    print(f"[리포트] {len(tickers)}종목 시세 조회 중...")
    names = name_map()
    prices = latest_prices(tickers)

    blocks = ""
    blocks += "<h2>KIS 모의계좌 (실제 잔고)</h2>"
    if kis_bal is not None:
        blocks += kis_real_block(kis_bal, names, prices)
    elif os.path.exists(LIVE_STATE):
        live = json.load(open(LIVE_STATE, encoding="utf-8"))
        blocks += "<p class='muted'>※ API 조회 실패 — 로컬 추정값</p>"
        blocks += strat_block("듀얼모멘텀(로컬추정)", live.get("positions", {}), prices, names,
                              CAP_KIS, live.get("cash", CAP_KIS))
    else:
        blocks += "<p class='muted'>KIS 데이터 없음</p>"

    blocks += "<h2>로컬 5전략 비교 (각 2천만)</h2>"
    order = sorted(local.keys(),
                   key=lambda k: (local[k].get("equity_history", [[None, CAP_LOCAL]])[-1][1]),
                   reverse=True)
    for nm in order:
        st = local[nm]
        blocks += strat_block(nm, st.get("positions", {}), prices, names,
                              CAP_LOCAL, st.get("cash", CAP_LOCAL))

    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<title>트레이딩 리포트 {today}</title>
<style>
body{{font-family:'Malgun Gothic',sans-serif;margin:24px;color:#222;background:#fafafa}}
h1{{color:#1F3A5F}} h2{{color:#2E75B6;border-bottom:2px solid #2E75B6;padding-bottom:4px;margin-top:28px}}
h3{{margin:18px 0 6px}} .sub{{font-size:13px;font-weight:normal;color:#555}}
table{{border-collapse:collapse;width:100%;background:#fff;margin-bottom:8px;font-size:13px}}
th,td{{border:1px solid #ddd;padding:6px 8px}} th{{background:#1F3A5F;color:#fff}}
.r{{text-align:right}} .pos{{color:#c0392b}} .neg{{color:#1f6fb2}} .muted{{color:#999}}
</style></head><body>
<h1>트레이딩 현황 리포트</h1>
<p class="muted">생성: {today} · 등락률=전일대비 · 빨강=이익/상승, 파랑=손실/하락</p>
{blocks}
</body></html>"""

    os.makedirs(OUT_DIR, exist_ok=True)
    for fn in [f"{OUT_DIR}/report_{today}.html", f"{OUT_DIR}/report_latest.html"]:
        with open(fn, "w", encoding="utf-8") as f:
            f.write(html)
    print(f"[리포트] 저장 완료 -> {OUT_DIR}/report_{today}.html")


if __name__ == "__main__":
    main()
