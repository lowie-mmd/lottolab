"""資料模型與 draws.json 讀寫（規格 §2.1）。

Draw 為單期開獎的凍結表示。引擎、策略、統計模組皆消費此型別。
容錯設計：早期期數可能為 partial / numbers_only，缺欄位不得使消費端崩潰。
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

# data_quality 三級（規格 §2.1）
QUALITY_FULL = "full"
QUALITY_PARTIAL = "partial"
QUALITY_NUMBERS_ONLY = "numbers_only"

TIERS = ("t1", "t2", "t3", "t4", "t5", "t6", "t7", "t8")


@dataclass(frozen=True)
class Draw:
    period: str
    date: str
    numbers: tuple[int, ...]          # 升冪排序的一般號（lotto649 為 6 碼）
    special: Optional[int]            # 特別號；numbers_only 早期期數可能為 None
    sales_amount: Optional[int]       # 當期銷售金額；partial/numbers_only 可能為 None
    prizes: dict                      # {t1:{winners,amount},...}；缺漏時為空 dict
    data_quality: str                 # full | partial | numbers_only
    promo: Optional[dict] = None      # 節慶加碼（§2.3）；核心引擎不讀

    @property
    def period_int(self) -> int:
        return int(self.period)

    def prize_amount(self, tier: str) -> Optional[int]:
        """該期該獎項的實際單注公告獎額（perPrize）；缺漏回傳 None。"""
        node = self.prizes.get(tier)
        if not node:
            return None
        return node.get("amount")

    def prize_winners(self, tier: str) -> Optional[int]:
        node = self.prizes.get(tier)
        if not node:
            return None
        return node.get("winners")


def draw_from_dict(d: dict[str, Any]) -> Draw:
    return Draw(
        period=str(d["period"]),
        date=d.get("date", ""),
        numbers=tuple(d.get("numbers") or ()),
        special=d.get("special"),
        sales_amount=d.get("sales_amount"),
        prizes=d.get("prizes") or {},
        data_quality=d.get("data_quality", QUALITY_NUMBERS_ONLY),
        promo=d.get("promo"),
    )


def draw_to_dict(dr: Draw) -> dict[str, Any]:
    return {
        "period": dr.period,
        "date": dr.date,
        "numbers": list(dr.numbers),
        "special": dr.special,
        "sales_amount": dr.sales_amount,
        "prizes": dr.prizes,
        "data_quality": dr.data_quality,
        "promo": dr.promo,
    }


def load_draws(path: str | Path) -> list[Draw]:
    """讀取 draws.json，回傳依 period 升冪排序的 Draw 清單。"""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    draws = [draw_from_dict(d) for d in data.get("draws", [])]
    draws.sort(key=lambda d: d.period_int)
    return draws


def load_draws_file(path: str | Path) -> dict[str, Any]:
    """讀取完整 draws.json（含 meta），供爬蟲增量更新。"""
    p = Path(path)
    if not p.exists():
        return {"meta": {}, "draws": []}
    return json.loads(p.read_text(encoding="utf-8"))


def save_draws_file(path: str | Path, meta: dict, draws: list[Draw]) -> None:
    payload = {
        "meta": meta,
        "draws": [draw_to_dict(d) for d in sorted(draws, key=lambda d: d.period_int)],
    }
    Path(path).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
