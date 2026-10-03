"""리포트 생성 : 최신 스냅샷 + 누적 이력 -> HTML 대시보드, 마크다운, 엑셀

산출물
  docs/index.html                 최신 리포트 (GitHub Pages 첫 화면)
  docs/reports/YYYY-MM-DD.html    날짜별 보관본
  docs/fruitbasket_prices.xlsx    엑셀 (최신 소매·도매, 최근 이력)
  reports/YYYY-MM-DD.md           GitHub에서 바로 읽는 요약
  reports/LATEST.md               최신 요약 사본
"""
from __future__ import annotations

import html
import re
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import store  # noqa: E402

KST = timezone(timedelta(hours=9))
DOCS = store.ROOT / "docs"
REPORTS = store.ROOT / "reports"
WEEK = "월화수목금토일"

GRADES = {
    "GREEN": ("쌈", "#2E9E5B"),
    "YELLOW": ("보통", "#C99A06"),
    "ORANGE": ("비쌈", "#EE7B1E"),
    "RED": ("매우 비쌈", "#D64545"),
}
UP, DOWN = "#D64545", "#2F6FD0"  # 상승 빨강, 하락 파랑


# ---------- 계산 ----------

def pct(cur: int | None, base: int | None) -> Decimal | None:
    """정수 가격에서 사사오입 소수 1자리 등락률 (부동소수점 반올림 사용 안 함)"""
    if cur is None or not base:
        return None
    return ((Decimal(cur) - Decimal(base)) * 100 / Decimal(base)).quantize(Decimal("0.1"), ROUND_HALF_UP)


def grade_of(p: Decimal | None, g: dict) -> str | None:
    if p is None:
        return None
    if p <= Decimal(str(g["green_max"])):
        return "GREEN"
    if p <= Decimal(str(g["yellow_max"])):
        return "YELLOW"
    if p <= Decimal(str(g["orange_max"])):
        return "ORANGE"
    return "RED"


def label_of(it: dict) -> str:
    kind = it.get("kind_name", "")
    name = it["item_name"]
    return f"{name}({kind})" if kind and kind != name else name


def build_records(snap: dict, cfg: dict) -> dict:
    """{cls_name: {cat_name: [record,...]}}"""
    ranks = set(cfg.get("rank_filter") or [])
    out: dict = defaultdict(dict)
    for g in snap["groups"]:
        recs = []
        for it in g["items"]:
            p = it["prices"]
            if p.get("today") is None:
                continue
            if ranks and it.get("rank") and it["rank"] not in ranks:
                continue
            base_key = "avg" if p.get("avg") else "y1"
            r = {
                "label": label_of(it), "rank": it.get("rank", ""), "unit": it["unit"],
                "cat": g["cat_name"], "cls": g["cls_name"],
                "sid": "|".join([g["cls_code"], it["item_code"], it["kind_code"], it["rank_code"]]),
                "today": p.get("today"),
                "d1": pct(p.get("today"), p.get("d1")),
                "w1": pct(p.get("today"), p.get("w1")),
                "m1": pct(p.get("today"), p.get("m1")),
                "y1": pct(p.get("today"), p.get("y1")),
                "avg": pct(p.get("today"), p.get("avg")),
                "base_key": base_key,
            }
            r["base"] = r[base_key]
            r["grade"] = grade_of(r["base"], cfg["grade"])
            recs.append(r)
        # 같은 이름(품종)이 여러 등급이면 등급을 라벨에 붙임
        counts = defaultdict(int)
        for r in recs:
            counts[r["label"]] += 1
        for r in recs:
            if counts[r["label"]] > 1 and r["rank"]:
                r["label"] = f"{r['label']} {r['rank']}"
        if recs:
            out[g["cls_name"]][g["cat_name"]] = recs
    return out


# ---------- 표기 ----------

def won(v: int | None) -> str:
    return "-" if v is None else f"{v:,}"


def sp(p: Decimal | None) -> str:
    if p is None:
        return "-"
    return f"+{p:,.1f}%" if p > 0 else f"{p:,.1f}%"


