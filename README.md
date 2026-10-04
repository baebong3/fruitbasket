# 과일바구니 가격 추적 서버

KAMIS Open API(부류별 일별 가격)로 과일·채소 소매·도매 가격을 매일 수집해 이력을 쌓고,
리포트(HTML 대시보드, 마크다운, 엑셀)를 자동 생성하는 GitHub Actions 기반 서버

## 동작

| 시각 | 작업 |
|---|---|
| 매일 18:07 KST | `collect.py` 최신 조사일 가격 수집 (주말·공휴일이면 직전 조사일 확인, 중복이면 건너뜀) |
| 새 데이터가 있을 때 | `report.py` 리포트 생성 → 검증 게이트 통과 시 저장 |
| 이어서 | `data/`·`docs/`·`reports/` 변경분만 커밋·푸시 |

## 첫 화면 구성

1. **장보기 지수** (0~100) - 평년 대비 50% + 1년 중 위치 30% + 1주 추세 20%. 80 이상 아주 좋은 날, 60 좋은 날, 40 보통, 20 비싼 날, 그 아래 미룰 날
2. **오늘 장을 본다면** - 품목군(과일·잎채소·열매채소·뿌리채소·양념채소)마다 평년보다 싼 품목으로 짠 4인 가구 1주일 장바구니, 비용과 절약액, 만들 수 있는 요리
3. **오늘의 알뜰 요리** - 주재료가 평년보다 싼 레시피 3개 (전체는 recipes.html)
4. **장바구니 지수와 공개 물가지표 비교** - 고정 장바구니 지수(평년 = 100), 국가데이터처 신선식품·신선과실·신선채소·농산물·CPI 전년동월비, 장보기 지수 1년 추이
5. 품목별 가격(소매·도매), 가격 추이, 지난 리포트

## 산출물

| 경로 | 내용 |
|---|---|
| `data/prices.csv` | 누적 이력 (날짜 × 구분 × 품목·품종·등급, 당일가). 엑셀에서 바로 열리는 UTF-8 BOM |
| `data/status.json` | 마지막 실행 시각·결과(new_data / unchanged / no_data / error)·누적 행 수. 매 실행마다 갱신되어 저장소 활동이 유지됨 |
| `data/snapshots/YYYY-MM-DD.json` | 조사일별 원자료 (전일·1주·1개월·1년 전·평년 가격 포함) |
| `docs/index.html` | 최신 대시보드 (GitHub Pages 첫 화면, JS 없이도 표시) |
| `docs/reports/YYYY-MM-DD.html` | 날짜별 보관본 |
| `docs/items/<품목>-<품종>.html` | 품목별 상세 페이지 - 소매·도매 오늘 가격, 1개월~1년 추이 그래프, 월별 가격, 1년 범위 안의 현재 위치, 개조식 리포트 |
| `docs/recipes.html` | 오늘의 알뜰 요리 - 주재료가 평년보다 싼 레시피와 재료비(조사 가격 × 수량), 1인분 비용 |
| `docs/basket.html` | 과일바구니 장바구니 지수 - 4인 가구 1주일 과일·채소 18종 고정 장바구니 비용(평년 = 100), 1년 추이, 국가데이터처 신선식품지수와 비교 |
| `docs/fruitbasket_prices.xlsx` | 최신 소매·도매 표 + 최근 90일 이력 |
| `reports/LATEST.md`, `reports/YYYY-MM-DD.md` | GitHub에서 바로 읽는 요약 |

## 처음 설정 (1회)

1. **Secrets 등록** : Settings → Secrets and variables → Actions → New repository secret
   - `KAMIS_CERT_KEY` : KAMIS 인증키
   - `KAMIS_CERT_ID` : KAMIS 요청자 ID
   - `KAMIS_PROXY_URL` (선택) : KAMIS가 해외 IP(GitHub 러너는 미국)를 막을 때 쓰는 중계 주소.
     설정하면 KAMIS와 같은 쿼리스트링을 이 주소로 보냄 (기존 Supabase Edge Function 또는 Cloudflare Worker 활용)
2. **Actions 권한** : Settings → Actions → General → Workflow permissions → *Read and write permissions*
3. **첫 실행** : Actions → 「과거 가격 백필 (수동)」 → Run workflow (기본 365일). 추이 그래프가 바로 채워짐
4. **Pages** : Settings → Pages → Source *Deploy from a branch*, Branch `main` / `/docs`
   - 비공개 저장소의 Pages는 GitHub Pro 이상에서만 가능. 무료 계정이면 저장소를 공개로 바꾸거나
     `reports/LATEST.md`를 GitHub에서 바로 보면 됨

## 설정 바꾸기 (`config.yml`)

- `categories` : 수집 부류 (기본 과일류 400, 채소류 200)
- `product_classes` : 소매 01 / 도매 02
- `grade` : 가격 수준 기준 (평년 대비 %) - 앱의 GREEN/YELLOW/ORANGE/RED 기준과 맞춰 조정
- `rank_priority` : 품목·품종별 대표 등급 우선순위 (상품 → L과 → 특 → 중품 …; 포도처럼 상품 등급이 없는 품목도 빠지지 않음)
- `trend_days`, `trend_items` : 추이 그래프 기간·품목 수

## 레시피·장바구니·외부 지표 손보기 (`data/`)

- `recipes.yml` : 레시피. 재료는 KAMIS 품목명(+품종)과 수량·단위로 적음. `main: true` 재료가 평년보다 싸면 그날 추천에 오름
- `staples.yml` : 1개 평균 무게(kg 가격 ↔ 개 수량 환산)와 계란·두부 등 KAMIS 비조사 재료의 참고가
- `basket.yml` : 장바구니 구성(품목·품종 우선순위·수량). 바꾸면 지수의 과거 추이도 같은 구성으로 다시 계산됨
- `external.yml` : 국가데이터처 소비자물가동향 수치(전년동월비·전월비). 매월 초 발표되면 값만 고쳐 커밋

## 로컬 실행

```bash
pip install -r requirements.txt
export KAMIS_CERT_KEY=... KAMIS_CERT_ID=...
python scripts/collect.py            # 최신 조사일
python scripts/collect.py --date 2026-10-02
python scripts/backfill.py --days 90
python scripts/report.py

# KAMIS 없이 테스트 (가상 데이터)
python tests/make_fixture.py /tmp/fx 1
python scripts/collect.py --date 2026-10-02 --fixture /tmp/fx
```

## 앱과 연결

앱(React Native)은 Pages의 정적 파일을 읽어도 됨 :
`https://<사용자>.github.io/fruitbasket/` 의 `reports/LATEST.md`나 `data/snapshots/` JSON을
Supabase에 적재하거나, Actions 마지막 단계에 Supabase upsert를 추가하는 방식으로 확장 가능

자료 출처: 한국농수산식품유통공사(aT) KAMIS 농산물유통정보
