"""품목별 상세 페이지 : docs/items/<item>-<kind>.html

소매·도매 오늘 가격과 가격 수준, 기간별(1개월·3개월·6개월·1년) 가격 추이 그래프,
월별 요약 표, 1년 가격 범위 안의 현재 위치, 개조식 리포트
"""
from __future__ import annotations

import math
from collections import defaultdict
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

import store
from theme import (GRADES, GRADE_SHORT, UP, DOWN, INK, SUB, GOLD, ACC, badge, chg_span, esc, face_svg,
                   kdate, mdate, label_of, pct, shell, sp, split_name, won)

PERIODS = [(30, "1개월"), (90, "3개월"), (180, "6개월"), (365, "1년")]


def page_key(item_code: str, kind_code: str) -> str:
    return f"{item_code}-{kind_code}"


def page_path(item_code: str, kind_code: str) -> str:
    return f"items/{page_key(item_code, kind_code)}.html"


def mean_int(vals: list[int]) -> int:
    return int((Decimal(sum(vals)) / Decimal(len(vals))).quantize(Decimal(1), ROUND_HALF_UP))


# ---------- 그래프 ----------

def nice_ticks(lo: float, hi: float, n: int = 4) -> list[int]:
    span = hi - lo if hi > lo else max(hi, 1)
    raw = span / n
    mag = 10 ** math.floor(math.log10(raw)) if raw > 0 else 1
    step = next(s * mag for s in (1, 2, 2.5, 5, 10) if s * mag >= raw)
    start = math.floor(lo / step) * step
    ticks = []
    t = start
    while t <= hi + step * 0.001:
        if t >= lo - step * 0.001:
            ticks.append(int(round(t)))
        t += step
    return ticks


