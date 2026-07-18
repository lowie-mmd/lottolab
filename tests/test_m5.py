"""M5 驗收（規格 §7）：
① repo 全文＋建置產物無明文號碼（加密確實隱藏）
② 錯誤密語不洩漏資訊（GCM 驗證失敗）
③ engine.js ↔ Python 引擎共用測試向量輸出全等
④ add_bet.py 加密→解密往返無損，且與 crypto.js 互通
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from tools.add_bet import decrypt_envelope, encrypt_envelope

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "tests" / "js"
HAS_NODE = shutil.which("node") is not None

CANARY = {  # 已知測試號碼型樣（§7.2 grep 依據）
    "recurring": [{"label": "測試夢境", "numbers": [11, 22, 33, 44, 45, 46], "since": "113000001"}],
    "bets": [{"period": "113000001",
              "tickets": [{"label": "測試夢境"}, {"label": "電腦選號", "numbers": [3, 13, 23, 37, 41, 49]}],
              "cost": 100}],
}
CANARY_SEQS = ["11, 22, 33, 44, 45, 46", "11,22,33,44,45,46", "3, 13, 23, 37, 41, 49"]


# ---------- ④ Python 往返 ----------
def test_python_roundtrip_lossless():
    env = encrypt_envelope(CANARY, "correct horse battery staple")
    assert decrypt_envelope(env, "correct horse battery staple") == CANARY


# ---------- ② 錯誤密語 ----------
def test_wrong_passphrase_raises():
    env = encrypt_envelope(CANARY, "right-pass")
    with pytest.raises(Exception):
        decrypt_envelope(env, "wrong-pass")


# ---------- ① 密文不含明文號碼 ----------
def test_ciphertext_hides_plaintext_numbers():
    env = encrypt_envelope(CANARY, "secret")
    blob = json.dumps(env, ensure_ascii=False)
    for seq in CANARY_SEQS:
        assert seq not in blob
    assert "測試夢境" not in blob and "電腦選號" not in blob


def test_no_plaintext_bets_in_tracked_files():
    """git 追蹤檔中不得有明文投注（data/private 只允許 .enc）。"""
    tracked = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True).stdout.split()
    for f in tracked:
        if f.startswith("data/private/"):
            assert f.endswith(".enc"), f"data/private 出現非密文檔：{f}"
    # 若已存在真實 bets.enc，確認是 envelope 而非明文
    enc = ROOT / "data" / "private" / "bets.enc"
    if enc.exists():
        obj = json.loads(enc.read_text(encoding="utf-8"))
        assert set(obj) >= {"ct", "iv", "salt"} and "numbers" not in obj


# ---------- ③ engine.js 與 Python 向量全等 ----------
@pytest.mark.skipif(not HAS_NODE, reason="node 未安裝")
def test_js_engine_parity_with_vectors():
    r = subprocess.run(["node", str(JS / "engine_check.mjs")], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert r.stdout.startswith("OK"), r.stdout


# ---------- ④ 跨語言互通：Python 加密 → JS 解密，JS 加密 → Python 解密 ----------
@pytest.mark.skipif(not HAS_NODE, reason="node 未安裝")
def test_interop_python_encrypt_js_decrypt():
    env = encrypt_envelope(CANARY, "pw-interop")
    r = subprocess.run(["node", str(JS / "crypto_cli.mjs"), "decrypt", "pw-interop"],
                       input=json.dumps(env), capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout) == CANARY


@pytest.mark.skipif(not HAS_NODE, reason="node 未安裝")
def test_interop_js_encrypt_python_decrypt():
    r = subprocess.run(["node", str(JS / "crypto_cli.mjs"), "encrypt", "pw-interop"],
                       input=json.dumps(CANARY), capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    env = json.loads(r.stdout)
    assert decrypt_envelope(env, "pw-interop") == CANARY