def esc(s: str) -> str:
    return html.escape(str(s), quote=True)


def kdate(d: str) -> str:
    dt = date.fromisoformat(d)
    return f"{dt.year}년 {dt.month}월 {dt.day}일({WEEK[dt.weekday()]})"


def no_dash(s: str) -> str:
    return s.replace("—", "-").replace("–", "-")


# ---------- 요약 문장 ----------

def summarize(recs_by_cls: dict) -> dict:
    retail = recs_by_cls.get("소매") or next(iter(recs_by_cls.values()), {})
    allr = [r for rs in retail.values() for r in rs]
    fruit = retail.get("과일류", allr)
    with_base = [r for r in fruit if r["base"] is not None]
    pricey = [r for r in with_base if r["grade"] in ("ORANGE", "RED")]
    cheap = sorted([r for r in with_base if r["grade"] == "GREEN"], key=lambda r: r["base"])
    top = max(with_base, key=lambda r: r["base"], default=None)
    low = min(with_base, key=lambda r: r["base"], default=None)
    cls_name = "소매" if "소매" in recs_by_cls else next(iter(recs_by_cls), "")
    cat_name = "과일" if "과일류" in retail else "품목"

    if top and top["base"] > 0:
        ref = "평년" if top["base_key"] == "avg" else "1년 전"
        head = (f"{top['label']} {ref}보다 {top['base']:,.1f}% 비싸, "
                f"{cls_name} {cat_name} {len(with_base):,}개 중 {len(pricey):,}개가 평년보다 비쌈")
    elif low:
        head = (f"{cls_name} {cat_name} 가격 대체로 평년 이하, "
                f"{low['label']} 평년보다 {abs(low['base']):,.1f}% 쌈")
    else:
        head = "가격 비교 기준(평년·1년 전) 자료 없음"

    up = sum(1 for r in allr if r["d1"] is not None and r["d1"] > 0)
    down = sum(1 for r in allr if r["d1"] is not None and r["d1"] < 0)
    return {
        "headline": head, "n_items": len(allr), "up": up, "down": down,
        "pricey": len(pricey), "n_fruit": len(with_base),
        "top": top, "low": low, "cheap": cheap[:6], "cls_name": cls_name,
    }


# ---------- HTML 조각 ----------

def bars_html(recs: list[dict]) -> str:
    rs = sorted([r for r in recs if r["base"] is not None], key=lambda r: r["base"], reverse=True)
    if not rs:
        return '<p class="empty">비교 기준 가격이 없는 품목만 있음</p>'
    mx = max(abs(r["base"]) for r in rs) or Decimal(1)
    rows = []
    for r in rs:
        w = float(abs(r["base"]) / mx) * 72  # 반쪽 폭의 최대 72%, 나머지는 수치 라벨 자리
        color = GRADES[r["grade"]][1]
        val = f'<span class="v">{sp(r["base"])}</span>'
        bar = f'<i style="width:{w:.1f}%;background:{color}"></i>'
        neg = f"{val}{bar}" if r["base"] < 0 else ""
        pos = f"{bar}{val}" if r["base"] >= 0 else ""
        mark = "" if r["base_key"] == "avg" else '<sup title="평년가 없음, 1년 전 대비">*</sup>'
        rows.append(f'<div class="bl">{esc(r["label"])}{mark}</div>'
                    f'<div class="bt"><div class="neg">{neg}</div><div class="pos">{pos}</div></div>')
    note = ""
    if any(r["base_key"] != "avg" for r in rs):
        note = '<p class="note">* 평년가가 없어 1년 전 가격과 비교</p>'
    return f'<div class="bars">{"".join(rows)}</div>{note}'


def chg_cell(p: Decimal | None) -> str:
    if p is None:
        return '<td><span class="n">-</span></td>'
    c = UP if p > 0 else DOWN if p < 0 else "inherit"
    return f'<td><span class="n" style="color:{c}">{sp(p)}</span></td>'


