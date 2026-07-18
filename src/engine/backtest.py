"""回測引擎（M2，規格 §4）。

- Walk-Forward：predict 只拿得到第 N 期以前的資料（§4.1）
- 前視保護：餵入含未來期數的切片應丟例外（LookAheadError）
- 雙軌 ROI（§4.2）：理論軌（推論主指標）＋ 實際軌（展示用）
- 加碼獎項（§2.3）不計入任何一軌（§4.2 凍結決策）——本引擎不讀 draw.promo
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .game import Game, Ticket
from .models import Draw, QUALITY_FULL


class LookAheadError(Exception):
    """策略被餵到當期或未來期數的資料時丟出。"""


def assert_no_lookahead(history: list[Draw], target_period: str) -> None:
    """前視保護守門（§4.1）。history 內任一期 >= 目標期 即違規。"""
    tp = int(target_period)
    for d in history:
        if d.period_int >= tp:
            raise LookAheadError(
                f"前視違規：history 含期別 {d.period} >= 目標期 {target_period}"
            )


@dataclass
class PeriodResult:
    period: str
    strategy_id: str
    cost: int
    payout_theoretical: int
    payout_actual: Optional[int]          # data_quality != full → None（缺值）
    tier_hits: dict = field(default_factory=dict)  # {t1..t8: 命中注數}

    def to_dict(self) -> dict:
        return {
            "period": self.period,
            "strategy_id": self.strategy_id,
            "cost": self.cost,
            "payout_theoretical": self.payout_theoretical,
            "payout_actual": self.payout_actual,
            "tier_hits": self.tier_hits,
        }


class TheoreticalPrizeTable:
    """理論軌獎額（§2.2）：t5–t8 固定；t1–t4 凍結中位數。"""

    def __init__(self, fixed: dict, frozen_median: dict):
        self._amounts: dict[str, int] = {}
        for tier, amt in fixed.items():
            self._amounts[tier] = int(amt)
        for tier, amt in (frozen_median or {}).items():
            if amt is not None:
                self._amounts[tier] = int(amt)

    def amount(self, tier: str) -> int:
        # 未凍結（None）的獎項在理論軌以 0 計，避免 KeyError；正常初始化後應齊全
        return self._amounts.get(tier, 0)

    @classmethod
    def from_config(cls, cfg: dict) -> "TheoreticalPrizeTable":
        tp = cfg["theoretical_prizes"]
        return cls(tp["fixed"], tp.get("frozen_median", {}))


def score_period(
    game: Game,
    tickets: list[Ticket],
    draw: Draw,
    theoretical: TheoreticalPrizeTable,
    strategy_id: str,
) -> PeriodResult:
    """對單期，將一組注計分並累計雙軌 payout。"""
    tier_hits: dict[str, int] = {}
    payout_theo = 0
    payout_actual: Optional[int] = 0
    actual_available = draw.data_quality == QUALITY_FULL

    for ticket in tickets:
        tier = game.score(ticket, draw)
        if tier is None:
            continue
        tier_hits[tier] = tier_hits.get(tier, 0) + 1
        payout_theo += theoretical.amount(tier)
        if actual_available:
            amt = draw.prize_amount(tier)
            # full 期數理應有 amount；防禦性處理 None
            payout_actual = (payout_actual or 0) + (amt or 0)

    if not actual_available:
        payout_actual = None

    return PeriodResult(
        period=draw.period,
        strategy_id=strategy_id,
        cost=game.ticket_cost * len(tickets),
        payout_theoretical=payout_theo,
        payout_actual=payout_actual,
        tier_hits=tier_hits,
    )


def run_walk_forward(
    game: Game,
    strategy,
    draws: list[Draw],
    theoretical: TheoreticalPrizeTable,
    start_index: int = 0,
    end_index: Optional[int] = None,
) -> list[PeriodResult]:
    """對 draws[start_index:end_index] 逐期 walk-forward 回測一個策略。

    第 i 期：history = draws[:i]（嚴格早於 draws[i]），predict → 對 draws[i] 計分。
    每步均過前視守門，即使策略自身不作弊也保證引擎層不洩未來。
    """
    assert start_index >= 0
    if end_index is None:
        end_index = len(draws)
    results: list[PeriodResult] = []

    for i in range(start_index, end_index):
        target = draws[i]
        history = draws[:i]
        assert_no_lookahead(history, target.period)  # 引擎層強制切片保護
        tickets = list(strategy.predict(history))
        for tk in tickets:
            if not game.valid_ticket(tk):
                raise ValueError(
                    f"策略 {getattr(strategy, 'id', '?')} 於期 {target.period} "
                    f"產生非法注：{tk}"
                )
        results.append(score_period(game, tickets, target, theoretical, strategy.id))

    return results


def summarize(results: list[PeriodResult]) -> dict:
    """累積指標（§4.3）：理論軌累積 ROI（主）、實際軌、命中分布、最大回落。"""
    total_cost = sum(r.cost for r in results)
    total_theo = sum(r.payout_theoretical for r in results)
    actual_results = [r for r in results if r.payout_actual is not None]
    total_actual_cost = sum(r.cost for r in actual_results)
    total_actual = sum(r.payout_actual or 0 for r in actual_results)

    tier_totals: dict[str, int] = {}
    for r in results:
        for tier, n in r.tier_hits.items():
            tier_totals[tier] = tier_totals.get(tier, 0) + n

    # 理論軌累積損益曲線與最大回落
    cum = 0
    peak = 0
    max_drawdown = 0
    curve = []
    for r in results:
        cum += r.payout_theoretical - r.cost
        curve.append(cum)
        peak = max(peak, cum)
        max_drawdown = min(max_drawdown, cum - peak)

    return {
        "periods": len(results),
        "total_cost": total_cost,
        "total_payout_theoretical": total_theo,
        "roi_theoretical": (total_theo / total_cost) if total_cost else None,
        "total_payout_actual": total_actual,
        "roi_actual": (total_actual / total_actual_cost) if total_actual_cost else None,
        "actual_periods": len(actual_results),
        "tier_hits": tier_totals,
        "max_drawdown_theoretical": max_drawdown,
        "cumulative_curve_theoretical": curve,
    }
