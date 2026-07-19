// glossary.js — R1 名詞索引：全站行內浮窗（dfn）＋ guide 完整詞表 ＋ KaTeX 公式。
// 單一真相來源 glossary.json；頁面不 hardcode 詞條文案（§1.4）。
// 桌機 hover、手機/鍵盤 focus 觸發小浮窗（一句白話＋完整說明→），Esc 關閉，380px 不出界。

const GLOSSARY_URL = "./glossary.json";
const KATEX_CSS = "https://cdnjs.cloudflare.com/ajax/libs/KaTeX/0.16.9/katex.min.css";
const KATEX_JS = "https://cdnjs.cloudflare.com/ajax/libs/KaTeX/0.16.9/katex.min.js";
const GROUP_LABEL = { stat: "統計核心", design: "實驗設計", lottery: "彩券應用" };

let TERMS = null;
let BYID = {};
let currentDfn = null;
let hideTimer = null;

function esc(s) {
  return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

function injectStyles() {
  if (document.getElementById("gloss-style")) return;
  const css = `
  dfn[data-term]{ font-style:normal; border-bottom:1px dashed currentColor; cursor:help; }
  dfn[data-term]:focus{ outline:2px solid var(--accent,#2a7ae2); outline-offset:2px; border-radius:2px; }
  #gloss-pop{ position:absolute; z-index:9999; display:none; max-width:300px;
    background:var(--bg,#fff); color:var(--fg,#222); border:1px solid var(--ctrl,#bbb);
    border-radius:10px; padding:10px 12px; box-shadow:0 6px 24px rgba(0,0,0,.18);
    font-size:.86rem; line-height:1.5; }
  @media (prefers-color-scheme: dark){ #gloss-pop{ background:#1c1e22; color:#e6e6e6; border-color:#556; } }
  #gloss-pop .gp-term{ font-weight:700; margin-bottom:3px; }
  #gloss-pop .gp-more{ display:inline-block; margin-top:6px; color:var(--accent,#2a7ae2); text-decoration:none; font-size:.82rem; }
  #glossary-list .gl-group{ margin-top:26px; padding-bottom:4px; border-bottom:1px solid #8884; }
  #glossary-list .gl-term{ padding:12px 0; border-bottom:1px solid #8882; }
  #glossary-list .gl-name{ font-size:1.05rem; font-weight:700; }
  #glossary-list .gl-alias{ font-size:.78rem; color:#8899; font-weight:400; margin-left:6px; }
  #glossary-list .gl-one{ margin-top:3px; }
  #glossary-list details{ margin-top:6px; }
  #glossary-list summary{ cursor:pointer; color:var(--accent,#2a7ae2); font-size:.88rem; }
  #glossary-list .gl-formula{ margin:8px 0; overflow-x:auto; }
  #glossary-list .gl-formula-raw{ font-family:ui-monospace,Menlo,monospace; font-size:.82rem; color:#8899; }
  #glossary-list .gl-meta{ margin-top:8px; font-size:.82rem; color:#8899; }
  #glossary-list .gl-meta a{ color:var(--accent,#2a7ae2); text-decoration:none; }
  `;
  const s = document.createElement("style");
  s.id = "gloss-style";
  s.textContent = css;
  document.head.appendChild(s);
}

async function loadGlossary() {
  const r = await fetch(GLOSSARY_URL, { cache: "no-store" });
  if (!r.ok) throw new Error("glossary.json");
  const data = await r.json();
  TERMS = data.terms;
  BYID = Object.fromEntries(TERMS.map((t) => [t.id, t]));
}

function ensurePopup() {
  let p = document.getElementById("gloss-pop");
  if (!p) {
    p = document.createElement("div");
    p.id = "gloss-pop";
    p.setAttribute("role", "tooltip");
    p.addEventListener("mouseenter", () => clearTimeout(hideTimer));
    p.addEventListener("mouseleave", scheduleHide);
    document.body.appendChild(p);
  }
  return p;
}

function showPopup(dfn) {
  const t = BYID[dfn.dataset.term];
  if (!t) return;
  clearTimeout(hideTimer);
  const pop = ensurePopup();
  pop.innerHTML =
    `<div class="gp-term">${esc(t.term)}</div>` +
    `<div class="gp-one">${esc(t.oneliner)}</div>` +
    `<a class="gp-more" href="guide.html#term-${t.id}">完整說明 →</a>`;
  pop.style.display = "block";
  const r = dfn.getBoundingClientRect();
  const pw = Math.min(300, window.innerWidth - 20);
  pop.style.maxWidth = pw + "px";
  let left = window.scrollX + r.left;
  left = Math.min(left, window.scrollX + window.innerWidth - pw - 10);
  left = Math.max(window.scrollX + 8, left);
  pop.style.left = left + "px";
  pop.style.top = window.scrollY + r.bottom + 6 + "px";
  currentDfn = dfn;
}

function scheduleHide() {
  clearTimeout(hideTimer);
  hideTimer = setTimeout(hidePopup, 180);
}
function hidePopup() {
  const p = document.getElementById("gloss-pop");
  if (p) p.style.display = "none";
  currentDfn = null;
}

function enhanceDfns() {
  document.querySelectorAll("dfn[data-term]").forEach((dfn) => {
    const t = BYID[dfn.dataset.term];
    if (!t) return; // 未知 id：不增強，正文照樣可讀
    dfn.setAttribute("tabindex", "0");
    dfn.setAttribute("role", "button");
    dfn.setAttribute("aria-label", `${t.term}：${t.oneliner}`);
    dfn.addEventListener("mouseenter", () => showPopup(dfn));
    dfn.addEventListener("mouseleave", scheduleHide);
    dfn.addEventListener("focus", () => showPopup(dfn));
    dfn.addEventListener("blur", scheduleHide);
    dfn.addEventListener("click", (e) => {
      e.preventDefault();
      if (currentDfn === dfn) hidePopup();
      else showPopup(dfn);
    });
  });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") hidePopup(); });
  document.addEventListener("click", (e) => {
    if (currentDfn && !e.target.closest("dfn[data-term]") && !e.target.closest("#gloss-pop")) hidePopup();
  });
}

function loadKatex() {
  return new Promise((res, rej) => {
    if (window.katex) return res();
    if (!document.getElementById("katex-css")) {
      const css = document.createElement("link");
      css.id = "katex-css"; css.rel = "stylesheet"; css.href = KATEX_CSS;
      document.head.appendChild(css);
    }
    const js = document.createElement("script");
    js.src = KATEX_JS;
    js.onload = () => res();
    js.onerror = () => rej(new Error("katex load failed"));
    document.head.appendChild(js);
  });
}

async function renderFormulas(scope) {
  const nodes = scope.querySelectorAll(".gl-formula[data-tex]");
  if (!nodes.length) return;
  try {
    await loadKatex();
    nodes.forEach((n) => {
      try { window.katex.render(n.dataset.tex, n, { throwOnError: false, displayMode: false }); }
      catch (e) { n.textContent = n.dataset.tex; n.classList.add("gl-formula-raw"); }
    });
  } catch (e) {
    // KaTeX 載入失敗 → fallback 純文字公式（§1.4 驗收③）
    nodes.forEach((n) => { n.textContent = n.dataset.tex; n.classList.add("gl-formula-raw"); });
  }
}

function renderGlossaryList(el) {
  let html = "";
  for (const [g, label] of Object.entries(GROUP_LABEL)) {
    html += `<h3 class="gl-group" id="gl-${g}">${label}</h3>`;
    for (const t of TERMS.filter((x) => x.group === g)) {
      const rel = t.related
        .map((r) => (BYID[r] ? `<a href="#term-${r}">${esc(BYID[r].term)}</a>` : esc(r)))
        .join("、");
      html +=
        `<div class="gl-term" id="term-${t.id}">` +
        `<div class="gl-name">${esc(t.term)}<span class="gl-alias">${esc(t.aliases.join("・"))}</span></div>` +
        `<div class="gl-one">${esc(t.oneliner)}</div>` +
        `<details><summary>詳細說明</summary>` +
        `<div>${esc(t.detail)}</div>` +
        (t.formula ? `<div class="gl-formula" data-tex="${esc(t.formula)}"></div>` : "") +
        `<div class="gl-meta">用在哪：${esc(t.usedIn.join("、"))}　相關：${rel}</div>` +
        `</details></div>`;
    }
  }
  el.innerHTML = html;
  renderFormulas(el);
}

(async function () {
  injectStyles();
  try { await loadGlossary(); }
  catch (e) { return; } // 載入失敗：正文照樣可讀，僅無浮窗
  enhanceDfns();
  const list = document.getElementById("glossary-list");
  if (list) renderGlossaryList(list);
  if (location.hash.startsWith("#term-")) {
    const el = document.getElementById(location.hash.slice(1));
    if (el) { const d = el.querySelector("details"); if (d) d.open = true; el.scrollIntoView(); }
  }
})();
