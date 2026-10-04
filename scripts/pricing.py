"""소매 가격표와 수량 환산 : 레시피·장바구니 비용 계산의 공통 기반"""
from __future__ import annotations

import re
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import yaml

import store
from theme import split_name

DATA = store.ROOT / "data"
COUNT_UNITS = {"개", "포기", "쪽", "장", "대", "줌", "통", "단", "속", "마리", "봉", "송이"}


def load_yaml(name: str):
    with open(DATA / name, encoding="utf-8") as f:
        return yaml.safe_load(f)


def parse_unit(u: str) -> tuple[Decimal, str] | None:
    """'10개' -> (10, '개'), '1kg' -> (1000, 'g'), '100g' -> (100, 'g'), '1포기' -> (1, '포기')"""
    m = re.match(r"^\s*([\d.]+)\s*(kg|g|ml|L|개|포기|통|단|속|마리|봉|송이)\s*$", u)
    if not m:
        return None
    n, unit = Decimal(m.group(1)), m.group(2)
    if unit == "kg":
        return n * 1000, "g"
    if unit == "L":
        return n * 1000, "ml"
    return n, unit


def rint(x: Decimal) -> int:
    return int(x.quantize(Decimal(1), ROUND_HALF_UP))


class PriceBook:
    """오늘 소매 가격표 : (품목명, 품종) -> 대표 등급 가격·단위·평년·1년 전"""

    def __init__(self, snap: dict, cfg: dict, history_idx: dict | None = None):
        from items import pick_rank, fill_from_history
        prio = cfg.get("rank_priority") or ["상품"]
        st = load_yaml("staples.yml")
        self.piece_g: dict = st.get("piece_g", {})
        self.staples: dict = st.get("staples", {})
        self.by_name: dict = {}  # name -> list of entries(kind)
        groups: dict = {}
        for g in snap["groups"]:
            if g["cls_code"] != "01":
                continue
            for it in g["items"]:
                if it["prices"].get("today") is None:
                    continue
                groups.setdefault((it["item_code"], it["kind_code"]), []).append((g, it))
        for (ic, kc), cands in groups.items():
            g = cands[0][0]
            it = pick_rank([x[1] for x in cands], prio)
            p = it["prices"]
            if history_idx is not None:
                sid = "|".join(["01", ic, kc, it["rank_code"]])
                p = fill_from_history(p, history_idx.get(sid, {}), snap["date"])
            pu = parse_unit(it["unit"])
            if not pu:
                continue
            name, kind = split_name(it["item_name"], it["kind_name"])
            e = {"name": name, "kind": kind, "rank": it["rank"], "unit": it["unit"], "n": pu[0], "u": pu[1],
                 "today": p["today"], "avg": p.get("avg"), "y1": p.get("y1"), "m1": p.get("m1"), "w1": p.get("w1"),
                 "cat": g["cat_name"], "key": (ic, kc)}
            self.by_name.setdefault(name, []).append(e)

    def find(self, name: str, kind: str = "") -> dict | None:
        cands = self.by_name.get(name) or []
        if not cands:
            return None
        if kind:
            kinds = kind if isinstance(kind, list) else [kind]
            for k in kinds:
                for e in cands:
                    if e["kind"] == k:
                        return e
                for e in cands:
                    if k in e["kind"] or e["kind"] in k:
                        return e
            if isinstance(kind, list):  # 선호 품종이 모두 없으면 가장 싼 품종
                kind = ""
            else:
                return None
        # 품종 미지정 : 오늘 기준 g 당 가격이 가장 싼 품종
        def per_unit(e):
            c = self.cost(e, Decimal(100), "g", "today")
            return c if c is not None else Decimal(10**12)
        return min(cands, key=per_unit)

    def cost(self, e: dict, qty: Decimal, unit: str, which: str = "today") -> Decimal | None:
        price = e.get(which)
        if price is None:
            return None
        price = Decimal(price)
        pg = self.piece_g.get(e["name"])
        if e["u"] in ("g", "ml"):
            per_g = price / e["n"]
            if unit in ("g", "ml"):
                return per_g * qty
            if unit in COUNT_UNITS and pg:
                return per_g * Decimal(pg) * qty
            return None
        # 개·포기 단위 가격
        per_piece = price / e["n"]
        if unit in COUNT_UNITS:
            if unit in ("쪽", "장", "대", "줌") and e["u"] != unit and pg:
                # 가격 단위는 '개'인데 레시피는 쪽·장 등 세부 단위 : 1개 무게 대비 비율은 알 수 없어 g 환산 불가 -> 그대로 1단위로 봄
                return per_piece * qty
            return per_piece * qty
        if unit in ("g", "ml") and pg:
            return per_piece * qty / Decimal(pg)
        return None

    def staple_cost(self, name: str, qty: Decimal, unit: str) -> int | None:
        s = self.staples.get(name)
        if not s:
            return None
        if unit in ("g",) and "per_g" in s:
            return rint(Decimal(str(s["per_g"])) * qty)
        if unit in ("ml",) and "per_ml" in s:
            return rint(Decimal(str(s["per_ml"])) * qty)
        if s.get("unit") == unit or unit in ("개", "모", "장", "공기"):
            return rint(Decimal(str(s["price"])) * qty)
        return None