def line_chart(points: list[tuple[str, int]], color: str, ref: int | None, ref_name: str,
               W: int = 760, H: int = 300) -> str:
    """기간 가격 추이 : 오른쪽 눈금, 가로 괘선, 최고·최저·현재 라벨(겹침 회피), 평년 기준선"""
    L, R, T, B = 28, 64, 30, 34
    vals = [v for _, v in points]
    lo, hi = min(vals), max(vals)
    if ref is not None:
        lo, hi = min(lo, ref), max(hi, ref)
    pad = (hi - lo) * 0.12 or max(hi * 0.05, 1)
    lo2, hi2 = lo - pad, hi + pad
    ticks = nice_ticks(lo2, hi2)
    if ticks:
        lo2, hi2 = min(lo2, ticks[0]), max(hi2, ticks[-1])
    n = len(points)
    d0, d1 = date.fromisoformat(points[0][0]), date.fromisoformat(points[-1][0])
    span_days = max((d1 - d0).days, 1)
    x_of = lambda d: L + (W - L - R) * (date.fromisoformat(d) - d0).days / span_days
    y_of = lambda v: T + (H - T - B) * (1 - (v - lo2) / (hi2 - lo2))
    xs = [x_of(d) for d, _ in points]
    ys = [y_of(v) for v in vals]
    # 조사 공백(계절 품목 등)이 14일 넘게 벌어지면 선을 끊어서 그림
    segs, cur = [], [0]
    for i in range(1, n):
        gap = (date.fromisoformat(points[i][0]) - date.fromisoformat(points[i - 1][0])).days
        if gap > 14:
            segs.append(cur)
            cur = []
        cur.append(i)
    segs.append(cur)
    paths, areas = [], []
    for sg in segs:
        pth = " ".join(f"{'M' if j == 0 else 'L'}{xs[i]:.1f},{ys[i]:.1f}" for j, i in enumerate(sg))
        paths.append(pth)
        areas.append(f"{pth} L{xs[sg[-1]]:.1f},{H - B:.1f} L{xs[sg[0]]:.1f},{H - B:.1f} Z")
    path, area = " ".join(paths), " ".join(areas)
    out = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="가격 추이 그래프">']
    if len(segs) > 1:
        for a, b2 in zip(segs, segs[1:]):
            xm = (xs[a[-1]] + xs[b2[0]]) / 2
            out.append(f'<text x="{xm:.1f}" y="{(H - B) / 2 + T / 2:.1f}" class="ax" text-anchor="middle">조사 없음</text>')
    # 가로 괘선 + 오른쪽 눈금
    for t in ticks:
        y = y_of(t)
        out.append(f'<line x1="{L}" x2="{W - R + 6}" y1="{y:.1f}" y2="{y:.1f}" stroke="#E6E2DA" stroke-width="1"/>'
                   f'<text x="{W - R + 10}" y="{y + 4:.1f}" class="ax">{t:,}</text>')
    # x 눈금 : 월 경계 (짧은 기간은 주 단위)
    if span_days <= 45:
        d = d0
        labels = []
        while d <= d1:
            labels.append(d)
            d += timedelta(days=7)
        fmt = lambda d: f"{d.month}/{d.day}"
    else:
        labels, d = [], date(d0.year, d0.month, 1)
        while d <= d1:
            if d >= d0:
                labels.append(d)
            d = date(d.year + (d.month == 12), d.month % 12 + 1, 1)
        if span_days > 200:
            labels = [d for d in labels if d.month % 2 == 1]
        fmt = lambda d: f"{d.year}.{d.month:02d}" if d.month == 1 or d == labels[0] else f"{d.month}월"
    for d in labels:
        x = x_of(d.isoformat())
        anc = "start" if x < L + 14 else "end" if x > W - R - 14 else "middle"
        out.append(f'<line x1="{x:.1f}" x2="{x:.1f}" y1="{H - B}" y2="{H - B + 5}" stroke="#B8B2A7"/>'
                   f'<text x="{x:.1f}" y="{H - B + 19}" class="ax" text-anchor="{anc}">{fmt(d)}</text>')
    out.append(f'<line x1="{L}" x2="{W - R + 6}" y1="{H - B}" y2="{H - B}" stroke="#1B1F24" stroke-width="1"/>')
    # 평년 기준선
    if ref is not None:
        y = y_of(ref)
        out.append(f'<line x1="{L}" x2="{W - R + 6}" y1="{y:.1f}" y2="{y:.1f}" stroke="{GOLD}" stroke-width="1.4" stroke-dasharray="5 4"/>')
    out.append(f'<path d="{area}" fill="{color}" opacity=".08"/>')
    out.append(f'<path d="{path}" fill="none" stroke="{color}" stroke-width="2.2" stroke-linejoin="round" stroke-linecap="round"/>')

    # 라벨 : 최고, 최저, 현재, 평년 - 다른 라벨·선·축과 겹치지 않는 자리를 고름 (모두 겹치면 가장 덜 겹치는 자리)
    placed: list[tuple[float, float, float, float]] = []
    for t in ticks:  # 오른쪽 눈금 숫자 자리도 피함
        ty = y_of(t)
        placed.append((W - R + 8, ty - 8, W, ty + 6))
    samples = []
    for i in range(1, n):  # 선 위의 점을 촘촘히 표본화
        for t in (0.0, 0.25, 0.5, 0.75):
            samples.append((xs[i - 1] + (xs[i] - xs[i - 1]) * t, ys[i - 1] + (ys[i] - ys[i - 1]) * t))
    samples.append((xs[-1], ys[-1]))

    def box_of(x: float, y: float, text: str, anchor: str) -> tuple[float, float, float, float]:
        w = len(text) * 7.2 + 4
        x1 = x - w if anchor == "end" else x - w / 2 if anchor == "middle" else x
        return (x1, y - 11, x1 + w, y + 3)

    def penalty(b: tuple[float, float, float, float]) -> float:
        pen = 0.0
        if b[1] < 2 or b[3] > H - B - 2 or b[0] < 0 or b[2] > W - R + 4:
            pen += 200
        pen += sum(60 for p in placed if b[0] < p[2] and b[2] > p[0] and b[1] < p[3] and b[3] > p[1])
        pen += min(30, sum(1 for px, py in samples if b[0] - 2 < px < b[2] + 2 and b[1] - 2 < py < b[3] + 2))
        return pen

    def put(x: float, y: float, text: str, prefer: str, cls: str = "lab") -> None:
        """prefer = above | below : 우선 방향. 후보 자리 중 겹침이 가장 적은 곳에 배치"""
        up_c = [(x, y - 12, "middle"), (x - 8, y - 6, "end"), (x + 8, y - 6, "start"), (x, y - 28, "middle"),
                (x - 10, y - 22, "end"), (x + 10, y - 22, "start"), (x, y - 44, "middle"),
                (x - 12, y + 4, "end"), (x + 12, y + 4, "start"), (x - 34, y - 6, "end"), (x - 34, y + 10, "end")]
        dn_c = [(x, y + 20, "middle"), (x - 8, y + 14, "end"), (x + 8, y + 14, "start"), (x, y + 36, "middle"),
                (x - 10, y + 30, "end"), (x + 10, y + 30, "start"), (x, y + 52, "middle"),
                (x - 12, y + 4, "end"), (x + 12, y + 4, "start"), (x - 34, y + 10, "end"), (x - 34, y - 6, "end")]
        cands = up_c + dn_c if prefer == "above" else dn_c + up_c
        best, best_pen = None, 1e9
        for cx, cy, anc in cands:
            # 가장자리에서는 anchor 를 안쪽으로
            if anc == "middle" and cx < L + 50:
                anc = "start"
            elif anc == "middle" and cx > W - R - 50:
                anc = "end"
            bx = box_of(cx, cy, text, anc)
            pen = penalty(bx)
            if pen < best_pen:
                best, best_pen = (cx, cy, anc, bx), pen
            if pen == 0:
                break
        cx, cy, anc, bx = best
        placed.append(bx)
        out.append(f'<text x="{cx:.1f}" y="{cy:.1f}" class="{cls}" text-anchor="{anc}">{text}</text>')

    i_hi, i_lo, last = vals.index(max(vals)), vals.index(min(vals)), n - 1
    out.append(f'<circle cx="{xs[last]:.1f}" cy="{ys[last]:.1f}" r="4.5" fill="{color}" stroke="#fff" stroke-width="2"/>')
    put(xs[last], ys[last], f"현재 {vals[last]:,}", "above")
    if i_hi != last:
        out.append(f'<circle cx="{xs[i_hi]:.1f}" cy="{ys[i_hi]:.1f}" r="3.2" fill="#fff" stroke="{color}" stroke-width="2"/>')
        put(xs[i_hi], ys[i_hi], f"최고 {vals[i_hi]:,}", "above", "lab sub")
    if i_lo != last and i_lo != i_hi:
        out.append(f'<circle cx="{xs[i_lo]:.1f}" cy="{ys[i_lo]:.1f}" r="3.2" fill="#fff" stroke="{color}" stroke-width="2"/>')
        put(xs[i_lo], ys[i_lo], f"최저 {vals[i_lo]:,}", "below", "lab sub")
    if ref is not None:
        ry = y_of(ref)
        txt = f"{ref_name} {ref:,}"
        # 기준선 라벨 : 왼쪽 위 -> 왼쪽 아래 -> 오른쪽 위 -> 오른쪽 아래 중 겹치지 않는 자리
        best, best_pen = None, 1e9
        for cx, cy, anc in ((L + 2, ry - 5, "start"), (L + 2, ry + 14, "start"), (W - R + 2, ry - 5, "end"), (W - R + 2, ry + 14, "end"),
                            (W / 2, ry - 5, "middle"), (W / 2, ry + 14, "middle")):
            bx = box_of(cx, cy, txt, anc)
            pen = penalty(bx)
            if pen < best_pen:
                best, best_pen = (cx, cy, anc, bx), pen
            if pen == 0:
                break
        cx, cy, anc, bx = best
        placed.append(bx)
        out.append(f'<text x="{cx:.1f}" y="{cy:.1f}" class="lab sub" text-anchor="{anc}">{txt}</text>')
    out.append("</svg>")
    return "".join(out)


