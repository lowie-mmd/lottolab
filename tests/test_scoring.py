"""計分正確性——以 M2↔M5 共用測試向量驗證（規格 §4.2 驗收③、M3 驗收）。"""
from __future__ import annotations

import json
from pathlib import Path

from engine.backtest import TheoreticalPrizeTable, score_period
from engine.game import Lotto649Game
from engine.models import draw_from_dict

VECTORS = json.loads(
    (Path(__file__).parent / "vectors" / "scoring_vectors.json").read_text(encoding="utf-8")
)


def test_score_tiers_match_vectors():
    game = Lotto649Game()
    draw = draw_from_dict(VECTORS["draw"])
    for case in VECTORS["cases"]:
        got = game.score(tuple(case["ticket"]), draw)
        assert got == case["tier"], f"{case['label']}: 期望 {case['tier']} 得 {got}"


def test_payouts_match_vectors():
    game = Lotto649Game()
    draw = draw_from_dict(VECTORS["draw"])
    theo = TheoreticalPrizeTable(
        VECTORS["theoretical_prizes"]["fixed"],
        VECTORS["theoretical_prizes"]["frozen_median"],
    )
    for case in VECTORS["cases"]:
        res = score_period(game, [tuple(case["ticket"])], draw, theo, "TEST")
        assert res.payout_theoretical == case["payout_theoretical"], case["label"]
        assert res.payout_actual == case["payout_actual"], case["label"]


def test_valid_ticket():
    game = Lotto649Game()
    assert game.valid_ticket((1, 2, 3, 4, 5, 6))
    assert not game.valid_ticket((1, 2, 3, 4, 5))          # 太少
    assert not game.valid_ticket((1, 2, 3, 4, 5, 5))        # 重複
    assert not game.valid_ticket((0, 2, 3, 4, 5, 6))        # 超出下界
    assert not game.valid_ticket((1, 2, 3, 4, 5, 50))       # 超出上界
