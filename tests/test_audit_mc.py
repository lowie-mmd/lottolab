"""硬體審計 MC 校準驗收（R1 裁決 A，roadmap §11）。

以已知答案的合成資料驗證：
- MC 單號 p 與解析縮放 p=P(χ²₄₈ ≥ S×48/43) 一致（交叉驗證）
- 純隨機（公平開獎）下，MC 校準檢定的型一錯誤率 ≈ 名目值（不因不放回而偏保守）
- 植入偏差時，MC 校準比教科書 χ²₄₈ 至少一樣靈敏（p_mc ≤ p_textbook）
- 特別號檢定未被 MC 改動（教科書 χ²，跨期獨立）
"""
from __future__ import annotations

import random

import numpy as np
from scipy import stats

from engine.game import Lotto649Game
from engine.models import Draw, QUALITY_FULL
from stats.audit import (
    _mc_null,
    _mc_pvalue,
    single_number_chisquare,
    special_chisquare,
)

GAME = Lotto649Game()
POOL, PICK = 49, 6


def _draw(i, nums, special):
    return Draw(period=str(100000000 + i), date="2020-01-01",
                numbers=tuple(sorted(nums)), special=special, sales_amount=100,
                prizes={}, data_quality=QUALITY_FULL, promo=None)


def fair_draws(n, seed):
    rng = random.Random(seed)
    out = []
    for i in range(n):
        nums = rng.sample(range(1, 50), 6)
        rest = [x for x in range(1, 50) if x not in nums]
        out.append(_draw(i, nums, rng.choice(rest)))
    return out


def biased_draws(n, seed, hot=7, extra_p=0.35):
    """植入偏差：每期有 extra_p 機率強制包含號碼 hot。"""
    rng = random.Random(seed)
    out = []
    for i in range(n):
        if rng.random() < extra_p:
            rest = rng.sample([x for x in range(1, 50) if x != hot], 5)
            nums = [hot] + rest
        else:
            nums = rng.sample(range(1, 50), 6)
        others = [x for x in range(1, 50) if x not in nums]
        out.append(_draw(i, nums, rng.choice(others)))
    return out


def test_mc_agrees_with_analytic_scaling():
    """MC 單號 p 與解析縮放 p（S×48/43 查 χ²₄₈）一致。"""
    draws = fair_draws(800, seed=1)
    r = single_number_chisquare(draws, GAME, n_sim=8000, seed=101)
    assert r["mc_calibrated"] is True
    assert abs(r["p_value"] - r["p_analytic_scaled_chi2"]) < 0.03, \
        f"MC 與解析不一致：mc={r['p_value']}, analytic={r['p_analytic_scaled_chi2']}"
    assert abs(r["z_sd_factor"] - (1 - PICK / POOL)) < 1e-5  # 43/49（6 位捨入）


def test_type_one_error_near_nominal_under_null():
    """純隨機下 MC 校準檢定的型一錯誤率 ≈ 名目值（此處驗 α=0.05）。"""
    n_draws = 400
    null, _ = _mc_null(n_draws, POOL, PICK, 6000, seed=202)
    # 另以獨立種子產生 1000 組公平統計量，計其 MC p<0.05 的比率
    rng = np.random.default_rng(999)
    E1 = n_draws * PICK / POOL
    hits = 0
    trials = 1000
    for _ in range(trials):
        rmat = rng.random((n_draws, POOL), dtype=np.float32)
        idx = np.argpartition(rmat, PICK, axis=1)[:, :PICK]
        M = np.zeros((n_draws, POOL), dtype=np.float32)
        np.put_along_axis(M, idx, np.float32(1.0), axis=1)
        counts = M.sum(axis=0)
        S = float((((counts - E1) ** 2) / E1).sum())
        if _mc_pvalue(S, null) < 0.05:
            hits += 1
    rate = hits / trials
    assert 0.03 <= rate <= 0.075, f"型一錯誤率偏離名目 0.05：{rate}"


def test_calibrated_less_conservative_than_textbook():
    """校準修掉保守性：MC 虛無分布的 95 百分位（拒絕門檻）低於教科書 χ²₄₈，
    故對同一統計量 MC 的偵測力 ≥ 教科書；且植入偏差確被 MC 偵測。"""
    null, _ = _mc_null(2000, POOL, PICK, 8000, seed=303)
    mc_crit = float(np.quantile(null, 0.95))
    textbook_crit = float(stats.chi2.ppf(0.95, 48))
    assert mc_crit < textbook_crit, \
        f"MC 拒絕門檻未低於教科書：mc={mc_crit}, textbook={textbook_crit}"
    # 存在一個統計量落在兩門檻之間：MC 判顯著、教科書判不顯著（校準抓到的漏網之魚）
    assert mc_crit < 0.5 * (mc_crit + textbook_crit) < textbook_crit
    # 植入明顯偏差 → MC 偵測（p<0.05）
    r = single_number_chisquare(biased_draws(1500, seed=3), GAME, n_sim=8000, seed=303)
    assert r["p_value"] < 0.05, f"植入偏差未被 MC 偵測：p={r['p_value']}"


def test_special_number_not_mc_calibrated():
    """特別號維持教科書 χ²（不校準），z 因子為 48/49。"""
    draws = fair_draws(600, seed=4)
    r = special_chisquare(draws, GAME)
    assert r["mc_calibrated"] is False
    assert abs(r["z_sd_factor"] - (1 - 1 / POOL)) < 1e-5  # 48/49（6 位捨入）
