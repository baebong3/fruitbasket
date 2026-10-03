"""KAMIS Open API 클라이언트 (부류별 일별 가격: dailyPriceByCategoryList)

환경변수
  KAMIS_CERT_KEY   KAMIS 인증키 (필수)
  KAMIS_CERT_ID    KAMIS 요청자 ID (필수)
  KAMIS_PROXY_URL  (선택) 해외 IP 차단 시 사용할 중계 URL.
                   설정하면 같은 쿼리스트링을 이 URL로 보냄
                   (예: 기존 Supabase Edge Function / Cloudflare Worker 중계)
"""
from __future__ import annotations

import os
import re
import time
from typing import Any

import requests

BASE_URL = "https://www.kamis.or.kr/service/price/xml.do"

# dayN 라벨 -> 표준 키. KAMIS가 라벨 순서를 바꿔도 라벨로 매핑
LABEL_KEYS = [
    (re.compile(r"당일"), "today"),
    (re.compile(r"1일\s*전"), "d1"),
    (re.compile(r"1주일?\s*전"), "w1"),
    (re.compile(r"2주일?\s*전"), "w2"),
    (re.compile(r"1개월\s*전"), "m1"),
    (re.compile(r"1년\s*전"), "y1"),
    (re.compile(r"평년"), "avg"),
]


class KamisError(RuntimeError):
    pass


def to_int(v: Any) -> int | None:
    """'12,345' -> 12345, '-'/''/[] -> None"""
    if v is None or isinstance(v, (list, dict)):
        return None
    s = str(v).replace(",", "").strip()
    if not s or s == "-":
        return None
    try:
        return int(round(float(s)))
    except ValueError:
        return None


def parse_items(payload: dict) -> tuple[str, list[dict]]:
    """응답 JSON -> (error_code, 표준화된 품목 리스트)"""
    data = payload.get("data")
    if isinstance(data, list):  # 데이터 없음이면 ["001"] 형태로 오는 경우
        code = str(data[0]) if data else "001"
        return code, []
    if not isinstance(data, dict):
        return "999", []
    code = str(data.get("error_code", "000"))
    items = data.get("item") or []
    if isinstance(items, dict):  # 1건이면 dict로 옴
        items = [items]
    out = []
    for it in items:
        prices: dict[str, int | None] = {}
        labels: dict[str, str] = {}
        for n in range(1, 10):
            label = it.get(f"day{n}")
            if label is None or isinstance(label, (list, dict)):
                continue
            for pat, key in LABEL_KEYS:
                if pat.search(str(label)):
                    prices[key] = to_int(it.get(f"dpr{n}"))
                    labels[key] = str(label)
                    break
        out.append(
            {
                "item_code": str(it.get("item_code", "")),
                "item_name": str(it.get("item_name", "")).strip(),
                "kind_code": str(it.get("kind_code", "")),
                "kind_name": str(it.get("kind_name", "")).strip(),
                "rank_code": str(it.get("rank_code", "")),
                "rank": str(it.get("rank", "")).strip(),
                "unit": str(it.get("unit", "")).strip(),
                "prices": prices,
                "labels": labels,
            }
        )
    return code, out


def fetch_category(
    regday: str,
    category_code: str,
    product_cls_code: str,
    country_code: str = "",
    retries: int = 3,
) -> tuple[str, list[dict]]:
    key = os.environ.get("KAMIS_CERT_KEY")
    cid = os.environ.get("KAMIS_CERT_ID")
    if not key or not cid:
        raise KamisError("KAMIS_CERT_KEY / KAMIS_CERT_ID 환경변수가 없음")
    params = {
        "action": "dailyPriceByCategoryList",
        "p_product_cls_code": product_cls_code,
        "p_country_code": country_code,
        "p_regday": regday,
        "p_convert_kg_yn": "N",
        "p_item_category_code": category_code,
        "p_cert_key": key,
        "p_cert_id": cid,
        "p_returntype": "json",
    }
    url = os.environ.get("KAMIS_PROXY_URL") or BASE_URL
    last: Exception | None = None
    for attempt in range(retries):
        try:
            r = requests.get(url, params=params, timeout=30)
            r.raise_for_status()
            return parse_items(r.json())
        except Exception as e:  # 네트워크·JSON 오류 재시도
            last = e
            time.sleep(3 * (attempt + 1))
    raise KamisError(f"KAMIS 요청 실패 ({category_code}/{product_cls_code}/{regday}): {last}")
