"""梯次二雙終點與多重性校正（裁決書附錄 K.4）。

共同主終點（並列預先承諾，兩份報告都必須發布）：
  ① full_track_roi   — 全軌理論軌每元回收（沿用梯次一註冊檢定口徑）
  ② small_prize_roi  — 小獎通道 t5–t8 理論軌每元回收（K.4 新增）

新增 ② 的理由（K.4）：104 期下全軌 δ₈₀≈每100元 2,454 元，對現實效應近乎零檢定力；
小獎通道 null 連續平滑（無 t1–t4 的離散跳階），δ₈₀≈126 元，具實用檢定力。徵集數十條
認真演算法參加一個註定測不到的比賽，與本站誠實原則衝突。

多重性校正（於凍結時由洛伊裁決採用何者，預設 bonferroni_split）：
  - bonferroni_split：α 平分至兩終點（各 α/2），於各終點內對 N 策略做 BH-FDR。
    保守、兩終點各自可獨立解讀，符合「共同主終點」慣例。
  - pooled_bh：2N 個 p 值併為單一 BH family，於 α 下控制整體 FDR。較有檢定力，
    但「某策略在哪個終點顯著」的解讀需連帶說明。
"""
from __future__ import annotations

from engine.backtest import TheoreticalPrizeTable
from stats.fdr import benjamini_hochberg

MODES = ("bonferroni_split", "pooled_bh")


def endpoint_prize_table(theoretical_prizes: dict, tiers) -> TheoreticalPrizeTable:
    """把 config 的理論獎額遮罩成只保留 tiers 的獎額表（其餘計 0）。

    用於小獎通道終點：統計量只計 t5–t8，null 因而連續平滑。
    遮罩只影響「該終點的統計量」，不改動任何已註冊資料或梯次一檢定。
    """
    keep = set(tiers)
    fixed = {k: (v if k in keep else 0) for k, v in (theoretical_prizes.get("fixed") or {}).items()}
    frozen = {k: (v if (k in keep and v is not None) else 0)
              for k, v in (theoretical_prizes.get("frozen_median") or {}).items()}
    return TheoreticalPrizeTable(fixed, frozen)


def dual_endpoint_correction(pvalues_by_endpoint: dict, alpha: float = 0.05,
                             mode: str = "bonferroni_split") -> dict:
    """對雙終點 × N 策略的 p 值做多重性校正。

    參數 pvalues_by_endpoint：{endpoint_key: {strategy_id: p}}（各終點策略集合須相同）。
    回傳 {endpoint_key: {strategy_id: {"p","q","rejected"}}, "_mode","_alpha","_n_tests"}。
    """
    if mode not in MODES:
        raise ValueError(f"multiplicity mode 須為 {MODES} 之一，得到 {mode!r}")
    keys = list(pvalues_by_endpoint.keys())
    if not keys:
        return {"_mode": mode, "_alpha": alpha, "_n_tests": 0}
    id_sets = [set(pvalues_by_endpoint[k]) for k in keys]
    if any(s != id_sets[0] for s in id_sets):
        raise ValueError("各終點的策略集合必須相同（共同主終點）")
    ids = sorted(id_sets[0])
    out: dict = {"_mode": mode, "_alpha": alpha, "_n_tests": len(keys) * len(ids)}

    if mode == "bonferroni_split":
        a_each = alpha / len(keys)
        for k in keys:
            pv = [pvalues_by_endpoint[k][sid] for sid in ids]
            bh = benjamini_hochberg(pv, alpha=a_each)
            out[k] = {sid: {"p": pv[i], "q": bh["q_values"][i], "rejected": bh["rejected"][i]}
                      for i, sid in enumerate(ids)}
            out.setdefault("_alpha_per_endpoint", a_each)
    else:  # pooled_bh
        flat, index = [], []
        for k in keys:
            for sid in ids:
                flat.append(pvalues_by_endpoint[k][sid])
                index.append((k, sid))
        bh = benjamini_hochberg(flat, alpha=alpha)
        for k in keys:
            out[k] = {}
        for i, (k, sid) in enumerate(index):
            out[k][sid] = {"p": flat[i], "q": bh["q_values"][i], "rejected": bh["rejected"][i]}
    return out


def any_endpoint_rejected(corrected: dict, strategy_id: str) -> bool:
    """該策略是否在任一共同主終點被判顯著（校正後）。"""
    return any(
        isinstance(v, dict) and strategy_id in v and v[strategy_id].get("rejected")
        for k, v in corrected.items() if not k.startswith("_")
    )


def summarize(corrected: dict) -> dict:
    """各終點顯著數與整體（任一終點）顯著數。"""
    eps = [k for k in corrected if not k.startswith("_")]
    per = {k: sum(1 for r in corrected[k].values() if r["rejected"]) for k in eps}
    ids = sorted({sid for k in eps for sid in corrected[k]})
    return {
        "mode": corrected.get("_mode"),
        "alpha": corrected.get("_alpha"),
        "n_tests": corrected.get("_n_tests"),
        "rejected_per_endpoint": per,
        "rejected_any_endpoint": sum(1 for sid in ids if any_endpoint_rejected(corrected, sid)),
        "n_strategies": len(ids),
    }
