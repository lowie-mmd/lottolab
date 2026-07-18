"""策略統一介面（規格 §3.1）與註冊表。

- 每注 NT$50。嚴禁前視：引擎層強制切片（見 engine.backtest）。
- 參數註冊即凍結；要改開新 id，舊策略不刪（防倖存者偏差）。
- 明確不做動態權重／流年冠軍加碼機制。
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from engine.game import Ticket
from engine.models import Draw


@runtime_checkable
class Strategy(Protocol):
    id: str                 # 註冊後凍結
    group: str
    registered_period: str

    def predict(self, history: list[Draw]) -> list[Ticket]:
        """依 history（第 N 期以前）產生對第 N 期的下注組合。

        決定性要求（§3.3 驗收）：同一 history 輸入重跑兩次，輸出必須相同。
        """
        ...


class StrategyRegistry:
    """所有註冊策略的容器。permutation test 的 N（FDR 校正）= len(all)。"""

    def __init__(self) -> None:
        self._by_id: dict[str, Strategy] = {}

    def register(self, strategy: Strategy) -> Strategy:
        if strategy.id in self._by_id:
            raise ValueError(f"策略 id 重複：{strategy.id}（註冊即凍結，改參數請開新 id）")
        self._by_id[strategy.id] = strategy
        return strategy

    def get(self, sid: str) -> Strategy:
        return self._by_id[sid]

    def all(self) -> list[Strategy]:
        return list(self._by_id.values())

    def by_group(self, group: str) -> list[Strategy]:
        return [s for s in self._by_id.values() if s.group == group]

    def __len__(self) -> int:
        return len(self._by_id)
