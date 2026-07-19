"""B 組｜統計類（規格 §3.2）。

B01 熱門號、B02 冷門號、B03 遺漏回補、B04 尾數分布加權、B05 奇偶大小平衡。
所有策略在 history 不足時退化為決定性 seeded 隨機（不崩潰、不前視）。
"""
from __future__ import annotations

from engine.game import Game, Ticket
from engine.models import Draw
from strategies.util import (
    RECENT_N,
    gaps,
    number_freq,
    seeded_pick,
    strat_seed,
    top_numbers,
    weighted_pick,
)

GROUP = "B"
REG = "115000072"


class _Base:
    group = GROUP
    registered_period = REG

    def __init__(self, game: Game):
        self.game = game
        self._pool = game.pool()
        self._pick = game.pick

    def _fallback(self, step: int) -> Ticket:
        return seeded_pick(self._pool, self._pick, strat_seed(self.id, step, 999))


class B01Hot(_Base):
    id = "B01"

    def predict(self, history: list[Draw]) -> list[Ticket]:
        if not history:
            return [self._fallback(0)]
        freq = number_freq(history, RECENT_N)
        return [top_numbers(freq, self._pool, self._pick, highest_first=True)]


class B02Cold(_Base):
    id = "B02"

    def predict(self, history: list[Draw]) -> list[Ticket]:
        if not history:
            return [self._fallback(0)]
        freq = number_freq(history, RECENT_N)
        # 冷門：頻率最低（含近窗從未出現者，頻率 0）
        score = {x: freq.get(x, 0) for x in self._pool}
        return [top_numbers(score, self._pool, self._pick, highest_first=False)]


class B03Gap(_Base):
    id = "B03"

    def predict(self, history: list[Draw]) -> list[Ticket]:
        if not history:
            return [self._fallback(0)]
        g = gaps(history, self.game)
        return [top_numbers(g, self._pool, self._pick, highest_first=True)]


class B04TailWeighted(_Base):
    id = "B04"

    def predict(self, history: list[Draw]) -> list[Ticket]:
        step = len(history)
        if not history:
            return [self._fallback(step)]
        freq = number_freq(history, RECENT_N)
        # 尾數（個位）頻率
        tail_freq: dict[int, int] = {}
        for x, c in freq.items():
            tail_freq[x % 10] = tail_freq.get(x % 10, 0) + c
        weights = {x: float(tail_freq.get(x % 10, 0)) for x in self._pool}
        return [weighted_pick(self._pool, weights, self._pick, strat_seed(self.id, step))]


class B05Balanced(_Base):
    id = "B05"

    def predict(self, history: list[Draw]) -> list[Ticket]:
        step = len(history)
        rng_seed = strat_seed(self.id, step)
        import random
        rng = random.Random(rng_seed)
        # 3 奇 3 偶、3 小(1-24) 3 大(25-49)。以參數 a 分派四桶（見 DECISIONS 推導）。
        odds = [n for n in self._pool if n % 2 == 1]
        evens = [n for n in self._pool if n % 2 == 0]
        low = set(range(1, 25))
        odd_low = [n for n in odds if n in low]
        odd_high = [n for n in odds if n not in low]
        even_low = [n for n in evens if n in low]
        even_high = [n for n in evens if n not in low]
        a = rng.randint(0, 3)  # odd_low 取 a、odd_high 取 3-a、even_low 取 3-a、even_high 取 a
        try:
            chosen = (
                rng.sample(odd_low, a)
                + rng.sample(odd_high, 3 - a)
                + rng.sample(even_low, 3 - a)
                + rng.sample(even_high, a)
            )
            if len(set(chosen)) == self._pick:
                return [tuple(sorted(chosen))]
        except ValueError:
            pass
        return [self._fallback(step)]


def build_group_b(game: Game) -> list:
    return [B01Hot(game), B02Cold(game), B03Gap(game), B04TailWeighted(game), B05Balanced(game)]
