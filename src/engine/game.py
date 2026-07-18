"""Game 抽象介面（規格 §10 多玩法擴充架構）。

號碼空間、抽出結構、注的格式、獎金表、計分函數皆由 Game 插件定義；
引擎、統計模組、對照組機制、dashboard 框架**不得寫死 49 選 6 的假設**。
v1 只有一個實作：Lotto649Game。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from .models import Draw, TIERS

Ticket = tuple[int, ...]


class Game(ABC):
    id: str
    pool_min: int
    pool_max: int
    pick: int              # 每注選幾個號
    ticket_cost: int
    tiers: tuple[str, ...]  # 由高至低的獎項鍵

    @abstractmethod
    def score(self, ticket: Ticket, draw: Draw) -> Optional[str]:
        """回傳中獎獎項鍵（如 't1'）；未中獎回傳 None。"""

    @abstractmethod
    def valid_ticket(self, ticket: Ticket) -> bool:
        """檢查一注是否合法（號碼數量、範圍、不重複）。"""

    def pool(self) -> list[int]:
        return list(range(self.pool_min, self.pool_max + 1))


class Lotto649Game(Game):
    """大樂透 6/49（規格 §2.2 獎項對照表）。

    一般號 1–49 選 6；特別號為剩餘 43 顆再抽 1 顆。
    計分：以一注 6 碼對中一般號的個數 + 是否對中特別號決定獎項。
    """

    id = "lotto649"
    pool_min = 1
    pool_max = 49
    pick = 6
    ticket_cost = 50
    tiers = TIERS

    def valid_ticket(self, ticket: Ticket) -> bool:
        if len(ticket) != self.pick:
            return False
        s = set(ticket)
        if len(s) != self.pick:
            return False
        return all(self.pool_min <= n <= self.pool_max for n in s)

    def score(self, ticket: Ticket, draw: Draw) -> Optional[str]:
        drawn = set(draw.numbers)
        t = set(ticket)
        match = len(t & drawn)
        special_hit = draw.special is not None and draw.special in t

        # 規格 §2.2：
        # t1 頭獎 6個 / t2 貳獎 5+特 / t3 參獎 5個 / t4 肆獎 4+特 /
        # t5 伍獎 4個 / t6 陸獎 3+特 / t7 柒獎 2+特 / t8 普獎 3個
        if match == 6:
            return "t1"
        if match == 5:
            return "t2" if special_hit else "t3"
        if match == 4:
            return "t4" if special_hit else "t5"
        if match == 3:
            return "t6" if special_hit else "t8"
        if match == 2 and special_hit:
            return "t7"
        return None


_REGISTRY: dict[str, Game] = {
    Lotto649Game.id: Lotto649Game(),
}


def get_game(game_id: str) -> Game:
    if game_id not in _REGISTRY:
        raise KeyError(f"未註冊的玩法：{game_id}")
    return _REGISTRY[game_id]
