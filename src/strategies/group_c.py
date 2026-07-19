"""C 組｜序列類（規格 §3.2）。

C01 馬可夫共現轉移、C02 上期重複 1–2 號＋隨機、C03 差值分布生成。
"""
from __future__ import annotations

import random
from collections import Counter

from engine.game import Game, Ticket
from engine.models import Draw
from strategies.util import RECENT_N, recent, seeded_pick, strat_seed

GROUP = "C"
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


class C01Markov(_Base):
    id = "C01"

    def predict(self, history: list[Draw]) -> list[Ticket]:
        step = len(history)
        if not history:
            return [self._fallback(step)]
        # 共現計數（全歷史）
        cooc: Counter = Counter()
        for d in history:
            nums = d.numbers
            for i in range(len(nums)):
                for j in range(i + 1, len(nums)):
                    cooc[(nums[i], nums[j])] += 1
                    cooc[(nums[j], nums[i])] += 1
        last = set(history[-1].numbers)
        score = {}
        for cand in self._pool:
            score[cand] = sum(cooc.get((cand, ln), 0) for ln in last)
        # 依共現分數高→低，同分升冪
        ranked = sorted(self._pool, key=lambda x: (-score[x], x))
        return [tuple(sorted(ranked[: self._pick]))]


class C02Repeat(_Base):
    id = "C02"

    def predict(self, history: list[Draw]) -> list[Ticket]:
        step = len(history)
        if not history:
            return [self._fallback(step)]
        rng = random.Random(strat_seed(self.id, step))
        last = list(history[-1].numbers)
        r = rng.choice([1, 2])
        r = min(r, len(last))
        repeats = rng.sample(last, r)
        remaining = [n for n in self._pool if n not in repeats]
        fill = rng.sample(remaining, self._pick - r)
        return [tuple(sorted(repeats + fill))]


class C03DiffDist(_Base):
    id = "C03"

    def predict(self, history: list[Draw]) -> list[Ticket]:
        step = len(history)
        if not history:
            return [self._fallback(step)]
        diffs: list[int] = []
        for d in recent(history, RECENT_N):
            nums = sorted(d.numbers)
            diffs.extend(nums[i + 1] - nums[i] for i in range(len(nums) - 1))
        if not diffs:
            return [self._fallback(step)]
        rng = random.Random(strat_seed(self.id, step))
        lo, hi = self.game.pool_min, self.game.pool_max
        for _ in range(50):  # 有限重試以滿足合法性
            start = rng.randint(lo, lo + 8)
            nums = [start]
            ok = True
            for _ in range(self._pick - 1):
                nxt = nums[-1] + rng.choice(diffs)
                if nxt > hi or nxt in nums:
                    ok = False
                    break
                nums.append(nxt)
            if ok and len(set(nums)) == self._pick:
                return [tuple(sorted(nums))]
        return [self._fallback(step)]


def build_group_c(game: Game) -> list:
    return [C01Markov(game), C02Repeat(game), C03DiffDist(game)]
