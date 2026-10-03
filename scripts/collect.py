"""매일 수집 : 가장 최근 조사일의 부류별 소매·도매 가격을 받아 저장

사용
  python scripts/collect.py                 # 오늘(KST)부터 최대 7일 거슬러 최신 조사일 탐색
  python scripts/collect.py --date 2026-10-02
  python scripts/collect.py --fixture tests/fixtures/2026-10-02  # 오프라인 테스트

종료 코드 : 0 = 새 데이터 저장 또는 변경 없음, 1 = 오류
GitHub Actions 출력 : new_data=true|false
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from kamis import fetch_category, parse_items  # noqa: E402
import store  # noqa: E402

KST = timezone(timedelta(hours=9))


def fetch_all(date: str, cfg: dict, fixture: Path | None) -> list[dict]:
    groups = []
    for cls in cfg["product_classes"]:
        for cat in cfg["categories"]:
            if fixture:
                f = fixture / f"{cls['code']}_{cat['code']}.json"
                code, items = parse_items(json.loads(f.read_text(encoding="utf-8"))) if f.exists() else ("001", [])
            else:
                code, items = fetch_category(date, cat["code"], cls["code"], cfg.get("country_code", ""))
            if code not in ("000", "001"):
                print(f"  ! {cls['name']} {cat['name']} error_code={code}")
            # 당일 가격이 하나도 없으면 미발표로 간주
            if not any(it["prices"].get("today") is not None for it in items):
                items = []
            groups.append({
                "cls_code": cls["code"], "cls_name": cls["name"],
                "cat_code": cat["code"], "cat_name": cat["name"],
                "items": items,
            })
    return groups


def set_output(name: str, value: str) -> None:
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as f:
            f.write(f"{name}={value}\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date")
    ap.add_argument("--lookback", type=int, default=7)
    ap.add_argument("--fixture", type=Path)
    args = ap.parse_args()
    cfg = store.load_config()

    if args.date:
        candidates = [args.date]
    else:
        today = datetime.now(KST).date()
        candidates = [(today - timedelta(days=i)).isoformat() for i in range(args.lookback)]

    for d in candidates:
        print(f"조회 {d}")
        groups = fetch_all(d, cfg, args.fixture)
        n = sum(len(g["items"]) for g in groups)
        if n == 0:
            print("  데이터 없음 (주말·공휴일 또는 미발표)")
            continue
        prev = store.load_snapshot(d)
        new_rows = store.rows_from_groups(d, groups)
        if prev and store.rows_from_groups(d, prev["groups"]) == new_rows:
            print(f"  {d} 이미 수집됨, 변경 없음")
            set_output("new_data", "false")
            set_output("date", d)
            return 0
        store.save_snapshot(d, groups, datetime.now(KST).isoformat(timespec="seconds"))
        total = store.upsert_history(new_rows)
        print(f"  저장 {d}: {n}개 시리즈 (이력 누적 {total:,}행)")
        set_output("new_data", "true")
        set_output("date", d)
        return 0

    print("최근 조사일 데이터를 찾지 못함")
    set_output("new_data", "false")
    return 0


if __name__ == "__main__":
    sys.exit(main())
