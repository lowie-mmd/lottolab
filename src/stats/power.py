"""檢定力分析與最小可偵測效應量（δ₈₀）｜roadmap R2 §2.2-3；實作依裁決書附錄 J。

把「接受 H0 ≠ 證明完美隨機」量化：在 n 期、N 條策略、α=0.05（FDR 校正後）、檢定力
80% 條件下，一條策略的理論軌每元回收需偏離對照基準（null）多少（δ₈₀），才可能被
偵測。比這更小的優勢會被淹沒在雜訊裡。

── 操作型定義（附錄 J.2，取代 mean/SD 位移式）──────────────────────────────
本站檢定為秩次型（permutation 百分位 p ＋ BH-FDR），臨界值由 null 極端百分位決定，
不受頭獎稀有事件影響。故 MDE 以模擬計算：
  1. 植入優勢 δ：各獎項命中率等比提升（λ_t → λ_t(1+g)），使理論軌每元回收 +δ
  2. 對真實 null 分布算 permutation p ＝ (1+#{null ≥ 觀測})/(n_perm+1)
  3. 跨 N 策略以 BH-FDR 校正（stats.fdr）→ 該策略是否被拒絕（偵測）
  4. δ₈₀ ＝ 偵測率達 target_power 的最小 δ（二分搜尋）

── 命中數模型（附錄 J.3：消除頭獎跑次跳動）──────────────────────────────────
各 bet_type 每期各獎期望命中數 λ_t（超幾何精確值 × 注數）已知；n 期各獎命中數以
Poisson(n·λ_t) 模擬，理論軌 payout = Σ hits_t·amount_t、每元回收 = payout/(n·cost)。
Poisson 直接穩定處理稀有頭獎（無需抽實際彩票、無跑次跳動），對應 J.3「半解析」精神。
口徑＝完整理論軌（含頭獎），與註冊檢定一致（附錄 J.2）。
"""
from __future__ import annotations

from math import comb
from typing import Dict, Iterable, Optional

import numpy as np

from stats.fdr import benjamini_hochberg

POOL, PICK, SPECIAL_POOL = 49, 6, 43  # 大樂透 49 取 6 + 特別號取自其餘 43
TIERS = ("t1", "t2", "t3", "t4", "t5", "t6", "t7", "t8")
BET_TYPES = {"single": 1, "wheel7": comb(7, 6), "wheel8": comb(8, 6)}  # 注數


def single_tier_probs() -> Dict[str, float]:
    """單注每期各獎命中機率（超幾何精確值）。特別號 P(命中|m 主中)=(6−m)/43。"""
    total = comb(POOL, PICK)
    p: Dict[str, float] = {t: 0.0 for t in TIERS}
    for m in range(2, 7):
        pm = comb(PICK, m) * comb(POOL - PICK, PICK - m) / total
        ps = (PICK - m) / SPECIAL_POOL  # P(特別號在票內 | m 主中)
        if m == 6:
            p["t1"] += pm
        elif m == 5:
            p["t2"] += pm * ps; p["t3"] += pm * (1 - ps)
        elif m == 4:
            p["t4"] += pm * ps; p["t5"] += pm * (1 - ps)
        elif m == 3:
            p["t6"] += pm * ps; p["t8"] += pm * (1 - ps)
        elif m == 2:
            p["t7"] += pm * ps  # m=2 僅「中 2＋特別號」有獎
    return p


def tier_lambdas(bet_type: str) -> Dict[str, float]:
    """各 bet_type 每期各獎期望命中數 λ_t＝注數 × 單注命中機率（期望值線性）。"""
    n_tickets = BET_TYPES[bet_type]
    sp = single_tier_probs()
    return {t: n_tickets * sp[t] for t in TIERS}


def expected_roi(lambdas: Dict[str, float], amounts: Dict[str, float], cost_per_period: float) -> float:
    return sum(lambdas[t] * amounts[t] for t in TIERS) / cost_per_period


def _simulate_roi(lambdas, amounts, n_periods, cost_per_period, n_sim, rng) -> np.ndarray:
    """n_sim 條「n 期理論軌每元回收」樣本（各獎命中數 ~ Poisson(n·λ_t)）。"""
    payout = np.zeros(n_sim)
    for t in TIERS:
        lam = lambdas[t] * n_periods
        if lam <= 0 or amounts[t] == 0:
            continue
        payout += rng.poisson(lam, size=n_sim) * amounts[t]
    return payout / (n_periods * cost_per_period)


def _boost(base: Dict[str, float], tiers: Iterable[str], g: float) -> Dict[str, float]:
    tset = set(tiers)
    return {t: (base[t] * (1 + g) if t in tset else base[t]) for t in TIERS}


def _perm_pvalues(obs: np.ndarray, sorted_null: np.ndarray) -> np.ndarray:
    m = len(sorted_null)
    ge = m - np.searchsorted(sorted_null, obs, side="left")  # #{null ≥ obs}
    return (1 + ge) / (m + 1)


