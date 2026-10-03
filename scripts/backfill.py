"""과거 가격 백필 : 지정 기간의 일별 당일가를 이력 CSV에 채움 (최초 1회 권장)

  python scripts/backfill.py --days 365
  python scripts/backfill.py --start 2025-10-01 --end 2026-09-30
"""
from __future__ import annotations

import argparse
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from collect import fetch_all  # noqa: E402
import store  # noqa: E402

KST = timezone(timedelta(hours=9))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=365)
    ap.add_argument("--start")
    ap.add_argument("--end")
    ap.add_argument("--sleep", type=float, default=0.3)
    args = ap.parse_args()
    cfg = store.load_config()

    end = date.fromisoformat(args.end) if args.end else datetime.now(KST).date() - timedelta(days=1)
    start = date.fromisoformat(args.start) if args.start else end - timedelta(days=args.days - 1)

    buf, filled, d = [], 0, start
    while d <= end:
        if d.weekday() < 6:  # 일요일은 조사 없음
            try:
                rows = store.rows_from_groups(d.isoformat(), fetch_all(d.isoformat(), cfg, None))
            except Exception as e:
                print(f"{d} 실패: {e}")
                rows = []
            if rows:
                buf.extend(rows)
                filled += 1
            print(f"{d} {len(rows):,}행")
            time.sleep(args.sleep)
        if len(buf) > 5000:
            store.upsert_history(buf)
            buf = []
        d += timedelta(days=1)
    total = store.upsert_history(buf)
    print(f"백필 완료: 조사일 {filled:,}일, 이력 누적 {total:,}행")
    return 0


if __name__ == "__main__":
    sys.exit(main())
