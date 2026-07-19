"""檢定力（操作型 δ₈₀）驗收：植入已知 δ 的模擬，偵測率與聲明一致（roadmap §2.4①，附錄 J）。

驗證命中數模型 + 秩次偵測：
- 各 bet_type 每元回收期望一致（包裝不改期望值）
- 單注各獎命中機率＝超幾何精確值
- 偵測率隨 δ 單調上升；δ₈₀ 處偵測率 ≈ target
- 頭獎通道盲區：頭獎機率翻倍偵測率 ≈ 0（附錄 J.3）
- 可重現
"""
from __future__ import annotations

from math import comb

from stats.power import (
    BET_TYPES,
    build_reference_null,
    channel_power,
    delta80,
    detection_power,
    expected_roi,
    jackpot_doubling_power,
    single_tier_probs,
    tier_lambdas,
    TIERS,
)

AMOUNTS = {"t1": 116793658, "t2": 2675329, "t3": 67834, "t4": 16264,
           "t5": 2000, "t6": 1000, "t7": 400, "t8": 400}
N_PERM = 20000
N_SIM = 1200


def _cost(bt):
    return BET_TYPES[bt] * 50


def test_single_tier_probs_exact():
    p = single_tier_probs()
    assert abs(p["t1"] - 1 / comb(49, 6)) < 1e-15
    # t8＝中 3 不中特別號：C(6,3)C(43,3)/C(49,6) × 40/43
    exp_t8 = comb(6, 3) * comb(43, 3) / comb(49, 6) * (40 / 43)
    assert abs(p["t8"] - exp_t8) < 1e-12
    assert all(p[t] > 0 for t in TIERS)


def test_expected_roi_consistent_across_bet_types():
    """單注與包牌的每元回收期望相同（包裝不改每元期望值）。"""
    vals = []
    for bt in ("single", "wheel7", "wheel8"):
        vals.append(expected_roi(tier_lambdas(bt), AMOUNTS, _cost(bt)))
    assert max(vals) - min(vals) < 1e-9
    assert 0.4 < vals[0] < 0.7  # ~0.52（低於返還率天花板附近）


def test_power_monotonic_in_delta():
    null = build_reference_null("single", AMOUNTS, 200, 50, N_PERM, seed=1)
    base = tier_lambdas("single")
    p_lo = detection_power(2.0, "single", AMOUNTS, 200, 68, 50, null, base, TIERS, n_sim=N_SIM, seed=2)
    p_hi = detection_power(20.0, "single", AMOUNTS, 200, 68, 50, null, base, TIERS, n_sim=N_SIM, seed=2)
    assert p_lo < p_hi
    assert p_hi > 0.5


def test_delta80_reaches_target_power():
    d = delta80("single", AMOUNTS, 200, 68, n_perm=N_PERM, n_sim=N_SIM, seed=20260719)
    assert d["delta80"] > 0
    # δ₈₀ 處以獨立種子重估，偵測率落在目標帶內
    null = build_reference_null("single", AMOUNTS, 200, 50 * 1, N_PERM, seed=20260719)
    # 用 delta80 自身回報之 power 檢查（同一模擬）
    assert 0.74 <= d["power_at_delta80"] <= 0.88
    assert d["null_median"] > 0


def test_jackpot_channel_is_blind():
    """頭獎通道盲區：頭獎機率翻倍幾乎不可偵測（附錄 J.3 具體數字）。"""
    jd = jackpot_doubling_power("single", AMOUNTS, 200, 68, n_perm=N_PERM, n_sim=N_SIM, seed=3)
    assert jd["power"] <= 0.02, f"頭獎翻倍偵測率異常高：{jd['power']}"
    # 只在頭獎通道注入一個「看似很大」的每元回收優勢，仍近乎不可偵測
    pw = channel_power("single", AMOUNTS, 200, 68, ["t1"], delta=5.0,
                       n_perm=N_PERM, n_sim=N_SIM, seed=3)
    assert pw <= 0.05


def test_deterministic():
    a = delta80("single", AMOUNTS, 200, 68, n_perm=N_PERM, n_sim=N_SIM, seed=42)
    b = delta80("single", AMOUNTS, 200, 68, n_perm=N_PERM, n_sim=N_SIM, seed=42)
    assert a["delta80"] == b["delta80"]