def table_html(recs: list[dict]) -> str:
    rs = sorted(recs, key=lambda r: (r["base"] is None, -(r["base"] or 0)))
    head = ("<tr><th>품목</th><th>단위</th><th>오늘 가격(원)</th><th>전일 대비</th><th>1주 전 대비</th>"
            "<th>1개월 전 대비</th><th>1년 전 대비</th><th>평년 대비</th><th>가격 수준</th></tr>")
    body = []
    for r in rs:
        g = GRADES.get(r["grade"])
        badge = f'<span class="badge" style="--c:{g[1]}">{g[0]}</span>' if g else "-"
        body.append(
            f'<tr><td class="l">{esc(r["label"])}</td><td class="u">{esc(r["unit"])}</td>'
            f'<td><span class="n"><b>{won(r["today"])}</b></span></td>'
            + chg_cell(r["d1"]) + chg_cell(r["w1"]) + chg_cell(r["m1"])
            + chg_cell(r["y1"]) + chg_cell(r["avg"]) + f"<td>{badge}</td></tr>"
        )
    return f'<div class="tw"><table><thead>{head}</thead><tbody>{"".join(body)}</tbody></table></div>'


def spark_svg(points: list[tuple[str, int]], color: str) -> str:
    W, H, L, R, T, B = 320, 140, 8, 8, 26, 40
    vals = [v for _, v in points]
    lo, hi = min(vals), max(vals)
    if hi == lo:
        hi, lo = hi + 1, lo - 1
    n = len(points)
    xs = [L + (W - L - R) * i / max(n - 1, 1) for i in range(n)]
    ys = [T + (H - T - B) * (1 - (v - lo) / (hi - lo)) for v in vals]
    path = " ".join(f"{'M' if i == 0 else 'L'}{x:.1f},{y:.1f}" for i, (x, y) in enumerate(zip(xs, ys)))
    d0, d1 = points[0][0][5:].replace("-", "."), points[-1][0][5:].replace("-", ".")
    # 수치 라벨은 선이 이어지는 반대쪽(위/아래)에 둬서 선·점과 겹치지 않게
    def ly(y: float, neighbor: float) -> float:
        below = neighbor < y  # 이웃 점이 더 위에 있으면 라벨은 아래로
        if below and y + 18 > H - B + 8:
            below = False
        if not below and y - 10 < 12:
            below = True
        return y + 18 if below else y - 10
    y0 = ly(ys[0], ys[1] if n > 1 else ys[0])
    y1 = ly(ys[-1], ys[-2] if n > 1 else ys[-1])
    return (
        f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="가격 추이">'
        f'<path d="{path}" fill="none" stroke="{color}" stroke-width="2.2" stroke-linejoin="round"/>'
        f'<circle cx="{xs[0]:.1f}" cy="{ys[0]:.1f}" r="3" fill="{color}"/>'
        f'<circle cx="{xs[-1]:.1f}" cy="{ys[-1]:.1f}" r="3.5" fill="{color}"/>'
        f'<text x="{L}" y="{y0:.1f}" class="sv">{vals[0]:,}</text>'
        f'<text x="{W - R}" y="{y1:.1f}" class="sv" text-anchor="end">{vals[-1]:,}</text>'
        f'<text x="{L}" y="{H - 4}" class="sd">{d0}</text>'
        f'<text x="{W - R}" y="{H - 4}" class="sd" text-anchor="end">{d1}</text>'
        "</svg>"
    )


def trends_html(recs_by_cat: dict, history: list[dict], cfg: dict, asof: str) -> str:
    start = (date.fromisoformat(asof) - timedelta(days=int(cfg.get("trend_days", 90)))).isoformat()
    series = defaultdict(list)
    for h in history:
        if start <= h["date"] <= asof:
            series[store.series_id(h)].append((h["date"], h["price"]))
    recs = [r for rs in recs_by_cat.values() for r in rs if r["base"] is not None]
    recs.sort(key=lambda r: abs(r["base"]), reverse=True)
    cards = []
    for r in recs:
        pts = sorted(series.get(r["sid"], []))
        if len(pts) < 2:
            continue
        color = GRADES[r["grade"]][1]
        cards.append(
            f'<div class="tc"><div class="tt">{esc(r["label"])}<span>{esc(r["unit"])}</span></div>'
            f'{spark_svg(pts, color)}</div>'
        )
        if len(cards) >= int(cfg.get("trend_items", 8)):
            break
    if not cards:
        return ('<p class="empty">이력이 2일 이상 쌓이면 추이 그래프가 표시됨 '
                '(Actions의 「과거 가격 백필」을 한 번 실행하면 바로 채워짐)</p>')
    return f'<div class="tg">{"".join(cards)}</div>'


