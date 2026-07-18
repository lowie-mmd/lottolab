"""北銀延伸層：第三方 HTML 解析 + 雙源對帳（含衝突停止）驗證。"""
from __future__ import annotations

import pytest

from scraper.build_pre2007 import SourceConflictError, build, reconcile
from scraper.thirdparty import parse_lotto8, parse_pilio

PILIO_HTML = '''
<td class="date-cell">01/05<br>04(一)</td>
<td class="number-cell">06,&nbsp;09,&nbsp;12,&nbsp;13,&nbsp;33,&nbsp;39</td>
<td class="bonus-cell">21</td>
<td class="date-cell">01/08<br>04(四)</td>
<td class="number-cell">16,&nbsp;21,&nbsp;27,&nbsp;30,&nbsp;31,&nbsp;47</td>
<td class="bonus-cell">35</td>
'''

LOTTO8_HTML = '''
<td>2004 01/05 (一)</td><td>06 , 09 , 12 , 13 , 33 , 39</td><td>21</td>
<td>2004 01/08 (四)</td><td>16 , 21 , 27 , 30 , 31 , 47</td><td>35</td>
'''


def test_parse_pilio():
    rows = parse_pilio(PILIO_HTML)
    assert rows[0] == ("2004-01-05", (6, 9, 12, 13, 33, 39), 21)
    assert rows[1] == ("2004-01-08", (16, 21, 27, 30, 31, 47), 35)


def test_parse_lotto8():
    rows = parse_lotto8(LOTTO8_HTML)
    assert rows[0] == ("2004-01-05", (6, 9, 12, 13, 33, 39), 21)
    assert rows[1] == ("2004-01-08", (16, 21, 27, 30, 31, 47), 35)


def test_reconcile_agreement():
    p = {d: (n, s) for d, n, s in parse_pilio(PILIO_HTML)}
    l = {d: (n, s) for d, n, s in parse_lotto8(LOTTO8_HTML)}
    agreed, conflicts, stats = reconcile(p, l)
    assert conflicts == []
    assert agreed == ["2004-01-05", "2004-01-08"]
    assert stats["agreed"] == 2


def test_reconcile_conflict_detected():
    p = {"2004-01-05": ((6, 9, 12, 13, 33, 39), 21)}
    l = {"2004-01-05": ((6, 9, 12, 13, 33, 39), 22)}  # 特別號不符
    agreed, conflicts, stats = reconcile(p, l)
    assert agreed == []
    assert len(conflicts) == 1 and conflicts[0]["date"] == "2004-01-05"


def test_build_reconstructs_period_and_tags_source():
    p = {d: (n, s) for d, n, s in parse_pilio(PILIO_HTML)}
    l = {d: (n, s) for d, n, s in parse_lotto8(LOTTO8_HTML)}
    agreed, _, _ = reconcile(p, l)
    draws = build(agreed, p)
    assert draws[0]["period"] == "093000001"      # 民國93 第1期（重建序）
    assert draws[1]["period"] == "093000002"
    assert draws[0]["data_quality"] == "numbers_only"
    assert draws[0]["source"] == "thirdparty_pre2007"
    assert draws[0]["prizes"] == {} and draws[0]["sales_amount"] is None
