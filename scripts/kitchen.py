"""오늘의 알뜰 요리 : 평년보다 싼 재료로 만드는 요리와 재료비 계산"""
from __future__ import annotations

from decimal import Decimal

import icons
from items import grade_for
from pricing import PriceBook, load_yaml, rint
from theme import GRADES, badge, esc, pct, sp, won, label_of


def compute_recipes(book: PriceBook, g_cfg: dict) -> list[dict]:
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
            "main_grade": main_grade, "main_base": main_base,
            "pick": main_grade == "GREEN" and saving_pct is not None and saving_pct < 0,
        })
    # 추천 : 주재료가 평년보다 싸고(GREEN) 재료비 절약률이 큰 순
    out.sort(key=lambda x: (not x["pick"], x["saving_pct"] if x["saving_pct"] is not None else Decimal(0)))
    return out


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
