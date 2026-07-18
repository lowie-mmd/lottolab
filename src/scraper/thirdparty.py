"""2004–2006 北銀時代 lotto649 第三方來源爬取（延伸資料層，見 DECISIONS.md 2026-07-18）。

無官方源 → 以兩個獨立第三方互相對帳（pilio + lotto-8）。僅取號碼＋特別號＋日期，
一律 numbers_only。範圍鎖定 2004-01 起的 6/49 大樂透（更早的 6/42 屬不同 Game）。
"""
from __future__ import annotations

import re
import time
from typing import Optional

import requests

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36")

PILIO_URL = "https://www.pilio.idv.tw/ltobig/ListbigAPP.asp"
LOTTO8_URL = "https://www.lotto-8.com/listltobigbbk.asp"

# 只保留此區間（含）：北銀時代 6/49
YEAR_MIN, YEAR_MAX = 2004, 2006


def _get(url: str, params: dict, retries: int = 3) -> bytes:
    last = None
    for a in range(retries):
        try:
            r = requests.get(url, params=params, headers={"User-Agent": UA}, timeout=25)
            r.raise_for_status()
            return r.content
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(1.0 * (a + 1))
    raise RuntimeError(f"抓取失敗 {url} {params}: {last}")


def parse_pilio(html: str) -> list[tuple[str, tuple[int, ...], int]]:
    """回傳 [(date 'YYYY-MM-DD', numbers(6, 升冪), special), ...]。"""
    dates = re.findall(r'date-cell">(\d{2})/(\d{2})<br>(\d{2})', html)
    nums = re.findall(r'number-cell">(.*?)</td>', html, re.S)
    bonus = re.findall(r'bonus-cell">\s*(\d+)', html)
    out = []
    n = min(len(dates), len(nums), len(bonus))
    for i in range(n):
        mm, dd, yy = dates[i]
        year = 2000 + int(yy)
        numbers = tuple(sorted(int(x) for x in re.findall(r'\d+', nums[i])[:6]))
        if len(numbers) != 6:
            continue
        out.append((f"{year:04d}-{mm}-{dd}", numbers, int(bonus[i])))
    return out


def parse_lotto8(html: str) -> list[tuple[str, tuple[int, ...], int]]:
    """lotto-8 為連續 <td> 三元組：[日期 '2004 01/05 (週)][6 號][特別號]。逐格掃描配對。"""
    cells = re.findall(r'<td[^>]*>(.*?)</td>', html, re.S)
    texts = []
    for c in cells:
        t = re.sub(r'<[^>]+>', ' ', c).replace('&nbsp;', ' ')
        texts.append(re.sub(r'\s+', ' ', t).strip())
    out = []
    for i, t in enumerate(texts):
        m = re.match(r'^(20\d{2})\s+(\d{2})/(\d{2})', t)
        if not m or i + 2 >= len(texts):
            continue
        nums = re.findall(r'\d+', texts[i + 1])
        sp = re.findall(r'\d+', texts[i + 2])
        if len(nums) < 6 or not sp:
            continue
        year, mm, dd = m.groups()
        numbers = tuple(sorted(int(x) for x in nums[:6]))
        if len(numbers) != 6:
            continue
        out.append((f"{year}-{mm}-{dd}", numbers, int(sp[0])))
    return out


def _fetch_source(url: str, parser, decode: str) -> dict[str, tuple[tuple[int, ...], int]]:
    """orderby=old 由最舊翻頁，收集 2004–2006；超過 2006 即停。回傳 date→(numbers, special)。"""
    result: dict[str, tuple[tuple[int, ...], int]] = {}
    page = 1
    while True:
        raw = _get(url, {"indexpage": page, "orderby": "old"})
        html = raw.decode(decode, errors="ignore")
        rows = parser(html)
        if not rows:
            break
        max_year = 0
        for date, numbers, special in rows:
            year = int(date[:4])
            max_year = max(max_year, year)
            if YEAR_MIN <= year <= YEAR_MAX:
                result[date] = (numbers, special)
        page += 1
        time.sleep(0.3)
        if max_year > YEAR_MAX or page > 40:  # 已越過區間或安全上限
            break
    return result


def fetch_pilio() -> dict[str, tuple[tuple[int, ...], int]]:
    return _fetch_source(PILIO_URL, parse_pilio, "utf-8")


def fetch_lotto8() -> dict[str, tuple[tuple[int, ...], int]]:
    return _fetch_source(LOTTO8_URL, parse_lotto8, "big5")
