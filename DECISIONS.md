# DECISIONS.md — Lotto Lab 實作期間細節裁決記錄

> 規格 §0：小於模組邊界的實作細節由 Opus 裁決並記錄於此；涉及統計方法或資料語意的變更一律回報洛伊，不得自行變更。
> 每筆記錄格式：日期 / 模組 / 決策 / 理由 / 是否需回報洛伊。

---

## 2026-07-18 · M1 · 台彩資料來源確定為 JSON API（非 HTML 爬蟲）

**決策**：主源改用台彩官方 JSON API，不做 HTML 爬蟲。
- 端點：`GET https://api.taiwanlottery.com/TLCAPIWeB/Lottery/Lotto649Result?month=YYYY-MM&pageNum=1&pageSize=50`
- 必要 header：`Origin: https://www.taiwanlottery.com`、`Referer: https://www.taiwanlottery.com/`、`User-Agent`、`Accept: application/json`（缺 Origin/Referer → 403）
- 回傳 `content.lotto649Res[]`，每期含 `period`(int)、`lotteryDate`(ISO)、`drawNumberSize`（前 6 碼升冪 + 第 7 為特別號）、`drawNumberAppear`（開出順序 + 特別號）、`sellAmount`(=sales_amount)、`totalAmount`、八個獎項 `{jackpot,second,third,fourth,fifth,sixth,seventh,normal}Assign`（各含 `winnerCount`/`perPrize`）

**理由**：規格 §9① 要求先驗證可爬性；發現官方有結構化 JSON API，比 HTML 爬穩健得多（無版面漂移風險）。屬「模組邊界內實作細節」，Opus 裁決。

**需回報洛伊**：否（實作細節）。

---

## 2026-07-18 · M1 · 歷史資料範圍：2007-01 起（非 2004）

**決策**：主 API 歷史涵蓋 **2007-01（period 96000001）→ 至今**，約 2,000 期。2004–2006 不在此端點。

**理由**：台灣彩券 2007-01 接手發行，期別編號自 96000001 重啟；2004–2006 為前手業者（北銀）時代、獨立編號，不在台彩 API。規格 §5.2 估「全歷史 ~2,300 期」含前手時代；實得 ~2,000 期，對硬體隨機性卡方審計（每號期望 ~250+ 次）檢定力仍充足。

**需回報洛伊**：FYI（資料可得性事實，非統計方法變更）。若日後要補 2004–2006，需接備援第三方源，另案處理。

---

## 2026-07-18 · M1 · 欄位對應（API → draws.json schema §2.1）

- `numbers` = `drawNumberSize[0:6]`（已升冪）；`special` = `drawNumberSize[6]`
- `sales_amount` = `sellAmount`
- `prizes.tN.winners` / `.amount` 對應：t1=jackpotAssign、t2=secondAssign、t3=thirdAssign、t4=fourthAssign、t5=fifthAssign、t6=sixthAssign、t7=seventhAssign、t8=normalAssign；`winners`=`winnerCount`，`amount`=`perPrize`
- `period` 轉為字串保存（schema 範例為字串 "113000001"）
- `data_quality`：API 期數皆有完整 prizes+sales → 標 `full`；若某欄缺漏則降級（partial/numbers_only）
- `promo`：此端點不含節慶加碼（百萬大紅包為獨立活動）→ 先一律存 `null`，加碼來源留待另案（核心引擎 M2–M4 不讀 promo，非核心阻斷項）

**需回報洛伊**：否（實作細節）。

---

## 2026-07-18 · M4 · permutation test 的 null 建構方式

**決策**：permutation test 採 Monte Carlo「同結構隨機重抽」——固定前瞻段開獎序列，
將策略每期下注替換為「同下注結構」的隨機注（single / wheel7 / wheel8），重抽 n_perm 次
建立理論軌 ROI 虛無分布；p = (1 + #{null ≥ 觀測}) / (n_perm + 1)。null 僅依 bet_type
與開獎序列，與策略內容無關，故依 bet_type 快取共用。

**理由**：此設計保留各策略的下注量結構（包牌 E 組每期 28 注 vs 單注），使 null 與觀測
在成本結構上可比；直接檢定「策略號碼選擇是否帶來超越同量隨機下注的每元報酬」，對應
規格 §5.1 主指標（理論軌 ROI）。屬統計方法的實作具體化，方法本身（permutation + FDR +
對照組冠軍）由規格凍結，未變更。

**需回報洛伊**：FYI（實作具體化；若洛伊認為 null 應改採 A 組經驗分布而非 MC 重抽，
屬統計方法變更，需另行裁決）。

---

## 2026-07-18 · M4 · 全歷史硬體審計初步結果（觀察，非結論）

單號卡方 p=0.935、配對共現 p=0.989 → 與均勻隨機高度一致。特別號卡方 p=0.044（多重檢定中
單一項的邊際值，不構成警訊；且規格 §5.2 已註明球組輪換使混池檢定僅偵測長期系統性偏差）。
符合「結果甲（預期）」。此為全歷史觀察，正式結論以前瞻段期滿報告為準。

**需回報洛伊**：FYI。

---

## 2026-07-18 · M5 · 實際軌對「假設性中獎」的邊界語意

**現象**：實際軌 payout 用當期公告單注獎額（perPrize）。若某注命中某獎項，而該期公告
該獎項 winnerCount=0（perPrize=0），實際軌會記 0（例：私人層測試以某期實際獎號當投注、
命中 t1，但該期無真實頭獎得主 → 實際軌 0）。理論軌（推論主指標）以凍結中位數計，不受影響。

**決策**：維持現狀——實際軌定義即「公告單注獎額」，屬展示用途（§4.2「實際軌為展示用」）；
理論軌才是推論主指標，正確反映期望。假設性中獎落在無得主期屬極罕見邊界，不特別加工。

**需回報洛伊**：FYI（展示軌邊界；若洛伊希望實際軌對頭獎改用「當期頭獎總獎金池」而非
公告單注額，屬資料語意變更，需另行裁決）。
