"""檢定力分析與最小可偵測效應量（MDE）｜規格 v2.0 學術報告硬要求（roadmap R2 §2.2-3）。

目的：把「接受 H0 ≠ 證明完美隨機」量化。回答——在 n 期、α=0.05（FDR 校正後）、
檢定力 target_power 條件下，一條策略的理論軌 ROI 需偏離對照基準（null 平均）多少，
才可能被偵測到？比這更小的優勢會被淹沒在雜訊裡。

方法：蒙地卡羅，忠實鏡射正式檢定管線（§5.1）——
  1. 檢定統計量＝前瞻段理論軌 ROI（stats.permutation）
  2. null＝同結構隨機下注的 ROI 分布（依 bet_type，permutation.null_roi_distribution）
  3. p 值＝(1 + #{null ≥ 觀測}) / (n_perm + 1)
  4. 跨 N 策略以 BH-FDR 校正（stats.fdr，N＝全部註冊策略數）
偵測＝該策略在 BH 校正後被拒絕（rejected）。

模型：把 null_dist 視為「同結構隨機下注在 n 期上的 ROI 抽樣分布」（平均 μ0）。
一條真有 δ 優勢的策略，其觀測 ROI 建模為 null_dist 的一次抽樣再上移 δ。
power(δ) ＝ 多次模擬中該策略被 BH 拒絕的比例。MDE ＝ 使 power(δ) ≥ target 的最小 δ。

power.py 的核心函式（simulate_detection_power / min_detectable_effect）只吃 null_dist，
與樂透引擎解耦，故可用已知效應量的合成資料獨立驗收（tests/test_power.py，roadmap §2.4 ①）。
null_dist_for_segment() 為便利包裝，供學術報告以真實資料估算 null 散度。
"""
from __future__ import annotations

import bisect
import random
import statistics
from typing import Optional, Sequence

from stats.fdr import benjamini_hochberg


def _pvalue_fn(null_ref: Sequence[float]):
    """回傳 x -> permutation p 值 的閉包；null_ref 為升冪排序後的參照 null 分布。
    p = (1 + #{null ≥ x}) / (m + 1)，與 permutation.permutation_pvalue 同式。"""
    nd = sorted(null_ref)
    m = len(nd)

    def pval(x: float) -> float:
        ge = m - bisect.bisect_left(nd, x)  # #{null ≥ x}
        return (1 + ge) / (m + 1)

    return pval


def simulate_detection_power(
    effect: float,
    null_dist: Sequence[float],
    n_strategies: int,
    alpha: float = 0.05,
    n_sim: int = 2000,
    seed: int = 20260719,
) -> float:
    """在 N 條策略中，一條真有 `effect`（ROI 上移量）的策略被 BH-FDR 偵測到的機率。

    每次模擬：該策略觀測 ROI = 抽 null_dist 一次 + effect；其餘 (N-1) 條為純 null
    （抽 null_dist）。全部算 permutation p 值後跨 N 做 BH，記錄目標策略是否被拒絕。
    """
    if n_strategies < 1:
        raise ValueError("n_strategies 需 >= 1")
    pval = _pvalue_fn(null_dist)
    pool = list(null_dist)
    rng = random.Random(seed)
    hits = 0
    for _ in range(n_sim):
        obs_test = rng.choice(pool) + effect
        pvals = [pval(obs_test)]
        for _ in range(n_strategies - 1):
            pvals.append(pval(rng.choice(pool)))
        rejected = benjamini_hochberg(pvals, alpha)["rejected"]
        if rejected[0]:
            hits += 1
    return hits / n_sim


def min_detectable_effect(
    null_dist: Sequence[float],
    n_strategies: int,
    alpha: float = 0.05,
    target_power: float = 0.80,
    n_sim: int = 3000,
    seed: int = 20260719,
    hi: Optional[float] = None,
    max_iter: int = 40,
) -> dict:
    """二分搜尋最小可偵測效應量（MDE）：使 power(δ) ≥ target_power 的最小 δ。

    回傳 {mde, mde_relative（占 null 平均之比）, power_at_mde, null_mean, null_sd,
          n_strategies, alpha, target_power}。
    """
    pool = list(null_dist)
    mu0 = statistics.mean(pool)
    sd = statistics.pstdev(pool) if len(pool) > 1 else 0.0
    if hi is None:
        hi = max(6.0 * sd, 1e-9)
    # 確保上界可達 target；不足則加倍擴張
    for _ in range(8):
        if simulate_detection_power(hi, pool, n_strategies, alpha, n_sim, seed) >= target_power:
            break
        hi *= 2.0
    lo = 0.0
    tol = max(sd / 400.0, 1e-6)
    power_hi = None
    for _ in range(max_iter):
        mid = (lo + hi) / 2.0
        p = simulate_detection_power(mid, pool, n_strategies, alpha, n_sim, seed)
        if p >= target_power:
            hi = mid
            power_hi = p
        else:
            lo = mid
        if hi - lo < tol:
            break
    if power_hi is None:
        power_hi = simulate_detection_power(hi, pool, n_strategies, alpha, n_sim, seed)
    return {
        "mde": hi,
        "mde_relative": (hi / mu0) if mu0 else None,
        "power_at_mde": power_hi,
        "null_mean": mu0,
        "null_sd": sd,
        "n_strategies": n_strategies,
        "alpha": alpha,
        "target_power": target_power,
    }


def null_dist_for_segment(
    bet_type: str,
    game,
    draws,
    theo,
    n_perm: int = 2000,
    seed: int = 20260719,
) -> list[float]:
    """便利包裝：以正式檢定的同結構隨機機制，產生某 bet_type 在給定開獎段上的
    理論軌 ROI null 分布。供學術報告以真實資料估算 null 散度（決定 MDE）。"""
    from stats.permutation import null_roi_distribution

    return null_roi_distribution(bet_type, game, draws, theo, n_perm, seed)


if __name__ == "__main__":  # 手動快速檢視（非測試）
    import json

    # 合成常態 null 示意：n 期越多、ROI 散度越小、MDE 越小
    for n_eff, sd in [("cohort1~200 期", 0.06), ("cohort2~104 期", 0.085)]:
        rng = random.Random(1)
        nd = [rng.gauss(0.30, sd) for _ in range(2000)]
        r = min_detectable_effect(nd, n_strategies=68, n_sim=1500)
        print(n_eff, json.dumps({k: round(v, 4) if isinstance(v, float) else v
                                 for k, v in r.items()}, ensure_ascii=False))