CSS = """
:root{--ink:#16202a;--sub:#5b6875;--line:#e3e7ec;--bg:#fff;--soft:#f6f8fa;--acc:#E8590C}
*{box-sizing:border-box}html{color-scheme:light}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.6 Pretendard,"Pretendard Variable",-apple-system,"Apple SD Gothic Neo","Malgun Gothic",sans-serif;font-variant-numeric:tabular-nums}
.wrap{max-width:1080px;margin:0 auto;padding:0 16px 48px}
header{border-bottom:3px solid var(--ink);padding:22px 0 12px;display:flex;justify-content:space-between;align-items:flex-end;gap:12px;flex-wrap:wrap}
.brand{font-weight:800;font-size:20px;letter-spacing:-.02em}.brand em{font-style:normal;color:var(--acc)}
.meta{color:var(--sub);font-size:13px}
h1{font-size:26px;line-height:1.35;letter-spacing:-.03em;margin:22px 0 14px;word-break:keep-all}
.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:8px}
.kpi{border-top:2px solid var(--ink);padding:10px 2px 4px}
.kpi .k{font-size:13px;color:var(--sub)}.kpi .x{font-size:26px;font-weight:800;letter-spacing:-.02em}
.kpi .x small{font-size:14px;font-weight:600;color:var(--sub);margin-left:2px}
.chips{display:flex;flex-wrap:wrap;gap:6px;margin:10px 0 0}.chip{font-size:13px;padding:3px 10px;border-radius:999px;background:#eaf6ef;color:#1d6b3d}
.tabs input{position:absolute;opacity:0}
.tabs>label{display:inline-block;padding:9px 22px;margin:26px 4px 0 0;border:1px solid var(--line);border-bottom:0;border-radius:8px 8px 0 0;cursor:pointer;font-weight:700;color:var(--sub);background:var(--soft)}
.tabs input:checked+label{background:var(--ink);color:#fff;border-color:var(--ink)}
.panel{display:none;border-top:2px solid var(--ink);padding-top:6px}
#t0:checked~#p0,#t1:checked~#p1,#t2:checked~#p2{display:block}
h2{font-size:19px;margin:26px 0 4px;letter-spacing:-.02em}h3{font-size:15px;margin:18px 0 8px;color:var(--sub)}
.bars{display:grid;grid-template-columns:max-content 1fr;column-gap:12px;row-gap:5px;align-items:center}
.bl{font-size:14px;white-space:nowrap;text-align:right}.bl sup{color:var(--sub)}
.bt{display:grid;grid-template-columns:1fr 1fr;height:24px;border-left:0}
.neg,.pos{display:flex;align-items:center;gap:6px}.neg{justify-content:flex-end;border-right:1px solid #9aa4ae}
.bt i{display:block;height:16px;border-radius:2px}.v{font-size:13.5px;font-weight:700;white-space:nowrap}
.note,.empty{color:var(--sub);font-size:13px}
.tw{overflow-x:auto;-webkit-overflow-scrolling:touch}
table{border-collapse:collapse;width:100%;min-width:760px;font-size:14px}
th{font-size:13px;color:var(--sub);font-weight:600;padding:8px 6px;border-bottom:2px solid var(--ink);white-space:nowrap;text-align:center}
td{padding:7px 6px;border-bottom:1px solid var(--line);text-align:center;white-space:nowrap}
td.l{text-align:left;font-weight:600}td.u{color:var(--sub);font-size:13px}
.n{display:inline-block;min-width:6.2em;text-align:right}
tbody tr:last-child td{border-bottom:2px solid var(--ink)}
.badge{display:inline-block;font-size:12.5px;font-weight:700;color:var(--c);border:1.5px solid var(--c);border-radius:4px;padding:0 7px}
.tg{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:12px}
.tc{border:1px solid var(--line);border-radius:8px;padding:10px 12px 4px}
.tt{font-weight:700;font-size:14px}.tt span{font-weight:400;color:var(--sub);font-size:12.5px;margin-left:6px}
.tc svg{width:100%;height:auto;display:block}.sv{font-size:13px;font-weight:700;fill:var(--ink)}.sd{font-size:11.5px;fill:var(--sub)}
.legend{display:flex;flex-wrap:wrap;gap:12px;font-size:13px;color:var(--sub);margin:6px 0 0}.legend b{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:4px;vertical-align:-1px}
.arch{columns:3 150px;font-size:14px;padding-left:18px}.arch a{color:var(--ink)}
footer{margin-top:40px;padding-top:12px;border-top:1px solid var(--line);color:var(--sub);font-size:12.5px}
@media (max-width:640px){h1{font-size:21px}.kpis{grid-template-columns:repeat(2,1fr)}.kpi .x{font-size:22px}.tabs>label{padding:8px 16px}}
"""


