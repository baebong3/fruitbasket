"""오늘의 알뜰 요리 : 평년보다 싼 재료로 만드는 요리와 재료비 계산"""
from __future__ import annotations

from decimal import Decimal

import store

import icons
from items import grade_for
from pricing import PriceBook, load_yaml, rint
from theme import GRADES, badge, esc, pct, sp, won, label_of


COURSES = ["메인·한 그릇", "국·찌개", "반찬·김치", "샐러드·디저트"]
# 거의 모든 요리에 들어가는 양념 채소 : 요리끼리 비슷한지 따질 때 뺌
AROMATICS = {"파", "깐마늘(국산)", "양파", "고춧가루", "풋고추", "붉은고추", "생강"}


def course_of(tags: list[str]) -> str:
    t = set(tags)
    if t & {"메인", "한 그릇"}:
        return "메인·한 그릇"
    if t & {"국", "찌개"}:
        return "국·찌개"
    if t & {"샐러드", "디저트", "음료"}:
        return "샐러드·디저트"
    return "반찬·김치"


def _core(r: dict) -> set:
    return {i["name"] for i in r["ingredients"] if i["name"] not in AROMATICS}


def _main_name(r: dict) -> str:
    return next((i["name"] for i in r["ingredients"] if i["main"]), r["ingredients"][0]["name"])


def diversify(picks: list[dict], recent: set) -> list[dict]:
    """추천 요리 순서 : 절약 폭이 큰 순을 기본으로, 요리 종류·주재료·재료 구성이 겹치지 않게 고름.
    첫 4개는 요리 종류 4가지에서 하나씩(가능한 만큼), 주재료는 전체 목록에서 되도록 한 번씩만.
    최근 3일 첫 화면에 나온 요리는 뒤로 미뤄 날마다 바뀌게 함"""
    def base(r):
        return float(-(r["saving_pct"] or 0)) * 0.6 + float(-(r["main_base"] or 0)) * 0.4

    pool, out = list(picks), []
    while pool:
        courses = [x["course"] for x in out]
        mains = {x["main_name"] for x in out}
        cands = pool
        if len(out) < len(COURSES):
            fresh = [r for r in pool if r["course"] not in courses and r["main_name"] not in mains]
            cands = fresh or [r for r in pool if r["main_name"] not in mains] or pool

        def score(r):
            sc = base(r)
            if r["main_name"] in mains:
                sc -= 25
            sc -= 6 * courses.count(r["course"])
            if out:
                core = r["core"]
                sim = max((len(core & x["core"]) / len(core | x["core"])) if core | x["core"] else 0 for x in out)
                sc -= 20 * sim
            if r["name"] in recent:
                sc -= 15
            return sc

        best = max(cands, key=lambda r: (score(r), r["name"]))
        out.append(best)
        pool.remove(best)
    return out


def compute_recipes(book: PriceBook, g_cfg: dict, recent: set | None = None, month: int | None = None) -> list[dict]:
    out = []
    for r in load_yaml("recipes.yml"):
        ings, missing = [], []
        tot = {"today": Decimal(0), "avg": Decimal(0), "y1": Decimal(0)}
        avg_ok = y1_ok = True
        main_grade, main_base = None, None
        for ing in r["ingredients"]:
            e = book.find(ing["item"], ing.get("kind", ""))
            if e is None:
                missing.append(ing["item"])
                continue
            qty, unit = Decimal(str(ing["qty"])), ing["unit"]
            c_today = book.cost(e, qty, unit, "today")
            if c_today is None:
                missing.append(ing["item"])
                continue
            c_avg = book.cost(e, qty, unit, "avg")
            c_y1 = book.cost(e, qty, unit, "y1")
            base = pct(e["today"], e["avg"] or e["y1"])
            grade = grade_for(base, g_cfg)
            tot["today"] += c_today
            if c_avg is None:
                avg_ok = False
            else:
                tot["avg"] += c_avg
            if c_y1 is None:
                y1_ok = False
            else:
                tot["y1"] += c_y1
            if ing.get("main"):
                main_grade, main_base = grade, base
            ings.append({"label": label_of(e["name"], e["kind"]), "name": e["name"], "qty": ing["qty"], "unit": unit, "rank": e["rank"],
                         "price": e["today"], "price_unit": e["unit"], "cost": rint(c_today),
                         "cost_avg": rint(c_avg) if c_avg is not None else None, "base": base, "grade": grade,
                         "main": bool(ing.get("main")), "key": e["key"]})
        if missing or not ings:
            continue
        staples, st_cost = [], 0
        for s in r.get("staples", []) or []:
            c = book.staple_cost(s["name"], Decimal(str(s["qty"])), s["unit"])
            staples.append({"name": s["name"], "qty": s["qty"], "unit": s["unit"], "cost": c})
            st_cost += c or 0
        kamis = rint(tot["today"])
        avg_cost = rint(tot["avg"]) if avg_ok else None
        y1_cost = rint(tot["y1"]) if y1_ok else None
        saving = (avg_cost - kamis) if avg_cost is not None else None
        saving_pct = pct(kamis, avg_cost) if avg_cost else None
        out.append({
            "name": r["name"], "servings": r["servings"], "time": r.get("time", ""), "tags": r.get("tags", []),
            "ingredients": ings, "staples": staples, "seasoning": r.get("seasoning", []), "steps": r["steps"],
            "kamis_cost": kamis, "staple_cost": st_cost, "total": kamis + st_cost,
            "per_serving": rint(Decimal(kamis + st_cost) / Decimal(r["servings"])),
            "avg_cost": avg_cost, "y1_cost": y1_cost, "saving": saving, "saving_pct": saving_pct,
            "main_grade": main_grade, "main_base": main_base, "course": course_of(r.get("tags", [])),
            "in_season": not r.get("months") or month is None or month in r["months"],
        })
        rec = out[-1]
        rec["pick"] = main_grade == "GREEN" and saving_pct is not None and saving_pct < 0 and rec["in_season"]
        rec["main_name"], rec["core"] = _main_name(rec), _core(rec)
    # 추천 : 주재료가 평년보다 싸고(GREEN) 재료비가 평년보다 덜 드는 요리를 다양하게
    picks = diversify([x for x in out if x["pick"]], recent or set())
    others = sorted((x for x in out if not x["pick"]),
                    key=lambda x: (COURSES.index(x["course"]), x["saving_pct"] if x["saving_pct"] is not None else Decimal(0)))
    return picks + others


