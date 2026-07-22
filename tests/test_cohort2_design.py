"""梯次二設計驗收：cohort 隔離（A2 對照組）＋雙終點多重性校正（附錄 K.4）。"""
from __future__ import annotations

import json
import random

import pytest

from cohort2.control import (
    build_cohort2_control,
    is_frozen,
    load_cohort2_config,
)
from cohort2.endpoints import (
    dual_endpoint_correction,
    endpoint_prize_table,
    summarize,
)
from engine.game import Lotto649Game
from engine.models import QUALITY_FULL, Draw
from strategies.group_a import build_group_a

GAME = Lotto649Game()
CFG2 = load_cohort2_config()


def _draws(n=60, seed=3):
    rng = random.Random(seed)
    out = []
    for i in range(n):
        nums = tuple(sorted(rng.sample(range(1, 50), 6)))
        sp = rng.choice([x for x in range(1, 50) if x not in nums])
        out.append(Draw(period=str(100000000 + i), date="2020-01-01", numbers=nums, special=sp,
                        sales_amount=100, prizes={}, data_quality=QUALITY_FULL, promo=None))
    return out


DRAWS = _draws()


# ---------- cohort 隔離 ----------

def test_cohort2_control_built():
    ctrl = build_cohort2_control(CFG2, GAME)
    assert len(ctrl) == 50
    assert all(s.group == "A2" for s in ctrl)
    assert ctrl[0].id == "A2-00" and ctrl[-1].id == "A2-49"


def test_cohort2_seed_base_must_be_new():
    bad = json.loads(json.dumps(CFG2))
    bad["control"]["seed_base"] = 42424242  # 梯次一的 seed_base
    with pytest.raises(ValueError):
        build_cohort2_control(bad, GAME)


def test_cohort2_control_does_not_collide_with_cohort1():
    """A2 與梯次一 A 組在同一段歷史上的選號不得雷同（樣本全新）。"""
    cfg1 = json.loads((__import__("pathlib").Path(__file__).resolve().parents[1]
                       / "config" / "config.json").read_text(encoding="utf-8"))
    a1 = build_group_a(cfg1, GAME)
    a2 = build_cohort2_control(CFG2, GAME)
    hist = DRAWS[:30]
    same = 0
    for x, y in zip(a1, a2):
        if set(x.predict(hist)[0]) == set(y.predict(hist)[0]):
            same += 1
    assert same == 0, f"A2 與 A 有 {same} 條在同期選出完全相同的號碼（seeds 未真正獨立）"


def test_cohort2_control_deterministic():
    a2 = build_cohort2_control(CFG2, GAME)[0]
    hist = DRAWS[:20]
    assert a2.predict(hist) == a2.predict(hist)


def test_cohort2_not_frozen_yet():
    """草案階段不得被誤認為已註冊。"""
    assert is_frozen(CFG2) is False
    assert CFG2["registered_period"] is None and CFG2["fdr_n"] is None


# ---------- 雙終點 ----------

def test_endpoint_prize_table_masks_tiers():
    tp = {"fixed": {"t5": 2000, "t6": 1000, "t7": 400, "t8": 400},
          "frozen_median": {"t1": 116793658, "t2": 2675329, "t3": 67834, "t4": 16264}}
    small = endpoint_prize_table(tp, ["t5", "t6", "t7", "t8"])
    assert small.amount("t5") == 2000 and small.amount("t8") == 400
    assert small.amount("t1") == 0 and small.amount("t3") == 0
    full = endpoint_prize_table(tp, ["t1", "t2", "t3", "t4", "t5", "t6", "t7", "t8"])
    assert full.amount("t1") == 116793658


def _pvals(sig_id=None, n=10, sig_p=1e-6):
    d = {f"S{i:02d}": 0.6 for i in range(n)}
    if sig_id:
        d[sig_id] = sig_p
    return d


def test_bonferroni_split_applies_half_alpha():
    pv = {"full_track_roi": _pvals("S03"), "small_prize_roi": _pvals()}
    out = dual_endpoint_correction(pv, alpha=0.05, mode="bonferroni_split")
    assert out["_alpha_per_endpoint"] == pytest.approx(0.025)
    assert out["full_track_roi"]["S03"]["rejected"] is True
    assert out["small_prize_roi"]["S03"]["rejected"] is False
    s = summarize(out)
    assert s["rejected_per_endpoint"]["full_track_roi"] == 1
    assert s["rejected_any_endpoint"] == 1 and s["n_tests"] == 20


def test_pooled_bh_mode():
    pv = {"full_track_roi": _pvals("S01"), "small_prize_roi": _pvals("S01")}
    out = dual_endpoint_correction(pv, alpha=0.05, mode="pooled_bh")
    assert out["full_track_roi"]["S01"]["rejected"] is True
    assert out["small_prize_roi"]["S01"]["rejected"] is True
    assert summarize(out)["rejected_any_endpoint"] == 1


def test_no_false_positive_under_global_null():
    pv = {"full_track_roi": _pvals(), "small_prize_roi": _pvals()}
    for mode in ("bonferroni_split", "pooled_bh"):
        out = dual_endpoint_correction(pv, mode=mode)
        assert summarize(out)["rejected_any_endpoint"] == 0


def test_mismatched_strategy_sets_rejected():
    pv = {"full_track_roi": {"S01": 0.1}, "small_prize_roi": {"S02": 0.1}}
    with pytest.raises(ValueError):
        dual_endpoint_correction(pv)


def test_invalid_mode():
    with pytest.raises(ValueError):
        dual_endpoint_correction({"a": {"S": 0.1}}, mode="nope")
