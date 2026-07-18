"""A 組｜對照基準（規格 §3.2）：A00–A49，50 個 seeded 純隨機策略。

這是整個實驗的「運氣雲」——真策略必須顯著贏過這 50 個假算法的最佳者
（不是平均，見 §5.1）才算跳出雜訊。

決定性：每策略每期以 seed = seed_base*1000003 + index*10007 + step 導出，
step = len(history)（walk-forward 的期序），純整數運算、跨執行重現、無前視。
"""
from __future__ import annotations

import random

from engine.game import Game, Ticket
from engine.models import Draw


class SeededRandomStrategy:
    group = "A"

    def __init__(
        self,
        sid: str,
        index: int,
        seed_base: int,
        game: Game,
        registered_period: str,
        n_tickets: int = 1,
    ) -> None:
        self.id = sid
        self.index = index
        self.seed_base = seed_base
        self.game = game
        self.registered_period = registered_period
        self.n_tickets = n_tickets
        self._pool = game.pool()
        self._pick = game.pick

    def _seed(self, step: int) -> int:
        return self.seed_base * 1_000_003 + self.index * 10_007 + step

    def predict(self, history: list[Draw]) -> list[Ticket]:
        step = len(history)
        rng = random.Random(self._seed(step))
        tickets: list[Ticket] = []
        for _ in range(self.n_tickets):
            nums = tuple(sorted(rng.sample(self._pool, self._pick)))
            tickets.append(nums)
        return tickets


def build_group_a(cfg: dict, game: Game) -> list[SeededRandomStrategy]:
    """依 config 建立 A00–A49。"""
    a = cfg["strategies"]["A"]
    count = int(a["count"])
    seed_base = int(a["seed_base"])
    reg = a.get("registered_period", "TBD")
    strategies = []
    for i in range(count):
        sid = f"A{i:02d}"
        strategies.append(
            SeededRandomStrategy(sid, i, seed_base, game, reg, n_tickets=1)
        )
    return strategies