def page_html(snap: dict, recs_by_cls: dict, s: dict, history: list[dict], cfg: dict,
              archive: list[str], rel: str) -> str:
    asof = snap["date"]
    g = cfg["grade"]
    legend = (
        f'<div class="legend"><span><b style="background:{GRADES["GREEN"][1]}"></b>쌈 ({g["green_max"]:+.0f}% 이하)</span>'
        f'<span><b style="background:{GRADES["YELLOW"][1]}"></b>보통</span>'
        f'<span><b style="background:{GRADES["ORANGE"][1]}"></b>비쌈 ({g["yellow_max"]:+.0f}% 초과)</span>'
        f'<span><b style="background:{GRADES["RED"][1]}"></b>매우 비쌈 ({g["orange_max"]:+.0f}% 초과)</span></div>'
    )
    tabs, panels = [], []
    for i, (cls, cats) in enumerate(recs_by_cls.items()):
        chk = " checked" if i == 0 else ""
        tabs.append(f'<input type="radio" name="t" id="t{i}"{chk}><label for="t{i}">{esc(cls)}</label>')
        sec = []
        for cat, recs in cats.items():
            sec.append(f"<h2>{esc(cat)} {esc(cls)} 가격</h2><h3>평년 대비 등락률</h3>{legend}"
                       f"{bars_html(recs)}<h3>품목별 가격</h3>{table_html(recs)}")
        sec.append(f"<h2>{esc(cls)} 가격 추이</h2><h3>최근 {int(cfg.get('trend_days', 90)):,}일, 평년 대비 변동이 큰 품목</h3>"
                   + trends_html(cats, history, cfg, asof))
        panels.append(f'<section class="panel" id="p{i}">{"".join(sec)}</section>')

    top = s["top"]
    top_txt = f'{esc(top["label"])}<small>{sp(top["base"])}</small>' if top and top["base"] is not None else "-"
    chips = "".join(f'<span class="chip">{esc(r["label"])} {sp(r["base"])}</span>' for r in s["cheap"])
    chips_html = f'<div class="chips">평년보다 싼 {s["cls_name"]} 과일 {chips}</div>' if chips else ""
    arch = "".join(f'<li><a href="{rel}reports/{d}.html">{kdate(d)}</a></li>' for d in archive[:60])

    out = f"""<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light">
<title>과일바구니 가격 리포트 {asof}</title>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard-dynamic-subset.min.css">
<style>{CSS}</style></head><body><div class="wrap">
<header><div class="brand">과일<em>바구니</em> 가격 리포트</div>
<div class="meta"><span style="white-space:nowrap">조사일 {kdate(asof)}</span> · <span style="white-space:nowrap">갱신 {esc(snap.get('fetched_at', '')[:16].replace('T', ' '))} KST</span></div></header>
<h1>{esc(s['headline'])}</h1>
<div class="kpis">
<div class="kpi"><div class="k">조사 품목({esc(s['cls_name'])})</div><div class="x">{s['n_items']:,}<small>개</small></div></div>
<div class="kpi"><div class="k">전일 대비 상승 / 하락</div><div class="x" ><span style="color:{UP}">{s['up']:,}</span><small>/</small><span style="color:{DOWN}">{s['down']:,}</span></div></div>
<div class="kpi"><div class="k">평년보다 비싼 과일</div><div class="x">{s['pricey']:,}<small>/ {s['n_fruit']:,}개</small></div></div>
<div class="kpi"><div class="k">평년 대비 최대 상승</div><div class="x" style="font-size:20px">{top_txt}</div></div>
</div>{chips_html}
<div class="tabs">{''.join(tabs)}{''.join(panels)}</div>
<h2>지난 리포트</h2><ul class="arch">{arch}</ul>
<footer>자료: KAMIS 농산물유통정보(한국농수산식품유통공사) 일별 부류별 가격 · 가격 수준은 평년(최근 5년 중 최대·최소 제외 평균) 대비 등락률 기준 · GitHub Actions로 매일 자동 생성 · <a style="white-space:nowrap" href="{rel}fruitbasket_prices.xlsx">엑셀 받기</a></footer>
</div></body></html>"""
    return no_dash(out)


