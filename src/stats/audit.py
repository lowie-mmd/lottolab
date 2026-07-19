"""硬體隨機性審計（規格 §5.2）——獨立於策略驗證，用全歷史。

- 單號頻率卡方適合度檢定（Monte Carlo 校準）
- 特別號獨立卡方（教科書 χ²，每期一顆、跨期獨立，無需校準）
- 號碼配對共現頻率檢定（Monte Carlo 校準；超幾何結構）
- 分段檢定：依年份分窗重跑（MC 校準）
明確不做 NIST 隨機性套件（§5.2）。
誠實標註：台彩定期輪換球組與搖獎機，全歷史混池檢定只能偵測長期系統性偏差。

── MC 校準（R1 裁決 A，2026-07-19）──────────────────────────────────────
大樂透每期同時抽 6 顆不放回：單號每期出現機率 p=6/49，49 顆球次數兩兩負相關。
單號統計量 S=Σ(O−E)²/E 在虛無下 E[S]=49×(1−6/49)=43，小於 χ²₄₈ 的期望 48，
故直接查 χ²₄₈ 表偏保守（真有偏差時較難偵測）。改以模擬公平開獎（每期 49 取 6
不放回）建立實證虛無分布計算 p；並以解析縮放 p=P(χ²₄₈ ≥ S×48/43) 交叉驗證。
特別號每期恰一顆、跨期為 multinomial(n,1/49)，χ²₄₈ 成立，不校準（p 維持原值）。

── 標準化殘差 z（R1 裁決 B）──────────────────────────────────────────────
z=(O−E)/√(E·(1−p))，單號 p=6/49（因子 43/49）、特別號 p=1/49（因子 48/49）。
漏掉 (1−p) 的皮爾森殘差 √E 會系統性低估 z，使灰帶邊界球被漏標。
"""
from __future__ import annotations

from collections import Counter
from functools import lru_cache
from itertools import combinations
from math import comb

import numpy as np
from scipy import stats

from engine.game import Game
from engine.models import Draw

# MC 模擬次數：主檢定（單號＋配對共用一份模擬）與分段（年窗，較輕）
MC_NSIM = 12000
SEG_NSIM = 2500
MC_SEED = 20260719


@lru_cache(maxsize=16)
def _mc_null(n_draws: int, pool_size: int, pick: int, n_sim: int, seed: int):
    """模擬 n_sim 次「公平開獎 n_draws 期」，回傳單號與配對統計量的實證虛無分布。

    單號與配對共用同一批模擬（同 (n_draws,pool,pick,n_sim,seed) 之呼叫命中快取），
    避免重複模擬。回傳 (single_stats, pair_stats)：兩個長度 n_sim 的 np.ndarray。
    """
    rng = np.random.default_rng(seed)
    E1 = n_draws * pick / pool_size
    p_both = comb(pool_size - 2, pick - 2) / comb(pool_size, pick)
    Epair = n_draws * p_both
    triu = np.triu_indices(pool_size, k=1)
    single_stats = np.empty(n_sim)
    pair_stats = np.empty(n_sim)
    for s in range(n_sim):
        r = rng.random((n_draws, pool_size), dtype=np.float32)
        idx = np.argpartition(r, pick, axis=1)[:, :pick]  # 每期取 pick 個相異號
        M = np.zeros((n_draws, pool_size), dtype=np.float32)
        np.put_along_axis(M, idx, np.float32(1.0), axis=1)
        counts = M.sum(axis=0)
        single_stats[s] = (((counts - E1) ** 2) / E1).sum()
        C = M.T @ M                      # 共現矩陣（float32 走 BLAS）；上三角為配對共現次數
        pc = C[triu]
        pair_stats[s] = (((pc - Epair) ** 2) / Epair).sum()
    return single_stats, pair_stats


def _mc_pvalue(observed: float, null: np.ndarray) -> float:
    ge = int((null >= observed).sum())
    return (1 + ge) / (len(null) + 1)


def single_number_chisquare(draws: list[Draw], game: Game,
                            n_sim: int = MC_NSIM, seed: int = MC_SEED) -> dict:
    pool = game.pool()
    pick = game.pick
    counts = Counter()
    for d in draws:
        counts.update(d.numbers)
    observed = [counts.get(n, 0) for n in pool]
    total = sum(observed)
    exp = total / len(pool) if pool else 0
    chi2 = float(sum((o - exp) ** 2 / exp for o in observed)) if exp else 0.0
    df = len(pool) - 1
    # MC 校準 p（主）＋ 解析縮放交叉驗證
    single_null, _ = _mc_null(len(draws), len(pool), pick, n_sim, seed)
    p_mc = _mc_pvalue(chi2, single_null)
    # 解析交叉驗證：S 在虛無下 ≈ (43/48)·χ²₄₈，故 χ²₄₈ ≈ S×48/43（僅 df=48 適用）
    p_analytic = float(stats.chi2.sf(chi2 * 48.0 / 43.0, df)) if df == 48 else None
    return _pack(chi2, p_mc, df, observed, exp, pool, total, p_per=pick / len(pool),
                 p_analytic=p_analytic, n_sim=n_sim, mc_calibrated=True)


