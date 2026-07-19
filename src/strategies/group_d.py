"""D 組｜養牌類（公開，規格 §3.2）。

D01–D03：系統隨機產生後凍結的固定號碼（號碼在 config.d_group，由 tools.freeze_numbers 凍結）。
每期回傳同一組固定號碼，不看 history。
驗證命題：固定號碼 vs 每期換號，長期績效無差異。
（洛伊的夢境號碼不在此，在私人加密層 §7。）
"""
from __future__ import annotations

from engine.game import Game, Ticket
from engine.models import Draw

GROUP = "D"
REG = "115000072"


class FrozenStrategy:
    group = GROUP
    registered_period = REG

    def __init__(self, sid: str, numbers, game: Game):
        self.id = sid
        self.game = game
        self._ticket = tuple(sorted(numbers))
        if not game.valid_ticket(self._ticket):
            raise ValueError(f"{sid} 凍結號碼非法：{self._ticket}")

    def predict(self, history: list[Draw]) -> list[Ticket]:
        return [self._ticket]


def build_group_d(cfg: dict, game: Game) -> list:
    d = cfg.get("d_group", {})
    out = []
    for sid in ("D01", "D02", "D03"):
        nums = d.get(sid)
        if not nums:
            raise ValueError(f"{sid} 尚未凍結，請先執行 tools.freeze_numbers")
        out.append(FrozenStrategy(sid, nums, game))
    return out
