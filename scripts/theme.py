"""리포트 공통 디자인 : 색·글꼴·아이콘·CSS·공통 표기 함수"""
from __future__ import annotations

import html
import re
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

import icons

WEEK = "월화수목금토일"

# 가격 수준 : 이름, 주색, 연한 바탕, 진한 글자
GRADES = {
    "GREEN": ("쌈", "#2FA36B", "#E7F5EC", "#19613E"),
    "YELLOW": ("보통", "#D9A62E", "#FBF3DC", "#7A5A0E"),
    "ORANGE": ("비쌈", "#E07A3A", "#FBE9DD", "#9A4A18"),
    "RED": ("매우 비쌈", "#D2495A", "#F9E3E6", "#8E2635"),
}
GRADE_SHORT = {"GREEN": "사기 좋음", "YELLOW": "평년 수준", "ORANGE": "평년보다 비쌈", "RED": "크게 비쌈"}
UP, DOWN = "#C8403F", "#2F62B8"  # 상승 빨강, 하락 파랑
INK, SUB, LINE, PAPER, ACC, GOLD = "#1B1F24", "#6B7280", "#E6E2DA", "#F8F6F1", "#1F5F4A", "#B8923A"

SOURCE_SHORT = "자료: 한국농수산식품유통공사(aT) KAMIS 농산물유통정보"
SOURCE_LONG = ("자료 출처: 한국농수산식품유통공사(aT) 농산물유통정보(KAMIS) 일별 부류별 소매·도매 가격. "
               "가격 수준은 평년(최근 5년 중 최대·최소를 뺀 평균) 대비 등락률 기준")

FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com">'
         '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Noto+Serif+KR:wght@600;700&display=swap">'
         '<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard-dynamic-subset.min.css">')


def face_svg(grade: str, size: int = 18) -> str:
    """가격 수준 표정 (쌈 = 활짝, 보통 = 무표정, 비쌈 = 시무룩, 매우 비쌈 = 울상+땀)"""
    c = GRADES[grade][1]
    mouth = {"GREEN": "M7 13.2q5 4.6 10 0", "YELLOW": "M8 14.6h8",
             "ORANGE": "M8 15.6q4-2.6 8 0", "RED": "M7.6 16.4q4.4-4 8.8 0"}[grade]
    sweat = '<path d="M19.2 4.2q1.8 2.6 0 3.6q-1.8-1 0-3.6z" fill="#7CC4FF"/>' if grade == "RED" else ""
    cheeks = ('<circle cx="6" cy="12.6" r="1.4" fill="#fff" opacity=".45"/>'
              '<circle cx="18" cy="12.6" r="1.4" fill="#fff" opacity=".45"/>' if grade == "GREEN" else "")
    return (f'<svg class="face" width="{size}" height="{size}" viewBox="0 0 24 24" aria-hidden="true">'
            f'<circle cx="12" cy="12" r="11" fill="{c}"/>{cheeks}'
            '<circle cx="8.6" cy="9.6" r="1.35" fill="#2b2b2b"/><circle cx="15.4" cy="9.6" r="1.35" fill="#2b2b2b"/>'
            f'<path d="{mouth}" fill="none" stroke="#2b2b2b" stroke-width="1.6" stroke-linecap="round"/>{sweat}</svg>')


LOGO = (
    '<svg width="38" height="38" viewBox="0 0 48 48" aria-hidden="true">'
    '<path d="M12 22q12-18 24 0" fill="none" stroke="#B07A3C" stroke-width="3" stroke-linecap="round"/>'
    '<circle cx="18" cy="19" r="7" fill="#E25C5C"/><path d="M18 12q2-4 5-4" stroke="#6B4A2B" stroke-width="1.6" fill="none" stroke-linecap="round"/>'
    '<circle cx="29" cy="18.5" r="6.5" fill="#F0A82E"/><path d="M29 12q3-3 6-1.5q-2.5 3-6 1.5z" fill="#3E9F6E"/>'
    '<path d="M7 22h34l-3.5 17a3 3 0 0 1-3 2.4h-21a3 3 0 0 1-3-2.4z" fill="#D9995A"/>'
    '<path d="M9.5 28.5h29M11 34.5h26" stroke="#B07A3C" stroke-width="1.8" stroke-linecap="round"/>'
    '<circle cx="18" cy="20" r="1.2" fill="#fff" opacity=".7"/></svg>'
)


