"""全管線回測執行器：載入 draws + config，跑指定策略群，輸出結果快照。

用法：
    PYTHONPATH=src python -m engine.run_backtest --group A [--history] [--out data/results]

歷史段 vs 前瞻段（規格 §4.4）：--from-period 指定前瞻段起點；預設跑全部（歷史段觀察用）。
此執行器同時作為 M2+M3 的全管線煙霧測試：確認引擎不因早期缺欄位崩潰。
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from engine.backtest import TheoreticalPrizeTable, run_walk_forward, summarize
from engine.game import get_game
from engine.models import load_draws
from strategies.base import StrategyRegistry
from strategies.group_a import build_group_a

ROOT = Path(__file__).resolve().parents[2]
DRAWS_PATH = ROOT / "data" / "draws.json"
CONFIG_PATH = ROOT / "config" / "config.json"
RESULTS_DIR = ROOT / "data" / "results"


def build_registry(cfg: dict, game, groups: list[str]) -> StrategyRegistry:
    reg = StrategyRegistry()
    if "A" in groups:
        for s in build_group_a(cfg, game):
            reg.register(s)
    # B–F 於後續模組加入
    return reg


def find_start_index(draws, from_period: str | None) -> int:
    if not from_period:
        return 0
    for i, d in enumerate(draws):
        if d.period_int >= int(from_period):
            return i
    return len(draws)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--group", action="append", default=None, help="策略群（可重複），預設 A")
    ap.add_argument("--from-period", default=None, help="前瞻段起始期別（含）")
    ap.add_argument("--out", default=str(RESULTS_DIR))
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    groups = args.group or ["A"]
    cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    game = get_game(cfg["game"])
    draws = load_draws(DRAWS_PATH)
    theo = TheoreticalPrizeTable.from_config(cfg)
    reg = build_registry(cfg, game, groups)

    start = find_start_index(draws, args.from_period)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    summaries = {}
    for s in reg.all():
        results = run_walk_forward(game, s, draws, theo, start_index=start)
        summaries[s.id] = summarize(results)

    snapshot = {
        "n_draws": len(draws),
        "start_index": start,
        "n_strategies": len(reg),
        "groups": groups,
        "summaries": summaries,
    }
    (out_dir / "backtest_summary.json").write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    if not args.quiet:
        rois = sorted(
            ((sid, s["roi_theoretical"]) for sid, s in summaries.items()),
            key=lambda x: (x[1] is None, -(x[1] or 0)),
        )
        print(f"draws={len(draws)} strategies={len(reg)} start_index={start}")
        print("理論軌 ROI（前幾名 / 後幾名）：")
        for sid, roi in rois[:3] + rois[-3:]:
            print(f"  {sid}: {roi:.4f}" if roi is not None else f"  {sid}: n/a")
        # 對照組冠軍（A 組最佳理論軌 ROI）
        a_rois = [r for sid, r in rois if sid.startswith('A') and r is not None]
        if a_rois:
            print(f"A 組對照冠軍理論軌 ROI = {max(a_rois):.4f}，中位 = "
                  f"{sorted(a_rois)[len(a_rois)//2]:.4f}")


if __name__ == "__main__":
    main()
