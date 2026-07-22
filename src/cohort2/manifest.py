"""梯次二參賽策略 manifest（roadmap §3.4）。

格式：{ id, author, contact(可選), oneliner, bet_type, code_path, seed, registered_cohort:2 }

程式碼契約（准入鐵律，§3.2）：`code_path` 指向一個可 import 的模組，該模組必須
提供 `build(game, seed)` 並回傳實作 `Strategy` 協定的物件（具 id/group/predict）。
隨機性必須由 seed 導出；同輸入重跑輸出必須全等。
"""
from __future__ import annotations

import importlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

ID_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{1,31}$")
VALID_BET_TYPES = ("single", "wheel7", "wheel8")  # multiN 需另行裁決（影響 null 快取）
MAX_ONELINER = 120


class ManifestError(ValueError):
    """manifest 格式或契約不合規。"""


@dataclass
class Manifest:
    id: str
    author: str
    oneliner: str
    bet_type: str
    code_path: str
    seed: int
    registered_cohort: int = 2
    contact: Optional[str] = None
    source: Optional[Path] = field(default=None, compare=False)

    @classmethod
    def from_dict(cls, d: dict, source: Optional[Path] = None) -> "Manifest":
        missing = [k for k in ("id", "author", "oneliner", "bet_type", "code_path", "seed") if k not in d]
        if missing:
            raise ManifestError(f"缺少必要欄位：{missing}")
        m = cls(
            id=str(d["id"]), author=str(d["author"]), oneliner=str(d["oneliner"]),
            bet_type=str(d["bet_type"]), code_path=str(d["code_path"]),
            seed=int(d["seed"]), registered_cohort=int(d.get("registered_cohort", 2)),
            contact=d.get("contact"), source=source,
        )
        m.validate()
        return m

    @classmethod
    def load(cls, path) -> "Manifest":
        p = Path(path)
        return cls.from_dict(json.loads(p.read_text(encoding="utf-8")), source=p)

    def validate(self) -> None:
        if not ID_RE.match(self.id):
            raise ManifestError(f"id 不合法（英數字底線減號、2–32 字）：{self.id!r}")
        if self.registered_cohort != 2:
            raise ManifestError(f"registered_cohort 必須為 2（梯次二），得到 {self.registered_cohort}")
        if self.bet_type not in VALID_BET_TYPES:
            raise ManifestError(f"bet_type 須為 {VALID_BET_TYPES} 之一，得到 {self.bet_type!r}")
        if not self.oneliner.strip():
            raise ManifestError("oneliner（白話一句話）不可為空")
        if len(self.oneliner) > MAX_ONELINER:
            raise ManifestError(f"oneliner 過長（上限 {MAX_ONELINER} 字）")
        if not self.author.strip():
            raise ManifestError("author 不可為空")

    def build_strategy(self, game):
        """依契約 import code_path 並呼叫 build(game, seed)。"""
        try:
            mod = importlib.import_module(self.code_path)
        except Exception as e:  # noqa: BLE001 — 回報給參賽者的訊息需完整
            raise ManifestError(f"無法 import code_path {self.code_path!r}：{e}") from e
        if not hasattr(mod, "build"):
            raise ManifestError(f"{self.code_path} 未提供 build(game, seed)")
        try:
            s = mod.build(game, self.seed)
        except Exception as e:  # noqa: BLE001
            raise ManifestError(f"build(game, seed) 執行失敗：{e}") from e
        for attr in ("id", "predict"):
            if not hasattr(s, attr):
                raise ManifestError(f"策略物件缺少 {attr}（須符合 Strategy 協定）")
        return s
