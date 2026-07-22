"""梯次二驗證管線四關驗收（roadmap §3.2）：每一關都必須真的攔得到違規。"""
from __future__ import annotations

import json
import random

import pytest

from cohort2.manifest import Manifest, ManifestError
from cohort2.validate import (
    gate_determinism,
    gate_duplicate,
    gate_lookahead,
    gate_runtime,
    overlap_rate,
    validate_strategy,
)
from engine.game import Lotto649Game
from engine.models import QUALITY_FULL, Draw
from strategies.util import seeded_pick, strat_seed

GAME = Lotto649Game()


def make_draws(n=150, seed=7):
    rng = random.Random(seed)
    out = []
    for i in range(n):
        nums = tuple(sorted(rng.sample(range(1, 50), 6)))
        sp = rng.choice([x for x in range(1, 50) if x not in nums])
        out.append(Draw(period=str(100000000 + i), date="2020-01-01", numbers=nums, special=sp,
                        sales_amount=100, prizes={}, data_quality=QUALITY_FULL, promo=None))
    return out


DRAWS = make_draws()


class GoodStrategy:
    """合規：seeded、決定性、不改 history。"""
    group = "S2"
    registered_period = "TBD"

    def __init__(self, sid="GOOD", seed=1):
        self.id = sid
        self._seed = seed

    def predict(self, history):
        return [seeded_pick(GAME.pool(), GAME.pick, strat_seed(self.id, len(history), self._seed))]


class CloneableStrategy(GoodStrategy):
    """相同演算法、不同作者／id —— 真實的「重複投稿」情境（選號與 id 無關）。"""
    def predict(self, history):
        return [seeded_pick(GAME.pool(), GAME.pick, strat_seed("SHARED_LOGIC", len(history), self._seed))]


class RandomStrategy(GoodStrategy):
    """違規：未由 seed 導出隨機性 → 決定性測試應攔下。"""
    def predict(self, history):
        return [tuple(sorted(random.sample(range(1, 50), 6)))]


class MutatingStrategy(GoodStrategy):
    """違規：改動傳入的 history → 前視保護關應攔下。"""
    def predict(self, history):
        if history:
            history.pop()
        return [tuple(range(1, 7))]


class IllegalTicketStrategy(GoodStrategy):
    """違規：產生非法注（號碼重複）→ 前視保護關應攔下。"""
    def predict(self, history):
        return [(1, 1, 2, 3, 4, 5)]


# ---------- manifest ----------

def test_manifest_valid():
    m = Manifest.from_dict({"id": "yijing-01", "author": "洛伊", "oneliner": "以開獎日干支起卦映射號碼。",
                            "bet_type": "single", "code_path": "cohort2.examples.demo",
                            "seed": 42, "registered_cohort": 2})
    assert m.id == "yijing-01" and m.bet_type == "single"


@pytest.mark.parametrize("bad,err", [
    ({"id": "!!", "author": "a", "oneliner": "x", "bet_type": "single", "code_path": "m", "seed": 1}, "id"),
    ({"id": "ok1", "author": "a", "oneliner": "x", "bet_type": "multi9", "code_path": "m", "seed": 1}, "bet_type"),
    ({"id": "ok1", "author": "a", "oneliner": "", "bet_type": "single", "code_path": "m", "seed": 1}, "oneliner"),
    ({"id": "ok1", "author": "a", "oneliner": "x", "bet_type": "single", "code_path": "m", "seed": 1,
      "registered_cohort": 1}, "cohort"),
])
def test_manifest_rejects_bad(bad, err):
    with pytest.raises(ManifestError):
        Manifest.from_dict(bad)


def test_manifest_missing_field():
    with pytest.raises(ManifestError):
        Manifest.from_dict({"id": "ok1", "author": "a"})


# ---------- 四關 ----------

def test_determinism_gate_passes_and_catches():
    good = GoodStrategy()
    assert gate_determinism(good, lambda: GoodStrategy(), DRAWS).passed
    assert not gate_determinism(RandomStrategy(), lambda: RandomStrategy(), DRAWS).passed


def test_lookahead_gate_catches_mutation_and_illegal_ticket():
    assert gate_lookahead(GoodStrategy(), GAME, DRAWS).passed
    assert not gate_lookahead(MutatingStrategy(), GAME, list(DRAWS)).passed
    assert not gate_lookahead(IllegalTicketStrategy(), GAME, DRAWS).passed


def test_runtime_gate():
    assert gate_runtime(GoodStrategy(), DRAWS).passed
    # 上限設極小 → 應攔下
    assert not gate_runtime(GoodStrategy(), DRAWS, limit=0.0).passed


def test_duplicate_gate_catches_clone():
    a = CloneableStrategy("A1", seed=1)
    clone = CloneableStrategy("A2", seed=1)     # 不同作者/id、相同演算法 → 每期選號相同
    distinct = GoodStrategy("B1", seed=999)
    assert overlap_rate(a, clone, DRAWS, window=40) == pytest.approx(1.0)
    assert not gate_duplicate(a, [clone], DRAWS, window=40).passed
    assert gate_duplicate(a, [distinct], DRAWS, window=40).passed


def test_reference_demo_passes_all_gates(tmp_path):
    """文件宣稱的程式碼契約必須真的可用：參考實作要過四關（含 CLI 入口）。"""
    from cohort2.check import main as check_main
    from cohort2.manifest import Manifest

    man = Manifest.from_dict({
        "id": "demo-sum-offset", "author": "示範作者",
        "oneliner": "以上一期號碼之和決定偏移，再由 seed 決定性選號。",
        "bet_type": "single", "code_path": "cohort2.examples.demo",
        "seed": 20260722, "registered_cohort": 2,
    })
    s = man.build_strategy(GAME)
    assert hasattr(s, "predict") and s.group == "S2"
    rep = validate_strategy(s, GAME, DRAWS, existing=[], rebuild=lambda: man.build_strategy(GAME))
    assert rep.passed, rep.summary()

    # CLI：合規 manifest → 離開碼 0
    p = tmp_path / "m.json"
    p.write_text(json.dumps({
        "id": "demo-sum-offset", "author": "示範作者",
        "oneliner": "示範。", "bet_type": "single",
        "code_path": "cohort2.examples.demo", "seed": 20260722, "registered_cohort": 2,
    }, ensure_ascii=False), encoding="utf-8")
    assert check_main([str(p), "--window", "10"]) == 0


def test_cli_rejects_bad_manifest(tmp_path):
    from cohort2.check import main as check_main
    p = tmp_path / "bad.json"
    p.write_text(json.dumps({"id": "x", "author": "a"}), encoding="utf-8")
    assert check_main([str(p)]) == 1
    p2 = tmp_path / "nocode.json"
    p2.write_text(json.dumps({
        "id": "ghost", "author": "a", "oneliner": "x", "bet_type": "single",
        "code_path": "cohort2.examples.does_not_exist", "seed": 1, "registered_cohort": 2,
    }, ensure_ascii=False), encoding="utf-8")
    assert check_main([str(p2)]) == 1


def test_full_pipeline_report():
    rep = validate_strategy(GoodStrategy(), GAME, DRAWS,
                            existing=[GoodStrategy("OTHER", seed=999)],
                            rebuild=lambda: GoodStrategy())
    assert rep.passed
    assert len(rep.gates) == 4
    assert "通過" in rep.summary()
    assert rep.to_dict()["passed"] is True
