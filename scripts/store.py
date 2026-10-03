"""데이터 저장 : 스냅샷 JSON + 누적 이력 CSV"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SNAP = DATA / "snapshots"
HISTORY = DATA / "prices.csv"

FIELDS = [
    "date", "cls_code", "cls_name", "cat_code", "cat_name",
    "item_code", "item_name", "kind_code", "kind_name",
    "rank_code", "rank", "unit", "price",
]


def load_config() -> dict:
    with open(ROOT / "config.yml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def series_id(row: dict) -> str:
    return "|".join(str(row[k]) for k in ("cls_code", "item_code", "kind_code", "rank_code"))


def save_snapshot(date: str, groups: list[dict], fetched_at: str) -> Path:
    SNAP.mkdir(parents=True, exist_ok=True)
    p = SNAP / f"{date}.json"
    p.write_text(
        json.dumps({"date": date, "fetched_at": fetched_at, "groups": groups},
                   ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    return p


def load_snapshot(date: str) -> dict | None:
    p = SNAP / f"{date}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def latest_snapshot_date() -> str | None:
    files = sorted(SNAP.glob("*.json"))
    return files[-1].stem if files else None


def rows_from_groups(date: str, groups: list[dict]) -> list[dict]:
    rows = []
    for g in groups:
        for it in g["items"]:
            price = it["prices"].get("today")
            if price is None:
                continue
            rows.append({
                "date": date, "cls_code": g["cls_code"], "cls_name": g["cls_name"],
                "cat_code": g["cat_code"], "cat_name": g["cat_name"],
                "item_code": it["item_code"], "item_name": it["item_name"],
                "kind_code": it["kind_code"], "kind_name": it["kind_name"],
                "rank_code": it["rank_code"], "rank": it["rank"],
                "unit": it["unit"], "price": price,
            })
    return rows


def read_history() -> list[dict]:
    if not HISTORY.exists():
        return []
    with open(HISTORY, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r["price"] = int(r["price"])
    return rows


def upsert_history(new_rows: list[dict]) -> int:
    """같은 날짜·시리즈는 새 값으로 교체. 엑셀에서 바로 열리도록 UTF-8 BOM 저장"""
    rows = read_history()
    key = lambda r: (r["date"], series_id(r))
    merged = {key(r): r for r in rows}
    for r in new_rows:
        merged[key(r)] = r
    out = sorted(merged.values(), key=lambda r: (r["date"], r["cls_code"], r["cat_code"],
                                                 r["item_code"], r["kind_code"], r["rank_code"]))
    DATA.mkdir(parents=True, exist_ok=True)
    with open(HISTORY, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for r in out:
            w.writerow({k: r[k] for k in FIELDS})
    return len(out)
