"""장보기 지수와 오늘의 추천 장바구니

장보기 지수(0~100, 높을수록 사기 좋은 날)
  = 0.5 × 평년 점수 + 0.3 × 1년 위치 점수 + 0.2 × 추세 점수
  평년 점수   : 장바구니 지수(평년 = 100)가 70 이면 100점, 130 이면 0점 (선형)
  1년 위치 점수: 최근 1년 일별 장바구니 비용 가운데 오늘이 싼 쪽에 있을수록 높음 (분위 역순)
  추세 점수   : 1주 전보다 비용이 5% 내렸으면 100점, 5% 올랐으면 0점 (선형)
과거 시계열은 그날 기준 1년 위치·추세로만 계산 (평년가는 조사일 당일 값만 받기 때문)
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from items import grade_for, line_chart
from pricing import PriceBook, rint
from theme import GRADES, GRADE_SHORT, ACC, GOLD, UP, DOWN, badge, chg_span, esc, face_svg, pct, sp, won, label_of

LEVELS = [(80, "장보기 아주 좋은 날", "#19613E"), (60, "장보기 좋은 날", "#2FA36B"), (40, "보통인 날", "#D9A62E"),
          (20, "비싼 날", "#E07A3A"), (0, "장보기 미룰 날", "#D2495A")]

# 추천 장바구니 : 품목군별 기본 수량 (4인 가구 1주일 기준) 과 대체 가능 품목군
GROUPS = {
    "과일": {"items": ["사과", "배", "감귤", "포도", "바나나", "오렌지", "키위", "파인애플", "멜론", "수박", "망고", "블루베리", "레몬", "아보카도", "복숭아", "단감", "딸기", "참외", "자두", "체리"], "pick": 3,
           "qty": {"g": 1000, "개": 5, "default_g": 1000}},
    "잎채소": {"items": ["상추", "시금치", "깻잎", "열무", "얼갈이배추", "미나리", "부추", "알배기배추", "배추", "양배추", "쑥갓", "청경채"], "pick": 3,
            "qty": {"g": 300, "개": 1, "포기": 1, "default_g": 300}},
    "열매채소": {"items": ["오이", "호박", "가지", "토마토", "방울토마토", "피망", "파프리카", "풋고추", "브로콜리"], "pick": 3,
             "qty": {"g": 500, "개": 3, "default_g": 500}},
    "뿌리채소": {"items": ["무", "당근", "양파", "감자", "고구마", "생강"], "pick": 2, "qty": {"g": 1000, "개": 1, "default_g": 1000}},
    "양념채소": {"items": ["파", "깐마늘(국산)", "붉은고추", "고춧가루", "건고추"], "pick": 2, "qty": {"g": 300, "개": 1, "default_g": 300}},
}


def q1(x) -> Decimal:
    return Decimal(x).quantize(Decimal("0.1"), ROUND_HALF_UP)


def clamp(x: float, lo: float = 0, hi: float = 100) -> float:
    return max(lo, min(hi, x))


def level_of(score: int) -> tuple[str, str]:
    for th, name, color in LEVELS:
        if score >= th:
            return name, color
    return LEVELS[-1][1], LEVELS[-1][2]


def position_score(series: list[tuple[str, int]], d: str, cost: int) -> float | None:
    """d 기준 직전 1년 비용 분포에서 cost 가 싼 쪽에 있을수록 높음 (0~100)"""
    start = (date.fromisoformat(d) - timedelta(days=365)).isoformat()
    vals = [v for dd, v in series if start <= dd < d]
    if len(vals) < 20:
        return None
    above = sum(1 for v in vals if v > cost)
    return above * 100 / len(vals)


def trend_score(series_map: dict, d: str, cost: int) -> float | None:
    base = date.fromisoformat(d)
    for back in range(7, 12):
        dd = (base - timedelta(days=back)).isoformat()
        if dd in series_map:
            chg = (cost - series_map[dd]) / series_map[dd] * 100
            return clamp(50 - chg * 10)
    return None


def compute_index(bk: dict) -> dict:
    series = bk["series"]
    smap = dict(series)
    today_cost = bk["today"]
    asof = series[-1][0] if series else None
    idx = bk["idx_avg_all"]
    level_score = clamp((130 - float(idx)) / 60 * 100) if idx is not None else None
    pos = position_score(series, asof, today_cost) if asof else None
    tr = trend_score(smap, asof, today_cost) if asof else None
    parts = [(level_score, 0.5), (pos, 0.3), (tr, 0.2)]
    avail = [(v, w) for v, w in parts if v is not None]
    score = int(Decimal(sum(v * w for v, w in avail) / sum(w for _, w in avail)).quantize(Decimal(1), ROUND_HALF_UP)) if avail else None
    # 과거 시계열 (위치 0.6 + 추세 0.4)
    hist = []
    for d, c in series:
        p, t = position_score(series, d, c), trend_score(smap, d, c)
        if p is None:
            continue
        v = p * 0.6 + (t if t is not None else 50) * 0.4
        hist.append((d, int(Decimal(v).quantize(Decimal(1), ROUND_HALF_UP))))
    name, color = level_of(score) if score is not None else ("-", ACC)
    return {"score": score, "name": name, "color": color, "level_score": level_score, "pos_score": pos, "trend_score": tr,
            "history": hist, "week_change": pct(today_cost, smap.get(next((k for k in (
                (date.fromisoformat(asof) - timedelta(days=b)).isoformat() for b in range(7, 12)) if k in smap), ""), None)) if asof else None}


def gauge_svg(score: int | None, color: str, size: int = 220) -> str:
    """반원 게이지 : 0(왼쪽) ~ 100(오른쪽), 구간색 띠 + 바늘"""
    import math
    W, H, cx, cy, r = size, size * 0.70, size / 2, size * 0.56, size * 0.42
    def pt(v: float, rad: float) -> tuple[float, float]:
        a = math.pi * (1 - v / 100)
        return cx + rad * math.cos(a), cy - rad * math.sin(a)
    def arc(v0: float, v1: float, col: str) -> str:
        x0, y0 = pt(v0, r); x1, y1 = pt(v1, r)
        return f'<path d="M{x0:.1f},{y0:.1f} A{r:.1f},{r:.1f} 0 0 1 {x1:.1f},{y1:.1f}" stroke="{col}" stroke-width="{size*0.085:.1f}" fill="none" stroke-linecap="butt"/>'
    bands = [(0, 20, "#D2495A"), (20, 40, "#E07A3A"), (40, 60, "#D9A62E"), (60, 80, "#2FA36B"), (80, 100, "#19613E")]
    out = [f'<svg viewBox="0 0 {W} {H:.0f}" class="gauge" role="img" aria-label="장보기 지수">']
    out += [arc(a, b, c) for a, b, c in bands]
    if score is not None:
        x, y = pt(score, r - size * 0.01)
        out.append(f'<line x1="{cx:.1f}" y1="{cy:.1f}" x2="{x:.1f}" y2="{y:.1f}" stroke="#1B1F24" stroke-width="3" stroke-linecap="round"/>')
        out.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{size*0.035:.1f}" fill="#1B1F24"/>')
        out.append(f'<text x="{cx:.1f}" y="{cy - size*0.12:.1f}" text-anchor="middle" class="gv" fill="{color}">{score}</text>')
    out.append(f'<text x="{pt(0, r)[0]:.1f}" y="{cy + size*0.09:.1f}" class="ax">비쌈</text>')
    out.append(f'<text x="{pt(100, r)[0]:.1f}" y="{cy + size*0.09:.1f}" class="ax" text-anchor="end">쌈</text>')
    out.append("</svg>")
    return "".join(out)


def recommend_basket(book: PriceBook, g_cfg: dict, recipes: list[dict]) -> dict:
    """품목군마다 평년보다 싼 순으로 골라 4인 가구 1주일 장바구니를 짬"""
    uses: dict = defaultdict(list)  # label -> recipe names
    for r in recipes:
        for i in r["ingredients"]:
            if i["main"] and r["pick"]:
                uses[i["label"]].append(r["name"])
    rows, skipped = [], []
    for grp, spec in GROUPS.items():
        cands = []
        for name in spec["items"]:
            for e in book.by_name.get(name, []):
                base = pct(e["today"], e["avg"] or e["y1"])
                if base is None:
                    continue
                cands.append((base, e))
        cands.sort(key=lambda t: t[0])
        n, used_names = 0, set()
        for base, e in cands:
            grade = grade_for(base, g_cfg)
            if grade not in ("GREEN", "YELLOW") or n >= spec["pick"] or e["name"] in used_names:
                continue
            used_names.add(e["name"])
            if grade == "YELLOW" and base > 0:
                continue
            q = spec["qty"]
            if e["u"] in ("g", "ml"):
                qty, unit = q["g"], "g"
            elif e["u"] == "포기":
                qty, unit = q.get("포기", 1), "포기"
            else:
                qty, unit = q.get("개", 1), "개"
                if e["name"] in ("수박", "멜론", "파인애플"):
                    qty = 1
            c = book.cost(e, Decimal(qty), unit, "today")
            ca = book.cost(e, Decimal(qty), unit, "avg") or book.cost(e, Decimal(qty), unit, "y1")
            if c is None:
                continue
            label = label_of(e["name"], e["kind"])
            rows.append({"group": grp, "label": label, "qty": qty, "unit": unit, "rank": e["rank"], "price": e["today"], "price_unit": e["unit"],
                         "cost": rint(c), "cost_avg": rint(ca) if ca is not None else None, "base": base, "grade": grade,
                         "key": e["key"], "uses": uses.get(label, [])[:3]})
            n += 1
        if n == 0:
            skipped.append(grp)
    total = sum(r["cost"] for r in rows)
    total_avg = sum(r["cost_avg"] for r in rows if r["cost_avg"] is not None)
    return {"rows": rows, "total": total, "total_avg": total_avg, "saving": total_avg - total, "skipped": skipped}


def hero_html(sh: dict, bk: dict, s: dict, rel: str) -> str:
    score = sh["score"]
    comp = []
    for nm, v in (("평년 대비", sh["level_score"]), ("1년 중 위치", sh["pos_score"]), ("최근 1주 추세", sh["trend_score"])):
        comp.append(f'<div><div class="k">{nm}</div><div class="x2">{int(round(v)) if v is not None else "-"}<small>점</small></div></div>')
    wk = sh["week_change"]
    sub = (f'장바구니 비용 <b>{won(bk["today"])}원</b> (평년 가격이면 {won(bk["cost_avg_all"])}원) · {esc(s.get("sub", ""))}'
           if bk.get("cost_avg_all") is not None else f'장바구니 비용 <b>{won(bk["today"])}원</b> · {esc(s.get("sub", ""))}')
    return (f'<section class="hero2"><div class="g"><div class="eyebrow">오늘의 장보기 지수</div>{gauge_svg(score, sh["color"])}'
            f'<div class="gl" style="color:{sh["color"]}">{esc(sh["name"])}</div></div>'
            f'<div class="ht"><div class="eyebrow">Today\'s Market</div><h1>{esc(s["headline"])}</h1><p class="hsub">{sub}</p>'
            f'<div class="comp">{"".join(comp)}</div>'
            f'<p class="note">장보기 지수 = 평년 대비 50% + 1년 중 위치 30% + 1주 추세 20%. 100에 가까울수록 과일·채소를 사기 좋은 날</p></div></section>')


def index_history_html(sh: dict) -> str:
    h = [(d, v) for d, v in sh["history"]]
    if len(h) < 2:
        return ""
    return (f'<h3>장보기 지수 추이 <span class="muted">최근 1년 · 과거는 1년 위치·1주 추세로 계산 (평년 대비는 조사일만)</span></h3>'
            f'<div class="cd">{line_chart(h, GOLD, None, "", W=760, H=220)}</div><div class="cm">{line_chart(h, GOLD, None, "", W=400, H=220)}</div>')


def basket_html(rb: dict, rel: str, links: dict) -> str:
    rows = []
    for r in rb["rows"]:
        href = links.get(r["key"])
        nm = f'<a href="{rel}{href}">{esc(r["label"])}</a>' if href else esc(r["label"])
        use = ("<small>" + esc(", ".join(r["uses"])) + "</small>") if r["uses"] else ""
        rows.append(f'<tr><td class="g">{esc(r["group"])}</td><td class="l">{nm}{use}</td><td>{r["qty"]:g}{esc(r["unit"])}</td>'
                    f'<td class="u">{won(r["price"])}원/{esc(r["price_unit"])}</td><td><span class="n">{won(r["cost"])}</span></td>'
                    f'<td>{chg_span(r["base"])}</td><td>{badge(r["grade"], 14, False)}</td></tr>')
    tab = (f'<table class="rt rb"><thead><tr><th>구분</th><th class="l">품목</th><th>수량</th><th class="u">조사 가격</th><th>비용(원)</th><th>평년 대비</th><th>수준</th></tr></thead>'
           f'<tbody>{"".join(rows)}</tbody></table>')
    tot = (f'<div class="rc-cost big"><span>오늘 사면 <b>{won(rb["total"])}원</b></span><span>평년 가격이면 <b>{won(rb["total_avg"])}원</b></span>'
           f'<span style="color:{DOWN}">{won(rb["saving"])}원 절약</span></div>')
    skip = f'<p class="note">{esc("·".join(rb["skipped"]))}군은 오늘 평년보다 싼 품목이 없어 뺌</p>' if rb["skipped"] else ""
    return (f'<div class="card" id="todaybasket"><h2>오늘 장을 본다면<small>평년보다 싼 품목으로 짠 4인 가구 1주일 장바구니 · 품목 아래는 만들 수 있는 요리</small></h2>'
            f'{tot}<div class="tw">{tab}</div>{skip}</div>')


def headline(recs_by_cls: dict, bk: dict, sh: dict) -> tuple[str, str]:
    """오늘 상황을 한 문장으로 : 수준 + 특히 싼 품목 + 비싼 품목. 둘째 값은 보조 설명"""
    retail = recs_by_cls.get("소매") or next(iter(recs_by_cls.values()), {})
    allr = [r for rs in retail.values() for r in rs if r["base"] is not None]
    idx = bk["idx_avg_all"]
    if idx is None:
        level = "평년 비교 자료 없음"
    else:
        d = float(idx) - 100
        if d <= -10:
            level = f"과일·채소 장바구니가 평년보다 {abs(d):.0f}% 싼 날"
        elif d <= -3:
            level = "과일·채소 장바구니가 평년보다 조금 싼 날"
        elif d < 3:
            level = "과일·채소 장바구니가 평년 수준인 날"
        elif d < 10:
            level = "과일·채소 장바구니가 평년보다 조금 비싼 날"
        else:
            level = f"과일·채소 장바구니가 평년보다 {d:.0f}% 비싼 날"
    # 특히 싼 품목 : 품목명 기준 중복 제거, 평년 대비 하락폭 큰 순 3개
    seen, cheap, pricey = set(), [], []
    for r in sorted(allr, key=lambda r: r["base"]):
        if r["grade"] == "GREEN" and r["name"] not in seen and len(cheap) < 3:
            cheap.append(r["name"]); seen.add(r["name"])
    seen = set()
    for r in sorted(allr, key=lambda r: -r["base"]):
        if r["grade"] in ("RED", "ORANGE") and r["name"] not in seen and len(pricey) < 2:
            pricey.append(r["name"]); seen.add(r["name"])
    parts = []
    if cheap:
        parts.append(f"{'·'.join(cheap)}는 특히 싸고")
    if pricey:
        parts.append(f"{'·'.join(pricey)}는 평년보다 비쌈")
    elif cheap:
        parts[-1] = parts[-1].replace("싸고", "쌈")
    head = f"{level} - {' '.join(parts)}" if parts else level
    n_green = sum(1 for r in allr if r["grade"] == "GREEN")
    n_bad = sum(1 for r in allr if r["grade"] in ("RED", "ORANGE"))
    wk = sh.get("week_change")
    sub = f"비교 가능한 {len(allr):,}개 품목 중 평년보다 싼 품목 {n_green:,}개, 비싼 품목 {n_bad:,}개"
    if wk is not None:
        sub += f" · 장바구니 비용은 1주 전보다 {abs(wk):,.1f}% {'내림' if wk < 0 else '오름' if wk > 0 else '같음'}"
    return head, sub