# ---------- 자료 준비 ----------

def fill_from_history(p: dict, series: dict, asof: str) -> dict:
    """KAMIS가 비워 둔 1주·1개월 전 가격(명절 휴장 등)을 가장 가까운 이전 조사일 값으로 채움"""
    if not series:
        return p
    p = dict(p)
    base = date.fromisoformat(asof)
    for key, days in (("w1", 7), ("m1", 30)):
        if p.get(key) is not None:
            continue
        for back in range(0, 7):
            d = (base - timedelta(days=days + back)).isoformat()
            if d in series:
                p[key] = series[d]
                break
    return p


def series_index(history: list[dict]) -> dict:
    idx: dict = defaultdict(dict)
    for h in history:
        idx[store.series_id(h)][h["date"]] = h["price"]
    return idx


def pick_rank(cands: list[dict], priority: list[str]) -> dict | None:
    for rk in priority:
        for it in cands:
            if it.get("rank") == rk:
                return it
    return cands[0] if cands else None


def period_points(series: dict, asof: str, days: int) -> list[tuple[str, int]]:
    start = (date.fromisoformat(asof) - timedelta(days=days)).isoformat()
    return sorted((d, v) for d, v in series.items() if start <= d <= asof)


def monthly_rows(series: dict, asof: str) -> list[dict]:
    by_m: dict = defaultdict(list)
    start = (date.fromisoformat(asof) - timedelta(days=365)).isoformat()
    for d, v in series.items():
        if start <= d <= asof:
            by_m[d[:7]].append(v)
    rows, prev = [], None
    for m in sorted(by_m):
        vals = by_m[m]
        avg = mean_int(vals)
        rows.append({"m": m, "avg": avg, "lo": min(vals), "hi": max(vals), "n": len(vals), "chg": pct(avg, prev)})
        prev = avg
    return rows


