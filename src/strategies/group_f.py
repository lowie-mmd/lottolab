"""F 組｜反熱門類（規格 §3.2）。

F01 全大號（6 號皆 >31）、F02 反模式（排除順子／等差／同尾過多後隨機）。
誠實標註：理論優勢僅在高額獎項分獎時體現，回測低獎項損益量測不到；
由 6.3 熱門度分析間接驗證其前提。
"""
from __future__ import annotations

import random
from collections import Counter

from engine.game import Game, Ticket
from engine.models import Draw
from strategies.util import seeded_pick, strat_seed

GROUP = "F"
REG = "115000072"


class _Base:
    group = GROUP
    registered_period = REG

    def __init__(self, game: Game):
        self.game = game
        self._pool = game.pool()
        self._pick = game.pick


class F01AllHigh(_Base):
    id = "F01"

    def predict(self, history: list[Draw]) -> list[Ticket]:
        high_pool = [n for n in self._pool if n > 31]
        return [seeded_pick(high_pool, self._pick, strat_seed(self.id, len(history)))]


def _has_run(nums: list[int], run_len: int = 3) -> bool:
    """是否含 run_len 個以上連續號（順子）。"""
    s = sorted(nums)
    run = 1
    for i in range(1, len(s)):
        run = run + 1 if s[i] == s[i - 1] + 1 else 1
        if run >= run_len:
            return True
    return False


def _is_arithmetic(nums: list[int]) -> bool:
    """整組是否構成等差數列。"""
    s = sorted(nums)
    d = s[1] - s[0]
    return all(s[i + 1] - s[i] == d for i in range(len(s) - 1))


def _tail_overloaded(nums: list[int], limit: int = 3) -> bool:
    """同尾數是否過多（>= limit）。"""
    c = Counter(n % 10 for n in nums)
    return max(c.values()) >= limit


def anti_pattern_ok(nums: list[int]) -> bool:
    return not (_has_run(nums) or _is_arithmetic(nums) or _tail_overloaded(nums))


class F02AntiPattern(_Base):
    id = "F02"

    def predict(self, history: list[Draw]) -> list[Ticket]:
        step = len(history)
        rng = random.Random(strat_seed(self.id, step))
        for _ in range(200):
            cand = sorted(rng.sample(self._pool, self._pick))
            if anti_pattern_ok(cand):
                return [tuple(cand)]
        # 極少數退化情況：直接回傳最後候選
        return [tuple(sorted(rng.sample(self._pool, self._pick)))]


def build_group_f(game: Game) -> list:
    return [F01AllHigh(game), F02AntiPattern(game)]
