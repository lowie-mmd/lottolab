// engine.js 與 Python 共用測試向量的全等檢查 + 加碼比對（規格 §4.2③/§7.3）。
// 用法：node tests/js/engine_check.mjs   → 全過印 "OK"，否則 throw。
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { scoreTicket, scorePeriod, scorePromo } from "../../docs/engine.js";

const here = dirname(fileURLToPath(import.meta.url));
const V = JSON.parse(readFileSync(join(here, "../vectors/scoring_vectors.json"), "utf-8"));

let n = 0;
function eq(a, b, msg) {
  if (JSON.stringify(a) !== JSON.stringify(b)) throw new Error(`FAIL ${msg}: ${JSON.stringify(a)} != ${JSON.stringify(b)}`);
  n++;
}

// 計分向量
const draw = V.draw;
for (const c of V.cases) {
  eq(scoreTicket(c.ticket, draw.numbers, draw.special), c.tier, `tier ${c.label}`);
  const r = scorePeriod([c.ticket], draw, V.theoretical_prizes);
  eq(r.payout_theoretical, c.payout_theoretical, `theo ${c.label}`);
  eq(r.payout_actual, c.payout_actual, `actual ${c.label}`);
}

// 加碼比對（sets）
const promoSets = { format: "sets", data: { sets: [[1,2,3,4,5,6],[7,8,9,10,11,12]], prize: 1000000 } };
eq(scorePromo([1,2,3,4,5,6], promoSets).win, 1000000, "sets exact match");
eq(scorePromo([1,2,3,4,5,7], promoSets).win, 0, "sets no match");

// 加碼比對（pool）
const promoPool = { format: "pool", data: { pool: [1,2,3,4,5,6,7,8,9], bonus: 10, prizes: { big: 1000000, small: 100000 } } };
eq(scorePromo([1,2,3,4,5,6], promoPool).win, 1000000, "pool big (6 in pool)");
eq(scorePromo([1,2,3,4,5,10], promoPool).win, 100000, "pool small (5 in pool + bonus)");
eq(scorePromo([1,2,3,4,5,20], promoPool).win, 0, "pool none (5 in pool, no bonus)");

console.log(`OK ${n} checks`);