def detection_power(delta, bet_type, amounts, n_periods, n_strategies, cost_per_period,
                    sorted_null, base_lambdas, boost_tiers, alpha=0.05,
                    n_sim=2000, seed=0) -> float:
    """植入優勢 δ（提升 boost_tiers 命中率使每元回收 +δ）的策略被 BH-FDR 偵測的機率。"""
    e_boost = sum(base_lambdas[t] * amounts[t] for t in boost_tiers) / cost_per_period
    if e_boost <= 0:
        return 0.0
    g = delta / e_boost                      # 令 boost_tiers 通道貢獻的每元回收 +δ
    lam = _boost(base_lambdas, boost_tiers, g)
    rng = np.random.default_rng(seed)
    strat = _simulate_roi(lam, amounts, n_periods, cost_per_period, n_sim, rng)
    p_strat = _perm_pvalues(strat, sorted_null)
    null_draw = rng.choice(sorted_null, size=(n_sim, n_strategies - 1))
    p_null = _perm_pvalues(null_draw, sorted_null)
    hits = 0
    for i in range(n_sim):
        pv = [float(p_strat[i])] + p_null[i].tolist()
        if benjamini_hochberg(pv, alpha)["rejected"][0]:
            hits += 1
    return hits / n_sim


def build_reference_null(bet_type, amounts, n_periods, cost_per_period, n_perm, seed) -> np.ndarray:
    rng = np.random.default_rng(seed)
    base = tier_lambdas(bet_type)
    null = _simulate_roi(base, amounts, n_periods, cost_per_period, n_perm, rng)
    null.sort()
    return null


def delta80(bet_type, amounts, n_periods, n_strategies, alpha=0.05, target_power=0.80,
            boost_tiers=None, n_perm=100000, n_sim=2000, seed=20260719,
            hi=None, max_iter=32) -> dict:
    """二分搜尋 δ₈₀：使偵測率達 target_power 的最小每元回收偏離。boost_tiers=None → 全獎項通道。"""
    n_tickets = BET_TYPES[bet_type]
    cost = n_tickets * 50
    base = tier_lambdas(bet_type)
    tiers = tuple(TIERS if boost_tiers is None else boost_tiers)
    sorted_null = build_reference_null(bet_type, amounts, n_periods, cost, n_perm, seed)
    e_base = expected_roi(base, amounts, cost)

    def power_at(d):
        return detection_power(d, bet_type, amounts, n_periods, n_strategies, cost,
                               sorted_null, base, tiers, alpha, n_sim, seed + 1)

    if hi is None:
        hi = max(2.0 * e_base, 0.2)
    for _ in range(10):
        if power_at(hi) >= target_power:
            break
        hi *= 1.7
    lo, p_hi = 0.0, None
    tol = e_base / 300.0
    for _ in range(max_iter):
        mid = (lo + hi) / 2
        if power_at(mid) >= target_power:
            hi, p_hi = mid, None
        else:
            lo = mid
        if hi - lo < tol:
            break
    p_hi = power_at(hi)
    return {
        "bet_type": bet_type, "n_periods": n_periods, "n_strategies": n_strategies,
        "delta80": hi, "delta80_per_100": hi * 100, "power_at_delta80": p_hi,
        "null_median": float(np.median(sorted_null)),
        "null_p95": float(np.quantile(sorted_null, 0.95)),
        "expected_roi_null": e_base, "n_perm": n_perm, "n_sim": n_sim,
        "boost_tiers": list(tiers),
    }


def channel_power(bet_type, amounts, n_periods, n_strategies, boost_tiers, delta,
                  alpha=0.05, n_perm=100000, n_sim=2000, seed=20260719) -> float:
    """在單一通道（boost_tiers）注入每元回收 +δ 時的偵測率（盲區量化用）。"""
    n_tickets = BET_TYPES[bet_type]
    cost = n_tickets * 50
    base = tier_lambdas(bet_type)
    sorted_null = build_reference_null(bet_type, amounts, n_periods, cost, n_perm, seed)
    return detection_power(delta, bet_type, amounts, n_periods, n_strategies, cost,
                           sorted_null, base, tuple(boost_tiers), alpha, n_sim, seed + 1)


def jackpot_doubling_power(bet_type, amounts, n_periods, n_strategies,
                           alpha=0.05, n_perm=100000, n_sim=2000, seed=20260719) -> dict:
    """盲區具體數字：把頭獎(t1)命中率翻倍（g=1）時的偵測率（附錄 J.3）。"""
    n_tickets = BET_TYPES[bet_type]
    cost = n_tickets * 50
    base = tier_lambdas(bet_type)
    sorted_null = build_reference_null(bet_type, amounts, n_periods, cost, n_perm, seed)
    rng = np.random.default_rng(seed + 7)
    lam = _boost(base, ("t1",), 1.0)  # 頭獎機率 ×2
    strat = _simulate_roi(lam, amounts, n_periods, cost, n_sim, rng)
    p_strat = _perm_pvalues(strat, sorted_null)
    null_draw = rng.choice(sorted_null, size=(n_sim, n_strategies - 1))
    p_null = _perm_pvalues(null_draw, sorted_null)
    hits = sum(1 for i in range(n_sim)
               if benjamini_hochberg([float(p_strat[i])] + p_null[i].tolist(), alpha)["rejected"][0])
    extra_roi = base["t1"] * amounts["t1"] / cost  # 翻倍所增加的每元回收
    return {"power": hits / n_sim, "extra_roi_per_100": extra_roi * 100}
