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

from engine.backtest import TheoreticalPrizeTable, run_walk_forward, summarize
from engine.game import get_game
from engine.models import load_draws
from strategies.registry import build_all_strategies

ROOT = Path(__file__).resolve().parents[2]
DRAWS_PATH = ROOT / "data" / "draws.json"
CONFIG_PATH = ROOT / "config" / "config.json"
RESULTS_DIR = ROOT / "data" / "results"
DOCS_DATA = ROOT / "docs" / "data"

SAMPLE_POINTS = 160  # 曲線降采樣點數

GITHUB_PATH = {  # 各組原始碼路徑（策略卡「原始碼 →」連結）
    "A": "src/strategies/group_a.py", "B": "src/strategies/group_b.py",
    "C": "src/strategies/group_c.py", "D": "src/strategies/group_d.py",
    "E": "src/strategies/group_e.py", "F": "src/strategies/group_f.py",
}

# 策略卡展示文案（名稱／白話一句話／本期選號依據摘要）。文案為 v1.3 §2.3 定稿，逐字沿用。
# D01–03（養牌）、E01–05（包牌）各共用一句話。
_ONELINER_D = "一組隨機產生後就永遠固定的號碼。驗證「長期養一組牌」和每期換號有沒有差。"
_ONELINER_E = "多選幾個號碼、排出所有 6 碼組合全買。中獎次數更多，但成本等比放大──驗證包牌到底有沒有改變每一塊錢的期望值。"
STRATEGY_META = {
    "B01": ("熱門號", "哪些號碼最近 50 期最常開，就買哪些。", "近 50 期出現頻率排行前段"),
    "B02": ("冷門號", "哪些號碼最近 50 期最少開，就買哪些（賭它「該輪到了」）。", "近 50 期出現頻率最低段"),
    "B03": ("遺漏回補", "哪些號碼最久沒出現，就買哪些。", "遺漏期數（最久未出現）前段"),
    "B04": ("尾數平衡", "按歷史上各尾數（0–9）出現的比例抽號。", "各尾數歷史比例加權抽樣"),
    "B05": ("奇偶大小平衡", "強制 3 單 3 雙、3 大 3 小的隨機組合。", "3 單 3 雙 × 3 大 3 小 約束隨機"),
    "C01": ("馬可夫轉移", "統計哪些號碼傾向跟著哪些號碼一起出現，選共現機率最高的組合。", "共現轉移機率前段"),
    "C02": ("上期重複", "保留上期 1–2 個號碼，其餘隨機（歷史上約四成的期數會重複上期至少一號）。", "保留上期 1–2 號 + 其餘隨機"),
    "C03": ("差值模式", "模仿歷史上相鄰號碼之間差距的分布來生成號碼。", "相鄰號差距分布抽樣"),
    "D01": ("養牌 D01", _ONELINER_D, "固定號（開跑前凍結）"),
    "D02": ("養牌 D02", _ONELINER_D, "固定號（開跑前凍結）"),
    "D03": ("養牌 D03", _ONELINER_D, "固定號（開跑前凍結）"),
    "E01": ("包牌 E01｜隨機 7 號", _ONELINER_E, "隨機 7 號包牌"),
    "E02": ("包牌 E02｜隨機 8 號", _ONELINER_E, "隨機 8 號包牌"),
    "E03": ("包牌 E03｜熱門 8 號", _ONELINER_E, "近 50 期熱門 8 號包牌"),
    "E04": ("包牌 E04｜冷門 8 號", _ONELINER_E, "近 50 期冷門 8 號包牌"),
    "E05": ("包牌 E05｜凍結 8 號", _ONELINER_E, "固定 8 號（開跑前凍結）包牌"),
    "F01": ("全大號", "6 個號碼全部大於 31──避開生日數字。就算中獎機率相同，中的時候分獎的人比較少。", "全部 >31 的號碼隨機"),
    "F02": ("反模式", "排除順子、等差、同尾數過多這些人類愛買的「漂亮組合」後隨機選。", "排除人類偏好「漂亮組合」後隨機"),
}
_ONELINER_A = "這 50 個不是策略，是量尺。純亂數選號，用來畫出「純運氣能有多好」的範圍。"


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


