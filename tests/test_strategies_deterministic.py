"""A 組決定性與合法性（規格 §3 M3 驗收：同一 history 重跑兩次輸出必須相同）。"""
from __future__ import annotations

import json
from pathlib import Path

from engine.game import Lotto649Game
from engine.models import Draw, QUALITY_FULL
from strategies.group_a import build_group_a

CONFIG = json.loads((Path(__file__).parents[1] / "config" / "config.json").read_text("utf-8"))


def _history(n: int) -> list[Draw]:
    return [
        Draw(period=f"1130000{i:02d}", date="2024-01-01", numbers=(1, 2, 3, 4, 5, 6),
             special=7, sales_amount=1, prizes={}, data_quality=QUALITY_FULL, promo=None)
        for i in range(1, n + 1)
    ]


def test_group_a_has_50():
    strategies = build_group_a(CONFIG, Lotto649Game())
    assert len(strategies) == 50
    assert strategies[0].id == "A00"
    assert strategies[-1].id == "A49"


def test_deterministic_same_history_same_output():
    game = Lotto649Game()
    strategies = build_group_a(CONFIG, game)
    hist = _history(30)
    for s in strategies:
        out1 = s.predict(hist)
        out2 = s.predict(hist)
        assert out1 == out2


def test_output_valid_and_varies_by_step():
    game = Lotto649Game()
    s = build_group_a(CONFIG, game)[0]
    # 不同 step（history 長度）應通常產生不同號碼（非固定）
    outs = {s.predict(_history(n))[0] for n in range(5, 25)}
    assert len(outs) > 1
    # 每注合法
    for n in range(5, 25):
        for tk in s.predict(_history(n)):
            assert game.valid_ticket(tk)


def test_distinct_strategies_differ():
    game = Lotto649Game()
    strategies = build_group_a(CONFIG, game)
    hist = _history(10)
    tickets = [s.predict(hist)[0] for s in strategies]
    # 50 個獨立 seed 於同一 step 不應全部相同
    assert len(set(tickets)) > 1
