"""硬體隨機性審計（規格 §5.2）——獨立於策略驗證，用全歷史。

- 單號頻率卡方適合度檢定
- 特別號獨立卡方
- 號碼配對共現頻率檢定（對比超幾何期望）
- 分段檢定：依年份分窗重跑
明確不做 NIST 隨機性套件（§5.2）。
誠實標註：台彩定期輪換球組與搖獎機，全歷史混池檢定只能偵測長期系統性偏差。
"""
from __future__ import annotations

from collections import Counter
from itertools import combinations
from math import comb

from scipy import stats

from engine.game import Game
from engine.models import Draw


def single_number_chisquare(draws: list[Draw], game: Game) -> dict:
    pool = game.pool()
    counts = Counter()
    for d in draws:
        counts.update(d.numbers)
    observed = [counts.get(n, 0) for n in pool]
    total = sum(observed)
    expected = [total / len(pool)] * len(pool)
    chi2, p = stats.chisquare(observed, expected)
    return _pack(chi2, p, len(pool) - 1, observed, expected, pool, total)


def special_chisquare(draws: list[Draw], game: Game) -> dict:
    pool = game.pool()
    counts = Counter(d.special for d in draws if d.special is not None)
    observed = [counts.get(n, 0) for n in pool]
    total = sum(observed)
    expected = [total / len(pool)] * len(pool)
    chi2, p = stats.chisquare(observed, expected)
    return _pack(chi2, p, len(pool) - 1, observed, expected, pool, total)


def pair_cooccurrence(draws: list[Draw], game: Game, top_k: int = 15) -> dict:
    """成對共現 vs 超幾何期望。E = n_draws × C(pool-2, pick-2)/C(pool, pick)。"""
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
        z = (o - expected) / (expected ** 0.5)
        residuals.append((abs(z), z, a, b, o))
    residuals.sort(reverse=True)
    n_pairs = comb(N, 2)
    df = n_pairs - 1
    p = stats.chi2.sf(chi2, df)
    return {
        "test": "pair_cooccurrence",
        "n_draws": n_draws,
        "expected_per_pair": expected,
        "chi2": chi2,
        "df": df,
        "p_value": p,
        "n_pairs": n_pairs,
        "top_deviations": [
            {"pair": [a, b], "observed": o, "z": round(z, 3)}
            for _az, z, a, b, o in residuals[:top_k]
        ],
        "note": "配對非獨立，chi2 為近似統計量；top_deviations 供人工檢視離群配對",
    }


def segmented_by_year(draws: list[Draw], game: Game) -> dict:
    by_year: dict[str, list[Draw]] = {}
    for d in draws:
        y = (d.date or "")[:4]
        if y:
            by_year.setdefault(y, []).append(d)
    out = {}
    for y in sorted(by_year):
        r = single_number_chisquare(by_year[y], game)
        out[y] = {"n_draws": len(by_year[y]), "chi2": r["chi2"],
                  "p_value": r["p_value"], "df": r["df"]}
    return {"test": "segmented_single_number_by_year", "windows": out,
            "note": "球組輪換的間接偵測：觀察偏差是否集中於特定年份"}


def _pack(chi2, p, df, observed, expected, pool, total) -> dict:
    # 標準化殘差找最偏離的號
    exp = expected[0] if expected else 0
    devs = []
    for n, o in zip(pool, observed):
        z = (o - exp) / (exp ** 0.5) if exp > 0 else 0.0
        devs.append((abs(z), z, n, o))
    devs.sort(reverse=True)
    return {
        "chi2": chi2,
        "p_value": p,
        "df": df,
        "total_observations": total,
        "expected_per_number": exp,
        "top_deviations": [
            {"number": n, "observed": o, "z": round(z, 3)}
            for _az, z, n, o in devs[:10]
        ],
    }
