"""手工對照樣本：3 期 × 3 策略，引擎輸出須與手算全等（規格 M2 驗收②）。"""
from __future__ import annotations

from engine.backtest import TheoreticalPrizeTable, run_walk_forward, summarize
from engine.game import Lotto649Game
from engine.models import Draw, QUALITY_FULL

# 理論軌固定表
THEO = TheoreticalPrizeTable(
    fixed={"t5": 2000, "t6": 1000, "t7": 400, "t8": 400},
    frozen_median={"t1": 1000000, "t2": 50000, "t3": 10000, "t4": 5000},
)


def _draw(period, nums, special, amounts):
    prizes = {t: {"winners": 1, "amount": amounts.get(t)} for t in
              ("t1", "t2", "t3", "t4", "t5", "t6", "t7", "t8")}
    return Draw(period=period, date="2024-01-01", numbers=tuple(nums), special=special,
                sales_amount=100, prizes=prizes, data_quality=QUALITY_FULL, promo=None)


# d0: 命中 S1→t1, S2→t2 ; d1: 命中 S3→t2 ; d2: 命中 S1、S2→t8
DRAWS = [
    _draw("113000001", [1, 2, 3, 4, 5, 6], 7, {"t1": 1200000, "t2": 60000}),
    _draw("113000002", [10, 11, 12, 13, 14, 15], 16, {"t2": 55000}),
    _draw("113000003", [1, 2, 3, 20, 21, 22], 23, {"t8": 400}),
]


class Fixed:
    group = "T"
    registered_period = "TBD"

    def __init__(self, sid, ticket):
        self.id = sid
        self._ticket = tuple(ticket)

    def predict(self, history):
        return [self._ticket]


def test_manual_three_by_three():
    game = Lotto649Game()
    s1 = Fixed("S1", [1, 2, 3, 4, 5, 6])    # d0 t1, d1 null, d2 t8
    s2 = Fixed("S2", [1, 2, 3, 4, 5, 7])    # d0 t2(5+特), d1 null, d2 t8
    s3 = Fixed("S3", [10, 11, 12, 13, 14, 16])  # d0 null, d1 t2(5+特), d2 null

    r1 = summarize(run_walk_forward(game, s1, DRAWS, THEO))
    r2 = summarize(run_walk_forward(game, s2, DRAWS, THEO))
    r3 = summarize(run_walk_forward(game, s3, DRAWS, THEO))

    # S1：理論 t1(1000000)+t8(400)=1000400；實際 1200000+400=1200400
    assert r1["total_cost"] == 150
    assert r1["total_payout_theoretical"] == 1000400
    assert r1["total_payout_actual"] == 1200400
    assert r1["tier_hits"] == {"t1": 1, "t8": 1}

    # S2：理論 t2(50000)+t8(400)=50400；實際 60000+400=60400
    assert r2["total_payout_theoretical"] == 50400
    assert r2["total_payout_actual"] == 60400
    assert r2["tier_hits"] == {"t2": 1, "t8": 1}

    # S3：理論 t2(50000)=50000；實際 55000
    assert r3["total_payout_theoretical"] == 50000
    assert r3["total_payout_actual"] == 55000
    assert r3["tier_hits"] == {"t2": 1}


def test_actual_track_none_for_non_full():
    game = Lotto649Game()
    d = Draw(period="113000009", date="2024-01-01", numbers=(1, 2, 3, 4, 5, 6),
             special=7, sales_amount=None, prizes={}, data_quality="numbers_only", promo=None)
    s = Fixed("S", [1, 2, 3, 4, 5, 6])
    results = run_walk_forward(game, s, [d], THEO)
    assert results[0].payout_actual is None            # 缺值
    assert results[0].payout_theoretical == 1000000     # 理論軌仍計分
