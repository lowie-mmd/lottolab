"""產生學術報告頁資料 docs/data/academic.json（roadmap R2 §2.2/§2.4）。

原則：全部數字自動由 data/results/ 與檢定力模擬生成，禁止手填（§2.4③）。
檢定力採操作型 δ₈₀（裁決書附錄 J，洛伊 2026-07-19 裁決）：口徑＝完整理論軌（含頭獎），
各獎命中數以 Poisson(n·λ_t) 模擬、秩次偵測（permutation p＋BH-FDR），各 bet_type 分開，
附通道分解與頭獎盲區。修正記錄（裁決 A）之「前（教科書 χ²）／後（MC 校準）」p 由已存
chi2 現場重算，非手填。

用法：PYTHONPATH=src python -m tools.build_academic
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from scipy import stats as scipy_stats

from engine.models import load_draws
from stats.power import (
    BET_TYPES,
    channel_power,
    delta80,
    jackpot_doubling_power,
)

ROOT = Path(__file__).resolve().parents[2]
DRAWS_PATH = ROOT / "data" / "draws.json"
CONFIG_PATH = ROOT / "config" / "config.json"
RESULTS_DIR = ROOT / "data" / "results"
DOCS_DATA = ROOT / "docs" / "data"

# 檢定力聲明條件（roadmap §2.2-3）
COHORTS = [
    {"key": "cohort1", "label": "梯次一（啟動期實驗）", "n_periods": 200, "n_strategies": 68},
    {"key": "cohort2", "label": "梯次二（社群實驗，規劃）", "n_periods": 104, "n_strategies": 50},
]
N_PERM = 100000   # 需足夠解析 BH 臨界區（附錄 J.3）
N_SIM = 2000
SEED = 20260719


def _git(*args) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=str(ROOT)).decode().strip()
    except Exception:
        return ""


CHANNELS = {  # 通道分解（附錄 J.3）
    "jackpot_t1": ["t1"],
    "tier2_t2": ["t2"],
    "detect_t3_t8": ["t3", "t4", "t5", "t6", "t7", "t8"],
    "small_t5_t8": ["t5", "t6", "t7", "t8"],
}


def power_statement(amounts, n_periods, n_strategies, seed):
    """操作型 δ₈₀（附錄 J.2）：各 bet_type 全獎項命中率通道；另附通道分解與頭獎盲區。
    口徑＝完整理論軌（含頭獎），與註冊檢定一致。"""
    out = {"n_periods": n_periods, "n_strategies": n_strategies,
           "n_perm": N_PERM, "n_sim": N_SIM, "bet_types": {}}
    for bt in ("single", "wheel7", "wheel8"):
        d = delta80(bt, amounts, n_periods, n_strategies, n_perm=N_PERM, n_sim=N_SIM, seed=seed)
        entry = {
            "n_tickets": BET_TYPES[bt],
            "delta80": round(d["delta80"], 4),
            "delta80_per_100": round(d["delta80_per_100"], 1),
            "power_at_delta80": round(d["power_at_delta80"], 3),
            "null_median": round(d["null_median"], 4),
            "null_p95": round(d["null_p95"], 4),
            "expected_roi_null": round(d["expected_roi_null"], 4),
        }
        # 頭獎盲區（附錄 J.3 具體數字）
        jd = jackpot_doubling_power(bt, amounts, n_periods, n_strategies,
                                    n_perm=N_PERM, n_sim=N_SIM, seed=seed)
        entry["jackpot_doubling_power"] = round(jd["power"], 4)
        entry["jackpot_doubling_extra_per_100"] = round(jd["extra_roi_per_100"], 1)
        out["bet_types"][bt] = entry
    # 通道分解：single 上、固定 δ=null_p95 邊際優勢時各通道的偵測率（診斷用）
    single_p95 = out["bet_types"]["single"]["null_p95"]
    probe = round(2.0 * single_p95, 4)
    out["channel_decomposition"] = {
        "probe_delta": probe,
        "note": f"在 single、每元回收優勢 δ={probe}（≈2×null p95）下，各通道單獨注入的偵測率",
        "channels": {name: round(channel_power("single", amounts, n_periods, n_strategies,
                                               tiers, probe, n_perm=N_PERM, n_sim=N_SIM, seed=seed), 4)
                     for name, tiers in CHANNELS.items()},
    }
    return out


def audit_correction(audit):
    """裁決 A 修正記錄：MC 校準（後）vs 教科書 χ²（前）。前值由 chi2 現場重算。"""
    sn, pr, sp = audit["single_number"], audit["pair_cooccurrence"], audit["special_number"]

    def textbook(x):
        return round(float(scipy_stats.chi2.sf(x["chi2"], x["df"])), 4)

    return {
        "single": {"chi2": round(sn["chi2"], 2), "df": sn["df"],
                   "p_textbook_before": textbook(sn), "p_mc_after": round(sn["p_value"], 4),
                   "p_analytic_crosscheck": sn.get("p_analytic_scaled_chi2"),
                   "n_sim": sn.get("n_sim")},
        "pair": {"chi2": round(pr["chi2"], 1), "df": pr["df"],
                 "p_textbook_before": textbook(pr), "p_mc_after": round(pr["p_value"], 4)},
        "special": {"chi2": round(sp["chi2"], 2), "df": sp["df"],
                    "p": round(sp["p_value"], 4), "calibrated": False,
                    "note": "每期一顆、跨期獨立，χ²₄₈ 成立，不校準；p 維持原值"},
    }


def observational_summary(sv):
    if not sv or sv.get("label", "").startswith("not"):
        return {"available": False}
    strategies = sv.get("strategies", {})
    n_rejected = sum(1 for s in strategies.values() if s.get("fdr_rejected"))
    return {
        "available": True,
        "label": sv.get("label"),
        "n_periods": sv.get("n_periods"),
        "n_strategies": len(strategies),
        "n_perm": sv.get("n_perm"),
        "champion_roi": round(sv["champion_roi"], 4) if sv.get("champion_roi") is not None else None,
        "champion_median": round(sv["champion_median"], 4) if sv.get("champion_median") is not None else None,
        "n_fdr_rejected": n_rejected,
        "honest_note": sv.get("honest_note", ""),
    }


def main():
    cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    draws = load_draws(DRAWS_PATH)
    audit = json.loads((RESULTS_DIR / "audit.json").read_text(encoding="utf-8"))
    audit_ext = None
    p_ext = RESULTS_DIR / "audit_extended.json"
    if p_ext.exists():
        audit_ext = json.loads(p_ext.read_text(encoding="utf-8"))
    sv = None
    p_sv = RESULTS_DIR / "strategy_validation.json"
    if p_sv.exists():
        sv = json.loads(p_sv.read_text(encoding="utf-8"))

    tp = cfg["theoretical_prizes"]
    amounts = {**tp["fixed"], **{k: v for k, v in tp.get("frozen_median", {}).items() if v is not None}}
    print("檢定力模擬（操作型 δ₈₀，Poisson 命中數模型，附錄 J）…")
    power = {}
    for c in COHORTS:
        power[c["key"]] = {"label": c["label"],
                           **power_statement(amounts, c["n_periods"], c["n_strategies"], SEED)}
        s = power[c["key"]]["bet_types"]["single"]
        print(f"  {c['label']}：{c['n_periods']} 期 N={c['n_strategies']} → single "
              f"δ80≈每100元 {s['delta80_per_100']} 元（power {s['power_at_delta80']}）"
              f" 頭獎翻倍偵測率 {s['jackpot_doubling_power']}")

    academic = {
        "generated_at_period": draws[-1].period if draws else None,
        "last_date": draws[-1].date if draws else None,
        "n_periods_official": len(draws),
        "prospective_start_period": cfg.get("prospective_start_period"),
        "git_commit": _git("rev-parse", "HEAD"),
        "git_commit_short": _git("rev-parse", "--short", "HEAD"),
        "audit": audit,
        "audit_extended": audit_ext,
        "audit_correction": audit_correction(audit),
        "observational_validation": observational_summary(sv),
        "power": power,
        "power_note": ("δ₈₀＝一條策略理論軌每元回收需偏離對照基準多少，才能在 n 期、N 策略、"
                       "α=0.05（BH-FDR 校正後）下以 80% 機率被偵測（附錄 J 操作型定義）。"
                       "口徑＝完整理論軌（含頭獎），與註冊檢定一致；命中數以 Poisson(n·λ_t) 模擬，"
                       "稀有頭獎穩定處理。channel_decomposition 為各獎項通道的偵測貢獻診斷，"
                       "非聲明主體。"),
    }
    DOCS_DATA.mkdir(parents=True, exist_ok=True)
    (DOCS_DATA / "academic.json").write_text(
        json.dumps(academic, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"完成 → {(DOCS_DATA / 'academic.json').relative_to(ROOT)}")


if __name__ == "__main__":
    main()
