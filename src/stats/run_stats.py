"""M4 執行器：硬體隨機性審計（全歷史）＋ 策略驗證（前瞻段，若已啟動）。

用法：
    PYTHONPATH=src python -m stats.run_stats --audit
    PYTHONPATH=src python -m stats.run_stats --validate [--n-perm 1000]
    PYTHONPATH=src python -m stats.run_stats --validate --observational   # 用全歷史觀察（非註冊推論）
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from engine.backtest import TheoreticalPrizeTable
from engine.game import get_game
from engine.models import load_draws
from stats.audit import (
    pair_cooccurrence,
    segmented_by_year,
    single_number_chisquare,
    special_chisquare,
)
from stats.fdr import benjamini_hochberg
from stats.permutation import run_strategy_validation
from strategies.registry import build_all_strategies

ROOT = Path(__file__).resolve().parents[2]
DRAWS_PATH = ROOT / "data" / "draws.json"
CONFIG_PATH = ROOT / "config" / "config.json"
RESULTS_DIR = ROOT / "data" / "results"


def run_audit(draws, game) -> dict:
    print("硬體隨機性審計（全歷史）…")
    report = {
        "n_draws": len(draws),
        "single_number": single_number_chisquare(draws, game),
        "special_number": special_chisquare(draws, game),
        "pair_cooccurrence": pair_cooccurrence(draws, game),
        "segmented_by_year": segmented_by_year(draws, game),
        "note": (
            "不做 NIST 套件（§5.2）。台彩定期輪換球組與搖獎機，全歷史混池檢定"
            "只能偵測長期系統性偏差，無法偵測單一球組短期物理瑕疵。"
        ),
    }
    (RESULTS_DIR / "audit.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    sn, sp, pr = report["single_number"], report["special_number"], report["pair_cooccurrence"]
    print(f"  單號卡方  chi2={sn['chi2']:.2f} df={sn['df']} p={sn['p_value']:.4f}")
    print(f"  特別號卡方 chi2={sp['chi2']:.2f} df={sp['df']} p={sp['p_value']:.4f}")
    print(f"  配對共現  chi2={pr['chi2']:.2f} df={pr['df']} p={pr['p_value']:.4f}")
    return report


def run_validate(draws, game, cfg, n_perm, observational) -> dict:
    theo = TheoreticalPrizeTable.from_config(cfg)
    strategies = build_all_strategies(cfg, game)
    ps = cfg.get("prospective_start_period")
    if observational or not ps:
        start_index = 0
        label = "observational_full_history" if observational or not ps else "prospective"
    else:
        start_index = next((i for i, d in enumerate(draws) if d.period_int >= int(ps)), len(draws))
        label = "prospective"

    n_prospective = len(draws) - start_index
    if n_prospective == 0:
        print("前瞻段尚未啟動（prospective_start_period 未設定）；跳過策略驗證。")
        print("提示：可加 --observational 對全歷史做觀察性檢定（非註冊推論）。")
        return {"label": "not_started", "n_periods": 0}

    print(f"策略驗證（{label}，{n_prospective} 期，n_perm={n_perm}）…")
    res = run_strategy_validation(game, strategies, draws, theo, start_index, n_perm=n_perm)

    # FDR：N = 全部註冊策略數
    ids = list(res["strategies"].keys())
    pvals = [res["strategies"][i]["p_value"] for i in ids]
    fdr = benjamini_hochberg(pvals, alpha=0.05)
    for k, sid in enumerate(ids):
        res["strategies"][sid]["q_value"] = fdr["q_values"][k]
        res["strategies"][sid]["fdr_rejected"] = fdr["rejected"][k]

    res["label"] = label
    res["honest_note"] = (
        "200 期的檢定力只足以偵測『大幅』偏離；接受 H0 ≠ 證明完美隨機，"
        "只代表偏差（若存在）小於本實驗可偵測門檻（§5.1）。"
    )
    if label.startswith("observational"):
        res["honest_note"] = "觀察性（歷史段），非預先註冊推論；" + res["honest_note"]

    (RESULTS_DIR / "strategy_validation.json").write_text(
        json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")

    n_rej = sum(1 for sid in ids if res["strategies"][sid]["fdr_rejected"])
    print(f"  對照組冠軍 ROI={res['champion_roi']:.4f} 中位={res['champion_median']:.4f}")
    print(f"  FDR 校正後顯著策略數：{n_rej} / {len(ids)}")
    if n_rej:
        for sid in ids:
            if res["strategies"][sid]["fdr_rejected"]:
                r = res["strategies"][sid]
                print(f"    ⚠ {sid} ({r['group']}) ROI={r['roi_theoretical']:.4f} "
                      f"p={r['p_value']:.4f} q={r['q_value']:.4f}")
    return res


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--audit", action="store_true")
    ap.add_argument("--validate", action="store_true")
    ap.add_argument("--observational", action="store_true")
    ap.add_argument("--n-perm", type=int, default=1000)
    args = ap.parse_args()

    cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    game = get_game(cfg["game"])
    draws = load_draws(DRAWS_PATH)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    if args.audit:
        run_audit(draws, game)
    if args.validate:
        run_validate(draws, game, cfg, args.n_perm, args.observational)
    if not (args.audit or args.validate):
        ap.print_help()


if __name__ == "__main__":
    main()
