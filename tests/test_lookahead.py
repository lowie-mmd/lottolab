"""前視保護（規格 §4.1、M2 驗收①）——不可跳過項。

餵入含當期或未來期數的切片，引擎必須丟 LookAheadError。
"""
from __future__ import annotations

import pytest

from engine.backtest import LookAheadError, assert_no_lookahead, run_walk_forward
from engine.backtest import TheoreticalPrizeTable
from engine.game import Lotto649Game
from engine.models import Draw, QUALITY_FULL


def _mk(period: str, nums=(1, 2, 3, 4, 5, 6), special=7) -> Draw:
    return Draw(
        period=period, date="2024-01-01", numbers=tuple(nums), special=special,
        sales_amount=1, prizes={}, data_quality=QUALITY_FULL, promo=None,
    )


def test_guard_rejects_future_period():
    history = [_mk("113000001"), _mk("113000002")]
    # 目標期 == history 最後一期 → 違規
    with pytest.raises(LookAheadError):
        assert_no_lookahead(history, "113000002")
    # 目標期早於 history 中某期 → 違規
    with pytest.raises(LookAheadError):
        assert_no_lookahead(history, "113000001")


def test_guard_accepts_strict_past():
    history = [_mk("113000001"), _mk("113000002")]
    assert_no_lookahead(history, "113000003")  # 不丟例外


class _PeekingStrategy:
    """作弊策略：試圖回傳 history 中不該存在的未來資訊。此處僅用來觸發引擎守門。"""
    id = "PEEK"
    group = "X"
    registered_period = "TBD"

    def predict(self, history):
        return [(1, 2, 3, 4, 5, 6)]


def test_engine_slicing_never_leaks_future(monkeypatch):
    """即使把切片邏輯改壞，守門仍應攔截。模擬引擎誤傳未來切片。"""
    draws = [_mk("113000001"), _mk("113000002"), _mk("113000003")]
    theo = TheoreticalPrizeTable({"t5": 2000, "t6": 1000, "t7": 400, "t8": 400}, {})

    # 正常執行不應丟例外
    results = run_walk_forward(Lotto649Game(), _PeekingStrategy(), draws, theo)
    assert len(results) == 3

    # 直接對守門餵未來切片（模擬切片 bug：history 含目標當期）
    with pytest.raises(LookAheadError):
        assert_no_lookahead(draws[:2], draws[1].period)
