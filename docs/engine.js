// engine.js — 計分引擎 JS 移植（規格 §1、§7.3）。
// 與 Python 引擎共用測試向量（tests/vectors/scoring_vectors.json）；輸出須全等。
// 私人層專用：含加碼獎號比對（公開實驗不做，見 §4.2；私人層必做，見 §7.3）。

// 一注 6 碼對中一般號個數 + 是否對中特別號 → 獎項（規格 §2.2）。
export function scoreTicket(ticket, drawNumbers, special) {
  const drawn = new Set(drawNumbers);
  const t = new Set(ticket);
  let match = 0;
  for (const n of t) if (drawn.has(n)) match++;
  const specialHit = special != null && t.has(special);
  if (match === 6) return "t1";
  if (match === 5) return specialHit ? "t2" : "t3";
  if (match === 4) return specialHit ? "t4" : "t5";
  if (match === 3) return specialHit ? "t6" : "t8";
  if (match === 2 && specialHit) return "t7";
  return null;
}

// 理論軌獎額表（§2.2）：t5–t8 固定；t1–t4 凍結中位數。
export function theoreticalAmount(prizes, tier) {
  const fixed = prizes.fixed || {};
  const frozen = prizes.frozen_median || {};
  if (tier in fixed) return fixed[tier];
  if (tier in frozen && frozen[tier] != null) return frozen[tier];
  return 0;
}

// 對單期一組注計分（雙軌，加碼不含於此；加碼另由 scorePromo 處理）。
export function scorePeriod(tickets, draw, theoreticalPrizes) {
  const tierHits = {};
  let payoutTheoretical = 0;
  let payoutActual = 0;
  const actualAvailable = draw.data_quality === "full";
  for (const ticket of tickets) {
    const tier = scoreTicket(ticket, draw.numbers, draw.special);
    if (!tier) continue;
    tierHits[tier] = (tierHits[tier] || 0) + 1;
    payoutTheoretical += theoreticalAmount(theoreticalPrizes, tier);
    if (actualAvailable) {
      const node = (draw.prizes || {})[tier];
      payoutActual += (node && node.amount) || 0;
    }
  }
  return {
    payout_theoretical: payoutTheoretical,
    payout_actual: actualAvailable ? payoutActual : null,
    tier_hits: tierHits,
  };
}

// ---- 加碼獎號比對（私人層專用，規格 §7.3）----
// promo.format 分派：sets 逐組完全比對；pool 計算對中池內碼數 + 小紅包。
export function scorePromo(ticket, promo) {
  if (!promo || !promo.data) return { win: 0, detail: null };
  const t = new Set(ticket);
  if (promo.format === "sets") {
    const sets = promo.data.sets || [];
    const prize = promo.data.prize || 1000000;
    let wins = 0;
    const matchedSets = [];
    sets.forEach((s, i) => {
      // 完全對中：一注 6 碼與該組 6 碼完全相同
      if (s.length === ticket.length && s.every((n) => t.has(n))) {
        wins += 1;
        matchedSets.push(i);
      }
    });
    return { win: wins * prize, detail: { matchedSets, format: "sets" } };
  }
  if (promo.format === "pool") {
    const pool = new Set(promo.data.pool || []);
    const bonus = promo.data.bonus;
    const prizes = promo.data.prizes || { big: 1000000, small: 100000 };
    let inPool = 0;
    for (const n of t) if (pool.has(n)) inPool++;
    const hasBonus = bonus != null && t.has(bonus);
    // 對中池中任 6 碼 → 大紅包；對中任 5 碼 + 小紅包獎號 → 小紅包
    if (inPool >= 6) return { win: prizes.big, detail: { inPool, tier: "big", format: "pool" } };
    if (inPool >= 5 && hasBonus) return { win: prizes.small, detail: { inPool, tier: "small", format: "pool" } };
    return { win: 0, detail: { inPool, tier: null, format: "pool" } };
  }
  // unknown / 未來格式：不計分（附原始標記供人工檢視）
  return { win: 0, detail: { format: promo.format || "unknown" } };
}
