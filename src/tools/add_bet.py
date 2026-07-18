"""本地投注記錄工具（M5，規格 §7.2）。

輸入期別＋號碼＋密語 → 解密 bets.enc、附加、重加密、覆寫 → 洛伊自行 commit。
固定組（夢境／塔位）以 label 引用不重複輸入。

crypto 與 docs/crypto.js 完全相同（PBKDF2-SHA256 600k + AES-256-GCM + 同 envelope 格式），
故 add_bet.py 寫的密文瀏覽器可解、瀏覽器寫的密文本工具亦可解。

設計鐵律：明文只存在於本機記憶體與檔案系統暫態，密文（bets.enc）才進 repo。
明文 bets 檔（若匯出）受 .gitignore 排除。
"""
from __future__ import annotations

import argparse
import base64
import getpass
import hashlib
import json
import os
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

KDF_ITERATIONS = 600000
SALT_BYTES = 16
IV_BYTES = 12

ROOT = Path(__file__).resolve().parents[2]
ENC_PATH = ROOT / "data" / "private" / "bets.enc"


def _derive_key(passphrase: str, salt: bytes, iterations: int) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", passphrase.encode("utf-8"), salt, iterations, dklen=32)


def encrypt_envelope(obj: Any, passphrase: str, iterations: int = KDF_ITERATIONS) -> dict:
    salt = os.urandom(SALT_BYTES)
    iv = os.urandom(IV_BYTES)
    key = _derive_key(passphrase, salt, iterations)
    plaintext = json.dumps(obj, ensure_ascii=False).encode("utf-8")
    ct = AESGCM(key).encrypt(iv, plaintext, None)  # 回傳 ct||tag（與 WebCrypto 相同）
    return {
        "v": 1,
        "kdf": "PBKDF2-SHA256",
        "iter": iterations,
        "salt": base64.b64encode(salt).decode(),
        "iv": base64.b64encode(iv).decode(),
        "ct": base64.b64encode(ct).decode(),
    }


def decrypt_envelope(envelope: dict, passphrase: str) -> Any:
    salt = base64.b64decode(envelope["salt"])
    iv = base64.b64decode(envelope["iv"])
    ct = base64.b64decode(envelope["ct"])
    key = _derive_key(passphrase, salt, envelope.get("iter", KDF_ITERATIONS))
    plaintext = AESGCM(key).decrypt(iv, ct, None)  # 密語錯誤 → InvalidTag 例外
    return json.loads(plaintext.decode("utf-8"))


def _empty() -> dict:
    return {"recurring": [], "bets": []}


def load(passphrase: str) -> dict:
    if not ENC_PATH.exists():
        return _empty()
    return decrypt_envelope(json.loads(ENC_PATH.read_text(encoding="utf-8")), passphrase)


def save(obj: dict, passphrase: str) -> None:
    ENC_PATH.parent.mkdir(parents=True, exist_ok=True)
    env = encrypt_envelope(obj, passphrase)
    ENC_PATH.write_text(json.dumps(env, ensure_ascii=False, indent=2), encoding="utf-8")


def _parse_numbers(s: str) -> list[int]:
    return sorted(int(x) for x in s.replace(",", " ").split())


def main() -> None:
    ap = argparse.ArgumentParser(description="私人投注記錄工具（明文永不進 repo）")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init", help="建立空的 bets.enc")

    pr = sub.add_parser("add-recurring", help="新增固定組（夢境/塔位）")
    pr.add_argument("--label", required=True)
    pr.add_argument("--numbers", required=True, help='如 "1 2 3 4 5 6"')
    pr.add_argument("--since", required=True, help="起始期別")

    pb = sub.add_parser("add-bet", help="新增某期投注")
    pb.add_argument("--period", required=True)
    pb.add_argument("--cost", type=int, required=True)
    pb.add_argument("--ticket", action="append", default=[],
                    help='格式 label=名稱 或 label=名稱;numbers=1 2 3 4 5 6（可重複）')

    sub.add_parser("show", help="顯示筆數摘要（不印號碼明文）")

    args = ap.parse_args()
    passphrase = getpass.getpass("通關密語：")

    data = load(passphrase)

    if args.cmd == "init":
        if ENC_PATH.exists():
            print("bets.enc 已存在，未覆寫。")
            return
        save(_empty(), passphrase)
        print(f"已建立 {ENC_PATH.relative_to(ROOT)}")
    elif args.cmd == "add-recurring":
        data["recurring"].append({
            "label": args.label,
            "numbers": _parse_numbers(args.numbers),
            "since": args.since,
        })
        save(data, passphrase)
        print(f"已新增固定組「{args.label}」。")
    elif args.cmd == "add-bet":
        tickets = []
        for spec in args.ticket:
            parts = dict(p.split("=", 1) for p in spec.split(";"))
            tk = {"label": parts["label"]}
            if "numbers" in parts:
                tk["numbers"] = _parse_numbers(parts["numbers"])
            tickets.append(tk)
        data["bets"].append({"period": args.period, "tickets": tickets, "cost": args.cost})
        save(data, passphrase)
        print(f"已記錄期 {args.period} 投注（{len(tickets)} 組，成本 {args.cost}）。")
    elif args.cmd == "show":
        print(f"固定組 {len(data['recurring'])} 個；投注紀錄 {len(data['bets'])} 期。")


if __name__ == "__main__":
    main()
