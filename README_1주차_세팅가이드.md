# 1주차 — 개발 환경 세팅 가이드 (Windows 기준)

> 목표: 코드를 실행할 수 있는 환경을 만들고, 핵심 전략 1개를 확정한다.
> 예상 소요: 하루 3시간 × 약 5일. 천천히 따라오시면 됩니다.

---

## Day 1 — 프로그램 4개 설치 (약 1시간)

순서대로 설치하세요. 모두 무료입니다.

1. **Python** — https://www.python.org/downloads/
   - "Download Python 3.x" 클릭 → 설치 시작 화면에서 **`Add python.exe to PATH` 체크 필수!** (이거 빼먹으면 나중에 명령어가 안 먹습니다)
2. **VSCode** (코드 편집기) — https://code.visualstudio.com/
   - 설치 후 좌측 확장(Extensions) 아이콘 → "Python" 확장 설치
3. **Git** (버전 관리) — https://git-scm.com/download/win
   - 옵션은 전부 기본값(Next)으로 두면 됩니다.
4. (선택) **GitHub 계정** — https://github.com/ — 나중에 코드 백업/이력 관리용

### 설치 확인
시작 메뉴에서 **"PowerShell"** 또는 **"명령 프롬프트(cmd)"** 를 열고 입력:
```powershell
python --version
git --version
```
버전 숫자가 뜨면 성공입니다.

---

## Day 2 — 프로젝트 폴더 & 가상환경 (약 1시간)

가상환경(venv)은 "이 프로젝트 전용 파이썬 상자"입니다. 다른 작업과 패키지가 섞이지 않게 해 줍니다.

PowerShell을 열고 **이 프로젝트 폴더로 이동**한 뒤 명령을 입력하세요:
```powershell
# 1) 프로젝트 폴더로 이동 (경로는 본인 환경에 맞게)
cd "$env:USERPROFILE\Claude\Projects\Stock_TickerFind"

# 2) 가상환경 생성 (.venv 폴더가 만들어짐)
python -m venv .venv

# 3) 가상환경 활성화
.\.venv\Scripts\Activate.ps1
```

> ⚠️ 활성화 시 "스크립트 실행 권한" 오류가 나면 PowerShell에 아래 한 줄 입력 후 다시 시도:
> ```powershell
> Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
> ```

활성화에 성공하면 줄 맨 앞에 **`(.venv)`** 가 붙습니다. 앞으로 작업할 때는 항상 이 상태여야 합니다.

---

## Day 3 — 패키지 설치 & 환경 점검 (약 1시간)

`(.venv)` 가 붙은 상태에서:
```powershell
# 패키지 한 번에 설치
pip install -r requirements.txt

# 환경 점검 스크립트 실행
python src\check_env.py
```
모든 줄이 `[ OK ]` 로 뜨면 환경 세팅 완료입니다. 🎉

---

## Day 4 — 첫 데이터 받아보기 (약 1시간)

```powershell
python src\fetch_data.py
```
- 삼성전자(005930) 일봉을 받아 이동평균·RSI·20일 돌파신호를 계산합니다.
- `data\005930.csv` (데이터)와 `data\005930.png` (차트)가 생성됩니다.
- `src\fetch_data.py` 상단의 `TICKER` 값을 바꿔 다른 종목도 시험해 보세요.

이 단계의 핵심은 "데이터가 내 손에서 코드로 흐른다"를 체감하는 것입니다.

---

## Day 5 — 핵심 전략 1개 확정 (약 1시간)

전략 카탈로그(27개) 중 **딱 1개**만 고릅니다. 1주차에는 규칙이 명확한 것이 좋습니다.

권장 후보(제 추론):
- **#1 / #5 돌파형 (20일 신고가/돈치안 채널)** — 규칙이 가장 단순해 코딩·디버깅이 쉬움 → **입문 1순위 추천**
- **#9 이동평균 눌림목** — 추세장에서 직관적
- **#15 RSI 과매도 반등** — 횡보장 대응, 단 추세장 주의

확정 후 다음을 한 문장씩 **숫자로** 적어두면 2주차(규칙 명문화) 준비 끝:
1. 진입 조건 (예: "종가가 직전 20일 최고가 돌파")
2. 청산 조건 (예: "종가가 10일 최저가 이탈")
3. 손절 조건 (예: "매수가 대비 -7%")
4. 1회 매수 비중 (예: "총자산의 10%")

---

## 폴더 구조
```
Stock_TickerFind/
├─ README_1주차_세팅가이드.md   ← 이 파일
├─ requirements.txt            ← 설치할 패키지 목록
├─ .gitignore                  ← 깃 제외 목록(API키 보호)
├─ src/
│  ├─ check_env.py             ← 환경 점검
│  └─ fetch_data.py            ← 데이터 수집 + 지표 계산
└─ data/                       ← (자동 생성) csv·차트 저장
```

## 막히면
어느 단계든 에러 메시지를 그대로 복사해서 저에게 주시면 바로 풀어드리겠습니다.
"활성화가 안 돼요", "OK가 안 떠요" 처럼 단계 번호만 알려주셔도 됩니다.
