# GitHub Actions 자동화 가이드 (PC 없이 클라우드 자동 실행)

PC를 켜둘 필요 없이 GitHub 서버가 평일마다 자동 실행합니다.
- **KIS 모의주문** (듀얼모멘텀): 평일 15:05 KST
- **로컬 5전략 + 리포트 생성**: 평일 16:05 KST
- **리포트는 웹페이지**로 휴대폰·어디서든 열람 (GitHub Pages)

> 키는 코드가 아니라 GitHub Secrets에 저장되니 안전합니다.
> 저장소는 **공개(Public)** 를 권장합니다 — 리포트 웹페이지(Pages)가 무료로 되고,
> 코드엔 민감정보가 없습니다(키는 Secrets). 비공개로 하면 Pages는 유료입니다.

---

## 1단계 — GitHub 저장소 만들고 코드 올리기
GitHub에서 새 저장소(예: `stock-trading`) 생성(Public). 그다음 PC 터미널에서
프로젝트 폴더로 이동해(아래 경로는 본인 환경) 업로드:

```powershell
cd "$env:USERPROFILE\Claude\Projects\Stock_TickerFind"
git init
git add .
git commit -m "초기 업로드"
git branch -M main
git remote add origin https://github.com/<본인계정>/stock-trading.git
git push -u origin main
```

`.gitignore`가 `.env`(키)와 토큰·csv를 제외하므로 **키는 올라가지 않습니다.**

## 2단계 — Secrets / Variables 등록
저장소 → **Settings → Secrets and variables → Actions**

**Secrets**(비밀, "New repository secret"):
- `KIS_APP_KEY` = 모의투자 앱키
- `KIS_APP_SECRET` = 모의투자 앱시크릿
- `KIS_ACCOUNT` = 50194148 (계좌 앞 8자리)
- `KIS_PRODUCT` = 01

**Variables**(공개값, "Variables" 탭 → "New variable"):
- `KIS_LIVE` = `0`  (처음엔 0=시뮬레이션. 나중에 실제 모의주문은 `1`로 변경)

## 3단계 — GitHub Pages 켜기 (리포트 열람용)
저장소 → **Settings → Pages**
- Source: **Deploy from a branch**
- Branch: **main**, 폴더: **/docs** → Save

잠시 뒤 리포트 주소가 생깁니다:
`https://<본인계정>.github.io/stock-trading/`
→ 매일 16:05 갱신되는 리포트를 휴대폰·어디서든 이 주소로 봅니다.
(docs 폴더는 첫 Paper 실행 후 생성되므로, 4단계 수동 실행 후 Pages가 활성화됩니다.)

## 4단계 — 동작 테스트 (수동 실행)
저장소 → **Actions** 탭 → "Paper + Report" 선택 → **Run workflow** 클릭.
1~2분 뒤 초록 체크가 뜨고, `docs/index.html`이 생기면 Pages 주소로 리포트 확인.
"KIS Mock Trade"도 같은 방식으로 수동 실행해 로그를 확인하세요.

## 5단계 — 실제 모의주문 전환 (선택, 나중에)
며칠 시뮬레이션 로그를 확인한 뒤, 실제 KIS 모의계좌로 주문을 보내려면:
- Variables의 `KIS_LIVE`를 `1`로 변경
- ⚠️ 그 전에 저장소의 `data/live_state.json`을 비워(삭제 후 커밋) 로컬·실제를 초기화

---

## 알아둘 점
- **cron은 정시보다 몇 분~십수 분 늦을 수 있습니다**(무료 러너 특성). 그래서 KIS를
  15:05로 잡아 15:30 마감 전 여유를 뒀습니다. 더 빠르게/늦게 원하면 yml의 cron을 조정.
- 종가 기반 전략이라 장중(15:05) 실행 시 '당일 종가'가 아직 확정 전입니다(근사). 모의
  관찰 단계엔 충분하지만, 정밀 체결을 원하면 추후 '예약주문' 방식으로 고도화 필요.
- 상태(state)·리포트는 매 실행 후 저장소에 자동 커밋되어 다음 날로 이어집니다.
- KIS 키 변경 시 Secrets만 업데이트하면 됩니다(코드 수정 불필요).