# ---------- 표기 ----------

def won(v: int | None) -> str:
    return "-" if v is None else f"{v:,}"


def sp(p: Decimal | None) -> str:
    if p is None:
        return "-"
    if p == 0:
        return "0.0%"
    return f"+{p:,.1f}%" if p > 0 else f"{p:,.1f}%"


def esc(s) -> str:
    return html.escape(str(s), quote=True)


def kdate(d: str) -> str:
    dt = date.fromisoformat(d)
    return f"{dt.year}년 {dt.month}월 {dt.day}일({WEEK[dt.weekday()]})"


def mdate(d: str) -> str:
    dt = date.fromisoformat(d)
    return f"{dt.month}월 {dt.day}일"


def no_dash(s: str) -> str:
    return s.replace("—", "-").replace("–", "-")


def pct(cur: int | None, base: int | None) -> Decimal | None:
    """정수 가격에서 사사오입 소수 1자리 등락률"""
    if cur is None or not base:
        return None
    return ((Decimal(cur) - Decimal(base)) * 100 / Decimal(base)).quantize(Decimal("0.1"), ROUND_HALF_UP)


def chg_span(p: Decimal | None, cls: str = "n") -> str:
    if p is None:
        return f'<span class="{cls}">-</span>'
    c = UP if p > 0 else DOWN if p < 0 else "inherit"
    return f'<span class="{cls}" style="color:{c}">{sp(p)}</span>'


def badge(grade: str | None, size: int = 16, text: bool = True) -> str:
    if not grade:
        return "-"
    g = GRADES[grade]
    t = f"<em>{g[0]}</em>" if text else ""
    return f'<span class="badge" style="background:{g[2]};color:{g[3]}">{face_svg(grade, size)}{t}</span>'


def strip_unit(kind: str) -> str:
    """끝에 붙은 단위 괄호를 중첩까지 제거: '여름(고랭지)(10kg(그물망 3포기))' -> '여름(고랭지)'"""
    k = kind.strip()
    if not k.endswith(")"):
        return k
    depth = 0
    for i in range(len(k) - 1, -1, -1):
        depth += {")": 1, "(": -1}.get(k[i], 0)
        if depth == 0:
            inner = k[i + 1:-1]
            if re.search(r"\d", inner) and re.search(r"(kg|g|개|포기|마리|속|단|봉|통|L|ml|송이|입|묶음|접)", inner):
                return k[:i].strip()
            return k
    return k


def split_name(item_name: str, kind_name: str) -> tuple[str, str]:
    """(품목명, 품종명) - 품종이 품목명과 같거나 품목명을 포함하면 품종은 빈 문자열"""
    name = item_name.strip()
    kind = strip_unit(kind_name or "")
    if not kind or kind == name or kind in name:
        return name, ""
    return name, kind


def label_of(name: str, kind: str) -> str:
    return f"{name}({kind})" if kind else name


# ---------- CSS ----------

