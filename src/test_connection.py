# -*- coding: utf-8 -*-
"""
test_connection.py
KIS API 인증이 실제로 되는지 확인하는 '읽기 전용' 테스트 (주문 없음).
실행:  python src\\test_connection.py
"""
import kis_api

def main():
    print("설정:", kis_api.config_summary().replace("\n", " | "))
    try:
        token = kis_api.get_access_token()
        print(f"[1] 토큰 발급 성공 (앞 10자리: {token[:10]}...)")
    except Exception as e:
        print(f"[1] 토큰 발급 실패: {e}")
        print("    → 앱키/앱시크릿/환경(paper)·계좌 설정을 다시 확인하세요.")
        return
    try:
        price = kis_api.get_price("005930")
        print(f"[2] 시세 조회 성공 — 삼성전자 현재가: {price:,}원")
        print("\n✅ 인증·연결 정상! 이제 모의투자 주문 테스트로 넘어갈 수 있습니다.")
    except Exception as e:
        print(f"[2] 시세 조회 실패: {e}")

if __name__ == "__main__":
    main()
