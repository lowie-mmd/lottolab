# Lotto Lab — 大樂透隨機性驗證實驗裝置

> 這不是報明牌系統，而是一個「證明（或推翻）隨機性」的實驗裝置。
> 預設假說 H0：所有策略的長期每元投報率，統計上無法與純隨機對照組區分。

規格：[`lotto-lab-spec-v1.2.md`](lotto-lab-spec-v1.2.md)（凍結）。實作裁決記錄：[`DECISIONS.md`](DECISIONS.md)。

## 模組進度

| 模組 | 內容 | 狀態 |
|---|---|---|
| M1 資料層 | 台彩 JSON API 爬取、雙源比對、schema、data_quality | 建置中 |
| M2 回測引擎 | Game 抽象、walk-forward、前視保護、雙軌 ROI | 建置中 |
| M3 策略庫 | A–F 組策略（A 組先行） | 建置中 |
| M4 統計模組 | permutation test、卡方審計、FDR | 待建 |
| M5 私人加密層 | WebCrypto、engine.js、add_bet.py | 待建 |
| M6 展示層 | 公開 dashboard | 待建 |
| M7 自動化 | GitHub Actions（每日冪等） | 待建 |

## 開發環境

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest                      # Python 測試（M1/M2/M3/M4）

npm install                 # M5 JS 引擎測試依賴
npm test                    # vitest（engine.js ↔ Python 共用測試向量）
```

## 資料來源

台彩官方 JSON API（詳見 DECISIONS.md）：涵蓋 2007-01 起約 2,000 期。

## 隱私

私人投注號碼永不以明文進入 repo（設計鐵律 §7.2）；`data/private/bets.enc` 為 AES-256-GCM 密文，可安心公開存放。