def position_pct(series_vals: list[int], cur: int) -> int | None:
    """1년 가격 범위 안의 위치 (0 = 가장 쌈, 100 = 가장 비쌈) - 분위 기준"""
    if len(series_vals) < 5:
        return None
    below = sum(1 for v in series_vals if v < cur)
    return int((Decimal(below) * 100 / Decimal(len(series_vals))).quantize(Decimal(1), ROUND_HALF_UP))


# ---------- 페이지 ----------

def price_card(cls_name: str, it: dict | None, main: bool, g_cfg: dict, unit_note: str = "") -> str:
    if it is None:
        return (f'<div class="pc{" main" if main else ""}"><div class="t"><span>{esc(cls_name)}</span></div>'
                f'<p class="empty">{esc(cls_name)} 조사 가격 없음</p></div>')
    p = it["prices"]
    today = p["today"]
    base_key = "avg" if p.get("avg") else "y1"
    base = pct(today, p.get(base_key))
    grade = grade_for(base, g_cfg)
    ref = "평년" if base_key == "avg" else "1년 전"
    vs = (f'<div class="vs">{ref} 대비 {chg_span(base, "b")} · {esc(GRADE_SHORT.get(grade, ""))}</div>' if base is not None
          else '<div class="vs">평년·1년 전 가격 없음</div>')
    mini = "".join(f'<div>{k}<b>{chg_span(pct(today, p.get(kk)), "")}</b></div>'
                   for k, kk in (("전일", "d1"), ("1주 전", "w1"), ("1개월 전", "m1"), ("1년 전", "y1")))
    return (f'<div class="pc{" main" if main else ""}"><div class="t"><span>{esc(cls_name)} · {esc(it["rank"])}</span>{badge(grade, 18)}</div>'
            f'<div class="big">{won(today)}<small>원 / {esc(it["unit"])}</small></div>{vs}<div class="mini">{mini}</div></div>')


