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
