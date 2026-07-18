"""雙源比對衝突模擬（規格 §2.1、M1 驗收③）：號碼不一致須觸發停止機制。"""
from __future__ import annotations

import pytest

from scraper.build_draws import SourceConflictError, compare_sources


def _rec(period, nums, special):
    return {"period": period, "numbers": nums, "special": special}


def test_number_conflict_raises():
    primary = _rec("113000001", [1, 2, 3, 4, 5, 6], 7)
    backup = _rec("113000001", [1, 2, 3, 4, 5, 9], 7)   # 一般號不同
    with pytest.raises(SourceConflictError):
        compare_sources(primary, backup)


def test_special_conflict_raises():
    primary = _rec("113000001", [1, 2, 3, 4, 5, 6], 7)
    backup = _rec("113000001", [1, 2, 3, 4, 5, 6], 8)   # 特別號不同
    with pytest.raises(SourceConflictError):
        compare_sources(primary, backup)


def test_agreement_ok():
    primary = _rec("113000001", [1, 2, 3, 4, 5, 6], 7)
    backup = _rec("113000001", [1, 2, 3, 4, 5, 6], 7)
    compare_sources(primary, backup)   # 不丟例外


def test_different_period_skipped():
    # 期別不同視為不同期，不比對（不誤報）
    compare_sources(_rec("113000001", [1, 2, 3, 4, 5, 6], 7),
                    _rec("113000002", [9, 9, 9, 9, 9, 9], 9))
