"""梯次二對照組 A2（roadmap §3.3）：全新 seeds，與梯次一 A 組完全獨立、永不混池。

沿用梯次一之對照機制（seeded 純隨機、決定性、無前視），僅換 seed_base 與 id 前綴，
使「方法不變、樣本全新」。A2 的角色與 A 相同：畫出該梯次的運氣雲，真策略須贏過
其冠軍（非平均）才算跳出雜訊。
"""
from __future__ import annotations

import json
from pathlib import Path

from engine.game import Game
from strategies.group_a import SeededRandomStrategy

ROOT = Path(__file__).resolve().parents[2]
COHORT2_CONFIG = ROOT / "config" / "cohort2.json"


class Cohort2Control(SeededRandomStrategy):
    """A2 對照組成員。group 標記與梯次一區隔，確保統計不混池。"""
    group = "A2"


def load_cohort2_config(path=None) -> dict:
    p = Path(path) if path else COHORT2_CONFIG
    return json.loads(p.read_text(encoding="utf-8"))


def build_cohort2_control(cfg: dict, game: Game) -> list:
    """依 cohort2 config 建立 A2-00～A2-49。"""
    c = cfg["control"]
    count = int(c["count"])
    seed_base = int(c["seed_base"])
    prefix = c.get("id_prefix", "A2")
    reg = cfg.get("registered_period") or "TBD"
    if seed_base == 42424242:
        raise ValueError("梯次二 seed_base 不得沿用梯次一（42424242）——樣本必須全新（§3.3）")
    return [
        Cohort2Control(f"{prefix}-{i:02d}", i, seed_base, game, reg, n_tickets=1)
        for i in range(count)
    ]


def is_frozen(cfg: dict) -> bool:
    """梯次二是否已凍結（註冊）。未凍結前不得產出任何推論性結果。"""
    return bool(cfg.get("registered_period")) and cfg.get("fdr_n") is not None
