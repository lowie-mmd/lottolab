"""集中建構所有策略群（A–F）。permutation test 的 N（FDR）= 全部註冊策略數。"""
from __future__ import annotations

from engine.game import Game
from strategies.group_a import build_group_a
from strategies.group_b import build_group_b
from strategies.group_c import build_group_c
from strategies.group_d import build_group_d
from strategies.group_e import build_group_e
from strategies.group_f import build_group_f

ALL_GROUPS = ["A", "B", "C", "D", "E", "F"]


def build_all_strategies(cfg: dict, game: Game, groups: list[str] | None = None) -> list:
    groups = groups or ALL_GROUPS
    out: list = []
    if "A" in groups:
        out += build_group_a(cfg, game)
    if "B" in groups:
        out += build_group_b(game)
    if "C" in groups:
        out += build_group_c(game)
    if "D" in groups:
        out += build_group_d(cfg, game)
    if "E" in groups:
        out += build_group_e(cfg, game)
    if "F" in groups:
        out += build_group_f(game)
    return out