def special_chisquare(draws: list[Draw], game: Game) -> dict:
    """特別號：每期一顆、跨期獨立 → 教科書 χ²₄₈ 成立，不做 MC 校準（裁決 A-3）。"""
    pool = game.pool()
    counts = Counter(d.special for d in draws if d.special is not None)
    observed = [counts.get(n, 0) for n in pool]
    total = sum(observed)
    exp = total / len(pool) if pool else 0
    chi2, p = stats.chisquare(observed, [exp] * len(pool))
    return _pack(float(chi2), float(p), len(pool) - 1, observed, exp, pool, total,
                 p_per=1 / len(pool), p_analytic=None, n_sim=None, mc_calibrated=False)


def pair_cooccurrence(draws: list[Draw], game: Game, top_k: int = 15,
                      n_sim: int = MC_NSIM, seed: int = MC_SEED) -> dict:
    """成對共現 vs 超幾何期望，MC 校準。E = n_draws × C(pool-2,pick-2)/C(pool,pick)。"""
    pool = game.pool()
    N = len(pool)
    k = game.pick
    n_draws = len(draws)
    p_both = comb(N - 2, k - 2) / comb(N, k)
    expected = n_draws * p_both

    obs = Counter()
    for d in draws:
        for a, b in combinations(sorted(d.numbers), 2):
            obs[(a, b)] += 1

    chi2 = 0.0
    residuals = []
    for a, b in combinations(pool, 2):
        o = obs.get((a, b), 0)
        chi2 += (o - expected) ** 2 / expected
        z = (o - expected) / (expected ** 0.5)  # 皮爾森殘差（配對變異數結構複雜，供人工檢視）
        residuals.append((abs(z), z, a, b, o))
    residuals.sort(reverse=True)
    n_pairs = comb(N, 2)
    df = n_pairs - 1
    _, pair_null = _mc_null(n_draws, N, k, n_sim, seed)
    p = _mc_pvalue(chi2, pair_null)
    return {
        "test": "pair_cooccurrence",
        "n_draws": n_draws,
        "expected_per_pair": expected,
        "chi2": chi2,
        "df": df,
        "p_value": p,
        "n_pairs": n_pairs,
        "n_sim": n_sim,
        "mc_calibrated": True,
        "top_deviations": [
            {"pair": [a, b], "observed": o, "z": round(z, 3)}
            for _az, z, a, b, o in residuals[:top_k]
        ],
        "note": "配對非獨立，chi2 為近似統計量；p 由 Monte Carlo 校準；top_deviations 供人工檢視離群配對",
    }


def segmented_by_year(draws: list[Draw], game: Game, n_sim: int = SEG_NSIM) -> dict:
    by_year: dict[str, list[Draw]] = {}
    for d in draws:
        y = (d.date or "")[:4]
        if y:
            by_year.setdefault(y, []).append(d)
    out = {}
    for y in sorted(by_year):
        r = single_number_chisquare(by_year[y], game, n_sim=n_sim)
        out[y] = {"n_draws": len(by_year[y]), "chi2": r["chi2"],
                  "p_value": r["p_value"], "df": r["df"]}
    return {"test": "segmented_single_number_by_year", "windows": out,
            "note": "球組輪換的間接偵測：觀察偏差是否集中於特定年份（MC 校準）"}


def _pack(chi2, p, df, observed, exp, pool, total, p_per, p_analytic, n_sim,
          mc_calibrated) -> dict:
    # 標準化殘差 z=(O−E)/√(E·(1−p_per))（裁決 B）
    sd = (exp * (1 - p_per)) ** 0.5 if exp > 0 else 0.0
    devs = []
    for n, o in zip(pool, observed):
        z = (o - exp) / sd if sd > 0 else 0.0
        devs.append((abs(z), z, n, o))
    devs.sort(reverse=True)
    out = {
        "chi2": chi2,
        "p_value": p,
        "df": df,
        "total_observations": total,
        "expected_per_number": exp,
        "z_sd_factor": round(1 - p_per, 6),
        "mc_calibrated": mc_calibrated,
        "top_deviations": [
            {"number": n, "observed": o, "z": round(z, 3)}
            for _az, z, n, o in devs[:10]
        ],
    }
    if n_sim is not None:
        out["n_sim"] = n_sim
    if p_analytic is not None:
        out["p_analytic_scaled_chi2"] = round(p_analytic, 6)
    return out
