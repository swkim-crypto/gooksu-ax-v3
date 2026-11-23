/* ============================================================
 * i18n.js — 한/EN 토글 (의존성 없음)
 *  UI 문구 : window.I18N_DICT (i18n_dict.js) — 키 기반, t('key', {n:3})
 *  데이터값 : /static/i18n/en.json (백엔드 i18n_en.py와 같은 사전·같은 규칙) — term('유량조정조 펌프')
 *
 * HTML:  <span data-i18n="key">원문</span>  <b data-i18n-html="key">..</b>
 *        <input data-i18n-ph="key" placeholder="..">  <button data-i18n-title="key" title="..">
 * JS:    await I18N.ready;  t(key); term(label);  document.addEventListener('langchange', ...)
 * 서버:  fetch body에 lang: I18N.lang
 * ============================================================ */
(function () {
  const KEY = "ax_lang";
  const DICT = window.I18N_DICT || { ko: {}, en: {} };
  const TERMS_URL = window.I18N_TERMS_URL || "/static/i18n/en.json";
  let lang = "ko";
  try {
    const q = new URLSearchParams(location.search).get("lang");
    lang = q || localStorage.getItem(KEY) || "ko";
  } catch (_) {}
  if (lang !== "en") lang = "ko";

  /* ---------- UI 문구 ---------- */
  function t(key, vars) {
    let s = (DICT[lang] && DICT[lang][key]) ?? (DICT.ko && DICT.ko[key]) ?? key;
    if (vars) for (const k in vars) s = s.split("{" + k + "}").join(vars[k]);
    return s;
  }

  /* ---------- 데이터 값 (백엔드 L()과 동일 규칙) ---------- */
  let LABELS = {}, NOSPACE = {}, TERMS = [];
  const HANGUL = /[가-힣]/;
  const ready = fetch(TERMS_URL).then(r => r.ok ? r.json() : {}).catch(() => ({})).then(d => {
    LABELS = d.labels || {};
    for (const k in LABELS) NOSPACE[k.replace(/\s+/g, "")] = LABELS[k];
    TERMS = Object.entries(d.terms || {}).sort((a, b) => b[0].length - a[0].length);
  });
  function termEn(s) {
    if (s == null) return s;
    s = String(s);
    if (s in LABELS) return LABELS[s];
    if (!HANGUL.test(s)) return s;
    const ns = s.replace(/\s+/g, "");
    if (ns in NOSPACE) return NOSPACE[ns];
    let out = s;
    for (const [k, v] of TERMS) if (out.includes(k)) out = out.split(k).join(` ${v} `);
    return out.replace(/\s+/g, " ").replace(/\(\s+/g, "(").replace(/\s+([),])/g, "$1").trim();
  }
  const term = s => (lang === "en" ? termEn(s) : s);

  /* ---------- DOM 적용 ---------- */
  function apply(root) {
    root = root || document;
    root.querySelectorAll("[data-i18n]").forEach(el => {
      if (el.dataset.i18nKo == null) el.dataset.i18nKo = el.textContent;
      const v = lang === "ko" ? el.dataset.i18nKo : DICT.en[el.dataset.i18n];
      if (v != null) el.textContent = v;
    });
    root.querySelectorAll("[data-i18n-html]").forEach(el => {
      if (el.dataset.i18nKoHtml == null) el.dataset.i18nKoHtml = el.innerHTML;
      const v = lang === "ko" ? el.dataset.i18nKoHtml : DICT.en[el.dataset.i18nHtml];
      if (v != null) el.innerHTML = v;
    });
    for (const [attr, sel, store] of [["placeholder", "i18nPh", "koPh"], ["title", "i18nTitle", "koTitle"]]) {
      root.querySelectorAll(`[data-${sel === "i18nPh" ? "i18n-ph" : "i18n-title"}]`).forEach(el => {
        if (el.dataset[store] == null) el.dataset[store] = el.getAttribute(attr) || "";
        const v = lang === "ko" ? el.dataset[store] : DICT.en[el.dataset[sel]];
        if (v != null) el.setAttribute(attr, v);
      });
    }
    document.documentElement.lang = lang;
    document.querySelectorAll(".ax-lang-toggle button").forEach(b =>
      b.classList.toggle("on", b.dataset.lang === lang));
  }

  function set(l, fromStorage) {
    l = l === "en" ? "en" : "ko";
    if (l === lang) return;
    lang = l;
    if (!fromStorage) try { localStorage.setItem(KEY, lang); } catch (_) {}
    apply();
    document.dispatchEvent(new CustomEvent("langchange", { detail: { lang } }));
  }
  // 팝아웃(detail.html) 등 다른 창과 언어 동기화
  window.addEventListener("storage", e => { if (e.key === KEY && e.newValue) set(e.newValue, true); });

  function mountToggle(host) {
    const wrap = document.createElement("div");
    wrap.className = "ax-lang-toggle";
    wrap.innerHTML = '<button type="button" data-lang="ko">한</button><button type="button" data-lang="en">EN</button>';
    wrap.addEventListener("click", e => { const b = e.target.closest("button"); if (b) set(b.dataset.lang); });
    (host || document.body).appendChild(wrap);
    if (!host) wrap.classList.add("floating");
    apply(wrap);
  }

  const css = document.createElement("style");
  css.textContent = `
  .ax-lang-toggle{display:inline-flex;border:1px solid #3a4a5a;border-radius:999px;overflow:hidden;font:600 12px/1 system-ui,sans-serif;background:#16202b;vertical-align:middle}
  .ax-lang-toggle.floating{position:fixed;top:10px;right:12px;z-index:99999}
  .ax-lang-toggle button{all:unset;cursor:pointer;padding:6px 11px;color:#8fa3b5}
  .ax-lang-toggle button.on{background:#2b6cb0;color:#fff}`;
  document.head.appendChild(css);

  window.I18N = { get lang() { return lang; }, t, term, set, apply, mountToggle, ready };
  window.t = t; window.term = term;

  const boot = () => {
    const host = document.getElementById("lang-toggle");
    if (host) mountToggle(host);
    apply();
  };
  document.readyState === "loading" ? document.addEventListener("DOMContentLoaded", boot) : boot();
})();
