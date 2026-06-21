# -*- coding: utf-8 -*-
"""
check_env.py
1주차 환경 점검용 스크립트.
가상환경을 활성화한 뒤 `python src/check_env.py` 로 실행하세요.
모든 패키지가 OK로 뜨면 환경 세팅이 끝난 것입니다.
"""
import sys

print("=" * 50)
print(f"Python 버전: {sys.version.split()[0]}")
print(f"실행 위치  : {sys.executable}")   # .venv 안의 python 이어야 정상
print("=" * 50)

packages = [
    "pandas", "numpy", "matplotlib",
    "FinanceDataReader", "pykrx", "backtesting",
]

all_ok = True
for name in packages:
    try:
        mod = __import__(name)
        ver = getattr(mod, "__version__", "?")
        print(f"[ OK ] {name:20s} {ver}")
    except Exception as e:
        all_ok = False
        print(f"[FAIL] {name:20s} -> {e}")

print("=" * 50)
print("모든 패키지 정상! 다음 단계(fetch_data.py)로 가세요." if all_ok
      else "일부 패키지 실패. requirements.txt 재설치가 필요합니다.")
