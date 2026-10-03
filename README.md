# 과일바구니 가격 추적 서버

KAMIS Open API(부류별 일별 가격)로 과일·채소 소매·도매 가격을 매일 수집해 이력을 쌓고,
리포트(HTML 대시보드, 마크다운, 엑셀)를 자동 생성하는 GitHub Actions 기반 서버

## 동작

| 시각 | 작업 |
|---|---|
| 매일 18:07 KST | `collect.py` 최신 조사일 가격 수집 (주말·공휴일이면 직전 조사일 확인, 중복이면 건너뜀) |
| 새 데이터가 있을 때 | `report.py` 리포트 생성 → 검증 게이트 통과 시 저장 |
| 이어서 | `data/`·`docs/`·`reports/` 변경분만 커밋·푸시 |

## 산출물

| 경로 | 내용 |
|---|---|
| `data/prices.csv` | 누적 이력 (날짜 × 구분 × 품목·품종·등급, 당일가). 엑셀에서 바로 열리는 UTF-8 BOM |
| `data/snapshots/YYYY-MM-DD.json` | 조사일별 원자료 (전일·1주·1개월·1년 전·평년 가격 포함) |
| `docs/index.html` | 최신 대시보드 (GitHub Pages 첫 화면, JS 없이도 표시) |
| `docs/reports/YYYY-MM-DD.html` | 날짜별 보관본 |
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
- `rank_filter` : 리포트에 보일 등급 (기본 상품)
- `trend_days`, `trend_items` : 추이 그래프 기간·품목 수

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

자료: KAMIS 농산물유통정보 (한국농수산식품유통공사)
