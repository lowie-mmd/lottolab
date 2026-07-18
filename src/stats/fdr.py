"""Benjamini–Hochberg FDR 校正（規格 §5.1）。N = 全部註冊策略數。"""
from __future__ import annotations


def benjamini_hochberg(pvalues: list[float], alpha: float = 0.05) -> dict:
    """回傳 BH 校正結果：各 p 的 q 值（校正後）與是否在 alpha 下顯著。

    q_i = min_{k>=i}( p_(k) * N / k )（依 p 升冪，單調化）。
    """
    n = len(pvalues)
    if n == 0:
        return {"q_values": [], "rejected": [], "n": 0, "alpha": alpha}
    indexed = sorted(enumerate(pvalues), key=lambda t: t[1])
    q_sorted = [0.0] * n
    prev = 1.0
    # 由大到小做單調化
    for rank in range(n, 0, -1):
        orig_i, p = indexed[rank - 1]
        q = p * n / rank
        prev = min(prev, q)
        q_sorted[rank - 1] = prev
    q_values = [0.0] * n
    rejected = [False] * n
    for rank, (orig_i, _p) in enumerate(indexed, start=1):
        q_values[orig_i] = q_sorted[rank - 1]
        rejected[orig_i] = q_sorted[rank - 1] <= alpha
    return {"q_values": q_values, "rejected": rejected, "n": n, "alpha": alpha}