def recent_featured(asof: str, cfg: dict, days: int = 3, top: int = 3) -> set:
    """직전 조사일 며칠 동안 첫 화면(상위 top개)에 나온 요리 이름. 오래된 날부터 차례로 계산해 실제 노출 순서를 재현"""
    import json
    snaps = sorted(p for p in (store.ROOT / "data" / "snapshots").glob("*.json") if p.stem < asof)[-days:]
    shown: list[set] = []
    for p in snaps:
        snap = json.loads(p.read_text(encoding="utf-8"))
        prev = set().union(*shown) if shown else set()
        rs = compute_recipes(PriceBook(snap, cfg), cfg["grade"], prev, int(p.stem[5:7]))
        shown.append({r["name"] for r in rs[:top] if r["pick"]})
    return set().union(*shown) if shown else set()


def recipe_card(r: dict, rel: str, links: dict, full: bool) -> str:
    g = GRADES.get(r["main_grade"]) if r["main_grade"] else None
    chip = (f'<span class="rc-save" style="background:{g[2]};color:{g[3]}">평년보다 {abs(r["saving_pct"]):,.1f}% 절약</span>'
            if r["saving_pct"] is not None and r["saving_pct"] < 0 and g else
            (f'<span class="rc-save muted">평년 대비 {sp(r["saving_pct"])}</span>' if r["saving_pct"] is not None else ""))
    rows = []
    for i in r["ingredients"]:
        href = links.get(i["key"])
        nm = icons.item_icon(i["name"], 18) + (f'<a href="{rel}{href}">{esc(i["label"])}</a>' if href else esc(i["label"]))
        q = f'{i["qty"]:g}{i["unit"]}' if isinstance(i["qty"], (int, float)) else f'{i["qty"]}{i["unit"]}'
        rows.append(f'<tr><td class="l">{nm}{" <b class=main>주재료</b>" if i["main"] else ""}</td><td>{esc(q)}</td>'
                    f'<td class="u">{won(i["price"])}원/{esc(i["price_unit"])}</td><td><span class="n">{won(i["cost"])}</span></td>'
                    f'<td>{badge(i["grade"], 14, False) if i["grade"] else "-"}</td></tr>')
    for s in r["staples"]:
        c = won(s["cost"]) if s["cost"] is not None else "-"
        rows.append(f'<tr class="st"><td class="l">{esc(s["name"])}<small>참고가</small></td><td>{esc(str(s["qty"]))}{esc(s["unit"])}</td>'
                    f'<td class="u">-</td><td><span class="n">{c}</span></td><td>-</td></tr>')
    table = (f'<table class="rt{"" if full else " compact"}"><thead><tr><th class="l">재료</th><th>수량</th><th class="u">조사 가격</th><th>비용(원)</th><th>수준</th></tr></thead>'
             f'<tbody>{"".join(rows)}</tbody></table>')
    cost_line = (f'<div class="rc-cost"><span>농산물 재료비 <b>{won(r["kamis_cost"])}원</b></span>'
                 + (f'<span>기타 재료 참고가 <b>{won(r["staple_cost"])}원</b></span>' if r["staple_cost"] else "")
                 + f'<span>합계 <b>{won(r["total"])}원</b> · 1인분 {won(r["per_serving"])}원</span>'
                 + (f'<span class="sub">평년 가격이면 {won(r["avg_cost"] + r["staple_cost"])}원</span>' if r["avg_cost"] is not None else "")
                 + "</div>")
    steps = "".join(f"<li>{esc(s)}</li>" for s in r["steps"])
    seasoning = f'<p class="rc-season">양념: {esc(", ".join(r["seasoning"]))}</p>' if r["seasoning"] else ""
    meta = f'{r["servings"]}인분 · {esc(r["time"])} · {esc(" · ".join(r["tags"]))}'
    body = f'{table}{cost_line}<ol class="rc-steps">{steps}</ol>{seasoning}' if full else f'{table}{cost_line}'
    main_name = next((i["name"] for i in r["ingredients"] if i["main"]), r["ingredients"][0]["name"])
    dish = f'<span class="dish">{icons.use(icons.dish_icon(r["tags"]), 40)}{icons.item_icon(main_name, 34)}</span>'
    return (f'<article class="rc"><div class="rc-h"><span class="tl">{dish}<h3 class="serif">{esc(r["name"])}</h3></span>{chip}</div>'
            f'<div class="rc-meta">{meta}</div>{body}</article>')