def grade_for(p: Decimal | None, g: dict) -> str | None:
    if p is None:
        return None
    if p <= Decimal(str(g["green_max"])):
        return "GREEN"
    if p <= Decimal(str(g["yellow_max"])):
        return "YELLOW"
    if p <= Decimal(str(g["orange_max"])):
        return "ORANGE"
    return "RED"


def report_lines(name: str, retail: dict | None, whole: dict | None, r_series: dict, w_series: dict,
                 asof: str, g_cfg: dict) -> tuple[str | None, list[str]]:
    """개조식 리포트 문장과 한 줄 판단"""
    L: list[str] = []
    verdict_grade = None
    it = retail or whole
    cls = "소매" if retail else "도매"
    series = r_series if retail else w_series
    if not it:
        return None, ["조사 가격 없음"]
    p, today = it["prices"], it["prices"]["today"]
    base_key = "avg" if p.get("avg") else "y1"
    base = pct(today, p.get(base_key))
    grade = grade_for(base, g_cfg)
    verdict_grade = grade
    if base is not None:
        ref = "평년" if base_key == "avg" else "1년 전"
        word = "비쌈" if base > 0 else "쌈" if base < 0 else "같음"
        L.append(f"오늘 {cls} 가격 {today:,}원({it['unit']}, {it['rank']}) - {ref} {p[base_key]:,}원보다 {abs(base):,.1f}% {word}, 가격 수준 「{GRADES[grade][0]}」")
    else:
        L.append(f"오늘 {cls} 가격 {today:,}원({it['unit']}, {it['rank']}) - 평년·1년 전 비교 가격 없음")
    yr = period_points(series, asof, 365)
    if len(yr) >= 5:
        vals = [v for _, v in yr]
        pos = position_pct(vals, today)
        lo_d = min(yr, key=lambda t: t[1])
        hi_d = max(yr, key=lambda t: t[1])
        where = "낮은 편" if pos <= 33 else "중간" if pos <= 66 else "높은 편"
        L.append(f"최근 1년 범위 {min(vals):,}~{max(vals):,}원 (최저 {mdate(lo_d[0])}, 최고 {mdate(hi_d[0])}) - 현재는 1년 중 하위 {pos}% 위치로 {where}")
    mo = period_points(series, asof, 30)
    if len(mo) >= 2:
        c = pct(today, mo[0][1])
        trend = "상승" if c > 2 else "하락" if c < -2 else "보합"
        L.append(f"최근 1개월 흐름 {mdate(mo[0][0])} {mo[0][1]:,}원 → 오늘 {today:,}원, {sp(c)} {trend}")
    if p.get("w1") and p.get("y1"):
        L.append(f"1주 전 {p['w1']:,}원 대비 {sp(pct(today, p['w1']))}, 1년 전 {p['y1']:,}원 대비 {sp(pct(today, p['y1']))}")
    if retail and whole:
        wp = whole["prices"]
        wb = pct(wp["today"], wp.get("avg") or wp.get("y1"))
        wg = grade_for(wb, g_cfg)
        tail = f", 평년 대비 {sp(wb)} 「{GRADES[wg][0]}」" if wg else ""
        L.append(f"도매 {wp['today']:,}원({whole['unit']}, {whole['rank']}){tail}")
    return verdict_grade, L


