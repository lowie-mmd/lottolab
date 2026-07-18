"""台彩官方 JSON API 客戶端（M1 主源，見 DECISIONS.md）。

端點：GET https://api.taiwanlottery.com/TLCAPIWeB/Lottery/Lotto649Result
      ?month=YYYY-MM&pageNum=1&pageSize=50
必要 header：Origin / Referer 指向 www.taiwanlottery.com，否則 403。
"""
from __future__ import annotations

import time
from typing import Any, Iterator, Optional

import requests

API_URL = "https://api.taiwanlottery.com/TLCAPIWeB/Lottery/Lotto649Result"
HEADERS = {
    "Origin": "https://www.taiwanlottery.com",
    "Referer": "https://www.taiwanlottery.com/",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    ),
    "Accept": "application/json",
}

# 台彩接手發行、API 最早涵蓋月份（見 DECISIONS.md）
EARLIEST_YEAR = 2007
EARLIEST_MONTH = 1

# 獎項鍵 → API assign 節點名（規格 §2.2 對照）
TIER_TO_ASSIGN = {
    "t1": "jackpotAssign",
    "t2": "secondAssign",
    "t3": "thirdAssign",
    "t4": "fourthAssign",
    "t5": "fifthAssign",
    "t6": "sixthAssign",
    "t7": "seventhAssign",
    "t8": "normalAssign",
}


def fetch_month(
    year: int, month: int, *, session: Optional[requests.Session] = None,
    retries: int = 3, timeout: int = 25,
) -> list[dict[str, Any]]:
    """抓取某月所有 Lotto649 開獎原始記錄；無資料回傳空清單。"""
    sess = session or requests.Session()
    params = {"month": f"{year:04d}-{month:02d}", "pageNum": 1, "pageSize": 50}
    last_err: Optional[Exception] = None
    for attempt in range(retries):
        try:
            resp = sess.get(API_URL, headers=HEADERS, params=params, timeout=timeout)
            resp.raise_for_status()
            data = resp.json()
            if data.get("rtCode") not in (0, None):
                raise RuntimeError(f"API rtCode={data.get('rtCode')} msg={data.get('rtMsg')}")
            content = data.get("content") or {}
            return content.get("lotto649Res") or []
        except Exception as e:  # noqa: BLE001
            last_err = e
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"抓取 {year}-{month:02d} 失敗：{last_err}")


def iter_months(
    start_year: int = EARLIEST_YEAR, start_month: int = EARLIEST_MONTH,
    end_year: Optional[int] = None, end_month: Optional[int] = None,
) -> Iterator[tuple[int, int]]:
    import datetime as _dt
    if end_year is None or end_month is None:
        today = _dt.date.today()
        end_year, end_month = today.year, today.month
    y, m = start_year, start_month
    while (y, m) <= (end_year, end_month):
        yield y, m
        m += 1
        if m > 12:
            m = 1
            y += 1


def _assign(raw: dict, tier: str) -> dict:
    node = raw.get(TIER_TO_ASSIGN[tier]) or {}
    return node


def parse_record(raw: dict[str, Any]) -> dict[str, Any]:
    """API 原始記錄 → draws.json schema dict（規格 §2.1；對應見 DECISIONS.md）。

    drawNumberSize = 前 6 碼升冪 + 第 7 為特別號。
    """
    size = raw.get("drawNumberSize") or []
    numbers = sorted(size[:6]) if len(size) >= 6 else sorted(size)
    special = size[6] if len(size) >= 7 else None
    date = (raw.get("lotteryDate") or "")[:10]

    prizes: dict[str, dict] = {}
    for tier in TIER_TO_ASSIGN:
        node = _assign(raw, tier)
        prizes[tier] = {
            "winners": node.get("winnerCount"),
            "amount": node.get("perPrize"),
        }

    sales = raw.get("sellAmount")

    return {
        "period": str(raw.get("period")),
        "date": date,
        "numbers": numbers,
        "special": special,
        "sales_amount": sales,
        "prizes": prizes,
        "data_quality": classify_quality(numbers, special, sales, prizes),
        "promo": None,  # 此端點不含節慶加碼（見 DECISIONS.md）
    }


def classify_quality(numbers, special, sales, prizes) -> str:
    """data_quality 三級分類（規格 §2.1）。"""
    from engine.models import QUALITY_FULL, QUALITY_NUMBERS_ONLY, QUALITY_PARTIAL

    has_numbers = bool(numbers) and len(numbers) >= 6 and special is not None
    if not has_numbers:
        return QUALITY_NUMBERS_ONLY
    prizes_complete = all(
        (prizes.get(t, {}).get("winners") is not None
         and prizes.get(t, {}).get("amount") is not None)
        for t in TIER_TO_ASSIGN
    )
    has_sales = sales is not None and sales > 0
    if prizes_complete and has_sales:
        return QUALITY_FULL
    return QUALITY_PARTIAL
