"""檢定力模擬驗收：以已知效應量的合成資料驗證偵測率（roadmap R2 §2.4 ①）。

power.py 的核心與樂透引擎解耦（只吃 null_dist），故可用可控的合成常態 null
驗證機器行為：
- 全域 null（effect=0）下，特定策略被誤判顯著的機率受控（≪ α）
- power 隨 effect 單調上升；大 effect → power→1
- MDE 處的實測 power ≈ target_power
- null 散度越小（等效於期數越多）→ MDE 越小
- 相同 seed 完全可重現
"""
from __future__ import annotations

import random

from stats.power import (
    min_detectable_effect,
    simulate_detection_power,
)

N_STRAT = 68  # 對齊梯次一註冊策略數（FDR 的 N）


def synth_null(mu, sd, n=2000, seed=0):
    """合成常態 null 分布：代表「同結構隨機下注在 n 期上的 ROI 抽樣分布」。
    sd 越小 ≈ 期數越多（ROI 散度隨 √n 收斂）。"""
    rng = random.Random(seed)
    return [rng.gauss(mu, sd) for _ in range(n)]


def test_false_positive_controlled_under_global_null():
    """effect=0：全域 null 下，某特定策略被 BH 判為顯著的機率遠小於 α。
    （全域 null 時 BH 的每假設誤拒機率 ≈ α/N。）"""
    nd = synth_null(0.30, 0.07, seed=1)
    p0 = simulate_detection_power(0.0, nd, N_STRAT, alpha=0.05, n_sim=3000, seed=11)
    assert p0 <= 0.03, f"全域 null 誤判率過高：{p0}"


def test_power_monotonic_in_effect():
    """power 隨 effect 單調上升。"""
    nd = synth_null(0.30, 0.07, seed=2)
    sd = 0.07
    p_lo = simulate_detection_power(0.5 * sd, nd, N_STRAT, n_sim=1500, seed=22)
    p_mid = simulate_detection_power(2.0 * sd, nd, N_STRAT, n_sim=1500, seed=22)
    p_hi = simulate_detection_power(4.0 * sd, nd, N_STRAT, n_sim=1500, seed=22)
    assert p_lo < p_mid < p_hi, f"非單調：{p_lo}, {p_mid}, {p_hi}"


def test_power_reaches_one_for_large_effect():
    """夠大的 effect 幾乎必被偵測。"""
    nd = synth_null(0.30, 0.07, seed=3)
    p = simulate_detection_power(8.0 * 0.07, nd, N_STRAT, n_sim=1500, seed=33)
    assert p >= 0.98, f"大 effect 偵測率不足：{p}"


def test_mde_power_matches_target():
    """min_detectable_effect 回報的 MDE，其獨立重估 power ≈ target。"""
    nd = synth_null(0.30, 0.07, seed=4)
    res = min_detectable_effect(nd, N_STRAT, alpha=0.05, target_power=0.80,
                                n_sim=2500, seed=44)
    assert res["mde"] > 0
    # 以不同 seed、較大 n_sim 獨立重估 MDE 處 power，落在目標帶內
    check = simulate_detection_power(res["mde"], nd, N_STRAT, alpha=0.05,
                                     n_sim=4000, seed=4444)
    assert 0.73 <= check <= 0.88, f"MDE 處 power 偏離目標：{check}"
    # MDE 應為正且落在合理量級（數個 null 標準差內）
    assert res["mde"] < 6 * res["null_sd"]


def test_tighter_null_gives_smaller_mde():
    """null 散度越小（≈ 期數越多）→ MDE 越小。這是『更多期→更靈敏』的量化。"""
    nd_wide = synth_null(0.30, 0.10, seed=5)   # 較少期
    nd_tight = synth_null(0.30, 0.05, seed=5)  # 較多期
    mde_wide = min_detectable_effect(nd_wide, N_STRAT, n_sim=2000, seed=55)["mde"]
    mde_tight = min_detectable_effect(nd_tight, N_STRAT, n_sim=2000, seed=55)["mde"]
    assert mde_tight < mde_wide, f"散度小卻 MDE 較大：tight={mde_tight}, wide={mde_wide}"


def test_deterministic():
    """相同 seed → 完全相同結果（可重現，供學術報告引用）。"""
    nd = synth_null(0.30, 0.07, seed=6)
    a = simulate_detection_power(0.1, nd, N_STRAT, n_sim=1000, seed=66)
    b = simulate_detection_power(0.1, nd, N_STRAT, n_sim=1000, seed=66)
    assert a == b
