"""E 組｜包牌類（規格 §3.2）。

E01 隨機 7 號包牌（7 注/期）、E02 隨機 8 號包牌（28 注/期）、
E03 熱門 8 號包牌、E04 冷門 8 號包牌、E05 凍結 8 號包牌。
驗證命題：包牌不改變每元期望值，只改變波動性與命中頻率。
"""
from __future__ import annotations

from engine.game import Game, Ticket
from engine.models import Draw
from strategies.util import (
    RECENT_N,
    number_freq,
    seeded_pick,
    strat_seed,
    top_numbers,
    wheel,
)

GROUP = "E"
REG = "TBD"


class _Base:
    group = GROUP
    registered_period = REG

    def __init__(self, game: Game):
        self.game = game
        self._pool = game.pool()
        self._pick = game.pick


class E01RandomWheel7(_Base):
    id = "E01"
    wheel_size = 7

    def predict(self, history: list[Draw]) -> list[Ticket]:
        nums = seeded_pick(self._pool, self.wheel_size, strat_seed(self.id, len(history)))
        return wheel(nums, self._pick)  # C(7,6)=7 注


class E02RandomWheel8(_Base):
    id = "E02"
    wheel_size = 8

    def predict(self, history: list[Draw]) -> list[Ticket]:
        nums = seeded_pick(self._pool, self.wheel_size, strat_seed(self.id, len(history)))
        return wheel(nums, self._pick)  # C(8,6)=28 注


class E03HotWheel8(_Base):
    id = "E03"
    wheel_size = 8

    def predict(self, history: list[Draw]) -> list[Ticket]:
        if not history:
            nums = seeded_pick(self._pool, self.wheel_size, strat_seed(self.id, 0, 999))
        else:
            freq = number_freq(history, RECENT_N)
            nums = top_numbers(freq, self._pool, self.wheel_size, highest_first=True)
        return wheel(nums, self._pick)


class E04ColdWheel8(_Base):
    id = "E04"
    wheel_size = 8

    def predict(self, history: list[Draw]) -> list[Ticket]:
        if not history:
            nums = seeded_pick(self._pool, self.wheel_size, strat_seed(self.id, 0, 999))
        else:
            freq = number_freq(history, RECENT_N)
            score = {x: freq.get(x, 0) for x in self._pool}
            nums = top_numbers(score, self._pool, self.wheel_size, highest_first=False)
        return wheel(nums, self._pick)


class E05FrozenWheel8(_Base):
    id = "E05"
    wheel_size = 8

    def __init__(self, game: Game, numbers):
        super().__init__(game)
        self._nums = tuple(sorted(numbers))
        self._tickets = wheel(self._nums, self._pick)

    def predict(self, history: list[Draw]) -> list[Ticket]:
        return list(self._tickets)


def build_group_e(cfg: dict, game: Game) -> list:
    e = cfg.get("e_group") or {}
    frozen = e.get("E05_wheel")
    if not frozen:
        raise ValueError("E05 尚未凍結，請先執行 tools.freeze_numbers")
    return [
        E01RandomWheel7(game),
        E02RandomWheel8(game),
        E03HotWheel8(game),
        E04ColdWheel8(game),
        E05FrozenWheel8(game, frozen),
    ]
