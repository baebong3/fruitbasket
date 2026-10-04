"""과일바구니 장바구니 지수 : 고정 장바구니 비용(평년 = 100)과 외부 공개 물가지표 비교"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

import store
from items import line_chart
from pricing import PriceBook, load_yaml, parse_unit, rint
from theme import ACC, GOLD, UP, DOWN, chg_span, esc, pct, sp, won, label_of


def q1(x: Decimal) -> Decimal:
    return x.quantize(Decimal("0.1"), ROUND_HALF_UP)


def basket_costs(book: PriceBook) -> dict:
    """장바구니 항목별 오늘·평년·1년 전·1개월 전·1주 전 비용"""
    spec = load_yaml("basket.yml")
    rows, miss = [], []
    for b in spec["items"]:
        e = book.find(b["item"], b.get("kind", ""))
        if e is None:
            miss.append(b["item"])
            continue
        qty, unit = Decimal(str(b["qty"])), b["unit"]
        c = {k: book.cost(e, qty, unit, k) for k in ("today", "avg", "y1", "m1", "w1")}
        if c["today"] is None:
            miss.append(b["item"])
            continue
        rows.append({"label": label_of(e["name"], e["kind"]), "group": b["group"], "qty": b["qty"], "unit": unit,
                     "rank": e["rank"], "price": e["today"], "price_unit": e["unit"], "key": e["key"], "entry": e, **c})
    return {"spec": spec, "rows": rows, "missing": miss}


def sums(rows: list[dict], key: str, group: str | None = None) -> Decimal | None:
    """해당 비교값이 있는 항목만 더함 - 오늘 비용도 같은 항목으로 맞춰 비교"""
    sel = [r for r in rows if (group is None or r["group"] == group) and r[key] is not None]
    return sum((r[key] for r in sel), Decimal(0)) if sel else None


def sum_today_matching(rows: list[dict], key: str, group: str | None = None) -> Decimal | None:
    sel = [r for r in rows if (group is None or r["group"] == group) and r[key] is not None]
    return sum((r["today"] for r in sel), Decimal(0)) if sel else None


def index_of(rows: list[dict], key: str, group: str | None = None) -> Decimal | None:
    base, cur = sums(rows, key, group), sum_today_matching(rows, key, group)
    if not base or cur is None:
        return None
    return q1(cur * 100 / base)


def history_series(book: PriceBook, rows: list[dict], history: list[dict], asof: str, days: int = 365) -> list[tuple[str, int]]:
    """일별 장바구니 비용(원) - 그날 조사 없는 품목은 직전 조사 가격을 씀 (전 품목 가격이 한 번 이상 나온 날부터)"""
    start = (date.fromisoformat(asof) - timedelta(days=days)).isoformat()
    sids = {}
    for r in rows:
        e = r["entry"]
        sids[r["label"]] = ("|".join(["01", e["key"][0], e["key"][1], ""]), r)  # rank_code 는 아래에서 맞춤
    # 시리즈 id 는 cls|item|kind|rank_code 이므로 이력에서 rank 이름으로 찾음
    by_key: dict = defaultdict(dict)
    for h in history:
        if h["cls_code"] != "01" or h["date"] < start or h["date"] > asof:
            continue
        by_key[(h["item_code"], h["kind_code"], h["rank"])][h["date"]] = h["price"]
    dates = sorted({d for s in by_key.values() for d in s})
    last: dict = {}
    out = []
    for d in dates:
        total = Decimal(0)
        ok = True
        for r in rows:
            e = r["entry"]
            ser = by_key.get((e["key"][0], e["key"][1], e["rank"]), {})
            if d in ser:
                last[r["label"]] = ser[d]
            if r["label"] not in last:
                ok = False
                break
            tmp = dict(e, today=last[r["label"]])
            c = book.cost(tmp, Decimal(str(r["qty"])), r["unit"], "today")
            if c is None:
                ok = False
                break
            total += c
        if ok:
            out.append((d, rint(total)))
    return out


def build(book: PriceBook, history: list[dict], asof: str) -> dict:
    bc = basket_costs(book)
    rows = bc["rows"]
    res = {"rows": rows, "missing": bc["missing"], "spec": bc["spec"]}
    res["today"] = rint(sum((r["today"] for r in rows), Decimal(0)))
    for grp in (None, "과일", "채소"):
        k = "all" if grp is None else grp
        res[f"idx_avg_{k}"] = index_of(rows, "avg", grp)
        res[f"idx_y1_{k}"] = index_of(rows, "y1", grp)
        res[f"idx_m1_{k}"] = index_of(rows, "m1", grp)
        res[f"idx_w1_{k}"] = index_of(rows, "w1", grp)
        res[f"cost_{k}"] = rint(sum((r["today"] for r in rows if grp is None or r["group"] == grp), Decimal(0)))
        a = sums(rows, "avg", grp)
        res[f"cost_avg_{k}"] = rint(a) if a is not None else None
    res["series"] = history_series(book, rows, history, asof)
    res["external"] = load_yaml("external.yml")
    return res


def yoy_pct(idx: Decimal | None) -> Decimal | None:
    return None if idx is None else q1(idx - 100)


def section_html(b: dict, rel: str, links: dict, full: bool) -> str:
    ext = b["external"]
    es = ext.get("series", {})
    idx = b["idx_avg_all"]
    verdict = ("평년보다 비쌈" if idx and idx > 100 else "평년보다 쌈" if idx and idx < 100 else "평년 수준") if idx else "-"
    color = UP if idx and idx > 100 else DOWN

    def cmp_row(name: str, ours: Decimal | None, ext_key: str, ext_field: str = "yoy") -> str:
        ev = es.get(ext_key, {}).get(ext_field)
        return (f'<tr><td class="l">{esc(name)}</td><td>{chg_span(ours)}</td>'
                f'<td>{chg_span(Decimal(str(ev)).quantize(Decimal("0.1")) if ev is not None else None)}</td></tr>')
    cmp_tab = (f'<table class="rt cmp"><thead><tr><th class="l">전년 동기 대비</th><th>과일바구니 지수</th><th>국가데이터처 ({esc(ext["reference_month"][:4])}년 {int(ext["reference_month"][5:])}월)</th></tr></thead><tbody>'
               + cmp_row("과일 (신선과실)", yoy_pct(b["idx_y1_과일"]), "신선과실")
               + cmp_row("채소 (신선채소)", yoy_pct(b["idx_y1_채소"]), "신선채소")
               + cmp_row("과일+채소 (신선식품)", yoy_pct(b["idx_y1_all"]), "신선식품지수")
               + f'<tr><td class="l">전월 대비 (신선식품)</td><td>{chg_span(yoy_pct(b["idx_m1_all"]))}</td><td>{chg_span(Decimal(str(es.get("신선식품지수", {}).get("mom"))).quantize(Decimal("0.1")) if es.get("신선식품지수", {}).get("mom") is not None else None)}</td></tr>'
               + "</tbody></table>")
    kpis = (f'<div class="bk"><div class="bk-main"><div class="k">과일바구니 지수 <small>평년 = 100</small></div>'
            f'<div class="x" style="color:{color}">{idx if idx is not None else "-"}</div><div class="v">{esc(verdict)}</div></div>'
            f'<div class="bk-grid">'
            f'<div><div class="k">과일 지수</div><div class="x2">{b["idx_avg_과일"] if b["idx_avg_과일"] is not None else "-"}</div></div>'
            f'<div><div class="k">채소 지수</div><div class="x2">{b["idx_avg_채소"] if b["idx_avg_채소"] is not None else "-"}</div></div>'
            f'<div><div class="k">장바구니 비용</div><div class="x2">{won(b["today"])}<small>원</small></div></div>'
            f'<div><div class="k">평년 가격이면</div><div class="x2">{won(b["cost_avg_all"]) if b["cost_avg_all"] is not None else "-"}<small>원</small></div></div>'
            f'</div></div>')
    chart = ""
    if len(b["series"]) >= 2:
        chart = (f'<h3>장바구니 비용 추이 <span class="muted">최근 1년, 원</span></h3><div class="cd">{line_chart(b["series"], ACC, b["cost_avg_all"], "평년")}</div>'
                 f'<div class="cm">{line_chart(b["series"], ACC, b["cost_avg_all"], "평년", W=400, H=250)}</div>')
    note = (f'<p class="note">{esc(b["spec"]["household"])} 과일·채소 {len(b["rows"])}종 고정 장바구니를 KAMIS 소매 가격(대표 등급)으로 계산. '
            f'지수는 같은 장바구니를 평년 가격으로 샀을 때를 100으로 둔 값. 전년·전월 비교는 국가데이터처 소비자물가동향의 신선식품지수(전년동월비·전월비)와 같은 방향으로 읽되, 과일바구니 지수는 조사일 하루 가격이고 국가데이터처는 월평균·전국 가중치라 수준은 다를 수 있음. '
            f'외부 지표 출처: <a href="{esc(ext["source_url"])}">{esc(ext["source_name"])}</a> ({esc(ext["published"])} 발표)</p>')
    if not full:
        return (f'<div class="card" id="basket"><h2>과일바구니 장바구니 지수<small><a href="{rel}basket.html">상세 보기 ›</a></small></h2>'
                f'{kpis}{cmp_tab}{note}</div>')
    rows = []
    for r in sorted(b["rows"], key=lambda r: (r["group"], -r["today"])):
        href = links.get(r["key"])
        nm = f'<a href="{rel}{href}">{esc(r["label"])}</a>' if href else esc(r["label"])
        rows.append(f'<tr><td class="l">{nm}</td><td class="u">{esc(r["group"])}</td><td>{r["qty"]:g}{esc(r["unit"])}</td>'
                    f'<td class="u">{won(r["price"])}원/{esc(r["price_unit"])}</td><td><span class="n">{won(rint(r["today"]))}</span></td>'
                    f'<td><span class="n">{won(rint(r["avg"])) if r["avg"] is not None else "-"}</span></td>'
                    f'<td>{chg_span(pct(rint(r["today"]), rint(r["avg"])) if r["avg"] else None)}</td></tr>')
    tab = (f'<table class="rt"><thead><tr><th class="l">품목</th><th class="u">구분</th><th>수량</th><th class="u">조사 가격</th>'
           f'<th>오늘 비용(원)</th><th>평년 비용(원)</th><th>평년 대비</th></tr></thead><tbody>{"".join(rows)}</tbody></table>')
    return (f'<div class="card"><h2>과일바구니 장바구니 지수</h2>{kpis}{chart}</div>'
            f'<div class="card"><h2>공개 물가지표와 비교</h2>{cmp_tab}{note}</div>'
            f'<div class="card"><h2>장바구니 구성<small>{esc(b["spec"]["household"])}</small></h2><div class="tw">{tab}</div></div>')
