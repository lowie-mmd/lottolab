"""建立 / 增量更新 data/draws.json，並計算理論軌凍結獎額與 data_quality 報告（M1）。

用法：
    PYTHONPATH=src python -m scraper.build_draws --full        # 初始化全歷史
    PYTHONPATH=src python -m scraper.build_draws --update      # 冪等增量（M7 用）
    PYTHONPATH=src python -m scraper.build_draws --report      # 只印 data_quality 報告

雙源比對（規格 §2.1）：主源為台彩官方 API。備源第三方尚未接入——
compare_sources() 已實作衝突偵測邏輯與停止機制，以合成資料測試（M1 驗收③）；
真備源接入為後續工作，見 DECISIONS.md。
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import statistics
import time
from collections import Counter
from pathlib import Path
from typing import Any, Optional

import requests

from engine.models import (
    QUALITY_FULL,
    draw_from_dict,
    load_draws_file,
)
from scraper.taiwanlottery import (
    TIER_TO_ASSIGN,
    fetch_month,
    iter_months,
    parse_record,
)

ROOT = Path(__file__).resolve().parents[2]
DRAWS_PATH = ROOT / "data" / "draws.json"
CONFIG_PATH = ROOT / "config" / "config.json"
REPORT_PATH = ROOT / "data" / "quality_report.json"

FLOATING_TIERS = ("t1", "t2", "t3", "t4")  # 理論軌需凍結中位數的浮動獎項


class SourceConflictError(Exception):
    """雙源號碼不一致——停止 commit、開 issue、等人工裁決（規格 §2.1）。"""


def compare_sources(primary: dict, backup: dict) -> None:
    """比對同一期兩源。號碼不一致 → 丟 SourceConflictError（硬性停止）；
    僅獎金細節不一致 → 以官網為準（呼叫端記 log）。"""
    if str(primary.get("period")) != str(backup.get("period")):
        return
    if list(primary.get("numbers") or []) != list(backup.get("numbers") or []) or \
       primary.get("special") != backup.get("special"):
        raise SourceConflictError(
            f"期別 {primary.get('period')} 號碼雙源不一致："
            f"primary={primary.get('numbers')}+{primary.get('special')} "
            f"backup={backup.get('numbers')}+{backup.get('special')}"
        )


def fetch_all(start=(2007, 1), end: Optional[tuple[int, int]] = None,
              delay: float = 0.25, verbose: bool = True) -> list[dict[str, Any]]:
    """抓取 start..end 每月的所有期數，回傳 parse 後 schema dict 清單（升冪）。"""
    sess = requests.Session()
    records: list[dict[str, Any]] = []
    ey, em = (end or (None, None))
    for y, m in iter_months(start[0], start[1], ey, em):
        raw_list = fetch_month(y, m, session=sess)
        for raw in raw_list:
            records.append(parse_record(raw))
        if verbose and raw_list:
            print(f"  {y}-{m:02d}: {len(raw_list)} 期")
        time.sleep(delay)
    records.sort(key=lambda r: int(r["period"]))
    return records


def compute_frozen_medians(records: list[dict]) -> dict[str, int]:
    """以 data_quality=full 且該獎項 winnerCount>0 的期數，取單注獎額中位數（§2.2）。

    條件 winnerCount>0：無人中獎期 perPrize=0，會把中位數壓成 0；理論軌要的是
    「命中該獎項時的典型單注獎額」，故僅取實際有中獎的期數。（見 DECISIONS.md）
    """
    medians: dict[str, int] = {}
    for tier in FLOATING_TIERS:
        vals = []
        for r in records:
            if r["data_quality"] != QUALITY_FULL:
                continue
            node = r["prizes"].get(tier, {})
            winners = node.get("winners")
            amount = node.get("amount")
            if winners and winners > 0 and amount and amount > 0:
                vals.append(amount)
        medians[tier] = int(statistics.median(vals)) if vals else 0
    return medians


def quality_report(records: list[dict]) -> dict:
    counts = Counter(r["data_quality"] for r in records)
    years = Counter(r["date"][:4] for r in records if r.get("date"))
    return {
        "total_periods": len(records),
        "by_quality": dict(counts),
        "by_year": dict(sorted(years.items())),
        "first_period": records[0]["period"] if records else None,
        "last_period": records[-1]["period"] if records else None,
        "first_date": records[0]["date"] if records else None,
        "last_date": records[-1]["date"] if records else None,
    }


def _write_draws(records: list[dict]) -> None:
    payload = {
        "meta": {
            "game": "lotto649",
            "updated": dt.datetime.now(dt.timezone.utc).isoformat(),
            "sources": ["taiwanlottery"],
        },
        "draws": records,
    }
    DRAWS_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _update_config_medians(medians: dict[str, int]) -> None:
    cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    cfg["theoretical_prizes"]["frozen_median"] = medians
    CONFIG_PATH.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")


def build_full() -> dict:
    print("抓取全歷史（2007-01 → 至今）…")
    records = fetch_all()
    _write_draws(records)
    medians = compute_frozen_medians(records)
    _update_config_medians(medians)
    report = quality_report(records)
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n完成：{report['total_periods']} 期 "
          f"({report['first_period']} → {report['last_period']})")
    print(f"data_quality 分布：{report['by_quality']}")
    print(f"理論軌凍結中位數：{medians}")
    return report


def build_update() -> dict:
    """冪等增量（M7）：只補比現有 draws.json 更新的期數；無新期數 no-op。"""
    existing = load_draws_file(DRAWS_PATH)
    have = {str(d["period"]) for d in existing.get("draws", [])}
    last_date = None
    if existing.get("draws"):
        last_date = max((d.get("date") or "") for d in existing["draws"])
    start = (2007, 1)
    if last_date:
        y, m = int(last_date[:4]), int(last_date[5:7])
        start = (y, m)  # 從最後一期所在月重抓（含補當月後續期）
    fresh = fetch_all(start=start)
    new_records = [r for r in fresh if str(r["period"]) not in have]
    if not new_records:
        print("無新期數，冪等退出（no-op）。")
        return {"new_periods": 0}
    merged = existing.get("draws", []) + new_records
    merged.sort(key=lambda r: int(r["period"]))
    _write_draws(merged)
    print(f"新增 {len(new_records)} 期：{[r['period'] for r in new_records]}")
    return {"new_periods": len(new_records)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--full", action="store_true", help="初始化全歷史")
    ap.add_argument("--update", action="store_true", help="冪等增量更新")
    ap.add_argument("--report", action="store_true", help="只印現有 draws.json 的品質報告")
    args = ap.parse_args()

    if args.full:
        build_full()
    elif args.update:
        build_update()
    elif args.report:
        data = load_draws_file(DRAWS_PATH)
        print(json.dumps(quality_report(data.get("draws", [])), ensure_ascii=False, indent=2))
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
