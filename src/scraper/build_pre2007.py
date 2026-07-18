"""建立 2004–2006 北銀延伸資料層 data/draws_pre2007.json（見 DECISIONS.md 2026-07-18）。

雙第三方（pilio + lotto-8）互相對帳：僅收「兩源皆有且完全一致」的期數；
任一期兩源號碼/特別號不符 → 停止入庫、報告衝突（CI 應開 issue）——信任層級降低，
但對帳紀律不降。全部 numbers_only、source 標「thirdparty_pre2007」。

period 為重建之 ROC 年序（民國年*1e6 + 當年序號），與官方編號慣例一致且排序正確，
但屬重建值（北銀官方期號未由第三方提供），不與官方 2007+ 資料同級信任。

用法：PYTHONPATH=src python -m scraper.build_pre2007 [--check]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path

from scraper.thirdparty import fetch_lotto8, fetch_pilio

ROOT = Path(__file__).resolve().parents[2]
OUT_PATH = ROOT / "data" / "draws_pre2007.json"


class SourceConflictError(Exception):
    pass


def reconcile(pilio: dict, lotto8: dict) -> tuple[list, list, dict]:
    """回傳 (agreed_dates 排序, conflicts, stats)。conflicts 非空即應停止入庫。"""
    common = sorted(set(pilio) & set(lotto8))
    conflicts = []
    agreed = []
    for d in common:
        if pilio[d] == lotto8[d]:
            agreed.append(d)
        else:
            conflicts.append({"date": d, "pilio": pilio[d], "lotto8": lotto8[d]})
    stats = {
        "pilio_count": len(pilio),
        "lotto8_count": len(lotto8),
        "common": len(common),
        "agreed": len(agreed),
        "conflicts": len(conflicts),
        "pilio_only": sorted(set(pilio) - set(lotto8)),
        "lotto8_only": sorted(set(lotto8) - set(pilio)),
    }
    return agreed, conflicts, stats


def _reconstruct_period(date: str, seq_in_year: int) -> str:
    roc = int(date[:4]) - 1911
    return f"{roc:03d}{seq_in_year:06d}"


def build(agreed: list, source_data: dict) -> list[dict]:
    draws = []
    seq_by_year: dict[int, int] = {}
    for date in agreed:  # 已按日期排序
        year = int(date[:4])
        seq_by_year[year] = seq_by_year.get(year, 0) + 1
        numbers, special = source_data[date]
        draws.append({
            "period": _reconstruct_period(date, seq_by_year[year]),
            "date": date,
            "numbers": list(numbers),
            "special": special,
            "sales_amount": None,
            "prizes": {},
            "data_quality": "numbers_only",
            "promo": None,
            "source": "thirdparty_pre2007",
        })
    return draws


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="只對帳報告，不寫檔")
    args = ap.parse_args()

    print("抓取 pilio…")
    pilio = fetch_pilio()
    print(f"  pilio 2004–2006：{len(pilio)} 期")
    print("抓取 lotto-8…")
    lotto8 = fetch_lotto8()
    print(f"  lotto-8 2004–2006：{len(lotto8)} 期")

    agreed, conflicts, stats = reconcile(pilio, lotto8)
    print(f"對帳：共同 {stats['common']}、一致 {stats['agreed']}、"
          f"衝突 {stats['conflicts']}、pilio 獨有 {len(stats['pilio_only'])}、"
          f"lotto8 獨有 {len(stats['lotto8_only'])}")

    if conflicts:
        for c in conflicts[:10]:
            print(f"  ⚠ 衝突 {c['date']}: pilio={c['pilio']} lotto8={c['lotto8']}")
        raise SourceConflictError(
            f"雙第三方號碼不一致 {len(conflicts)} 期 → 停止入庫（規格對帳紀律）。")

    if args.check:
        print("--check：僅報告，未寫檔。")
        return

    draws = build(agreed, pilio)  # pilio==lotto8（已對帳一致），取 pilio
    payload = {
        "meta": {
            "game": "lotto649",
            "era": "taipeibank_2004_2006",
            "updated": dt.datetime.now(dt.timezone.utc).isoformat(),
            "sources": ["pilio", "lotto-8"],
            "trust_tier": "extended_thirdparty",
            "note": ("北銀時代延伸資料層；numbers_only；雙第三方對帳；"
                     "僅用於硬體審計延伸視圖與分段檢定，不進策略推論，"
                     "主混池檢定維持官方源（見 DECISIONS.md 2026-07-18）"),
        },
        "draws": draws,
    }
    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"寫入 {OUT_PATH.relative_to(ROOT)}：{len(draws)} 期 "
          f"({draws[0]['date']}→{draws[-1]['date']})" if draws else "無資料")


if __name__ == "__main__":
    main()
