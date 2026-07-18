"""B–F 策略決定性、合法性、注數與空 history 容錯（規格 M3 驗收）。"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from engine.game import Lotto649Game
from engine.models import Draw, QUALITY_FULL
from strategies.registry import build_all_strategies

CONFIG = json.loads((Path(__file__).parents[1] / "config" / "config.json").read_text("utf-8"))
GAME = Lotto649Game()


def _history(n: int) -> list[Draw]:
    # 用可變號碼讓頻率/序列策略有分布可算
    out = []
    for i in range(1, n + 1):
        base = ((i * 7) % 43) + 1
        nums = sorted({((base + k * 5 - 1) % 49) + 1 for k in range(6)})
        while len(nums) < 6:
            nums = sorted(set(nums) | {((nums[-1]) % 49) + 1})
        out.append(Draw(period=f"1130{i:05d}", date="2024-01-01", numbers=tuple(nums[:6]),
                        special=((i * 3) % 49) + 1, sales_amount=1, prizes={},
                        data_quality=QUALITY_FULL, promo=None))
    return out


ALL = build_all_strategies(CONFIG, GAME)
NON_A = [s for s in ALL if s.group != "A"]


def test_counts():
    groups = {}
    for s in ALL:
        groups[s.group] = groups.get(s.group, 0) + 1
    assert groups == {"A": 50, "B": 5, "C": 3, "D": 3, "E": 5, "F": 2}


@pytest.mark.parametrize("n", [0, 1, 5, 60])
def test_all_strategies_deterministic_and_valid(n):
    hist = _history(n)
    for s in ALL:
        out1 = s.predict(hist)
        out2 = s.predict(hist)
        assert out1 == out2, f"{s.id} 非決定性 (n={n})"
        assert len(out1) >= 1
        for tk in out1:
            assert GAME.valid_ticket(tk), f"{s.id} 產生非法注 {tk} (n={n})"


def test_wheel_counts():
    hist = _history(60)
    by_id = {s.id: s for s in ALL}
    assert len(by_id["E01"].predict(hist)) == 7      # C(7,6)
    for sid in ("E02", "E03", "E04", "E05"):
        assert len(by_id[sid].predict(hist)) == 28    # C(8,6)


def test_f01_all_high():
    hist = _history(10)
    f01 = next(s for s in ALL if s.id == "F01")
    for tk in f01.predict(hist):
        assert all(n > 31 for n in tk)


def test_f02_anti_pattern():
    from strategies.group_f import anti_pattern_ok
    assert not anti_pattern_ok([1, 2, 3, 10, 20, 30])      # 順子 1,2,3
    assert not anti_pattern_ok([2, 4, 6, 8, 10, 12])       # 等差
    assert not anti_pattern_ok([3, 13, 23, 33, 5, 7])      # 尾數 3 過多
    assert anti_pattern_ok([1, 5, 12, 28, 34, 47])         # 正常


def test_d_group_frozen_matches_config():
    d = CONFIG["d_group"]
    by_id = {s.id: s for s in ALL}
    hist = _history(3)
    for sid in ("D01", "D02", "D03"):
        assert by_id[sid].predict(hist)[0] == tuple(sorted(d[sid]))
        # 養牌：每期同一組（不隨 history 改變）
        assert by_id[sid].predict(_history(99)) == by_id[sid].predict(hist)
