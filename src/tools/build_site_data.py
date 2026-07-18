"""產生公開 dashboard（M6）所需的彙整 JSON，輸出到 docs/data/。

- luck_cloud.json：A 組對照 + 真策略的累積理論軌 ROI 曲線（降采樣）
- group_comparison.json：各組彙整（理論/實際 ROI、包牌每元報酬標準差）
- hotness.json：熱門度分析（t5–t8 中獎注數 ÷ 總注數，僅 full 期，§6.3）
- audit.json：由 stats.run_stats 產生（此處僅確保複製到 docs/data）

用法：PYTHONPATH=src python -m tools.build_site_data
"""
from __future__ import annotations

import json
import shutil
import statistics
from pathlib import Path

from engine.backtest import TheoreticalPrizeTable, run_walk_forward
from engine.game import get_game
from engine.models import load_draws
from strategies.registry import build_all_strategies

ROOT = Path(__file__).resolve().parents[2]
DRAWS_PATH = ROOT / "data" / "draws.json"
CONFIG_PATH = ROOT / "config" / "config.json"
RESULTS_DIR = ROOT / "data" / "results"
DOCS_DATA = ROOT / "docs" / "data"

SAMPLE_POINTS = 160  # 曲線降采樣點數


def _downsample(xs, k):
    if len(xs) <= k:
        return list(range(len(xs))), xs
    step = len(xs) / k
    idx = [min(int(i * step), len(xs) - 1) for i in range(k)]
    return idx, [xs[i] for i in idx]


def build_luck_cloud(game, strategies, draws, theo):
    per_strategy = {}
    period_labels = [d.period for d in draws]
    for s in strategies:
        results = run_walk_forward(game, s, draws, theo)
        cum_cost = 0
        cum_pay = 0
        roi_curve = []
        for r in results:
            cum_cost += r.cost
            cum_pay += r.payout_theoretical
            roi_curve.append(cum_pay / cum_cost if cum_cost else 0.0)
        idx, sampled = _downsample(roi_curve, SAMPLE_POINTS)
        per_strategy[s.id] = {
            "group": s.group,
            "roi_final": roi_curve[-1] if roi_curve else None,
            "curve": [round(v, 4) for v in sampled],
        }
    sample_idx, _ = _downsample(period_labels, SAMPLE_POINTS)
    return {
        "n_periods": len(draws),
        "sample_periods": [period_labels[i] for i in sample_idx],
        "strategies": per_strategy,
    }


def build_group_comparison(luck):
    by_group = {}
    for sid, s in luck["strategies"].items():
        by_group.setdefault(s["group"], []).append(s["roi_final"])
    out = {}
    a_rois = sorted(by_group.get("A", []))
    for g, rois in sorted(by_group.items()):
        rois_valid = [r for r in rois if r is not None]
        out[g] = {
            "n": len(rois),
            "roi_mean": statistics.mean(rois_valid) if rois_valid else None,
            "roi_median": statistics.median(rois_valid) if rois_valid else None,
            "roi_min": min(rois_valid) if rois_valid else None,
            "roi_max": max(rois_valid) if rois_valid else None,
        }
    out["_control_champion"] = max(a_rois) if a_rois else None
    out["_control_median"] = statistics.median(a_rois) if a_rois else None
    return out


def build_hotness(draws):
    series = []
    for d in draws:
        if d.data_quality != "full" or not d.sales_amount:
            continue
        low = sum((d.prize_winners(t) or 0) for t in ("t5", "t6", "t7", "t8"))
        total_notes = d.sales_amount / 50.0
        if total_notes <= 0:
            continue
        rate = low / total_notes * 10000  # 每萬注低獎中獎注數
        series.append({"period": d.period, "date": d.date, "rate_per_10k": round(rate, 3)})
    rates = [x["rate_per_10k"] for x in series]
    mean = statistics.mean(rates) if rates else 0
    std = statistics.pstdev(rates) if len(rates) > 1 else 1
    for x in series:
        x["z"] = round((x["rate_per_10k"] - mean) / std, 2) if std else 0
    return {
        "n": len(series),
        "mean_rate_per_10k": round(mean, 3),
        "series": series,
        "note": ("電腦選號（均勻隨機）佔實際投注相當比例，會稀釋人為偏好訊號；"
                 "本分析測到的是『剩餘人為偏好強度』，異常升高(z 大)代表該期號碼為群眾熱門組合。"),
    }


def main() -> None:
    cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    game = get_game(cfg["game"])
    draws = load_draws(DRAWS_PATH)
    theo = TheoreticalPrizeTable.from_config(cfg)
    strategies = build_all_strategies(cfg, game)

    DOCS_DATA.mkdir(parents=True, exist_ok=True)
    print(f"建立站台資料：{len(strategies)} 策略 × {len(draws)} 期")

    luck = build_luck_cloud(game, strategies, draws, theo)
    (DOCS_DATA / "luck_cloud.json").write_text(json.dumps(luck, ensure_ascii=False), encoding="utf-8")

    (DOCS_DATA / "group_comparison.json").write_text(
        json.dumps(build_group_comparison(luck), ensure_ascii=False, indent=2), encoding="utf-8")

    (DOCS_DATA / "hotness.json").write_text(
        json.dumps(build_hotness(draws), ensure_ascii=False), encoding="utf-8")

    # 複製審計結果（若已由 run_stats 產生）
    audit = RESULTS_DIR / "audit.json"
    if audit.exists():
        shutil.copy(audit, DOCS_DATA / "audit.json")

    # 供 personal.html 於 GitHub Pages（docs/）下取用：開獎、config，以及
    # 洛伊已 commit 的 bets.enc（僅複製密文，永不接觸密語或明文，符合 §8）
    shutil.copy(DRAWS_PATH, DOCS_DATA / "draws.json")
    shutil.copy(CONFIG_PATH, DOCS_DATA / "config.json")
    bets_enc = ROOT / "data" / "private" / "bets.enc"
    if bets_enc.exists():
        shutil.copy(bets_enc, DOCS_DATA / "bets.enc")

    # meta
    (DOCS_DATA / "meta.json").write_text(json.dumps({
        "n_periods": len(draws),
        "first_period": draws[0].period if draws else None,
        "last_period": draws[-1].period if draws else None,
        "last_date": draws[-1].date if draws else None,
        "prospective_start_period": cfg.get("prospective_start_period"),
        "n_strategies": len(strategies),
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"完成 → {DOCS_DATA.relative_to(ROOT)}/")


if __name__ == "__main__":
    main()
