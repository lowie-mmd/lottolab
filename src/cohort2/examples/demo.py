"""參考實作：梯次二參賽策略的程式碼契約範例（非註冊策略，僅供參賽者複製起手式）。

契約三條（roadmap §3.2 准入鐵律）：
  1. 模組提供 `build(game, seed)`，回傳具 `id` / `group` / `predict(history)` 的物件
  2. 隨機性一律由 seed 導出（禁用 random 全域狀態、時間、檔案、網路）
  3. `predict(history)` 只能讀 history（第 N 期以前），不得改動它；回傳合法注的 list

本範例：以「上一期號碼之和」決定偏移量，再由 seed 導出決定性選號——
純粹示範結構，不主張任何預測力。
"""
from __future__ import annotations

import random

from engine.game import Game, Ticket
from engine.models import Draw


class DemoStrategy:
    group = "S2"                      # 梯次二參賽策略統一 group 標記
    registered_period = "TBD"         # 凍結時由 config 寫入

    def __init__(self, game: Game, seed: int, sid: str = "demo-sum-offset"):
        self.id = sid
        self.game = game
        self.seed = int(seed)
        self._pool = game.pool()
        self._pick = game.pick

    def predict(self, history: list[Draw]) -> list[Ticket]:
        # 只讀 history；無 history 時退化為純 seed 決定性選號（不崩潰、不前視）
        offset = sum(history[-1].numbers) if history else 0
        rng = random.Random(self.seed * 1_000_003 + len(history) * 10_007 + offset)
        return [tuple(sorted(rng.sample(self._pool, self._pick)))]


def build(game: Game, seed: int):
    """驗證管線的唯一入口點。"""
    return DemoStrategy(game, seed)
