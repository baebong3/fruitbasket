"""인스타그램 카드뉴스 생성 : 1080×1080 정사각형 4장 + 캡션

  python scripts/insta.py                 # 최신 조사일
  python scripts/insta.py 2026-10-08 --out docs/insta

산출물 (out/YYYY-MM-DD/)
  1.jpg 표지 - 장보기 지수, 오늘 헤드라인, 장바구니 비용
  2.jpg 싼 품목·비싼 품목
  3.jpg 주요 품목 가격 흐름 (+ 원인 요약 자리)
  4.jpg 오늘의 알뜰 요리
  caption.txt 게시 글
  causes.json 이 있으면 3장에 원인 요약을 넣음 (뉴스 연동 단계에서 생성)
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import store  # noqa: E402
import items as itemmod  # noqa: E402
import kitchen  # noqa: E402
import basket as basketmod  # noqa: E402
import shopping  # noqa: E402
import icons  # noqa: E402
import report  # noqa: E402
from pricing import PriceBook  # noqa: E402
from theme import GRADES, LOGO, UP, DOWN, ACC, GOLD, INK, SUB, LINE, PAPER, face_svg, esc, sp, won, label_of, pct, no_dash, WEEK  # noqa: E402

ROOT = store.ROOT
FONTS = ROOT / "assets" / "fonts"
AT_LOGO = ROOT / "docs" / "assets" / "at_ci.png"
KEY_ITEMS = [("사과", ["후지", "홍로"]), ("배", ["신고"]), ("배추", []), ("무", []), ("양파", []), ("파", ["대파"])]


def kd(d: str) -> str:
    x = date.fromisoformat(d)
    return f"{x.month}월 {x.day}일({WEEK[x.weekday()]})"


def font_css() -> str:
    f = FONTS.as_uri()
    css = "".join(f"@font-face{{font-family:P;src:url({f}/Pretendard-{n}.woff2) format('woff2');font-weight:{w}}}"
                  for n, w in (("Regular", 400), ("SemiBold", 600), ("Bold", 700), ("ExtraBold", 800)))
    serif = (FONTS / "serif" / "700.css").read_text(encoding="utf-8").replace("./files/", f"{f}/serif/files/")
    # woff 대체 경로 제거 (woff2 만 보관)
    import re
    serif = re.sub(r",\s*url\([^)]*\.woff\) format\('woff'\)", "", serif)
    return css + serif


CSS = """
*{box-sizing:border-box;margin:0;padding:0}
html,body{width:1080px;height:1080px;overflow:hidden}
body{font-family:P,sans-serif;color:%(INK)s;background:#fff;font-variant-numeric:tabular-nums;-webkit-font-smoothing:antialiased;letter-spacing:-.01em}
.serif{font-family:'Noto Serif KR',serif;font-weight:700;letter-spacing:-.02em}
.card{position:relative;width:1080px;height:1080px;padding:64px 72px 0;display:flex;flex-direction:column}
.top{display:flex;justify-content:space-between;align-items:center;padding-bottom:22px;border-bottom:2px solid %(INK)s}
.brand{display:flex;align-items:center;gap:14px}.brand svg{width:56px;height:56px}
.brand b{display:block;font-family:'Noto Serif KR',serif;font-size:32px;line-height:1.1}
.brand small{display:block;font-size:14px;letter-spacing:.2em;color:%(GOLD)s;font-weight:700;margin-top:4px}
.date{text-align:right;font-size:22px;color:%(SUB)s;font-weight:600;line-height:1.35}.date b{color:%(INK)s;font-size:26px;display:block}
.foot{position:absolute;left:72px;right:72px;bottom:44px;display:flex;justify-content:space-between;align-items:center;font-size:17px;color:%(SUB)s;border-top:1px solid %(LINE)s;padding-top:18px}
.foot img{height:30px}.foot .pg{font-weight:800;color:%(INK)s;font-size:18px;letter-spacing:.08em}
.eyebrow{font-size:20px;letter-spacing:.18em;color:%(GOLD)s;font-weight:800;margin:40px 0 10px}
h1{font-family:'Noto Serif KR',serif;font-size:58px;line-height:1.28;letter-spacing:-.03em;word-break:keep-all;text-wrap:balance}
h2{font-family:'Noto Serif KR',serif;font-size:50px;line-height:1.25;letter-spacing:-.03em;margin:4px 0 8px;word-break:keep-all;text-wrap:balance}
.lead{font-size:24px;color:%(SUB)s;font-weight:600;margin-bottom:24px}
/* 1장 */
.cover{display:grid;grid-template-columns:380px 1fr;gap:40px;align-items:center;margin-top:34px}
.gauge{width:380px;height:auto;display:block}.gv{font-size:92px;font-weight:800;letter-spacing:-.04em}.ax{font-size:20px;fill:%(SUB)s;font-weight:600}
.lvl{text-align:center;font-size:34px;font-weight:800;margin-top:-6px;letter-spacing:-.02em}
.kpis{display:grid;grid-template-columns:repeat(3,1fr);gap:22px;margin-top:40px}
.kpi{border-top:3px solid %(INK)s;padding-top:14px}.kpi .k{font-size:21px;color:%(SUB)s;font-weight:700}.kpi .x{font-size:48px;font-weight:800;letter-spacing:-.03em;margin-top:4px;white-space:nowrap}.kpi .x small{font-size:22px;color:%(SUB)s;font-weight:700;margin-left:4px}
/* 2장 */
.list{display:flex;flex-direction:column;gap:0}
.row{display:grid;grid-template-columns:56px 260px 1fr 150px;align-items:center;gap:16px;padding:7px 0;border-bottom:1px solid %(LINE)s}
.row:last-child{border-bottom:0}
.row .nm{font-size:30px;font-weight:800;letter-spacing:-.03em;white-space:nowrap}.row .nm small{display:block;font-size:18px;color:%(SUB)s;font-weight:600;letter-spacing:0}
.row .bar{height:22px;border-radius:999px}.row .pv{font-size:32px;font-weight:800;text-align:right;white-space:nowrap}
.sec{font-size:24px;font-weight:800;margin:16px 0 2px;display:flex;align-items:center;gap:10px}.sec i{width:14px;height:14px;border-radius:50%%;display:inline-block}
/* 3장 */
.grid6{display:grid;grid-template-columns:repeat(3,1fr);gap:18px}
.it{border:1.5px solid %(LINE)s;border-radius:16px;padding:18px 20px 12px;background:#fff}
.it .h{display:flex;align-items:center;gap:10px;font-size:26px;font-weight:800;letter-spacing:-.03em}.it .h small{font-size:16px;color:%(SUB)s;font-weight:600;margin-left:auto}
.it .p{font-size:36px;font-weight:800;letter-spacing:-.03em;margin:6px 0 2px}.it .p small{font-size:17px;color:%(SUB)s;font-weight:600;margin-left:3px}
.it .c{display:flex;gap:14px;font-size:18px;color:%(SUB)s;font-weight:600}.it .c b{font-weight:800}
.it svg.sp{width:100%%;height:auto;display:block;margin-top:4px}
.why{margin-top:26px;border-radius:16px;padding:18px 22px;background:%(PAPER)s;font-size:21px;line-height:1.55}
.why b{display:block;font-size:20px;letter-spacing:.12em;color:%(GOLD)s;margin-bottom:6px}
.why.ph{background:#fff;border:2px dashed %(LINE)s;color:%(SUB)s}
.why ul{list-style:none}.why li{padding-left:22px;position:relative;margin:2px 0}.why li::before{content:"○";position:absolute;left:0;color:%(ACC)s;font-weight:800;font-size:16px;top:3px}
.why li small{color:%(SUB)s;font-size:16px;margin-left:6px}
/* 4장 */
.dishes{display:flex;flex-direction:column;gap:20px;margin-top:6px}
.dish{display:grid;grid-template-columns:150px 1fr 230px;gap:24px;align-items:center;border:1.5px solid %(LINE)s;border-radius:18px;padding:24px 26px}
.dish .ic2{display:flex;align-items:center}.dish .ic2 svg+svg{margin-left:-22px}
.dish .t{font-family:'Noto Serif KR',serif;font-size:38px;letter-spacing:-.03em}.dish .m{font-size:19px;color:%(SUB)s;font-weight:600;margin-top:6px;line-height:1.4}
.dish .cost{text-align:right}.dish .cost .x{font-size:40px;font-weight:800;letter-spacing:-.03em}.dish .cost .x small{font-size:20px;color:%(SUB)s;margin-left:2px}
.dish .save{display:inline-block;font-size:19px;font-weight:800;border-radius:999px;padding:4px 14px;margin-top:6px}
.cta{margin-top:30px;font-size:23px;font-weight:700;color:%(SUB)s;text-align:center}.cta b{color:%(ACC)s}
""" % dict(INK=INK, SUB=SUB, GOLD=GOLD, LINE=LINE, PAPER=PAPER, ACC=ACC)


def page(body: str, n: int, total: int, asof: str) -> str:
    logo = LOGO.replace('width="42" height="42"', 'width="56" height="56"')
    return no_dash(f"""<!doctype html><html lang="ko"><head><meta charset="utf-8"><style>{font_css()}{CSS}</style></head>
<body>{icons.sprite()}<div class="card">
<div class="top"><div class="brand">{logo}<div><b>과일바구니</b><small>DAILY PRICE BRIEF</small></div></div>
<div class="date"><b>{kd(asof)}</b>소매 가격 기준</div></div>
{body}
<div class="foot"><span style="display:flex;align-items:center;gap:12px">자료 <img src="{AT_LOGO.as_uri()}"> KAMIS</span><span class="pg">{n} / {total}</span></div>
</div></body></html>""")


def spark(points: list[tuple[str, int]], color: str, W: int = 300, H: int = 96) -> str:
    vals = [v for _, v in points]
    lo, hi = min(vals), max(vals)
    if hi == lo:
        hi, lo = hi + 1, lo - 1
    n = len(vals)
    xs = [6 + (W - 12) * i / max(n - 1, 1) for i in range(n)]
    ys = [8 + (H - 16) * (1 - (v - lo) / (hi - lo)) for v in vals]
    path = " ".join(f"{'M' if i == 0 else 'L'}{x:.1f},{y:.1f}" for i, (x, y) in enumerate(zip(xs, ys)))
    gid = f"g{abs(hash(tuple(vals))) % 10**7}"
    return (f'<svg class="sp" viewBox="0 0 {W} {H}"><defs><linearGradient id="{gid}" x1="0" y1="0" x2="0" y2="1">'
            f'<stop offset="0" stop-color="{color}" stop-opacity=".3"/><stop offset="1" stop-color="{color}" stop-opacity="0"/></linearGradient></defs>'
            f'<path d="{path} L{xs[-1]:.1f},{H} L{xs[0]:.1f},{H} Z" fill="url(#{gid})"/>'
            f'<path d="{path}" fill="none" stroke="{color}" stroke-width="3" stroke-linejoin="round" stroke-linecap="round"/>'
            f'<circle cx="{xs[-1]:.1f}" cy="{ys[-1]:.1f}" r="5.5" fill="{color}" stroke="#fff" stroke-width="2"/></svg>')


def build(asof: str | None = None) -> dict:
    cfg = store.load_config()
    asof = asof or store.latest_snapshot_date()
    snap = store.load_snapshot(asof)
    history = store.read_history()
    recs, used = report.build_records(snap, cfg, history)
    s = report.summarize(recs)
    idx = itemmod.series_index(history)
    book = PriceBook(snap, cfg, idx)
    recipes = kitchen.compute_recipes(book, cfg["grade"])
    bk = basketmod.build(book, history, asof)
    sh = shopping.compute_index(bk)
    s["headline"], s["sub"] = shopping.headline(recs, bk, sh)
    return {"cfg": cfg, "asof": asof, "recs": recs, "s": s, "book": book, "recipes": recipes, "bk": bk, "sh": sh, "idx": idx}


def slide1(d: dict) -> str:
    sh, bk, s = d["sh"], d["bk"], d["s"]
    gauge = shopping.gauge_svg(sh["score"], sh["color"], size=380)
    idx = bk["idx_avg_all"]
    vs = Decimal(str(idx)) - 100 if idx is not None else None
    wk = sh["week_change"]
    head, rest = (s["headline"].split(" - ", 1) + [""])[:2]
    kp = (f'<div class="kpis"><div class="kpi"><div class="k">장바구니 비용 (4인·1주)</div><div class="x">{won(bk["today"])}<small>원</small></div></div>'
          f'<div class="kpi"><div class="k">평년 대비</div><div class="x" style="color:{DOWN if vs is not None and vs < 0 else UP}">{sp(vs.quantize(Decimal("0.1")) if vs is not None else None)}</div></div>'
          f'<div class="kpi"><div class="k">1주 전 대비</div><div class="x" style="color:{DOWN if wk is not None and wk < 0 else UP}">{sp(wk)}</div></div></div>')
    body = (f'<div class="eyebrow">TODAY\'S MARKET</div><h1>{esc(head)}</h1>'
            f'<div class="cover"><div>{gauge}<div class="lvl" style="color:{sh["color"]}">{esc(sh["name"])}</div></div>'
            f'<div style="font-size:30px;line-height:1.5;font-weight:700;word-break:keep-all">{esc(rest)}'
            f'<div style="font-size:20px;color:{SUB};font-weight:600;margin-top:14px;line-height:1.5">장보기 지수 0~100<br>평년 대비 50% · 1년 중 위치 30% · 1주 추세 20%</div></div></div>{kp}')
    return body


def _rows(rs: list[dict], mx: Decimal) -> str:
    out = []
    for r in rs:
        g = GRADES[r["grade"]]
        w = float(abs(r["base"]) / mx) * 100 if mx else 0
        out.append(f'<div class="row">{icons.item_icon(r["name"], 52, "ic")}<div class="nm">{esc(r["name"])}<small>{esc(r["kind"] + " · ") if r["kind"] else ""}{won(r["today"])}원/{esc(r["unit"])}</small></div>'
                   f'<div><div class="bar" style="width:{max(w, 3):.1f}%;background:{g[1]}"></div></div><div class="pv" style="color:{DOWN if r["base"] < 0 else UP}">{sp(r["base"])}</div></div>')
    return "".join(out)


def slide2(d: dict) -> str:
    retail = d["recs"].get("소매", {})
    allr = [r for rs in retail.values() for r in rs if r["base"] is not None]
    seen, cheap, pricey = set(), [], []
    for r in sorted(allr, key=lambda r: r["base"]):
        if r["grade"] == "GREEN" and r["name"] not in seen and len(cheap) < 5:
            cheap.append(r); seen.add(r["name"])
    seen = set()
    for r in sorted(allr, key=lambda r: -r["base"]):
        if r["grade"] in ("RED", "ORANGE") and r["name"] not in seen and len(pricey) < 2:
            pricey.append(r); seen.add(r["name"])
    mx = max([abs(r["base"]) for r in cheap + pricey] or [Decimal(1)])
    body = (f'<div class="eyebrow">CHEAP &amp; PRICEY</div><h2>오늘 싼 것, 비싼 것</h2><div class="lead">평년 가격과 비교한 소매 가격 등락률</div>'
            f'<div class="sec"><i style="background:{GRADES["GREEN"][1]}"></i>평년보다 싼 품목</div><div class="list">{_rows(cheap, mx)}</div>')
    if pricey:
        body += f'<div class="sec"><i style="background:{GRADES["RED"][1]}"></i>평년보다 비싼 품목</div><div class="list">{_rows(pricey, mx)}</div>'
    return body


def slide3(d: dict, causes: list[dict] | None) -> str:
    book, idx, asof = d["book"], d["idx"], d["asof"]
    cards = []
    for name, kinds in KEY_ITEMS:
        e = book.find(name, kinds) if kinds else book.find(name)
        if e is None:
            continue
        # 대표 등급 시리즈 찾기
        ser = {}
        for sid, sv in idx.items():
            c, ic, kc, rc = sid.split("|")
            if c == "01" and ic == e["key"][0] and kc == e["key"][1]:
                if not ser or len(sv) > len(ser):
                    ser = sv
        p30 = itemmod.period_points(ser, asof, 35)
        base = pct(e["today"], e["avg"] or e["y1"])
        wk = pct(e["today"], e["w1"])
        color = GRADES[itemmod.grade_for(base, d["cfg"]["grade"])][1] if base is not None else ACC
        cards.append(f'<div class="it"><div class="h">{icons.item_icon(name, 40, "ic")}{esc(label_of(e["name"], e["kind"]) if len(label_of(e["name"], e["kind"])) <= 6 else e["name"])}<small>{esc(e["unit"])}</small></div>'
                     f'<div class="p">{won(e["today"])}<small>원</small></div>'
                     f'<div class="c"><span>1주 <b style="color:{DOWN if wk is not None and wk < 0 else UP}">{sp(wk)}</b></span><span>평년 <b style="color:{DOWN if base is not None and base < 0 else UP}">{sp(base)}</b></span></div>'
                     f'{spark(p30, color) if len(p30) >= 2 else ""}</div>')
    if causes:
        lis = "".join(f'<li>{esc(c["text"])}<small>{esc(c.get("source", ""))}</small></li>' for c in causes[:3])
        why = f'<div class="why"><b>왜 움직였나</b><ul>{lis}</ul></div>'
    else:
        why = ('<div class="why ph"><b>왜 움직였나</b>뉴스·농업관측 연동 후 이 자리에 품목별 작황·가격 변동 원인 2~3줄이 '
               '출처와 함께 자동으로 들어감</div>')
    return (f'<div class="eyebrow">KEY ITEMS · 5 WEEKS</div><h2>주요 품목 가격 흐름</h2>'
            f'<div class="grid6">{"".join(cards)}</div>{why}')


def slide4(d: dict) -> str:
    picks = [r for r in d["recipes"] if r["pick"]][:3]
    out = []
    for r in picks:
        main = next((i["name"] for i in r["ingredients"] if i["main"]), r["ingredients"][0]["name"])
        g = GRADES[r["main_grade"]]
        ings = ", ".join(i["label"] for i in r["ingredients"][:4])
        out.append(f'<div class="dish"><div class="ic2">{icons.use(icons.dish_icon(r["tags"]), 96, "ic")}{icons.item_icon(main, 80, "ic")}</div>'
                   f'<div><div class="t">{esc(r["name"])}</div><div class="m">{esc(r["servings"])}인분 · {esc(r["time"])}<br>{esc(ings)}</div></div>'
                   f'<div class="cost"><div class="x">{won(r["total"])}<small>원</small></div>'
                   f'<div class="save" style="background:{g[2]};color:{g[3]}">평년보다 {abs(r["saving_pct"]):,.1f}% 절약</div></div></div>')
    return (f'<div class="eyebrow">TODAY\'S RECIPE</div><h2>오늘의 알뜰 요리</h2>'
            f'<div class="lead">주재료가 평년보다 싼 요리 · 재료비는 오늘 소매 가격으로 계산</div>'
            f'<div class="dishes">{"".join(out)}</div>'
            f'<div class="cta">품목별 가격과 레시피 전체는 <b>프로필 링크</b>에서</div>')


def caption(d: dict, causes: list[dict] | None) -> str:
    s, sh, bk, asof = d["s"], d["sh"], d["bk"], d["asof"]
    retail = d["recs"].get("소매", {})
    allr = [r for rs in retail.values() for r in rs if r["base"] is not None]
    cheap, seen = [], set()
    for r in sorted(allr, key=lambda r: r["base"]):
        if r["grade"] == "GREEN" and r["name"] not in seen and len(cheap) < 5:
            cheap.append(r); seen.add(r["name"])
    pricey, seen = [], set()
    for r in sorted(allr, key=lambda r: -r["base"]):
        if r["grade"] in ("RED", "ORANGE") and r["name"] not in seen and len(pricey) < 3:
            pricey.append(r); seen.add(r["name"])
    pick = next((r for r in d["recipes"] if r["pick"]), None)
    idx = bk["idx_avg_all"]
    L = [f"[{kd(asof)} 과일바구니 장보기 브리핑]", "",
         f"장보기 지수 {sh['score']} · {sh['name']}",
         s["headline"].replace(" - ", "\n"), "",
         f"▪ 4인 가구 1주일 과일·채소 장바구니 {won(bk['today'])}원 (평년 가격이면 {won(bk['cost_avg_all'])}원)"]
    if sh["week_change"] is not None:
        L.append(f"▪ 1주 전보다 {abs(sh['week_change']):,.1f}% {'내림' if sh['week_change'] < 0 else '오름'}")
    if cheap:
        L += ["", "평년보다 싼 품목"] + [f"▪ {r['name']} {won(r['today'])}원/{r['unit']} (평년 대비 {sp(r['base'])})" for r in cheap]
    if pricey:
        L += ["", "평년보다 비싼 품목"] + [f"▪ {r['name']} {won(r['today'])}원/{r['unit']} (평년 대비 {sp(r['base'])})" for r in pricey]
    if causes:
        L += ["", "왜 움직였나"] + [f"▪ {c['text']} ({c.get('source', '')})" for c in causes[:3]]
    if pick:
        L += ["", f"오늘의 알뜰 요리: {pick['name']} ({pick['servings']}인분 재료비 {won(pick['total'])}원, 평년보다 {abs(pick['saving_pct']):,.1f}% 절약)"]
    L += ["", "품목별 가격·추이·레시피 전체는 프로필 링크에서",
          f"자료: 한국농수산식품유통공사(aT) KAMIS 농산물유통정보, {kd(asof)} 소매 가격(대표 등급) · 평년은 최근 5년 중 최대·최소를 뺀 평균", "",
          "#과일바구니 #장보기 #장바구니물가 #농산물가격 #오늘의시세 #채소값 #과일값 #물가 #알뜰장보기 #집밥 "
          + " ".join(f"#{r['name']}" for r in cheap[:3])]
    return no_dash("\n".join(L))


def render(asof: str | None, out: Path) -> Path:
    from playwright.sync_api import sync_playwright
    d = build(asof)
    day = out / d["asof"]
    day.mkdir(parents=True, exist_ok=True)
    cf = day / "causes.json"
    causes = json.loads(cf.read_text(encoding="utf-8")) if cf.exists() else None
    slides = [slide1(d), slide2(d), slide3(d, causes), slide4(d)]
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1080, "height": 1080}, device_scale_factor=1)
        for i, body in enumerate(slides, 1):
            html = page(body, i, len(slides), d["asof"])
            (day / f"{i}.html").write_text(html, encoding="utf-8")
            pg.goto((day / f"{i}.html").as_uri())
            pg.wait_for_timeout(300)
            pg.evaluate("document.fonts.ready")
            # 넘침 검사 : 바닥글 위로 내용이 내려오면 실패
            over = pg.evaluate("""()=>{const f=document.querySelector('.foot').getBoundingClientRect().top;
              return [...document.querySelectorAll('.card > *:not(.foot)')].map(e=>e.getBoundingClientRect().bottom).filter(b=>b>f-6).length}""")
            if over:
                print(f"경고: {i}장 내용이 바닥글과 겹침")
            pg.screenshot(path=str(day / f"{i}.jpg"), type="jpeg", quality=92)
            (day / f"{i}.html").unlink()
        b.close()
    (day / "caption.txt").write_text(caption(d, causes), encoding="utf-8")
    print(f"카드뉴스 생성 {d['asof']}: {day}")
    return day


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("date", nargs="?")
    ap.add_argument("--out", default=str(ROOT / "docs" / "insta"))
    a = ap.parse_args()
    render(a.date, Path(a.out))
