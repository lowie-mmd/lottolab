"""策略共用工具：決定性種子、頻率／遺漏統計、包牌展開。

所有含隨機的策略均以 strat_seed(id, step) 導出種子，step=len(history)，
純整數、跨執行重現、無前視（不觸及當期或未來）。
"""
from __future__ import annotations

import itertools
import random
from collections import Counter

from engine.game import Game, Ticket
from engine.models import Draw

RECENT_N = 50  # 「近 50 期」預設窗（規格 §3.2 B 組）


def id_seed(sid: str) -> int:
    h = 0
    for ch in sid:
        h = h * 131 + ord(ch)
    return h & 0x7FFFFFFF


def strat_seed(sid: str, step: int, extra: int = 0) -> int:
    return (id_seed(sid) * 1_000_003 + step * 10_007 + extra) & 0x7FFFFFFF


def recent(history: list[Draw], n: int) -> list[Draw]:
    return history[-n:] if n else history


def number_freq(history: list[Draw], n: int) -> Counter:
    c: Counter = Counter()
    for d in recent(history, n):
        c.update(d.numbers)
    return c


def gaps(history: list[Draw], game: Game) -> dict[int, int]:
    """每個號碼距今幾期未出現；從未出現給予最大遺漏。"""
    last: dict[int, int] = {}
    for idx, d in enumerate(history):
        for x in d.numbers:
            last[x] = idx
    L = len(history)
    return {x: (L - last[x] if x in last else L + 1) for x in game.pool()}


def rank_pool(score_map: dict[int, float], pool: list[int], highest_first: bool) -> list[int]:
    """依分數排序 pool；同分以號碼升冪決勝（決定性）。"""
    return sorted(
        pool,
        key=lambda x: (-(score_map.get(x, 0)) if highest_first else score_map.get(x, 0), x),
    )


def top_numbers(score_map, pool, k, highest_first) -> tuple[int, ...]:
    chosen = rank_pool(score_map, pool, highest_first)[:k]
    return tuple(sorted(chosen))


def seeded_pick(pool: list[int], k: int, seed: int) -> tuple[int, ...]:
    rng = random.Random(seed)
    return tuple(sorted(rng.sample(pool, k)))


def weighted_pick(pool: list[int], weights: dict[int, float], k: int, seed: int) -> tuple[int, ...]:
    """無放回加權抽 k 個（決定性，依 seed）。權重全 0 時退化為等權。"""
    rng = random.Random(seed)
    remaining = list(pool)
    w = [max(weights.get(x, 0.0), 0.0) for x in remaining]
    if sum(w) <= 0:
        return seeded_pick(pool, k, seed)
    chosen: list[int] = []
    for _ in range(k):
        total = sum(w)
        if total <= 0:
            chosen.extend(rng.sample(remaining, k - len(chosen)))
            break
        r = rng.random() * total
        acc = 0.0
        idx = 0
        for i, wi in enumerate(w):
            acc += wi
            if r <= acc:
                idx = i
                break
        chosen.append(remaining.pop(idx))
        w.pop(idx)
    return tuple(sorted(chosen))


def wheel(numbers, pick: int) -> list[Ticket]:
    """包牌展開：從 numbers 取所有 C(len, pick) 組合為多注。"""
    return [tuple(sorted(c)) for c in itertools.combinations(sorted(numbers), pick)]
