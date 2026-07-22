# Lotto Lab — 大樂透隨機性驗證實驗裝置

> 這不是報明牌系統，而是一台「證明（或推翻）隨機性」的實驗裝置。
> 預設假說 **H0：所有策略的長期每元投報率，統計上無法與純隨機對照組區分。**

🌐 **公開實驗**：https://lowie-mmd.github.io/lottolab/ ｜ 🎲 [試玩沙盒](https://lowie-mmd.github.io/lottolab/playground.html) ｜ 📖 [使用說明／名詞索引](https://lowie-mmd.github.io/lottolab/guide.html) ｜ 🎓 [技術報告](https://lowie-mmd.github.io/lottolab/academic.html) ｜ 🔒 [私人分析](https://lowie-mmd.github.io/lottolab/personal.html)

規格（凍結）：[`lotto-lab-spec-v1.2.md`](lotto-lab-spec-v1.2.md)　實作裁決記錄：[`DECISIONS.md`](DECISIONS.md)　開發覆盤：[`RETROSPECTIVE.md`](RETROSPECTIVE.md)

---

## 它在做什麼

同時跑 **68 個選號策略**（熱門/冷門/遺漏/包牌/養牌/馬可夫/反熱門…）＋ **50 個純亂數對照組**，
用相同規則對 **2007 年起約 2,150 期**真實開獎做 walk-forward 回測，檢定有沒有任何策略能
顯著贏過亂數。防自欺三件套：**對照組 × walk-forward 前視保護 × 預先註冊**。

**目前狀態**：`🔒 已預先註冊`。啟動期 `115000072`（2026-07-21），config 凍結 commit 時間戳
即為預先註冊時點；前瞻段約 200 期為正式實驗。歷史觀察段結果：硬體審計符合隨機、
**0/68 策略跳出運氣雲**（符合 H0）。

## 模組

| 模組 | 內容 | 狀態 |
|---|---|---|
| M1 資料層 | 台彩 JSON API、雙源比對、data_quality、北銀 2004–2006 延伸層 | ✅ |
| M2 回測引擎 | Game 抽象、walk-forward + 前視保護、雙軌 ROI | ✅ |
| M3 策略庫 | A–F 共 68 策略 | ✅ |
| M4 統計 | permutation test + FDR、卡方硬體審計、合成資料驗收 | ✅ |
| M5 私人加密層 | WebCrypto AES-256-GCM、engine.js、網頁編輯器、add_bet.py | ✅ |
| M6 展示層 | 公開 dashboard（白話化）＋策略卡＋試玩沙盒＋名詞索引＋技術報告（學術切片） | ✅ |
| M7 自動化 | GitHub Actions 每日冪等更新 | ✅ |

## 怎麼用（不用寫程式）

- **看實驗**：開 [公開實驗頁](https://lowie-mmd.github.io/lottolab/)，運氣雲一眼看有沒有策略衝出亂數雲。
- **追蹤自己的投注**：開 [私人分析頁](https://lowie-mmd.github.io/lottolab/personal.html) →
  輸入密語 → 網頁上新增號碼 → 下載 `bets.enc` → 上傳到 GitHub `data/private/`。
  號碼全程加密，任何人看原始碼都看不到。詳見 [使用說明](https://lowie-mmd.github.io/lottolab/guide.html)。

## 開發環境

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest                                  # 44 tests（含前視保護、合成資料統計驗收、密文檢查）

PYTHONPATH=src python -m scraper.build_draws --full     # 初始化全歷史
PYTHONPATH=src python -m scraper.build_pre2007          # 北銀延伸層（雙第三方對帳）
PYTHONPATH=src python -m engine.run_backtest --group A --group B --group C --group D --group E --group F
PYTHONPATH=src python -m stats.run_stats --audit        # 硬體審計（自動含延伸視圖）
PYTHONPATH=src python -m tools.build_site_data          # 產生 dashboard 資料
```

## 隱私與防火牆

- 私人投注號碼**永不以明文進 repo**；`data/private/bets.enc` 為 AES-256-GCM 密文（PBKDF2 600k），可公開存放。
- **真錢防火牆**：系統只做虛擬損益；實際投注僅供個人分析，不回饋任何策略評分（規格 §5.3）。
