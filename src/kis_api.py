# -*- coding: utf-8 -*-
"""
kis_api.py
6주차: 한국투자증권(KIS) Open API 클라이언트 (최소 기능).

지원: 토큰발급(캐시) · 현재가 조회 · 잔고 조회 · 현금주문(매수/매도)
환경: KIS_ENV=paper(모의투자, 기본) / real(실전)

⚠️ 안전 원칙
  - 기본 환경은 '모의투자(paper)'. 실전 전환은 의도적으로만.
  - 주문 함수는 DRY_RUN이 True면 '실제 전송하지 않고' 의도만 반환한다.
  - API 키는 .env에서만 읽는다. 코드/깃에 절대 넣지 않는다(.gitignore 처리됨).

※ 엔드포인트·tr_id는 KIS Developers 명세 기준이며, 포털에서 최신값을 한 번 더
  확인하시길 권합니다(당사 공지 없이 업데이트될 수 있음).
  공식 샘플: https://github.com/koreainvestment/open-trading-api
"""
import os
import json
import time
import requests

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

# ---------- 환경 설정 ----------
ENV = os.getenv("KIS_ENV", "paper")          # paper | real
APP_KEY = os.getenv("KIS_APP_KEY", "")
APP_SECRET = os.getenv("KIS_APP_SECRET", "")
ACCOUNT = os.getenv("KIS_ACCOUNT", "")        # 계좌 앞 8자리
PRODUCT = os.getenv("KIS_PRODUCT", "01")      # 계좌 뒤 2자리 (종합 01)

BASE = ("https://openapivts.koreainvestment.com:29443" if ENV == "paper"
        else "https://openapi.koreainvestment.com:9443")

TOKEN_CACHE = "data/kis_token.json"

# tr_id: 환경별 주문 코드 (모의=V, 실전=T)
TR_ORDER = {
    ("paper", "buy"): "VTTC0802U", ("paper", "sell"): "VTTC0801U",
    ("real",  "buy"): "TTTC0802U", ("real",  "sell"): "TTTC0801U",
}
TR_BALANCE = "VTTC8434R" if ENV == "paper" else "TTTC8434R"
TR_PRICE = "FHKST01010100"


def _headers(tr_id: str, hashkey: str = None) -> dict:
    h = {
        "content-type": "application/json; charset=utf-8",
        "authorization": f"Bearer {get_access_token()}",
        "appkey": APP_KEY, "appsecret": APP_SECRET,
        "tr_id": tr_id, "custtype": "P",
    }
    if hashkey:
        h["hashkey"] = hashkey
    return h


# ---------- 토큰 (캐시: 1분당 1회 발급 제한 회피) ----------
def get_access_token() -> str:
    if os.path.exists(TOKEN_CACHE):
        try:
            with open(TOKEN_CACHE, encoding="utf-8") as f:
                c = json.load(f)
            if c.get("expire_at", 0) > time.time() + 600:  # 10분 여유
                return c["access_token"]
        except Exception:
            pass

    url = f"{BASE}/oauth2/tokenP"
    body = {"grant_type": "client_credentials", "appkey": APP_KEY, "appsecret": APP_SECRET}
    r = requests.post(url, json=body, timeout=10)
    r.raise_for_status()
    data = r.json()
    token = data["access_token"]
    expires_in = int(data.get("expires_in", 86400))
    os.makedirs(os.path.dirname(TOKEN_CACHE), exist_ok=True)
    with open(TOKEN_CACHE, "w", encoding="utf-8") as f:
        json.dump({"access_token": token, "expire_at": time.time() + expires_in}, f)
    return token


def _hashkey(body: dict) -> str:
    url = f"{BASE}/uapi/hashkey"
    h = {"content-type": "application/json", "appkey": APP_KEY, "appsecret": APP_SECRET}
    r = requests.post(url, headers=h, data=json.dumps(body), timeout=10)
    r.raise_for_status()
    return r.json()["HASH"]


# ---------- 현재가 ----------
def get_price(code: str) -> int:
    url = f"{BASE}/uapi/domestic-stock/v1/quotations/inquire-price"
    params = {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": code}
    r = requests.get(url, headers=_headers(TR_PRICE), params=params, timeout=10)
    r.raise_for_status()
    return int(r.json()["output"]["stck_prpr"])   # 주식 현재가


# ---------- 잔고 ----------
def get_balance() -> dict:
    url = f"{BASE}/uapi/domestic-stock/v1/trading/inquire-balance"
    params = {
        "CANO": ACCOUNT, "ACNT_PRDT_CD": PRODUCT,
        "AFHR_FLPR_YN": "N", "OFL_YN": "", "INQR_DVSN": "02",
        "UNPR_DVSN": "01", "FUND_STTL_ICLD_YN": "N",
        "FNCG_AMT_AUTO_RDPT_YN": "N", "PRCS_DVSN": "01",
        "CTX_AREA_FK100": "", "CTX_AREA_NK100": "",
    }
    r = requests.get(url, headers=_headers(TR_BALANCE), params=params, timeout=10)
    r.raise_for_status()
    return r.json()


# ---------- 현금 주문 ----------
def order_cash(code: str, qty: int, side: str, price: int = 0,
               ord_dvsn: str = "01", dry_run: bool = True) -> dict:
    """
    side: 'buy' | 'sell'
    ord_dvsn: '00'=지정가, '01'=시장가(기본)
    dry_run=True면 실제 전송하지 않고 의도만 반환(안전 기본값).
    """
    assert side in ("buy", "sell")
    body = {
        "CANO": ACCOUNT, "ACNT_PRDT_CD": PRODUCT, "PDNO": code,
        "ORD_DVSN": ord_dvsn, "ORD_QTY": str(int(qty)),
        "ORD_UNPR": str(int(price)),
    }
    intent = {"env": ENV, "side": side, "code": code, "qty": int(qty),
              "ord_dvsn": ord_dvsn, "price": int(price)}

    if dry_run:
        return {"dry_run": True, "intent": intent}

    url = f"{BASE}/uapi/domestic-stock/v1/trading/order-cash"
    tr_id = TR_ORDER[(ENV, side)]
    r = requests.post(url, headers=_headers(tr_id, _hashkey(body)),
                      data=json.dumps(body), timeout=10)
    r.raise_for_status()
    return {"dry_run": False, "intent": intent, "response": r.json()}


def config_summary() -> str:
    masked = (APP_KEY[:4] + "***") if APP_KEY else "(없음)"
    return (f"ENV={ENV} | BASE={BASE}\n"
            f"APP_KEY={masked} | ACCOUNT={'설정됨' if ACCOUNT else '(없음)'}-{PRODUCT}")