# ---------- 마크다운·엑셀 ----------

def markdown(snap: dict, recs_by_cls: dict, s: dict) -> str:
    L = [f"# 과일바구니 가격 리포트 {snap['date']}", "", f"**{s['headline']}**", "",
         f"- 조사 품목({s['cls_name']}) {s['n_items']:,}개, 전일 대비 상승 {s['up']:,}개 / 하락 {s['down']:,}개",
         f"- 평년보다 비싼 과일 {s['pricey']:,}개 / {s['n_fruit']:,}개", ""]
    for cls, cats in recs_by_cls.items():
        for cat, recs in cats.items():
            L += [f"## {cat} {cls}", "", "| 품목 | 단위 | 오늘(원) | 전일 | 1개월 전 | 평년 | 수준 |",
                  "|---|---|--:|--:|--:|--:|:-:|"]
            for r in sorted(recs, key=lambda r: (r["base"] is None, -(r["base"] or 0))):
                gname = GRADES[r["grade"]][0] if r["grade"] else "-"
                L.append(f"| {r['label']} | {r['unit']} | {won(r['today'])} | {sp(r['d1'])} | "
                         f"{sp(r['m1'])} | {sp(r['avg'])} | {gname} |")
            L.append("")
    L.append("자료: KAMIS 농산물유통정보 · 자동 생성")
    return no_dash("\n".join(L) + "\n")


