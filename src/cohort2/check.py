"""參賽策略交件檢查 CLI（roadmap §3.4「驗證管線自動回饋」）。

用法：
    PYTHONPATH=src python -m cohort2.check path/to/manifest.json
    PYTHONPATH=src python -m cohort2.check manifest.json --json      # 機器可讀（供 CI 貼 PR）

離開碼：0＝四關全過可收件；1＝未通過或 manifest 不合規。
比對對象為 config/cohort2.json 已收錄之策略（重複性關）；未凍結前清單為空。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from cohort2.control import load_cohort2_config
from cohort2.manifest import Manifest, ManifestError
from cohort2.validate import validate_manifest
from engine.game import get_game
from engine.models import load_draws

ROOT = Path(__file__).resolve().parents[2]
DRAWS_PATH = ROOT / "data" / "draws.json"


def _existing_strategies(cfg2: dict, game) -> list:
    """已收錄策略（重複性關比對對象）。未凍結前通常為空。"""
    out = []
    for entry in cfg2.get("strategies") or []:
        try:
            out.append(Manifest.from_dict(entry).build_strategy(game))
        except ManifestError as e:
            print(f"⚠️ 已收錄策略 {entry.get('id')} 無法建立，跳過比對：{e}", file=sys.stderr)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="梯次二參賽策略驗證管線")
    ap.add_argument("manifest", help="manifest JSON 路徑")
    ap.add_argument("--json", action="store_true", help="輸出機器可讀 JSON")
    ap.add_argument("--window", type=int, default=None, help="重複性比對期數（預設 100）")
    args = ap.parse_args(argv)

    cfg2 = load_cohort2_config()
    game = get_game(cfg2["game"])
    draws = load_draws(DRAWS_PATH)

    try:
        man = Manifest.load(args.manifest)
    except (ManifestError, OSError, json.JSONDecodeError) as e:
        msg = f"❌ manifest 不合規：{e}"
        print(json.dumps({"passed": False, "error": str(e)}, ensure_ascii=False)
              if args.json else msg)
        return 1

    kw = {"dup_window": args.window} if args.window else {}
    try:
        rep = validate_manifest(man, game, draws, existing=_existing_strategies(cfg2, game), **kw)
    except ManifestError as e:
        msg = f"❌ 策略無法建立（程式碼契約不符）：{e}"
        print(json.dumps({"passed": False, "error": str(e)}, ensure_ascii=False)
              if args.json else msg)
        return 1

    if args.json:
        print(json.dumps(rep.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(rep.summary())
        if rep.passed:
            print("\n可收件：四關全過。最終收錄與否仍由洛伊依「邏輯多樣性」準則篩選（§3.2）。")
    return 0 if rep.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
