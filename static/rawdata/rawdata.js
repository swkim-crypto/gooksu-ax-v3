/* ============================================================
 * rawdata.js — 원시데이터 설명 모달 (의존성 없음, i18n.js 있으면 한/영 연동)
 * 필요 파일 (같은 폴더): manifest.json, cases.json, img/*.png
 * 사용: <script src="/static/rawdata/rawdata.js" defer></script>
 *       버튼 위치 지정 → <span id="rawdata-btn-host"></span>  (없으면 좌하단 고정)
 *       코드에서 열기  → RawData.open('cases')      URL로 열기 → ?rawdata=1
 * ============================================================ */
(function () {
  const BASE = (document.currentScript && document.currentScript.src.replace(/[^/]*$/, "")) || "/static/rawdata/";
  const T = (k, v) => (window.t ? window.t(k, v) : k);
  const L = () => (window.I18N ? window.I18N.lang : "ko");
  const pick = (o, f) => o[f + "_" + L()] ?? o[f + "_ko"] ?? "";
  const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  // 윈도우 속성창과 같은 표기: 1024 단위, 버림 (GB 이상 소수 둘째, 그 외 첫째)
  const human = n => { const u = ["B", "KB", "MB", "GB", "TB"]; let i = 0; while (n >= 1024 && i < 4) { n /= 1024; i++; }
    if (!i) return n + "B"; const d = i >= 3 ? 100 : 10; return (Math.floor(n * d) / d).toFixed(i >= 3 ? 2 : 1) + u[i]; };

  const CAT = {
    cad: { c: "#f0a53a", x: ["dwg", "dxf", "dwf", "bak", "gbk", "dwl", "dwl2", "ctb", "shx"] },
    pdf: { c: "#ff7a6b", x: ["pdf"] },
    xls: { c: "#6fd39a", x: ["xls", "xlsx", "xlsm", "csv", "hwp", "hwpx", "doc", "docx"] },
    gis: { c: "#5fb2ff", x: ["shp", "dbf", "prj", "cpg", "sbn", "sbx", "qpj", "geojson", "kml", "kmz", "tif", "tfw"] },
    img: { c: "#c792ea", x: ["png", "jpg", "jpeg", "bmp", "gif"] },
    etc: { c: "#7d8899", x: [] }
  };
  const catOf = ext => { for (const k in CAT) if (CAT[k].x.includes(ext)) return k; return "etc"; };
  const EXT_LABEL = ext => (catOf(ext) === "gis" && ext === "shx" ? "gis" : catOf(ext));

  let M = null, C = null, NAMES = {}, flags = [], el = null, tab = "folder", openSet = new Set(), query = "";

  async function load() {
    if (M && C) return;
    const j = async f => { try { const r = await fetch(BASE + f, { cache: "no-cache" }); return r.ok ? r.json() : null; } catch (_) { return null; } };
    let N;
    [M, C, N] = await Promise.all([j("manifest.json"), j("cases.json"), j("names_en.json")]);
    NAMES = N || {};
    C = C || { cases: [], effort: { stages: [] } };
    flags = (C.flags || []).map(f => ({ re: new RegExp(f.match, "i"), id: f.case }));
    if (M && M.tree) openSet.add(pathKey([M.tree.name]));
  }
  const pathKey = a => a.join("/");

  /* ---------- 골격 ---------- */
  function build() {
    el = document.createElement("div");
    el.className = "rd-modal"; el.hidden = true;
    el.innerHTML = `
      <div class="rd-box" role="dialog" aria-modal="true">
        <div class="rd-head"><div><h2 data-k="rd.title"></h2><p data-k="rd.sub"></p></div><div class="rd-sp"></div>
          <span class="rd-langslot"></span><button class="rd-x" data-k-title="rd.close">×</button></div>
        <div class="rd-tabs">
          <button data-tab="folder" data-k="rd.tab.folder"></button>
          <button data-tab="cases" data-k="rd.tab.cases"></button>
          <button data-tab="effort" data-k="rd.tab.effort"></button></div>
        <div class="rd-body">
          <section class="rd-pane" data-pane="folder"></section>
          <section class="rd-pane" data-pane="cases"></section>
          <section class="rd-pane" data-pane="effort"></section></div></div>`;
    document.body.appendChild(el);
    el.addEventListener("click", e => {
      if (e.target === el || e.target.closest(".rd-x")) return close();
      const tb = e.target.closest("[data-tab]"); if (tb) return show(tb.dataset.tab);
      const d = e.target.closest(".rd-row.dir"); if (d) { const k = d.dataset.path; openSet.has(k) ? openSet.delete(k) : openSet.add(k); return renderTree(); }
      const fl = e.target.closest("[data-goto]"); if (fl) { show("cases"); const c = el.querySelector(`#rd-case-${fl.dataset.goto}`); if (c) { c.scrollIntoView({ behavior: "smooth", block: "center" }); c.animate([{ outline: "2px solid #f0a53a" }, { outline: "2px solid transparent" }], 1600); } return; }
      const fg = e.target.closest("figure[data-src]"); if (fg) return zoom(fg.dataset.src);
      if (e.target.closest("[data-act=expand]")) { walkDirs(M.tree, [], k => openSet.add(k)); return renderTree(); }
      if (e.target.closest("[data-act=collapse]")) { openSet = new Set([pathKey([M.tree.name])]); return renderTree(); }
    });
    document.addEventListener("keydown", e => { if (e.key === "Escape" && !el.hidden) { const z = document.querySelector(".rd-zoom"); z ? z.remove() : close(); } });
    document.addEventListener("langchange", () => { if (!el.hidden) renderAll(); });
  }

  function labels(root) {
    root.querySelectorAll("[data-k]").forEach(n => n.textContent = T(n.dataset.k));
    root.querySelectorAll("[data-k-title]").forEach(n => n.title = T(n.dataset.kTitle));
  }

  /* ---------- ① 폴더 ---------- */
  function walkDirs(n, trail, fn) { if (n.type !== "dir") return; const p = [...trail, n.name]; fn(pathKey(p)); (n.children || []).forEach(c => walkDirs(c, p, fn)); }

  function renderFolder() {
    const P = el.querySelector('[data-pane=folder]');
    if (!M) { P.innerHTML = `<div class="rd-warn">manifest.json — not found</div>`; return; }
    const cats = {}; (M.by_ext || []).forEach(e => { const k = catOf(e.ext); cats[k] = (cats[k] || 0) + e.size; });
    const tot = Object.values(cats).reduce((a, b) => a + b, 0) || 1;
    const order = Object.keys(CAT).filter(k => cats[k]);
    P.innerHTML = `
      ${M.sample ? `<div class="rd-warn">${esc(T("rd.sample"))}</div>` : ""}
      <div class="rd-stats">
        <div class="rd-stat"><b>${esc(M.total_size_h || human(M.total_size))}</b><span>${esc(T("rd.total"))}</span></div>
        <div class="rd-stat"><b>${(M.total_files || 0).toLocaleString()}</b><span>${esc(T("rd.files"))}</span></div>
        <div class="rd-stat"><b>${(M.total_dirs || 0).toLocaleString()}</b><span>${esc(T("rd.folders"))}</span></div>
        <div class="rd-stat"><span>${esc(T("rd.byext"))}</span>
          <div class="rd-extbar">${order.map(k => `<div style="width:${cats[k] / tot * 100}%;background:${CAT[k].c}" title="${T("rd.ext." + k)} ${human(cats[k])}"></div>`).join("")}</div>
          <div class="rd-extlegend">${order.map(k => `<span><i style="background:${CAT[k].c}"></i>${esc(T("rd.ext." + k))} ${human(cats[k])}</span>`).join("")}</div></div>
      </div>
      <div class="rd-tools"><input type="search" placeholder="${esc(T("rd.search"))}" value="${esc(query)}">
        <button data-act="expand">+ all</button><button data-act="collapse">− all</button></div>
      <div class="rd-tree"></div>`;
    const inp = P.querySelector("input");
    inp.addEventListener("input", () => { query = inp.value.trim(); renderTree(); });
    renderTree();
  }

  // 영문 모드: names_en.json 으로 표시 (원문은 마우스 올리면 보임), 검색은 원문·영문 모두
  const nm = n => (L() === "en" && NAMES[n.name]) || n.name;
  const hit = (n, q) => n.name.toLowerCase().includes(q) || (NAMES[n.name] || "").toLowerCase().includes(q);
  const ttl = n => (L() === "en" && NAMES[n.name] ? ` title="${esc(n.name)}"` : "");
  function matchDeep(n, q) { if (hit(n, q)) return true; return (n.children || []).some(c => matchDeep(c, q)); }

  function renderTree() {
    const box = el.querySelector(".rd-tree"); if (!box) return;
    const q = query.toLowerCase(), out = [];
    (function rec(n, depth, trail) {
      if (q && !matchDeep(n, q)) return;
      const pad = `padding-left:${8 + depth * 18}px`;
      if (n.type === "dir") {
        const p = [...trail, n.name], k = pathKey(p), op = q ? true : openSet.has(k);
        out.push(`<div class="rd-row dir ${op ? "open" : ""} ${q && hit(n, q) ? "rd-hit" : ""}" data-path="${esc(k)}" style="${pad}">
          <span class="nm"${ttl(n)}>${esc(nm(n))} <span style="color:#6b7584">(${n.files.toLocaleString()})</span></span><span class="sz">${human(n.size)}</span><span class="dt"></span></div>`);
        if (op) { (n.children || []).forEach(c => rec(c, depth + 1, p));
          if (n.omitted && !q) out.push(`<div class="rd-row more" style="padding-left:${26 + depth * 18}px"><span class="nm">… ${esc(T("rd.more", { n: n.omitted.toLocaleString() }))}</span></div>`); }
      } else {
        const cat = catOf(n.ext), f = flags.find(f => f.re.test(n.name));
        const cs = f && C.cases.find(c => c.id === f.id);
        out.push(`<div class="rd-row ${q && hit(n, q) ? "rd-hit" : ""}" style="${pad}">
          <span class="nm"${ttl(n)}><span class="chip" style="background:${CAT[cat].c}">${esc(n.ext)}</span>${esc(nm(n))}${cs ? `<span class="flag" data-goto="${cs.id}" style="cursor:pointer">⚠ ${esc(pick(cs, "group"))}</span>` : ""}</span>
          <span class="sz">${human(n.size)}</span><span class="dt">${esc(n.mtime || "")}</span></div>`);
      }
    })(M.tree, 0, []);
    box.innerHTML = out.join("") || `<div class="rd-row more"><span class="nm">—</span></div>`;
  }

  /* ---------- ② 사례 ---------- */
  function fig(src, cap) {
    if (!src) return "";
    const u = BASE + src;
    return `<figure data-src="${esc(u)}"><img src="${esc(u)}" alt="" loading="lazy"
      onerror="this.parentNode.classList.add('ph');this.parentNode.removeAttribute('data-src');this.parentNode.innerHTML='<span>${esc(T("rd.noimg"))}<br><small>${esc(src)}</small></span>'">
      <figcaption>${esc(cap)}</figcaption></figure>`;
  }
  function renderCases() {
    const P = el.querySelector('[data-pane=cases]');
    P.innerHTML = `<div class="rd-cases">${C.cases.map(c => {
      const imgs = [fig(c.img, T("rd.before")), fig(c.img_after, T("rd.after"))].filter(Boolean);
      return `<article class="rd-case" id="rd-case-${esc(c.id)}">
        ${imgs.length ? `<div class="imgs ${imgs.length === 1 ? "one" : ""}">${imgs.join("")}</div>` : ""}
        <div class="txt"><div class="grp">${esc(pick(c, "group"))}</div><h3>${esc(pick(c, "title"))}</h3>
          <dl><dt>${esc(T("rd.problem"))}</dt><dd>${esc(pick(c, "problem"))}</dd>
              <dt class="fix">${esc(T("rd.fix"))}</dt><dd>${esc(pick(c, "fix"))}</dd></dl></div></article>`;
    }).join("")}</div>`;
  }

  /* ---------- ③ 시간 ---------- */
  function renderEffort() {
    const P = el.querySelector('[data-pane=effort]'), E = C.effort || { stages: [] };
    const col = ["#f0a53a", "#5fb2ff", "#6fd39a", "#c792ea"];
    P.innerHTML = `<div class="rd-effort">
      <h3>${esc(T("rd.effort.head"))}</h3>
      <div class="rd-ebar">${E.stages.map((s, i) => `<div style="width:${s.pct}%;background:${col[i % 4]}"><b>${s.pct}%</b><span>${esc(pick(s, ""))}</span></div>`).join("")}</div>
      <div class="rd-enote">${esc(pick(E, "note"))}</div>
      <div class="rd-steps">${C.cases.map((c, i) => `<div data-goto="${esc(c.id)}"><b>${i + 1}. ${esc(pick(c, "group"))}</b>${esc(pick(c, "title"))}</div>`).join("")}</div>
      <div class="rd-msg">${esc(T("rd.effort.msg"))}</div></div>`;
    // pick(s,"") → s["_ko"] 형태가 아니라 s.ko/s.en 사용
    P.querySelectorAll(".rd-ebar span").forEach((sp, i) => sp.textContent = E.stages[i][L()] || E.stages[i].ko);
  }

  /* ---------- 공통 ---------- */
  function renderAll() {
    labels(el);
    el.querySelectorAll("[data-tab]").forEach(b => b.classList.toggle("on", b.dataset.tab === tab));
    el.querySelectorAll("[data-pane]").forEach(p => p.hidden = p.dataset.pane !== tab);
    renderFolder(); renderCases(); renderEffort();
  }
  function show(t) { tab = t; el.querySelectorAll("[data-tab]").forEach(b => b.classList.toggle("on", b.dataset.tab === tab)); el.querySelectorAll("[data-pane]").forEach(p => p.hidden = p.dataset.pane !== tab); el.querySelector(".rd-body").scrollTop = 0; }
  function zoom(src) { const z = document.createElement("div"); z.className = "rd-zoom"; z.innerHTML = `<img src="${esc(src)}" alt="">`; z.onclick = () => z.remove(); document.body.appendChild(z); }

  async function open(t) {
    if (!el) build();
    await load();
    if (t) tab = t;
    el.hidden = false; renderAll(); show(tab);
    const slot = el.querySelector(".rd-langslot");
    if (window.I18N && slot && !slot.childElementCount) window.I18N.mountToggle(slot);
  }
  function close() { if (el) el.hidden = true; }

  let launch = null;
  function relabelLaunch() { if (launch) launch.querySelector("span").textContent = T("rd.button"); }
  function mountLaunch() {
    launch = document.createElement("button");
    launch.type = "button"; launch.className = "rd-launch";
    launch.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/></svg><span></span>`;
    launch.onclick = () => open();
    const host = document.getElementById("rawdata-btn-host");
    if (host) { launch.classList.add("inline"); host.appendChild(launch); } else document.body.appendChild(launch);
    relabelLaunch();
  }

  // CSS 자동 로드
  if (!document.querySelector('link[href*="rawdata.css"]')) {
    const l = document.createElement("link"); l.rel = "stylesheet"; l.href = BASE + "rawdata.css"; document.head.appendChild(l);
  }
  const boot = () => {
    mountLaunch();
    document.addEventListener("langchange", relabelLaunch);
    if (window.I18N && I18N.ready) I18N.ready.then(relabelLaunch);
    if (/[?&]rawdata=1/.test(location.search)) open();
  };
  document.readyState === "loading" ? document.addEventListener("DOMContentLoaded", boot) : boot();

  window.RawData = { open, close };
})();