def build_item_pages(snap: dict, cfg: dict, history: list[dict], fetched: str) -> tuple[dict, int]:
    """모든 품목·품종 페이지 생성 -> ({(item_code, kind_code): 상대경로}, 생성 수)"""
    asof = snap["date"]
    idx = series_index(history)
    g_cfg = cfg["grade"]
    prio = cfg.get("rank_priority") or ["상품"]
    by_key: dict = defaultdict(lambda: {"01": [], "02": [], "cat": "", "name": "", "kind": ""})
    for g in snap["groups"]:
        for it in g["items"]:
            if it["prices"].get("today") is None:
                continue
            k = (it["item_code"], it["kind_code"])
            e = by_key[k]
            sid = "|".join([g["cls_code"], it["item_code"], it["kind_code"], it["rank_code"]])
            it = dict(it, prices=fill_from_history(it["prices"], idx.get(sid, {}), asof))
            e[g["cls_code"]].append(it)
            e["cat"] = g["cat_name"]
            e["name"], e["kind"] = split_name(it["item_name"], it["kind_name"])
    out_dir = store.ROOT / "docs" / "items"
    out_dir.mkdir(parents=True, exist_ok=True)
    links, made = {}, 0
    for (ic, kc), e in by_key.items():
        retail = pick_rank(e["01"], prio)
        whole = pick_rank(e["02"], prio)
        main_it = retail or whole
        if main_it is None:
            continue
        label = label_of(e["name"], e["kind"])
        sid_r = "|".join(["01", ic, kc, retail["rank_code"]]) if retail else None
        sid_w = "|".join(["02", ic, kc, whole["rank_code"]]) if whole else None
        r_series = idx.get(sid_r, {}) if sid_r else {}
        w_series = idx.get(sid_w, {}) if sid_w else {}
        main_series = r_series if retail else w_series
        main_cls = "소매" if retail else "도매"
        main_p = main_it["prices"]
        base_key = "avg" if main_p.get("avg") else "y1"
        base = pct(main_p["today"], main_p.get(base_key))
        grade = grade_for(base, g_cfg)
        color = GRADES[grade][1] if grade else ACC

        # 기간별 그래프
        charts, tabs = [], []
        for i, (days, nm) in enumerate(PERIODS):
            pts = period_points(main_series, asof, days)
            chk = " checked" if days == 90 else ""
            tabs.append(f'<input type="radio" name="r" id="r{days}"{chk}>')
            if len(pts) >= 2:
                svg = line_chart(pts, color, main_p.get("avg"), "평년")
                svg_m = line_chart(pts, color, main_p.get("avg"), "평년", W=400, H=250)
                charts.append(f'<div class="chart" id="c{days}"><div class="cd">{svg}</div><div class="cm">{svg_m}</div></div>')
            else:
                charts.append(f'<div class="chart" id="c{days}"><p class="empty">이 기간의 저장된 가격이 2일 미만</p></div>')
        labels = "".join(f'<label for="r{d}">{nm}</label>' for d, nm in PERIODS)
        chart_html = (f'<div class="ptabs-wrap">{"".join(tabs)}<div class="ptabs">{labels}</div>{"".join(charts)}</div>'
                      if main_series else '<p class="empty">저장된 가격 이력 없음</p>')

        # 월별 표
        mrows = monthly_rows(main_series, asof)
        mtab = ""
        if mrows:
            body = "".join(
                f'<tr><td class="l">{r["m"][:4]}년 {int(r["m"][5:])}월</td><td><span class="n">{r["avg"]:,}</span></td>'
                f'<td><span class="n">{r["lo"]:,}</span></td><td><span class="n">{r["hi"]:,}</span></td>'
                f'<td>{chg_span(r["chg"])}</td></tr>' for r in reversed(mrows))
            mtab = (f'<div class="tf"><table><thead><tr><th class="l">월</th><th>평균(원)</th><th>최저(원)</th>'
                    f'<th>최고(원)</th><th>전월 대비</th></tr></thead><tbody>{body}</tbody></table></div>')

        # 1년 위치
        yr_vals = [v for _, v in period_points(main_series, asof, 365)]
        pos = position_pct(yr_vals, main_p["today"]) if yr_vals else None
        pos_html = ""
        if pos is not None:
            pos_html = (f'<div class="pos-bar"><i style="left:{pos}%"></i></div>'
                        f'<div class="pos-lab"><span>1년 최저 {min(yr_vals):,}원</span><span><b>현재 하위 {pos}%</b></span><span>최고 {max(yr_vals):,}원</span></div>')
        stat = ""
        if yr_vals:
            mo = period_points(main_series, asof, 30)
            mo_vals = [v for _, v in mo] or [main_p["today"]]
            stat = (f'<div class="stat"><div><div class="k">1년 평균</div><div class="x">{mean_int(yr_vals):,}<small>원</small></div></div>'
                    f'<div><div class="k">1개월 평균</div><div class="x">{mean_int(mo_vals):,}<small>원</small></div></div>'
                    f'<div><div class="k">1개월 변동폭</div><div class="x">{min(mo_vals):,}~{max(mo_vals):,}<small>원</small></div></div></div>')

        vg, lines = report_lines(label, retail, whole, r_series, w_series, asof, g_cfg)
        verdict = ""
        if vg:
            g = GRADES[vg]
            verdict = (f'<div class="verdict" style="background:{g[2]};color:{g[3]}">{face_svg(vg, 26)}'
                       f'{esc(label)} - {esc(GRADE_SHORT[vg])} ({"평년" if base_key == "avg" else "1년 전"} 대비 {sp(base)})</div>')
        rep = "".join(f"<li>{esc(x)}</li>" for x in lines)

        # 등급별 오늘 가격
        rank_rows = []
        for cls_code, cls_name in (("01", "소매"), ("02", "도매")):
            for it in sorted(e[cls_code], key=lambda x: prio.index(x["rank"]) if x["rank"] in prio else 99):
                pp = it["prices"]
                b = pct(pp["today"], pp.get("avg") or pp.get("y1"))
                rank_rows.append(f'<tr><td class="l">{cls_name} {esc(it["rank"])}</td><td class="u">{esc(it["unit"])}</td>'
                                 f'<td><span class="n"><b>{won(pp["today"])}</b></span></td><td>{chg_span(pct(pp["today"], pp.get("d1")))}</td>'
                                 f'<td>{chg_span(b)}</td><td>{badge(grade_for(b, g_cfg), 15)}</td></tr>')
        rank_tab = (f'<div class="tf"><table><thead><tr><th class="l">구분</th><th class="u">단위</th><th>오늘(원)</th>'
                    f'<th>전일 대비</th><th>평년 대비</th><th>수준</th></tr></thead><tbody>{"".join(rank_rows)}</tbody></table></div>')

        sub = " · ".join(x for x in (e["cat"], f"품종 {e['kind']}" if e["kind"] else "", f"{main_cls} {main_it['rank']} {main_it['unit']} 기준") if x)
        body = f"""<div class="crumb"><a href="../index.html">과일바구니</a> › {esc(e["cat"])} › {esc(label)}</div>
<div class="ihead"><div><h1>{esc(label)}</h1><div class="sub">{esc(sub)}</div></div>{badge(grade, 22) if grade else ""}</div>
<div class="prices">{price_card("소매", retail, True, g_cfg)}{price_card("도매", whole, False, g_cfg)}</div>
<div class="card"><h2>가격 추이<small>{esc(main_cls)} {esc(main_it["rank"])} · {esc(main_it["unit"])} · 점선은 평년 가격</small></h2>{chart_html}{pos_html}{stat}</div>
<div class="card"><div class="two"><div><h2>오늘의 리포트</h2><h3>{esc(kdate(asof))} 기준</h3>{verdict}<ul class="rep">{rep}</ul></div>
<div><h2>월별 가격</h2><h3>최근 1년, {esc(main_cls)} {esc(main_it["rank"])} 기준</h3>{mtab or '<p class="empty">월별 이력 없음</p>'}</div></div></div>
<div class="card"><h2>등급별 오늘 가격</h2>{rank_tab}</div>"""
        html = shell(f"{label} 가격 - 과일바구니", body, "../", asof, fetched)
        (out_dir / f"{page_key(ic, kc)}.html").write_text(html, encoding="utf-8")
        links[(ic, kc)] = page_path(ic, kc)
        made += 1
    return links, made