def _bet_type_and_picks(tickets):
    """由 predict 輸出推導 bet_type 標示與卡片顯示號組。
    單注→顯示該注 6 碼；包牌→顯示 wheel 號組並標示注數。"""
    n = len(tickets)
    if n <= 1:
        return "單注", ([list(tickets[0])] if tickets else [])
    union = sorted({x for t in tickets for x in t})
    return f"{len(union)} 碼包牌 {n} 注", [union]


def build_strategy_cards(game, strategies, draws, theo, luck):
    """每策略一張卡（A 組彙整為單張「量尺」卡）。本期選號＝以全歷史 predict
    產生對下一期（前瞻段啟動期）的下注，與展示資料同源、不重算實驗結果。"""
    latest = draws[-1] if draws else None
    cards = []
    # A 組彙整卡（量尺）
    a_rois = [s["roi_final"] for sid, s in luck["strategies"].items()
              if s["group"] == "A" and s["roi_final"] is not None]
    cards.append({
        "id": "A", "group": "A", "name": "純亂數對照組（50）",
        "oneliner": _ONELINER_A,
        "ruler": {
            "champion": max(a_rois) if a_rois else None,
            "median": statistics.median(a_rois) if a_rois else None,
            "n": len(a_rois),
        },
        "github_path": GITHUB_PATH["A"],
    })
    # B–F 真策略卡
    for s in strategies:
        if s.group == "A":
            continue
        name, oneliner, basis = STRATEGY_META.get(s.id, (s.id, "", ""))
        results = run_walk_forward(game, s, draws, theo)
        summ = summarize(results)
        tickets = [tuple(t) for t in s.predict(draws)]  # 本期選號（對啟動期）
        bet_type, picks = _bet_type_and_picks(tickets)
        cards.append({
            "id": s.id, "group": s.group, "name": name,
            "oneliner": oneliner, "bet_type": bet_type,
            "picks": picks, "picks_basis": basis,
            "roi_final": round(summ["roi_theoretical"], 4) if summ["roi_theoretical"] is not None else None,
            "tier_hits": summ["tier_hits"],
            "roi_curve": luck["strategies"].get(s.id, {}).get("curve", []),
            "github_path": GITHUB_PATH.get(s.group),
        })
    return {
        "for_period": latest.period if latest else None,
        "note": "本期選號＝以截至上表最後一期的全歷史，對下一期（前瞻段啟動期 115000072）之下注；每期由每日 Actions 更新。",
        "cards": cards,
    }


def build_audit_balls(draws):
    """49 顆球的出現次數與標準化殘差 z（供搖獎機體檢球形圖）。
    z=(觀測-期望)/√期望，與 stats.audit 單號卡方同法、同源，純展示、不改寫審計結果。"""
    pool_max = 49
    counts = {n: 0 for n in range(1, pool_max + 1)}
    for d in draws:
        for x in d.numbers:
            if x in counts:
                counts[x] += 1
    total = sum(counts.values())
    expected = total / pool_max if pool_max else 0
    sd = expected ** 0.5 if expected else 1
    single = [{"number": n, "observed": counts[n],
               "z": round((counts[n] - expected) / sd, 3) if sd else 0}
              for n in range(1, pool_max + 1)]
    return {"expected_per_number": round(expected, 3),
            "total_observations": total,
            "single_number": single}


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

    # 策略卡（本期選號／bet_type／各獎命中／迷你圖）與 49 顆球審計殘差
    (DOCS_DATA / "strategy_cards.json").write_text(
        json.dumps(build_strategy_cards(game, strategies, draws, theo, luck),
                   ensure_ascii=False), encoding="utf-8")
    (DOCS_DATA / "audit_balls.json").write_text(
        json.dumps(build_audit_balls(draws), ensure_ascii=False), encoding="utf-8")

    # 複製審計結果（若已由 run_stats 產生）
    audit = RESULTS_DIR / "audit.json"
    if audit.exists():
        shutil.copy(audit, DOCS_DATA / "audit.json")
    audit_ext = RESULTS_DIR / "audit_extended.json"
    if audit_ext.exists():
        shutil.copy(audit_ext, DOCS_DATA / "audit_extended.json")

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