CSS = f"""
:root{{--ink:{INK};--sub:{SUB};--line:{LINE};--paper:{PAPER};--acc:{ACC};--gold:{GOLD};--up:{UP};--down:{DOWN}}}
*{{box-sizing:border-box}}html{{color-scheme:light}}
body{{margin:0;background:#fff;color:var(--ink);font:15px/1.65 Pretendard,"Pretendard Variable",-apple-system,"Apple SD Gothic Neo","Malgun Gothic",sans-serif;font-variant-numeric:tabular-nums;-webkit-font-smoothing:antialiased}}
a{{color:inherit}}
.serif{{font-family:"Noto Serif KR",Pretendard,serif}}
.wrap{{max-width:1080px;margin:0 auto;padding:0 20px 64px}}
header{{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap;padding:22px 0 14px;border-bottom:1px solid var(--ink)}}
.brand{{display:flex;align-items:center;gap:11px;text-decoration:none}}.brand b{{font-size:21px;font-weight:800;letter-spacing:-.03em;display:block;line-height:1.2}}
.brand small{{display:block;font-size:12px;color:var(--sub);font-weight:500;letter-spacing:.02em}}
.meta{{font-size:12.5px;color:var(--sub);text-align:right;line-height:1.5}}.meta b{{color:var(--ink);font-weight:700}}
.src{{display:inline-flex;align-items:center;gap:6px;font-size:12px;color:var(--sub)}}.src i{{font-style:normal;font-weight:800;color:var(--acc);border:1.5px solid var(--acc);border-radius:4px;padding:0 5px;font-size:11px;letter-spacing:.02em}}
.hero{{display:grid;grid-template-columns:1.35fr 1fr;gap:28px;padding:30px 0 26px;border-bottom:1px solid var(--line);align-items:start}}
.eyebrow{{font-size:12px;font-weight:700;letter-spacing:.14em;color:var(--gold);text-transform:uppercase;margin-bottom:10px}}
h1{{font-family:"Noto Serif KR",Pretendard,serif;font-size:30px;line-height:1.42;letter-spacing:-.02em;margin:0 0 18px;word-break:keep-all;font-weight:700}}
.chips{{display:flex;flex-wrap:wrap;align-items:center;gap:6px;font-size:13px;color:var(--sub);font-weight:600}}
.chip{{display:inline-flex;align-items:center;gap:5px;font-size:13px;font-weight:600;padding:3px 11px 3px 5px;border-radius:999px;background:var(--paper);color:#19613E;text-decoration:none;border:1px solid var(--line)}}
.chip:hover{{border-color:var(--acc)}}
.kpis{{display:grid;grid-template-columns:1fr 1fr;gap:0 18px;border-left:1px solid var(--line);padding-left:22px}}
.kpi{{padding:10px 0 12px;border-bottom:1px solid var(--line)}}.kpi:nth-last-child(-n+2){{border-bottom:0}}
.kpi .k{{font-size:12.5px;color:var(--sub);font-weight:600;word-break:keep-all}}.kpi .x{{font-size:28px;font-weight:800;letter-spacing:-.03em;line-height:1.25;white-space:nowrap}}
.kpi .x small{{font-size:13px;font-weight:600;color:var(--sub);margin-left:3px}}
.tabs{{margin-top:8px}}.tabs input{{position:absolute;opacity:0;pointer-events:none}}
.seg{{display:flex;gap:26px;border-bottom:1px solid var(--line);margin-top:4px}}
.seg label{{padding:14px 2px 11px;cursor:pointer;font-weight:700;color:var(--sub);font-size:15px;border-bottom:2px solid transparent;margin-bottom:-1px}}
#t0:checked~.seg label[for=t0],#t1:checked~.seg label[for=t1],#t2:checked~.seg label[for=t2],#t3:checked~.seg label[for=t3]{{color:var(--ink);border-color:var(--ink)}}
.panel{{display:none}}#t0:checked~#p0,#t1:checked~#p1,#t2:checked~#p2,#t3:checked~#p3{{display:block}}
.card{{padding:26px 0 8px;border-bottom:1px solid var(--line)}}.card:last-child{{border-bottom:0}}
h2{{font-family:"Noto Serif KR",Pretendard,serif;font-size:21px;margin:0 0 4px;letter-spacing:-.02em;font-weight:700}}
h2 small{{font-family:Pretendard,sans-serif;font-size:12.5px;color:var(--sub);font-weight:600;margin-left:10px;letter-spacing:0}}
h3{{font-size:13px;margin:20px 0 10px;color:var(--sub);font-weight:700;letter-spacing:.04em}}
.legend{{display:flex;flex-wrap:wrap;gap:6px 16px;font-size:12.5px;color:var(--sub);margin:0 0 14px}}.legend span{{display:inline-flex;align-items:center;gap:5px}}
.bars{{display:grid;grid-template-columns:max-content 1fr;column-gap:14px;row-gap:7px;align-items:center}}
.bl{{font-size:14px;white-space:nowrap;text-align:right;font-weight:600}}.bl a{{text-decoration:none}}.bl a:hover{{color:var(--acc);text-decoration:underline}}.bl sup{{color:var(--sub)}}
.bt{{display:grid;grid-template-columns:1fr 1fr;height:24px}}
.neg,.pos{{display:flex;align-items:center;gap:7px}}.neg{{justify-content:flex-end;border-right:1px solid var(--ink);padding-right:2px}}.pos{{padding-left:2px}}
.bt i{{display:block;height:11px;border-radius:999px}}.v{{font-size:13px;font-weight:800;white-space:nowrap}}
.note,.empty{{color:var(--sub);font-size:12.5px;margin:10px 0 0}}
.tw{{overflow-x:auto;-webkit-overflow-scrolling:touch}}.tf table{{min-width:0}}.tf td.l,.tf th.l{{position:static;white-space:normal;word-break:keep-all}}.tf .n{{min-width:0}}
table{{border-collapse:collapse;width:100%;min-width:780px;font-size:14px}}
th{{font-size:12.5px;color:var(--sub);font-weight:700;padding:9px 6px;border-bottom:1.5px solid var(--ink);white-space:nowrap;text-align:center}}
td{{padding:9px 6px;border-bottom:1px solid var(--line);text-align:center;white-space:nowrap}}
tbody tr:last-child td{{border-bottom:1.5px solid var(--ink)}}
tbody tr:hover td{{background:var(--paper)}}
td.l,th.l{{text-align:left;font-weight:700;padding-left:4px;position:sticky;left:0;background:#fff;z-index:1}}
td.l a{{text-decoration:none}}td.l a:hover{{color:var(--acc);text-decoration:underline}}td.l a::after{{content:" ›";color:var(--gold)}}
td.u{{color:var(--sub);font-size:13px}}
.n{{display:inline-block;min-width:5.2em;text-align:right}}
.badge{{display:inline-flex;align-items:center;gap:5px;font-size:12.5px;font-weight:700;border-radius:999px;padding:2px 10px 2px 3px}}.badge em{{font-style:normal}}
.face{{flex:none;display:block}}.lu,.mn{{display:none}}
.tg{{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:14px}}
.tc{{border:1px solid var(--line);border-radius:6px;padding:12px 14px 6px;text-decoration:none;color:inherit;display:block}}.tc:hover{{border-color:var(--acc)}}
.tt{{display:flex;align-items:center;gap:6px;font-size:14px;flex-wrap:wrap}}.tu{{color:var(--sub);font-size:12px}}
.tp{{margin-left:auto;font-size:12px;font-weight:700;border-radius:999px;padding:1px 8px}}
.tc>svg{{width:100%;height:auto;display:block}}.sv{{font-size:13px;font-weight:800;fill:var(--ink)}}.sd{{font-size:11.5px;fill:var(--sub)}}
.arch{{display:flex;flex-wrap:wrap;gap:6px;padding:0;margin:0;list-style:none}}
.arch a{{display:inline-block;font-size:13px;color:var(--ink);text-decoration:none;border:1px solid var(--line);border-radius:999px;padding:4px 12px}}.arch a:hover{{border-color:var(--acc);color:var(--acc)}}
footer{{margin-top:36px;padding-top:16px;border-top:1px solid var(--ink);color:var(--sub);font-size:12px;line-height:1.8;display:flex;justify-content:space-between;gap:16px;flex-wrap:wrap}}
footer a{{color:var(--acc);font-weight:700;text-decoration:none;white-space:nowrap}}
/* 품목 페이지 */
.crumb{{font-size:13px;color:var(--sub);margin:18px 0 6px}}.crumb a{{text-decoration:none}}.crumb a:hover{{color:var(--acc)}}
.ihead{{display:flex;justify-content:space-between;align-items:flex-end;gap:16px;flex-wrap:wrap;padding-bottom:18px;border-bottom:1px solid var(--line)}}
.ihead h1{{margin:0;font-size:34px}}.ihead .sub{{font-size:14px;color:var(--sub);margin-top:6px}}
.prices{{display:grid;grid-template-columns:1fr 1fr;gap:22px;padding:22px 0;border-bottom:1px solid var(--line)}}
.pc{{border:1px solid var(--line);border-radius:8px;padding:16px 18px 14px;background:#fff}}.pc.main{{background:var(--paper)}}
.pc .t{{display:flex;justify-content:space-between;align-items:center;font-size:13px;color:var(--sub);font-weight:700}}
.pc .big{{font-size:34px;font-weight:800;letter-spacing:-.03em;line-height:1.2;margin:6px 0 2px}}.pc .big small{{font-size:14px;color:var(--sub);font-weight:600;margin-left:4px}}
.pc .vs{{font-size:14px;margin:4px 0 10px}}.pc .vs b{{font-size:17px}}
.mini{{display:grid;grid-template-columns:repeat(4,1fr);gap:6px;border-top:1px solid var(--line);padding-top:10px}}
.mini div{{font-size:11.5px;color:var(--sub);font-weight:600}}.mini b{{display:block;font-size:14px;color:var(--ink)}}
.ptabs{{display:flex;gap:4px;margin:16px 0 8px}}.ptabs-wrap input{{position:absolute;opacity:0;pointer-events:none}}
.ptabs label{{font-size:12.5px;font-weight:700;color:var(--sub);border:1px solid var(--line);border-radius:999px;padding:4px 12px;cursor:pointer}}
.chart{{display:none}}.chart svg{{width:100%;height:auto;display:block}}.cm{{display:none}}
#r30:checked~.ptabs label[for=r30],#r90:checked~.ptabs label[for=r90],#r180:checked~.ptabs label[for=r180],#r365:checked~.ptabs label[for=r365]{{background:var(--ink);color:#fff;border-color:var(--ink)}}
#r30:checked~#c30,#r90:checked~#c90,#r180:checked~#c180,#r365:checked~#c365{{display:block}}
.ax{{font-size:11.5px;fill:var(--sub)}}.lab{{font-size:12.5px;font-weight:800;fill:var(--ink)}}.lab.sub{{fill:var(--sub);font-weight:600}}
.two{{display:grid;grid-template-columns:1fr 1fr;gap:28px}}.two>div{{min-width:0}}
.rep{{list-style:none;padding:0;margin:0}}.rep li{{padding:9px 0 9px 18px;border-bottom:1px solid var(--line);position:relative;font-size:14.5px;word-break:keep-all}}
.rep li::before{{content:"○";position:absolute;left:0;color:var(--acc);font-weight:800;font-size:12px;top:11px}}.rep li:last-child{{border-bottom:0}}
.verdict{{display:flex;align-items:center;gap:12px;padding:14px 16px;border-radius:8px;margin:0 0 6px;font-weight:700;font-size:15px;word-break:keep-all}}.verdict .face{{flex:none}}
.stat{{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-top:8px}}.stat div{{border-top:1.5px solid var(--ink);padding:8px 0}}.stat .k{{font-size:12px;color:var(--sub);font-weight:600}}.stat .x{{font-size:20px;font-weight:800;letter-spacing:-.02em}}.stat .x small{{font-size:12px;color:var(--sub);font-weight:600;margin-left:2px}}
.pos-bar{{height:8px;border-radius:999px;background:linear-gradient(90deg,{GRADES["GREEN"][1]},{GRADES["YELLOW"][1]},{GRADES["RED"][1]});position:relative;margin:10px 0 4px}}
.pos-bar i{{position:absolute;top:-4px;width:16px;height:16px;border-radius:50%;background:#fff;border:3px solid var(--ink);margin-left:-8px}}
.pos-lab{{display:flex;justify-content:space-between;font-size:11.5px;color:var(--sub)}}
@media (max-width:760px){{.hero{{grid-template-columns:1fr;gap:18px}}.kpis{{border-left:0;padding-left:0;border-top:1px solid var(--line)}}.prices{{grid-template-columns:1fr}}.two{{grid-template-columns:1fr}}.ihead h1{{font-size:27px}}}}
@media (max-width:640px){{.cd{{display:none}}.cm{{display:block}}.wrap{{padding:0 16px 48px}}h1{{font-size:23px}}.kpi .x{{font-size:23px}}table{{min-width:0;font-size:13.5px}}td.u,th.u{{display:none}}.fl{{display:none}}.mn{{display:inline}}.lu{{display:block;font-size:11.5px;color:var(--sub);font-weight:500;white-space:normal;word-break:keep-all;max-width:9.5em}}.n{{min-width:0}}.badge{{padding:2px}}.badge em{{display:none}}th,td{{padding:8px 5px}}.bl{{font-size:13px;line-height:1.25}}.bl small{{display:block;font-size:11px;color:var(--sub);font-weight:500}}.bt{{height:auto;min-height:24px}}.v{{font-size:12.5px}}.seg{{gap:18px}}.mini{{grid-template-columns:repeat(2,1fr)}}.stat{{grid-template-columns:1fr 1fr}}.meta{{text-align:left}}}}
@media (max-width:420px){{table{{font-size:12.5px}}th,td{{padding:8px 3px}}.tw{{margin:0 -4px}}.pc .big{{font-size:28px}}.tf table{{font-size:12px}}.tf th,.tf td{{padding:7px 2px}}.tf .badge{{padding:1px}}}}

/* 알뜰 요리 · 장바구니 지수 */
.lead{{font-size:14px;color:var(--sub);margin:4px 0 14px;word-break:keep-all}}
.rgrid{{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}}.rgrid.full{{grid-template-columns:repeat(2,1fr)}}
.rc{{border:1px solid var(--line);border-radius:8px;padding:16px 16px 12px;min-width:0}}
.rc-h{{display:flex;justify-content:space-between;align-items:center;gap:8px;flex-wrap:wrap}}.rc h3{{font-size:19px;margin:0;color:var(--ink);letter-spacing:-.02em;font-weight:700}}
.rc-save{{font-size:12px;font-weight:700;border-radius:999px;padding:2px 9px;white-space:nowrap}}.rc-save.muted{{background:var(--paper);color:var(--sub)}}
.rc-meta{{font-size:12.5px;color:var(--sub);margin:4px 0 10px}}
.rt{{min-width:0;font-size:13px}}.rt th{{white-space:nowrap}}.rt th,.rt td{{padding:6px 4px}}.rt td{{white-space:normal}}.rt.compact td.u,.rt.compact th.u{{display:none}}.rt td.l,.rt th.l{{position:static;padding-left:0;white-space:normal;word-break:keep-all}}.rt .n{{min-width:0}}
.rt td.l small{{display:block;font-size:11px;color:var(--sub);font-weight:500}}.rt .main{{font-size:10.5px;color:var(--acc);font-weight:800;margin-left:4px;vertical-align:1px}}
.rt tr.st td{{color:var(--sub)}}.rt td.u,.rt th.u{{font-size:12px;color:var(--sub)}}
.rc-cost{{display:flex;flex-wrap:wrap;gap:4px 16px;font-size:13px;margin:10px 0 4px;color:var(--sub)}}.rc-cost b{{color:var(--ink)}}.rc-cost .sub{{width:100%;font-size:12px}}
.rc-steps{{margin:10px 0 0;padding-left:20px;font-size:14px;line-height:1.7;word-break:keep-all}}.rc-steps li{{margin-bottom:3px}}
.rc-season{{font-size:12.5px;color:var(--sub);margin:8px 0 0}}
.bk{{display:grid;grid-template-columns:1fr 1.6fr;gap:22px;align-items:stretch;margin:6px 0 16px}}
.bk-main{{background:var(--paper);border-radius:8px;padding:16px 18px}}.bk-main .k{{font-size:13px;color:var(--sub);font-weight:700}}.bk-main .k small{{font-weight:500}}
.bk-main .x{{font-size:48px;font-weight:800;letter-spacing:-.04em;line-height:1.1;margin:4px 0}}.bk-main .v{{font-size:14px;font-weight:700}}
.bk-grid{{display:grid;grid-template-columns:1fr 1fr;gap:10px 18px}}.bk-grid>div{{border-top:1.5px solid var(--ink);padding-top:8px}}
.bk-grid .k{{font-size:12.5px;color:var(--sub);font-weight:600}}.x2{{font-size:24px;font-weight:800;letter-spacing:-.03em}}.x2 small{{font-size:12px;color:var(--sub);font-weight:600;margin-left:2px}}
.cmp{{max-width:640px}}.cmp th{{white-space:normal;line-height:1.3}}.cmp th small{{font-weight:500}}.muted{{color:var(--sub);font-weight:500;font-size:12.5px}}
@media (max-width:900px){{.rgrid,.rgrid.full{{grid-template-columns:1fr 1fr}}}}
@media (max-width:640px){{.rgrid,.rgrid.full{{grid-template-columns:1fr}}.bk{{grid-template-columns:1fr}}.bk-main .x{{font-size:40px}}.rt td.u,.rt th.u{{display:none}}}}

/* 장보기 지수 첫 화면 */
.hero2{{display:grid;grid-template-columns:270px 1fr;gap:30px;padding:26px 0 20px;border-bottom:1px solid var(--line);align-items:center}}
.hero2 .g{{text-align:center}}.gauge{{width:100%;height:auto;display:block}}.gv{{font-size:44px;font-weight:800;letter-spacing:-.04em}}
.gl{{font-size:17px;font-weight:800;margin-top:-6px;letter-spacing:-.02em}}
.hero2 h1{{font-size:27px;margin:0 0 10px}}.hsub{{font-size:15px;color:var(--sub);margin:0 0 14px;word-break:keep-all}}.hsub b{{color:var(--ink)}}
.comp{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;max-width:520px}}.comp>div{{border-top:1.5px solid var(--ink);padding-top:6px}}.comp .k{{font-size:12px;color:var(--sub);font-weight:600}}
.quick{{display:flex;flex-wrap:wrap;gap:8px;padding:14px 0 4px}}.quick a{{font-size:13px;font-weight:700;text-decoration:none;border:1px solid var(--line);border-radius:999px;padding:5px 13px;color:var(--ink)}}.quick a:hover{{border-color:var(--acc);color:var(--acc)}}
.rb{{min-width:720px}}.rb td.g{{color:var(--sub);font-size:12.5px;white-space:nowrap}}.rb td.l small{{display:block;font-size:11.5px;color:var(--sub);font-weight:500;white-space:normal}}
.rc-cost.big{{font-size:15px;margin:4px 0 12px}}.rc-cost.big b{{font-size:20px}}
@media (max-width:760px){{.hero2{{grid-template-columns:1fr;gap:10px}}.hero2 .g{{max-width:260px;margin:0 auto}}.comp{{grid-template-columns:repeat(3,1fr);gap:8px}}.x2{{font-size:20px}}}}
@media (max-width:640px){{.rb{{min-width:0;font-size:12.5px}}.rb td.g,.rb th:first-child,.rb td.u,.rb th.u{{display:none}}.rb th,.rb td{{padding:7px 3px}}}}

/* 스케치 아이콘 */
.ic{{vertical-align:-5px;margin-right:5px;flex:none;display:inline-block}}
.ic.big{{vertical-align:middle;margin:0}}
.ihead .ico{{width:84px;height:84px;flex:none;background:var(--paper);border-radius:50%;display:flex;align-items:center;justify-content:center}}
.ihead>div:first-child{{display:flex;align-items:center;gap:18px}}
.rc-h .dish{{display:flex;align-items:center;gap:0;flex:none}}.rc-h .dish .ic{{margin:0}}.rc-h .dish .ic+.ic{{margin-left:-10px}}
.rc-h .tl{{display:flex;align-items:center;gap:10px;min-width:0}}
.tt .ic{{vertical-align:-4px}}
.bl .ic{{vertical-align:-5px}}
"""


def shell(title: str, body: str, rel: str, asof: str, fetched: str, extra_meta: str = "") -> str:
    """공통 머리글·바닥글이 붙은 전체 HTML"""
    out = f"""<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><meta name="color-scheme" content="light">
<title>{esc(title)}</title>{FONTS}<style>{CSS}</style></head><body>{icons.sprite()}<div class="wrap">
<header><a class="brand" href="{rel}index.html">{LOGO}<div><b>과일바구니</b><small>과일·채소 가격 리포트</small></div></a>
<div class="meta"><span class="src"><i>aT</i>{esc(SOURCE_SHORT[4:])}</span><br>조사일 <b>{kdate(asof)}</b> · 갱신 {esc(fetched)}{extra_meta}</div></header>
{body}
<footer><span>{esc(SOURCE_LONG)}</span><span>매일 자동 수집·생성 · <a href="{rel}fruitbasket_prices.xlsx">엑셀 받기</a></span></footer>
</div></body></html>"""
    return no_dash(out)
