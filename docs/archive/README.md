# 學術頁不可變快照 archive/

依 roadmap R2 §2.3：學術報告頁在下列時點產生**不可變快照**，存為
`academic-YYYYMMDD-periodNNN.html`（自封裝、含當時全部數字），生成後永不修改：

- 註冊時（追溯建立）
- 每滿 52 期
- 主要終點（前瞻段期滿）
- 期滿

快照為「凍結完整性」與可引用性的載體：任何人可核對某時點的報告內容與 commit 對應。
動態版 `docs/academic.html` 隨 results 更新自動重生成；快照則凝固該時點的證據狀態。

> 產生方式（待前瞻段開跑後啟用）：以當時的 `docs/academic.html` ＋ `academic.json`
> 內聯自封裝為單檔存入本目錄。CI 可加 hash 檢查確保既有快照檔不被更動（後續維運）。
