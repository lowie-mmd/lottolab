"""M4 驗收：以已知答案的合成資料驗證統計正確性。

- 卡方：植入偏差應被偵測；純隨機不被誤報
- permutation test：植入可利用偏差的策略應顯著；純隨機策略不誤報
- FDR：小型已知案例正確
"""
from __future__ import annotations

import random

from engine.backtest import TheoreticalPrizeTable
from engine.game import Lotto649Game
from engine.models import Draw, QUALITY_FULL
from stats.audit import single_number_chisquare
from stats.fdr import benjamini_hochberg
from stats.permutation import run_strategy_validation

GAME = Lotto649Game()
THEO = TheoreticalPrizeTable(
    fixed={"t5": 2000, "t6": 1000, "t7": 400, "t8": 400},
    frozen_median={"t1": 100000000, "t2": 3000000, "t3": 60000, "t4": 15000},
)


def _draw(period, nums, special):
    prizes = {t: {"winners": 1, "amount": THEO.amount(t)} for t in
              ("t1", "t2", "t3", "t4", "t5", "t6", "t7", "t8")}
    return Draw(period=str(period), date="2020-01-01", numbers=tuple(sorted(nums)),
                special=special, sales_amount=100, prizes=prizes,
                data_quality=QUALITY_FULL, promo=None)


def make_unbiased(n, seed):
    rng = random.Random(seed)
    draws = []
    for i in range(n):
        nums = rng.sample(range(1, 50), 6)
        remaining = [x for x in range(1, 50) if x not in nums]
        draws.append(_draw(100000000 + i, nums, rng.choice(remaining)))
    return draws


def make_biased(n, seed, forced=(7, 13)):
    """植入偏差：號碼 forced 每期必開。"""
    rng = random.Random(seed)
    draws = []
    for i in range(n):
        rest = rng.sample([x for x in range(1, 50) if x not in forced], 6 - len(forced))
        nums = list(forced) + rest
        remaining = [x for x in range(1, 50) if x not in nums]
        draws.append(_draw(100000000 + i, nums, rng.choice(remaining)))
    return draws


# ---------- 卡方 ----------
def test_chisquare_detects_bias():
    r = single_number_chisquare(make_biased(500, 1), GAME)
    assert r["p_value"] < 1e-6, f"植入偏差未被偵測 p={r['p_value']}"


def test_chisquare_no_false_positive():
    r = single_number_chisquare(make_unbiased(2000, 2), GAME)
    assert r["p_value"] > 0.001, f"純隨機被誤報 p={r['p_value']}"


# ---------- permutation test ----------
class _PlantedStrategy:
    """利用偏差：每期必下注含 forced 號。"""
    id = "PLANT"
    group = "Z"
    registered_period = "TBD"

    def __init__(self, forced=(7, 13)):
        self.forced = list(forced)

    def predict(self, history):
        rng = random.Random(1234 + len(history))
        rest = rng.sample([x for x in range(1, 50) if x not in self.forced], 6 - len(self.forced))
        return [tuple(sorted(self.forced + rest))]


class _RandomStrategy:
    id = "RAND"
    group = "A"
    registered_period = "TBD"

    def predict(self, history):
        rng = random.Random(999 + len(history))
        return [tuple(sorted(rng.sample(range(1, 50), 6)))]


def test_permutation_detects_exploitable_bias():
    draws = make_biased(200, 3)
    res = run_strategy_validation(GAME, [_PlantedStrategy(), _RandomStrategy()],
                                  draws, THEO, start_index=0, n_perm=500)
    p_plant = res["strategies"]["PLANT"]["p_value"]
    assert p_plant < 0.05, f"可利用偏差策略未顯著 p={p_plant}"


def test_permutation_no_false_positive_on_random():
    draws = make_unbiased(200, 4)
    res = run_strategy_validation(GAME, [_RandomStrategy()], draws, THEO,
                                  start_index=0, n_perm=500)
    p_rand = res["strategies"]["RAND"]["p_value"]
    assert p_rand > 0.05, f"純隨機策略被誤報 p={p_rand}"


# ---------- FDR ----------
def test_fdr_basic():
    # 一個明顯小 p + 其餘大 p：只有第一個應被拒
    ps = [0.001, 0.4, 0.5, 0.6, 0.8]
    r = benjamini_hochberg(ps, alpha=0.05)
    assert r["rejected"][0] is True
    assert not any(r["rejected"][1:])


def test_fdr_all_null():
    ps = [0.2, 0.5, 0.7, 0.9]
    r = benjamini_hochberg(ps, alpha=0.05)
    assert not any(r["rejected"])


def test_fdr_monotone_qvalues():
    ps = [0.01, 0.02, 0.03, 0.04]
    r = benjamini_hochberg(ps, alpha=0.05)
    # q 值不應隨 p 升冪而下降（單調化）
    order = sorted(range(len(ps)), key=lambda i: ps[i])
    qs = [r["q_values"][i] for i in order]
    assert all(qs[i] <= qs[i + 1] + 1e-12 for i in range(len(qs) - 1))
