"""梯次二參賽策略驗證管線四關（roadmap §3.2）。

四關（全過才收件；任一關失敗回報明確原因，供 PR 自動回饋）：
  ① 決定性測試   — 同 history 重跑、獨立重建實例，輸出必須全等
  ② 前視保護測試 — 走查全程過引擎守門（assert_no_lookahead）；且 predict 不得改動 history
  ③ 執行時間上限 — 單期 predict < TIME_LIMIT_SEC（預設 10 秒）
  ④ 重複性檢查   — 與已收策略在近 DUP_WINDOW 期的預測重合率 > DUP_THRESHOLD 判定重複，
                   後到者退回（roadmap §3.2）

重合率定義：逐期取兩策略「該期所有注涵蓋的號碼集合」之 Jaccard，取平均。
單注與包牌因涵蓋號碼數不同，Jaccard 自然偏低——重複性主要用於攔截同 bet_type 的雷同演算法。
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional

from engine.backtest import assert_no_lookahead
from engine.models import Draw

TIME_LIMIT_SEC = 10.0
DUP_WINDOW = 100
DUP_THRESHOLD = 0.95


@dataclass
class GateResult:
    name: str
    passed: bool
    detail: str = ""


@dataclass
class ValidationReport:
    strategy_id: str
    gates: list = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(g.passed for g in self.gates)

    def to_dict(self) -> dict:
        return {"strategy_id": self.strategy_id, "passed": self.passed,
                "gates": [{"name": g.name, "passed": g.passed, "detail": g.detail} for g in self.gates]}

    def summary(self) -> str:
        lines = [f"策略 {self.strategy_id}：{'✅ 通過' if self.passed else '❌ 未通過'}"]
        for g in self.gates:
            lines.append(f"  {'✅' if g.passed else '❌'} {g.name}{'：' + g.detail if g.detail else ''}")
        return "\n".join(lines)


def _tickets_key(tickets) -> tuple:
    """把一期的注組合正規化成可比較的鍵（順序無關）。"""
    return tuple(sorted(tuple(sorted(t)) for t in tickets))


def _numbers_of(tickets) -> set:
    return {n for t in tickets for n in t}


def gate_determinism(strategy, rebuild, draws: list[Draw], probes: int = 5) -> GateResult:
    """同 history 重跑兩次、以及獨立重建的實例，輸出必須全等（§3.2 鐵律）。"""
    n = len(draws)
    idxs = [max(1, n * k // (probes + 1)) for k in range(1, probes + 1)]
    other = rebuild() if rebuild else None
    for i in idxs:
        hist = draws[:i]
        a = _tickets_key(strategy.predict(hist))
        b = _tickets_key(strategy.predict(hist))
        if a != b:
            return GateResult("決定性", False, f"同 history（{i} 期）重跑兩次輸出不同")
        if other is not None:
            c = _tickets_key(other.predict(hist))
            if a != c:
                return GateResult("決定性", False, f"獨立重建之實例於 {i} 期輸出不同（隨機性未由 seed 導出？）")
    return GateResult("決定性", True, f"{len(idxs)} 個取樣點重跑與重建皆全等")


def gate_lookahead(strategy, game, draws: list[Draw], probes: int = 5) -> GateResult:
    """引擎守門 + predict 不得改動 history + 產出須為合法注。"""
    n = len(draws)
    idxs = [max(1, n * k // (probes + 1)) for k in range(1, probes + 1)]
    for i in idxs:
        hist = draws[:i]
        target = draws[i]
        try:
            assert_no_lookahead(hist, target.period)
        except Exception as e:  # noqa: BLE001
            return GateResult("前視保護", False, f"切片守門失敗：{e}")
        before = [d.period for d in hist]
        tickets = list(strategy.predict(hist))
        if [d.period for d in hist] != before:
            return GateResult("前視保護", False, "predict 改動了傳入的 history（禁止）")
        if not tickets:
            return GateResult("前視保護", False, f"第 {i} 期 predict 未產生任何注")
        for tk in tickets:
            if not game.valid_ticket(tuple(tk)):
                return GateResult("前視保護", False, f"第 {i} 期產生非法注：{tk}")
    return GateResult("前視保護", True, f"{len(idxs)} 個取樣點皆過守門、注合法、未改動 history")


def gate_runtime(strategy, draws: list[Draw], limit: float = TIME_LIMIT_SEC,
                 probes: int = 5) -> GateResult:
    """單期 predict 執行時間上限。"""
    n = len(draws)
    idxs = [max(1, n * k // (probes + 1)) for k in range(1, probes + 1)]
    worst = 0.0
    for i in idxs:
        t0 = time.perf_counter()
        strategy.predict(draws[:i])
        dt = time.perf_counter() - t0
        worst = max(worst, dt)
        if dt > limit:
            return GateResult("執行時間", False, f"第 {i} 期 predict 耗時 {dt:.2f}s > 上限 {limit}s")
    return GateResult("執行時間", True, f"最慢單期 {worst:.3f}s（上限 {limit}s）")


def overlap_rate(a, b, draws: list[Draw], window: int = DUP_WINDOW) -> float:
    """兩策略在近 window 期預測的平均 Jaccard 重合率。"""
    n = len(draws)
    start = max(1, n - window)
    tot, cnt = 0.0, 0
    for i in range(start, n):
        hist = draws[:i]
        na, nb = _numbers_of(a.predict(hist)), _numbers_of(b.predict(hist))
        union = na | nb
        if union:
            tot += len(na & nb) / len(union)
            cnt += 1
    return tot / cnt if cnt else 0.0


def gate_duplicate(strategy, existing, draws: list[Draw], window: int = DUP_WINDOW,
                   threshold: float = DUP_THRESHOLD) -> GateResult:
    """與已收策略比對；重合率 > threshold 判定重複，後到者退回。"""
    worst_id, worst = None, 0.0
    for other in existing or []:
        if getattr(other, "id", None) == getattr(strategy, "id", None):
            continue
        r = overlap_rate(strategy, other, draws, window)
        if r > worst:
            worst_id, worst = getattr(other, "id", "?"), r
    if worst > threshold:
        return GateResult("重複性", False,
                          f"與已收策略 {worst_id} 近 {window} 期重合率 {worst:.3f} > {threshold}")
    detail = (f"最高重合率 {worst:.3f}（與 {worst_id}）" if worst_id else "無既有策略可比對")
    return GateResult("重複性", True, detail)


def validate_strategy(strategy, game, draws: list[Draw], existing=None, rebuild=None,
                      time_limit: float = TIME_LIMIT_SEC, dup_window: int = DUP_WINDOW,
                      dup_threshold: float = DUP_THRESHOLD) -> ValidationReport:
    """跑完四關，回傳可直接貼進 PR 的報告。"""
    rep = ValidationReport(strategy_id=getattr(strategy, "id", "?"))
    rep.gates.append(gate_determinism(strategy, rebuild, draws))
    rep.gates.append(gate_lookahead(strategy, game, draws))
    rep.gates.append(gate_runtime(strategy, draws, time_limit))
    rep.gates.append(gate_duplicate(strategy, existing, draws, dup_window, dup_threshold))
    return rep


def validate_manifest(manifest, game, draws: list[Draw], existing=None, **kw) -> ValidationReport:
    """由 manifest 建策略後跑四關（PR 自動回饋入口）。"""
    strategy = manifest.build_strategy(game)
    return validate_strategy(strategy, game, draws, existing=existing,
                             rebuild=lambda: manifest.build_strategy(game), **kw)
