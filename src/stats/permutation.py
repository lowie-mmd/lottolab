"""策略驗證：permutation test + 對照組冠軍比較（規格 §5.1）。

推論主指標為理論軌 ROI（§4.2）。虛無假說 H0：策略的號碼選擇無預測力，
其每元報酬與「同結構隨機下注」不可區分。

permutation（Monte Carlo）：固定前瞻段開獎序列，將策略每期下注替換為
「同下注結構」的隨機注（單注 / 7 號包牌 / 8 號包牌），重抽 n_perm 次建立
理論軌 ROI 的虛無分布；p = (1 + #{null >= 觀測}) / (n_perm + 1)。

同結構隨機的 null 僅取決於下注結構與開獎序列，與策略內容無關，故依
bet_type 快取共用，避免逐策略重算。
"""
from __future__ import annotations

import itertools
import random
from typing import Callable, Optional

from engine.backtest import TheoreticalPrizeTable, score_period
from engine.game import Game
from engine.models import Draw


def classify_bet_type(tickets: list) -> str:
    """由一期的注組合判定下注結構。"""
    n = len(tickets)
    if n == 1:
        return "single"
    if n == 7:
        return "wheel7"
    if n == 28:
        return "wheel8"
    return f"multi{n}"


def _random_tickets(bet_type: str, game: Game, rng: random.Random) -> list:
    pool = game.pool()
    pick = game.pick
    if bet_type == "single":
        return [tuple(sorted(rng.sample(pool, pick)))]
    if bet_type == "wheel7":
        w = sorted(rng.sample(pool, 7))
        return [tuple(sorted(c)) for c in itertools.combinations(w, pick)]
    if bet_type == "wheel8":
        w = sorted(rng.sample(pool, 8))
        return [tuple(sorted(c)) for c in itertools.combinations(w, pick)]
    # multiN：N 注獨立隨機
    n = int(bet_type.replace("multi", ""))
    return [tuple(sorted(rng.sample(pool, pick))) for _ in range(n)]


def roi_theoretical(game: Game, tickets_per_period: list[list], draws: list[Draw],
                    theo: TheoreticalPrizeTable) -> float:
    total_cost = 0
    total_payout = 0
    for tickets, draw in zip(tickets_per_period, draws):
        res = score_period(game, tickets, draw, theo, "PERM")
        total_cost += res.cost
        total_payout += res.payout_theoretical
    return (total_payout / total_cost) if total_cost else 0.0


def null_roi_distribution(bet_type: str, game: Game, draws: list[Draw],
                          theo: TheoreticalPrizeTable, n_perm: int, seed: int) -> list[float]:
    """同結構隨機下注的理論軌 ROI 虛無分布。"""
    rng = random.Random(seed)
    out = []
    for _ in range(n_perm):
        tickets_per_period = [_random_tickets(bet_type, game, rng) for _ in draws]
        out.append(roi_theoretical(game, tickets_per_period, draws, theo))
    return out


def observed_strategy_roi(game: Game, strategy, draws: list[Draw],
                          theo: TheoreticalPrizeTable, start_index: int) -> tuple[float, str]:
    """策略在 draws[start_index:] 前瞻段的理論軌 ROI 與 bet_type。"""
    tickets_per_period = []
    bet_type = "single"
    for i in range(start_index, len(draws)):
        tickets = list(strategy.predict(draws[:i]))
        if i == start_index:
            bet_type = classify_bet_type(tickets)
        tickets_per_period.append(tickets)
    segment = draws[start_index:]
    return roi_theoretical(game, tickets_per_period, segment, theo), bet_type


def permutation_pvalue(observed: float, null: list[float]) -> float:
    ge = sum(1 for x in null if x >= observed)
    return (1 + ge) / (len(null) + 1)


def run_strategy_validation(
    game: Game,
    strategies: list,
    draws: list[Draw],
    theo: TheoreticalPrizeTable,
    start_index: int,
    n_perm: int = 2000,
    seed: int = 20260718,
) -> dict:
    """對所有策略跑 permutation test，回傳每策略 ROI / p 值 / bet_type，
    以及對照組（A 組）冠軍比較。FDR 由呼叫端以 stats.fdr 套用（N=策略數）。"""
    segment = draws[start_index:]
    results = {}
    # 先算各策略 ROI 與 bet_type
    bet_types_needed = set()
    for s in strategies:
        roi, bt = observed_strategy_roi(game, s, draws, theo, start_index)
        results[s.id] = {"roi_theoretical": roi, "bet_type": bt, "group": s.group}
        bet_types_needed.add(bt)

    # 依 bet_type 快取 null 分布（共用）
    null_cache = {}
    for k, bt in enumerate(sorted(bet_types_needed)):
        null_cache[bt] = null_roi_distribution(bt, game, segment, theo, n_perm, seed + k)

    # p 值
    for sid, r in results.items():
        null = null_cache[r["bet_type"]]
        r["p_value"] = permutation_pvalue(r["roi_theoretical"], null)
        r["null_mean"] = sum(null) / len(null)

    # 對照組冠軍（A 組理論軌 ROI 最佳者，§5.1.1）
    a_rois = [r["roi_theoretical"] for sid, r in results.items() if r["group"] == "A"]
    champion = max(a_rois) if a_rois else None
    for sid, r in results.items():
        r["beats_champion"] = (champion is not None and r["roi_theoretical"] > champion)

    return {
        "n_periods": len(segment),
        "n_perm": n_perm,
        "champion_roi": champion,
        "champion_median": (sorted(a_rois)[len(a_rois) // 2] if a_rois else None),
        "strategies": results,
    }
