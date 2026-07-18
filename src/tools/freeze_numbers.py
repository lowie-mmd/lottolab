"""一次性凍結器：系統隨機產生 D 組養牌固定號碼與 E05 凍結包牌 8 號，寫入 config（規格 §3.2）。

養牌命題：固定號碼 vs 每期換號，長期績效無差異。號碼一旦凍結即全實驗期不變。
provenance：以下 FREEZE_SEED 為凍結來源；重跑本工具會產生相同號碼（決定性）。

用法：PYTHONPATH=src python -m tools.freeze_numbers   # 僅在號碼尚未凍結時寫入
"""
from __future__ import annotations

import json
import random
from pathlib import Path

FREEZE_SEED = 20260718  # 凍結日期為種子，決定性可重現

ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "config" / "config.json"


def _pick(rng: random.Random, k: int, lo=1, hi=49) -> list[int]:
    return sorted(rng.sample(range(lo, hi + 1), k))


def generate() -> dict:
    rng = random.Random(FREEZE_SEED)
    return {
        "d_group": {
            "D01": _pick(rng, 6),
            "D02": _pick(rng, 6),
            "D03": _pick(rng, 6),
        },
        "e_group": {
            "E05_wheel": _pick(rng, 8),  # 凍結 8 號包牌
        },
    }


def main() -> None:
    cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    gen = generate()

    # 若已凍結（非 null）則不覆寫，維持凍結鐵律
    d = cfg.get("d_group", {})
    already = all(d.get(k) for k in ("D01", "D02", "D03"))
    if already:
        print("D 組已凍結，跳過（如需重凍請先人工清空 config）。")
    else:
        d.update(gen["d_group"])
        cfg["d_group"] = d

    e = cfg.get("e_group") or {}
    if e.get("E05_wheel"):
        print("E05 已凍結，跳過。")
    else:
        e["E05_wheel"] = gen["e_group"]["E05_wheel"]
        e["_note"] = "E05 凍結包牌 8 號（系統隨機產生後凍結，規格 §3.2 E 組）"
        cfg["e_group"] = e

    CONFIG_PATH.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    print("D 組:", cfg["d_group"])
    print("E05:", cfg["e_group"]["E05_wheel"])


if __name__ == "__main__":
    main()