def excel(path: Path, recs_by_cls: dict, history: list[dict], asof: str, cfg: dict) -> None:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, Side
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    wb.remove(wb.active)
    bold, thick, thin = Font(bold=True), Side(style="medium"), Side(style="thin", color="D9D9D9")
    for cls, cats in recs_by_cls.items():
        ws = wb.create_sheet(f"최신_{cls}")
        hdr = ["부류", "품목", "단위", "오늘 가격(원)", "전일 대비(%)", "1주 전 대비(%)",
               "1개월 전 대비(%)", "1년 전 대비(%)", "평년 대비(%)", "가격 수준"]
        ws.append(hdr)
        for c in ws[1]:
            c.font, c.border, c.alignment = bold, Border(bottom=thick), Alignment(horizontal="center")
        for cat, recs in cats.items():
            for r in recs:
                ws.append([cat, r["label"], r["unit"], r["today"]]
                          + [float(r[k]) if r[k] is not None else None for k in ("d1", "w1", "m1", "y1", "avg")]
                          + [GRADES[r["grade"]][0] if r["grade"] else None])
        for row in ws.iter_rows(min_row=2):
            row[3].number_format = "#,##0"
            for c in row[4:9]:
                c.number_format = "+0.0;-0.0;0.0"
            for c in row:
                c.border = Border(bottom=thin)
        for i, w in enumerate([8, 24, 10, 13, 12, 13, 14, 13, 12, 10], 1):
            ws.column_dimensions[get_column_letter(i)].width = w
        ws.freeze_panes = "C2"

    # 최근 이력 (행 = 시리즈, 열 = 날짜)
    start = (date.fromisoformat(asof) - timedelta(days=int(cfg.get("trend_days", 90)))).isoformat()
    hist = [h for h in history if start <= h["date"] <= asof]
    dates = sorted({h["date"] for h in hist})
    meta, grid = {}, defaultdict(dict)
    for h in hist:
        sid = store.series_id(h)
        meta[sid] = h
        grid[sid][h["date"]] = h["price"]
    ws = wb.create_sheet("최근이력")
    ws.append(["구분", "부류", "품목", "품종", "등급", "단위"] + dates)
    for c in ws[1]:
        c.font, c.border = bold, Border(bottom=thick)
    for sid, h in sorted(meta.items(), key=lambda kv: (kv[1]["cls_code"], kv[1]["cat_code"], kv[1]["item_code"])):
        ws.append([h["cls_name"], h["cat_name"], h["item_name"], h["kind_name"], h["rank"], h["unit"]]
                  + [grid[sid].get(d) for d in dates])
    for row in ws.iter_rows(min_row=2, min_col=7):
        for c in row:
            c.number_format = "#,##0"
    ws.freeze_panes = "G2"
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)


# ---------- 검증 게이트 ----------

def verify(html_text: str, recs_by_cls: dict) -> list[str]:
    errs = []
    if "—" in html_text or "–" in html_text:
        errs.append("줄표(—, –) 포함")
    n_bars = sum(1 for cats in recs_by_cls.values() for rs in cats.values() for r in rs if r["base"] is not None)
    vals = re.findall(r'<span class="v">([^<]*)</span>', html_text)
    if len(vals) != n_bars:
        errs.append(f"막대 수치 라벨 수 불일치: {len(vals)} != {n_bars}")
    if any(not v.strip() for v in vals):
        errs.append("빈 막대 수치 라벨")
    for txt in re.findall(r'<span class="n"[^>]*>(?:<b>)?([^<]*)', html_text) + re.findall(r'class="sv"[^>]*>([^<]*)<', html_text):
        if re.search(r"\d{4,}", txt.replace(".", "")):
            errs.append(f"천 단위 콤마 누락: {txt}")
            break
    return errs


def main() -> int:
    cfg = store.load_config()
    asof = sys.argv[1] if len(sys.argv) > 1 else store.latest_snapshot_date()
    if not asof:
        print("스냅샷 없음, 먼저 collect.py 실행")
        return 1
    snap = store.load_snapshot(asof)
    history = store.read_history()
    recs = build_records(snap, cfg)
    if not recs:
        print("표시할 품목 없음")
        return 1
    s = summarize(recs)

    REPORTS.mkdir(parents=True, exist_ok=True)
    (DOCS / "reports").mkdir(parents=True, exist_ok=True)
    archive = sorted({p.stem for p in (DOCS / "reports").glob("*.html")} | {asof}, reverse=True)

    idx = page_html(snap, recs, s, history, cfg, archive, "")
    arc = page_html(snap, recs, s, history, cfg, archive, "../")
    errs = verify(idx, recs)
    if errs:
        print("검증 실패:\n  " + "\n  ".join(errs))
        return 2

    (DOCS / "index.html").write_text(idx, encoding="utf-8")
    (DOCS / "reports" / f"{asof}.html").write_text(arc, encoding="utf-8")
    (DOCS / ".nojekyll").write_text("", encoding="utf-8")
    md = markdown(snap, recs, s)
    (REPORTS / f"{asof}.md").write_text(md, encoding="utf-8")
    (REPORTS / "LATEST.md").write_text(md, encoding="utf-8")
    excel(DOCS / "fruitbasket_prices.xlsx", recs, history, asof, cfg)
    print(f"리포트 생성 {asof}: {s['headline']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
