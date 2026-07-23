/* 국수 하수처리 GIS+AI — 3패널 프론트
 * 지도: KAKAO_JS_KEY 있으면 카카오맵(지도/스카이뷰 전환), 없으면 Leaflet+OSM/위성
 * 점 객체는 클릭 가능한 오버레이로 렌더, 질의 결과는 지도 하이라이트 */

const STYLE = {
  pipes: f => ({
    color: { "자연유하추정": "#1f77b4", "압송추정": "#d62728" }[f.properties.kind] || "#888",
    weight: 2.2,
  }),
  manholes: { radius: 3, color: "#333", fillColor: "#ffb300", fillOpacity: 0.9, weight: 1 },
  pumpstations: { radius: 8, color: "#1b5e20", fillColor: "#4caf50", fillOpacity: 0.95, weight: 2 },
  equipment: { radius: 5, color: "#4a148c", fillColor: "#ab47bc", fillOpacity: 0.9, weight: 1 },
  facility: f => f.properties.geom === "polygon"
    ? { color: "#e65100", fillColor: "#ffcc80", fillOpacity: 0.45, weight: 1 }
    : f.properties.geom === "label"
    ? { radius: 4, color: "#37474f", fillColor: "#eceff1", fillOpacity: 0.95, weight: 1.5 }
    : { color: "#8d6e63", weight: 1 },
  plansheets: { color: "#00695c", fillColor: "#26a69a", fillOpacity: 0.10, weight: 1.5 },
};
const SWATCH = { pipes: "#1f77b4", manholes: "#ffb300", pumpstations: "#4caf50", facility: "#ffcc80", equipment: "#ab47bc", plansheets: "#26a69a" };
const DOT_PX = { manholes: 7, pumpstations: 14, equipment: 11 };  // 카카오 점 크기(px)

let map, cfg, kakaoMode = false;
const leafletLayers = {};
const kakaoObjects = {};
const geojsonCache = {};
let highlightObjs = [];   // 질의 하이라이트 (양쪽 모드 공용 컨테이너)
let kakaoInfo = null;     // 카카오 정보창 (단일 재사용)

init();

async function init() {
  cfg = await (await fetch("/api/config")).json();
  const layers = await (await fetch("/api/layers")).json();

  if (cfg.kakao_js_key) await initKakao(cfg.kakao_js_key);
  else initLeaflet();

  document.getElementById("map-status").innerHTML =
    `지도: ${kakaoMode ? "카카오맵" : "OSM (카카오 키 대기)"}<br>그래프: ${cfg.triples.toLocaleString()} 트리플` +
    `<br>LLM 폴백: ${cfg.llm_enabled ? "on" : "off"}`;

  const list = document.getElementById("layer-list");
  for (const ly of layers) {
    const el = document.createElement("label");
    el.className = "layer-item";
    el.innerHTML = `<input type="checkbox" ${ly.default ? "checked" : ""} data-id="${ly.id}">
      <span class="swatch" style="background:${SWATCH[ly.id] || "#999"}"></span>${ly.name}`;
    el.querySelector("input").addEventListener("change", e => toggleLayer(ly, e.target.checked));
    list.appendChild(el);
    if (ly.default) toggleLayer(ly, true);
  }
  document.getElementById("chat-form").addEventListener("submit", onAsk);
}

/* ---------- Leaflet (키 없이 즉시 동작) ---------- */
function initLeaflet() {
  map = L.map("map", { preferCanvas: true })   // 1,800+ 피처 → 캔버스 렌더 (패닝 성능)
    .setView([cfg.site_center.lat, cfg.site_center.lng], 15);
  const base = L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png",
    { attribution: "&copy; OpenStreetMap", maxZoom: 19 }).addTo(map);
  const sat = L.tileLayer(
    "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    { attribution: "Esri World Imagery", maxZoom: 19 });
  L.control.layers({ "일반지도": base, "항공사진": sat }, null,
    { position: "topright" }).addTo(map);
}

/* ---------- 카카오맵 ---------- */
function initKakao(key) {
  return new Promise(res => {
    const fallback = () => {          // SDK 로드 실패(도메인 미등록 등) → OSM 폴백
      if (map) return;
      console.warn("카카오 SDK 로드 실패 — OSM 폴백 (도메인 등록 확인 필요)");
      initLeaflet(); res();
    };
    const timer = setTimeout(fallback, 7000);
    const s = document.createElement("script");
    s.src = `https://dapi.kakao.com/v2/maps/sdk.js?appkey=${key}&autoload=false`;
    s.onerror = () => { clearTimeout(timer); fallback(); };
    s.onload = () => kakao.maps.load(() => {
      clearTimeout(timer);
      map = new kakao.maps.Map(document.getElementById("map"), {
        center: new kakao.maps.LatLng(cfg.site_center.lat, cfg.site_center.lng), level: 4,
      });
      map.addControl(new kakao.maps.MapTypeControl(), kakao.maps.ControlPosition.TOPRIGHT); // 지도|스카이뷰
      map.addControl(new kakao.maps.ZoomControl(), kakao.maps.ControlPosition.RIGHT);
      kakaoInfo = new kakao.maps.CustomOverlay({ yAnchor: 1.4, zIndex: 30 });
      kakao.maps.event.addListener(map, "click", (e) => {
        showKakaoInfo(e.latLng, `${e.latLng.getLat().toFixed(6)}, ${e.latLng.getLng().toFixed(6)}`);
      });
      kakaoMode = true; res();
    });
    document.head.appendChild(s);
  });
}

function showKakaoInfo(latlng, text, button) {
  const div = document.createElement("div");
  div.className = "kk-info";
  div.textContent = text;
  if (button) {
    const b = document.createElement("button");
    b.className = "kk-info-btn";
    b.textContent = button.label;
    b.onclick = ev => { ev.stopPropagation(); button.onClick(); };
    div.appendChild(b);
  }
  kakaoInfo.setContent(div);
  kakaoInfo.setPosition(latlng);
  kakaoInfo.setMap(map);
}

function kakaoDot(lon, lat, st, sizePx, text, zIndex = 10) {
  const div = document.createElement("div");
  div.className = "kk-dot";
  div.style.cssText = `width:${sizePx}px;height:${sizePx}px;background:${st.fillColor};
    border:1.5px solid ${st.color};`;
  if (text) div.title = text;
  const pos = new kakao.maps.LatLng(lat, lon);
  const ov = new kakao.maps.CustomOverlay({ position: pos, content: div, zIndex });
  if (text) div.addEventListener("click", ev => { ev.stopPropagation(); showKakaoInfo(pos, text); });
  return ov;
}

async function loadGeojson(file) {
  if (!geojsonCache[file])
    geojsonCache[file] = await (await fetch(`/static/geojson/${file}`)).json();
  return geojsonCache[file];
}

function featureText(f) {
  const p = f.properties;
  if (p.label) return p.tag ? `${p.label} (${p.tag})` : p.label;
  return p.name || p.kind || p.block || p.layer || String(f.id || "");
}

async function toggleLayer(ly, on) {
  const gj = await loadGeojson(ly.file);
  if (!kakaoMode) {
    if (on) {
      if (!leafletLayers[ly.id]) {
        const styler = STYLE[ly.id];
        leafletLayers[ly.id] = L.geoJSON(gj, {
          style: typeof styler === "function" ? styler : () => styler,
          pointToLayer: (f, latlng) =>
            L.circleMarker(latlng, typeof styler === "function" ? styler(f) : styler),
          onEachFeature: (f, l) => {
            const t = featureText(f); if (t) l.bindPopup(t);
            if (ly.id === "facility") {
              const g = f.geometry;
              const isLabelBldg = g.type === "Point" && /설\s*비\s*동/.test(t || "");
              l.on("click", async () => {
                let show = isLabelBldg;
                if (!show && g.type === "Polygon") {
                  const c = await equipCentroid();
                  show = c && polyContains(g.coordinates[0], c);
                }
                if (show) {
                  const el = document.createElement("div");
                  el.textContent = t || "설비동";
                  const b = document.createElement("button");
                  b.className = "kk-info-btn"; b.textContent = "내부 상세 보기";
                  b.onclick = () => openBuildingModal();
                  el.appendChild(b);
                  l.bindPopup(el).openPopup();
                }
              });
            }
            if (ly.id === "equipment") l.on("click", () => {
              const key = (f.properties.tag || "").split(" ")[0] || f.properties.label;
              showAssetCard(key);
            });
            if (ly.id === "plansheets") l.on("click", () => {
              const el = document.createElement("div");
              el.textContent = f.properties.title;
              const b = document.createElement("button");
              b.className = "kk-info-btn"; b.textContent = "도면 열람";
              b.onclick = () => openSheetViewer(f);
              el.appendChild(b);
              l.bindPopup(el).openPopup();
            });
          },
        });
      }
      leafletLayers[ly.id].addTo(map);
    } else if (leafletLayers[ly.id]) map.removeLayer(leafletLayers[ly.id]);
  } else {
    if (on) {
      if (!kakaoObjects[ly.id]) kakaoObjects[ly.id] = buildKakao(gj, ly.id);
      kakaoObjects[ly.id].forEach(o => o.setMap(map));
    } else if (kakaoObjects[ly.id]) kakaoObjects[ly.id].forEach(o => o.setMap(null));
  }
}

/* 장비 무게중심 (설비동 판정용) · 점-폴리곤 포함 검사 */
let _eqCentroid = null;
async function equipCentroid() {
  if (_eqCentroid) return _eqCentroid;
  try {
    const gj = await loadGeojson("equipment.geojson");
    const pts = gj.features.map(f => f.geometry.coordinates);
    _eqCentroid = [pts.reduce((s, p) => s + p[0], 0) / pts.length,
                   pts.reduce((s, p) => s + p[1], 0) / pts.length];
  } catch (e) { return null; }
  return _eqCentroid;
}
function polyContains(ring, pt) {
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const [xi, yi] = ring[i], [xj, yj] = ring[j];
    if ((yi > pt[1]) !== (yj > pt[1]) &&
        pt[0] < (xj - xi) * (pt[1] - yi) / (yj - yi) + xi) inside = !inside;
  }
  return inside;
}

function buildKakao(gj, id) {
  const objs = [];
  const styler = STYLE[id];
  for (const f of gj.features) {
    const st = typeof styler === "function" ? styler(f) : styler;
    const g = f.geometry;
    const toLL = c => new kakao.maps.LatLng(c[1], c[0]);
    const text = featureText(f);
    if (g.type === "LineString") {
      const pl = new kakao.maps.Polyline({
        path: g.coordinates.map(toLL), strokeColor: st.color, strokeWeight: st.weight || 2 });
      kakao.maps.event.addListener(pl, "click", (e) => showKakaoInfo(e.latLng, text));
      objs.push(pl);
    } else if (g.type === "Polygon") {
      const pg = new kakao.maps.Polygon({
        path: g.coordinates[0].map(toLL), strokeColor: st.color, strokeWeight: st.weight || 1,
        fillColor: st.fillColor, fillOpacity: st.fillOpacity || 0.5 });
      kakao.maps.event.addListener(pg, "click", async (e) => {
        let btn = null;
        if (id === "facility") {
          const c = await equipCentroid();
          if (c && polyContains(g.coordinates[0], c))
            btn = { label: "내부 상세 보기", onClick: openBuildingModal };
        }
        if (id === "plansheets")
          btn = { label: "도면 열람", onClick: () => openSheetViewer(f) };
        showKakaoInfo(e.latLng, (id === "plansheets" ? f.properties.title : text) || "시설", btn);
      });
      objs.push(pg);
    } else if (g.type === "Point") {
      const ov = kakaoDot(g.coordinates[0], g.coordinates[1], st,
        DOT_PX[id] || 9, text, id === "equipment" ? 15 : 10);
      if (id === "equipment") {
        const key = (f.properties.tag || "").split(" ")[0] || f.properties.label;
        ov.getContent().addEventListener("click", () => showAssetCard(key));
      }
      if (id === "facility" && /설\s*비\s*동/.test(text || "")) {
        // '설 비 동' 라벨 점 클릭 → 상세보기 버튼 (나중에 등록된 리스너가 인포 내용을 덮어씀)
        const pos = new kakao.maps.LatLng(g.coordinates[1], g.coordinates[0]);
        ov.getContent().addEventListener("click", ev => {
          ev.stopPropagation();
          showKakaoInfo(pos, text, { label: "내부 상세 보기", onClick: openBuildingModal });
        });
      }
      objs.push(ov);
    }
  }
  return objs;
}

/* ---------- 질의 결과 지도 하이라이트 ---------- */
function clearHighlights() {
  for (const o of highlightObjs) {
    if (kakaoMode) o.setMap(null); else map.removeLayer(o);
  }
  highlightObjs = [];
}

function drawHighlights(features) {
  clearHighlights();
  const HL = { color: "#d500f9", weight: 4 };
  const pts = [];
  for (const f of features) {
    if (f.kind === "edge") {
      pts.push(f.from, f.to);
      if (kakaoMode) {
        const pl = new kakao.maps.Polyline({
          path: [new kakao.maps.LatLng(f.from[1], f.from[0]), new kakao.maps.LatLng(f.to[1], f.to[0])],
          strokeColor: HL.color, strokeWeight: HL.weight, strokeStyle: "shortdash", zIndex: 20 });
        kakao.maps.event.addListener(pl, "click", (e) => showKakaoInfo(e.latLng, f.label));
        pl.setMap(map); highlightObjs.push(pl);
      } else {
        const l = L.polyline([[f.from[1], f.from[0]], [f.to[1], f.to[0]]],
          { color: HL.color, weight: HL.weight, dashArray: "6 6" }).bindPopup(f.label).addTo(map);
        highlightObjs.push(l);
      }
    } else if (f.kind === "point") {
      pts.push(f.coord);
      if (kakaoMode) {
        const ov = kakaoDot(f.coord[0], f.coord[1],
          { fillColor: "#ffff00", color: "#d500f9" }, 13, f.label, 25);
        ov.setMap(map); highlightObjs.push(ov);
      } else {
        const m = L.circleMarker([f.coord[1], f.coord[0]],
          { radius: 7, color: "#d500f9", fillColor: "#ffff00", fillOpacity: 0.95, weight: 2 })
          .bindPopup(f.label).addTo(map);
        highlightObjs.push(m);
      }
    }
  }
  if (!pts.length) return;
  // 하이라이트 범위로 이동
  if (kakaoMode) {
    const b = new kakao.maps.LatLngBounds();
    pts.forEach(c => b.extend(new kakao.maps.LatLng(c[1], c[0])));
    map.setBounds(b, 80, 80, 80, 80);
  } else {
    map.fitBounds(pts.map(c => [c[1], c[0]]), { padding: [60, 60] });
  }
}

/* ---------- AI 질의 ---------- */
async function ask(q) {
  addMsg("user", q);
  const btn = document.querySelector("#chat-form button");
  btn.disabled = true;
  try {
    const r = await (await fetch("/api/query", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: q }),
    })).json();
    addBotMsg(r);
    if (r.map && r.map.features && r.map.features.length) drawHighlights(r.map.features);
  } catch (err) {
    addMsg("bot", "질의 실패: " + err);
  }
  btn.disabled = false;
}

function onAsk(e) {
  e.preventDefault();
  const input = document.getElementById("chat-input");
  const q = input.value.trim();
  if (!q) return;
  input.value = "";
  ask(q);
}

/* ---------- 장비 종합 카드 (노드/점 클릭 → AI 패널) ---------- */
async function showAssetCard(key) {
  try {
    const resp = await fetch("/api/asset_card", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ key }),
    });
    const c = await resp.json();
    if (!resp.ok) { addMsg("bot", c.error || "카드 조회 실패"); return; }
    renderAssetCard(c);
    if (c.coord) drawHighlights([{ kind: "point", coord: c.coord, label: c.label }]);
  } catch (err) {
    addMsg("bot", "카드 조회 실패: " + err);
  }
}

function renderAssetCard(c) {
  const log = document.getElementById("chat-log");
  const d = buildAssetCardEl(c, q => ask(q));
  log.appendChild(d);
  log.scrollTop = log.scrollHeight;
}

/* 카드 DOM 생성 (채팅·모달 공용). onAsk(q)가 있으면 추천버튼 부착 */
function buildAssetCardEl(c, onAsk) {
  const d = document.createElement("div");
  d.className = "msg bot asset-card";
  const rows = [];
  rows.push(`<div class="ac-head">${c.label}${c.tag ? ` <b>[${c.tag}]</b>` : ""}</div>`);
  if (c.sysl) rows.push(`<div>계통: ${c.sysl}</div>`);
  if (c.spec) rows.push(`<div>사양: ${c.spec}</div>`);
  if (c.qty) rows.push(`<div>수량: ${c.qty}</div>`);
  if (c.kw) rows.push(`<div>동력: ${c.kw} kW</div>`);
  if (c.status) rows.push(`<div>검증상태: ${c.status}</div>`);
  const fi = (c.feeds_in || []).map(r => r.al).join(", ");
  const fo = (c.feeds_out || []).map(r => r.bl + (r.m ? `[${r.m}]` : "")).join(", ");
  if (fi) rows.push(`<div>← 유입: ${fi}</div>`);
  if (fo) rows.push(`<div>→ 유출: ${fo}</div>`);
  if (c.iso_sheets && c.iso_sheets.length) {
    const sh = c.iso_sheets.map(s => s.no).join(", ");
    rows.push(`<div>아이소시트: ${sh}</div>`);
  }
  if (c.pipe_summary) {
    const p = c.pipe_summary;
    const len = p.len ? `${Math.round(+p.len)}m` : "-";
    const wt = p.wt ? `${Math.round(+p.wt)}kg` : "-";
    rows.push(`<div>관련 배관: ${p.n}항목, 연장 ${len}, 중량 ${wt}</div>`);
  }
  if (!c.coord) rows.push(`<div class="ac-dim">(실좌표 미보유 — 지도 표시 불가)</div>`);
  d.innerHTML = rows.join("");

  // 추천 질문 버튼 — 클릭 = AI 질의 자동 실행
  if (onAsk) {
    const key = c.tag ? c.tag.split(" ")[0] : c.label;
    const sugg = [
      [`배관 물량`, `${key} 배관 물량`],
      [`고장 시 하류 영향`, `${c.label} 정지하면 하류 영향 범위는?`],
      [`소속 계통`, `${c.label}은 어느 계통이야?`],
    ];
    const bar = document.createElement("div");
    bar.className = "ac-suggest";
    for (const [lbl, q] of sugg) {
      const b = document.createElement("button");
      b.type = "button"; b.textContent = lbl;
      b.onclick = () => onAsk(q);
      bar.appendChild(b);
    }
    d.appendChild(bar);
  }
  return d;
}

function addMsg(cls, text) {
  const log = document.getElementById("chat-log");
  const d = document.createElement("div");
  d.className = "msg " + cls;
  d.textContent = text;
  log.appendChild(d);
  log.scrollTop = log.scrollHeight;
}

function addBotMsg(r) {
  const log = document.getElementById("chat-log");
  const d = document.createElement("div");
  d.className = "msg bot";
  d.textContent = r.answer || JSON.stringify(r);
  if (r.map && r.map.features && r.map.features.length) {
    const c = document.createElement("span");
    c.className = "toggle-sparql";
    c.textContent = "지도 표시 지우기";
    c.onclick = () => clearHighlights();
    d.appendChild(document.createElement("br"));
    d.appendChild(c);
  }
  if (r.sparql) {
    const t = document.createElement("span");
    t.className = "toggle-sparql";
    t.textContent = ` SPARQL 보기 (${r.route})`;
    const pre = document.createElement("div");
    pre.className = "sparql";
    pre.textContent = r.sparql;
    t.onclick = () => pre.classList.toggle("open");
    d.appendChild(t); d.appendChild(pre);
  }
  log.appendChild(d);
  log.scrollTop = log.scrollHeight;
}


/* ============ 관계 시각화 (Cytoscape, 3뷰) ============ */
let cy = null, graphData = null, curMode = "flow";
const SYS_COLOR = {
  SYS_PRETREAT: "#5b8def", SYS_BIO: "#2ca25f", SYS_IPR: "#d95f0e",
  SYS_UTILITY: "#8856a7", SYS_DEWATER: "#c51b8a", SYS_DEODOR: "#636363",
};
const sysKey = uri => (uri || "").split("/").pop();

document.querySelectorAll(".view-tab").forEach(tab => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".view-tab").forEach(t => t.classList.remove("active"));
    tab.classList.add("active");
    const v = tab.dataset.view;
    document.getElementById("map").hidden = v !== "map";
    document.getElementById("graph-view").hidden = v !== "graph";
    if (v === "graph") ensureGraph();
    else if (map && map.invalidateSize) setTimeout(() => map.invalidateSize(), 50);
  });
});
document.querySelectorAll(".gc-btn").forEach(b => {
  b.addEventListener("click", () => {
    document.querySelectorAll(".gc-btn").forEach(x => x.classList.remove("active"));
    b.classList.add("active");
    curMode = b.dataset.mode;
    renderGraph();
  });
});

async function ensureGraph() {
  if (!graphData) {
    graphData = await (await fetch("/api/graph")).json();
  }
  if (!cy) renderGraph();
  else setTimeout(() => { cy.resize(); cy.fit(null, 30); }, 30);
}

function baseStyle() {
  return [
    { selector: "node", style: {
      "label": "data(label)", "font-size": 10, "color": "#223",
      "text-wrap": "wrap", "text-max-width": 90, "text-valign": "bottom",
      "text-margin-y": 3, "width": 22, "height": 22,
      "background-color": "#9db3c6", "border-width": 1, "border-color": "#fff" } },
    { selector: 'node[kind="system"]', style: {
      "shape": "round-rectangle", "width": 130, "height": 34, "font-size": 12,
      "font-weight": "bold", "color": "#fff", "text-valign": "center",
      "text-max-width": 120, "text-margin-y": 0 } },
    { selector: 'node[kind="pumpstation"]', style: {
      "shape": "round-rectangle", "background-color": "#1b5e20", "color": "#fff",
      "width": 110, "height": 28, "font-size": 11, "text-valign": "center", "text-max-width": 100 } },
    { selector: 'node[kind="mcc"]', style: {
      "shape": "diamond", "background-color": "#f9a825", "width": 26, "height": 26 } },
    { selector: "edge", style: {
      "curve-style": "bezier", "target-arrow-shape": "triangle", "width": 1.6,
      "line-color": "#b7c3cf", "target-arrow-color": "#b7c3cf", "arrow-scale": 0.9 } },
    { selector: 'edge[rel="partOf"]', style: {
      "line-color": "#dbe3ea", "target-arrow-shape": "none", "width": 1.2 } },
    { selector: 'edge[rel="feeds"]', style: {
      "label": "data(media)", "font-size": 8, "color": "#8a5a2b",
      "text-rotation": "autorotate", "line-color": "#7d97ad", "target-arrow-color": "#7d97ad" } },
    { selector: 'edge[rel="powers"]', style: {
      "line-color": "#f9a825", "target-arrow-color": "#f9a825", "line-style": "dashed" } },
    { selector: 'edge[rel="contains"]', style: {
      "line-color": "#9e9e9e", "target-arrow-shape": "none" } },
    { selector: ".dim", style: { "opacity": 0.15 } },
    { selector: ".hl", style: { "border-width": 3, "border-color": "#ff6d00" } },
  ];
}

function colorNodes() {
  cy.nodes('[kind="system"]').forEach(n => {
    n.style("background-color", SYS_COLOR[sysKey(n.id())] || "#555");
  });
  cy.nodes('[kind="asset"]').forEach(n => {
    const s = sysKey(n.data("system"));
    n.style("background-color", SYS_COLOR[s] || "#9db3c6");
  });
}

function renderGraph() {
  if (!graphData) return;
  const legend = document.getElementById("gc-legend");
  const sysLegend = graphData.systems.map(s =>
    `<span><i style="background:${SYS_COLOR[sysKey(s.id)]}"></i>${s.label}</span>`).join("");

  // 모드별 요소 필터
  let els;
  if (curMode === "tree") {
    // 계통 → 장비 (partOf) 계층
    els = graphData.nodes.filter(n => ["system", "asset"].includes(n.data.kind))
      .concat(graphData.edges.filter(e => e.data.rel === "partOf"));
  } else {
    // flow / qty: feeds + 펌프 전원, 계통노드는 제외(위상 흐름 중심)
    const keepRels = ["feeds", "powers", "contains"];
    const edges = graphData.edges.filter(e => keepRels.includes(e.data.rel));
    const usedIds = new Set();
    edges.forEach(e => { usedIds.add(e.data.source); usedIds.add(e.data.target); });
    els = graphData.nodes.filter(n => usedIds.has(n.data.id) || n.data.kind === "pumpstation")
      .concat(edges);
  }

  if (cy) cy.destroy();
  cy = cytoscape({
    container: document.getElementById("cy"),
    elements: els, style: baseStyle(),
    layout: curMode === "tree"
      ? { name: "dagre", rankDir: "LR", nodeSep: 16, rankSep: 90, edgeSep: 8 }
      : { name: "dagre", rankDir: "LR", nodeSep: 22, rankSep: 70 },
    wheelSensitivity: 0.2,
  });
  colorNodes();

  if (curMode === "qty") {
    // 엣지 굵기·색 = 배관 물량(m), 노드 크기 = 관련 물량
    const qs = cy.edges('[rel="feeds"]').map(e => e.data("pipeQty") || 0);
    const qmax = Math.max(1, ...qs);
    cy.edges('[rel="feeds"]').forEach(e => {
      const q = e.data("pipeQty") || 0;
      const w = 1.5 + (q / qmax) * 9;
      const c = q > 0 ? `hsl(${210 - (q / qmax) * 190}, 75%, 45%)` : "#c8d2db";
      e.style({ "width": w, "line-color": c, "target-arrow-color": c,
        "label": q > 0 ? `${Math.round(q)}m` : "", "font-size": 9, "color": c });
    });
    cy.nodes('[kind="asset"]').forEach(n => {
      const q = n.data("pipeQty") || 0;
      const sz = 20 + Math.sqrt(q) * 2.5;
      n.style({ "width": sz, "height": sz });
    });
    legend.innerHTML = `<span><i style="background:hsl(20,75%,45%)"></i>물량 많음</span>` +
      `<span><i style="background:hsl(210,75%,45%)"></i>적음</span>` +
      `　엣지 굵기·라벨 = 배관 연장(m)`;
  } else if (curMode === "tree") {
    legend.innerHTML = sysLegend + `　<span>계통 → 소속 장비 (partOf)</span>`;
  } else {
    legend.innerHTML = sysLegend +
      `<span><i style="background:#f9a825"></i>MCC/전원</span>` +
      `　<span>화살표 = feeds 흐름</span>`;
  }

  cy.on("tap", "node", evt => {
    const d = evt.target.data();
    cy.elements().removeClass("hl dim");
    const nb = evt.target.closedNeighborhood();
    cy.elements().not(nb).addClass("dim");
    evt.target.addClass("hl");
    let t = `${d.label}`;
    if (d.tag) t += `  [${d.tag}]`;
    if (d.kind === "asset" && d.pipeQty) t += `\n관련 배관 물량 ≈ ${d.pipeQty} m`;
    if (d.kind === "system") t += `  (계통)`;
    if (d.kind === "pumpstation") t += `  (중계펌프장)`;
    document.getElementById("cy-tip").textContent = t;
    if (d.kind === "asset") showAssetCard(d.id);   // 클릭 = 종합 카드 질의
  });
  cy.on("tap", evt => {
    if (evt.target === cy) { cy.elements().removeClass("hl dim");
      document.getElementById("cy-tip").textContent = "노드를 클릭하면 상세가 표시됩니다."; }
  });
  setTimeout(() => cy.fit(null, 30), 40);
}

/* ================= 설비동 상세 뷰 (도면 + 리스트 + 관계도) ================= */
const FLOORS = [
  { sheet: "DXF:M-012", short: "상부층", label: "상부층 (M-012)" },
  { sheet: "DXF:M-013", short: "중간층", label: "중간층 EL+27.2 (M-013)" },
  { sheet: "DXF:M-014", short: "하부층", label: "하부층 EL+21.9 (M-014)" },
];
const bd = { floor: "DXF:M-013", tab: "plan", sel: null, eq: null, fac: null,
             cy: null, proj: null, sysColor: {}, realSvg: {} };

async function ensureGraphData() {
  if (!graphData) graphData = await (await fetch("/api/graph")).json();
  return graphData;
}

async function openBuildingModal() {
  document.getElementById("bd-modal").hidden = false;
  if (kakaoInfo) kakaoInfo.setMap(null);
  if (!bd.eq) {
    bd.eq = (await loadGeojson("equipment.geojson")).features;
    bd.fac = (await loadGeojson("facility.geojson")).features;
    await ensureGraphData();
    // 계통색: 관계도와 동일 팔레트 재사용
    const PAL = ["#2ca25f", "#5b8def", "#d95f0e", "#c51b8a", "#8856a7", "#636363"];
    graphData.systems.forEach((s, i) => { bd.sysColor[s.id] = PAL[i % PAL.length]; });
    buildProjection();
  }
  bdRenderTabs(); bdRenderList(); bdRenderView(); bdRenderCy(null);
  bdSelect(bd.sel, true);
}
function closeBuildingModal() { document.getElementById("bd-modal").hidden = true; }

/* WGS84 → 건물 로컬 미터 (소규모 영역 등장방형 근사)
   기준: 장비 48종 좌표 bbox — 시설 폴리곤 라벨에 의존하지 않음 */
function buildProjection() {
  const pts = bd.eq.map(f => f.geometry.coordinates);
  let minX = 1e9, maxX = -1e9, minY = 1e9, maxY = -1e9;
  const lat0 = pts.reduce((s, p) => s + p[1], 0) / pts.length;
  const kx = 111320 * Math.cos(lat0 * Math.PI / 180), ky = 110540;
  const toM = c => [c[0] * kx, c[1] * ky];
  pts.forEach(p => { const [x, y] = toM(p);
    minX = Math.min(minX, x); maxX = Math.max(maxX, x);
    minY = Math.min(minY, y); maxY = Math.max(maxY, y); });
  const pad = 15;
  bd.proj = { toM, minX: minX - pad, maxX: maxX + pad, minY: minY - pad, maxY: maxY + pad };
}
function inBox(x, y) {
  return x >= bd.proj.minX && x <= bd.proj.maxX && y >= bd.proj.minY && y <= bd.proj.maxY;
}

function bdAssets(floorOnly = true) {
  return bd.eq.filter(f => !floorOnly || f.properties.sheet === bd.floor);
}
function assetSystem(id) {
  const n = graphData.nodes.find(n => n.data.id.endsWith("/" + id));
  return n ? n.data.system : "";
}
function assetUri(id) {
  const n = graphData.nodes.find(n => n.data.id.endsWith("/" + id));
  return n ? n.data.id : null;
}

function bdRenderTabs() {
  const ft = document.getElementById("bd-floors");
  ft.innerHTML = "";
  FLOORS.forEach(fl => {
    const b = document.createElement("button");
    b.textContent = fl.short;
    b.className = fl.sheet === bd.floor ? "on" : "";
    b.title = fl.label;
    b.onclick = () => { bd.floor = fl.sheet; bdRenderTabs(); bdRenderList(); bdRenderView(); };
    ft.appendChild(b);
  });
  document.querySelectorAll("#bd-viewtabs button").forEach(b => {
    b.classList.toggle("on", b.dataset.tab === bd.tab);
    b.onclick = () => { bd.tab = b.dataset.tab; bdRenderTabs(); bdRenderView(); };
  });
}

function bdRenderList() {
  const box = document.getElementById("bd-list");
  const q = (document.getElementById("bd-search").value || "").trim();
  box.innerHTML = "";
  const items = bdAssets().filter(f =>
    !q || (f.properties.label + f.properties.tag).includes(q));
  document.getElementById("bd-count").textContent =
    `${items.length}종 (${FLOORS.find(f => f.sheet === bd.floor).label})`;
  items.forEach(f => {
    const d = document.createElement("div");
    d.className = "bd-item" + (bd.sel === f.id ? " on" : "");
    const c = bd.sysColor[assetSystem(f.id)] || "#999";
    d.innerHTML = `<span class="bd-dot" style="background:${c}"></span>
      <span class="bd-lab">${f.properties.label}</span>
      <span class="bd-tag">${f.properties.tag || ""}</span>`;
    d.onclick = () => bdSelect(f.id);
    box.appendChild(d);
  });
  if (!items.length) box.innerHTML = `<div class="bd-empty">해당 층에 표기된 장비가 없습니다</div>`;
}

/* 중앙 뷰 — plan(배치도) / flow(계통도) */
async function bdRenderView() {
  const host = document.getElementById("bd-view");
  host.innerHTML = "";
  if (bd.tab === "plan") await bdRenderPlan(host);
  else bdRenderFlow(host);
}

/* 배치도: 실 DXF-SVG(열람) / 약식 평면(마커 인터랙션) 서브 토글 */
async function bdRenderPlan(host) {
  const sheetId = bd.floor.replace("DXF:", "");
  if (!(sheetId in bd.realSvg)) {
    try {
      const [svgR, calR] = await Promise.all([
        fetch(`/static/drawings/${sheetId}.svg`, { method: "HEAD" }),
        fetch(`/static/drawings/${sheetId}.calib.json`)]);
      bd.realSvg[sheetId] = (svgR.ok && calR.ok)
        ? { url: `/static/drawings/${sheetId}.svg`, calib: await calR.json() } : null;
    } catch (e) { bd.realSvg[sheetId] = null; }
  }
  const real = bd.realSvg[sheetId];
  if (!bd.planMode) bd.planMode = real ? "real" : "schem";
  if (!real) bd.planMode = "schem";

  // 서브 토글 + 안내
  const bar = document.createElement("div");
  bar.className = "bd-note";
  if (real) {
    const mk = (mode, lbl) => {
      const b = document.createElement("button");
      b.className = "bd-chip" + (bd.planMode === mode ? " on" : "");
      b.textContent = lbl;
      b.onclick = () => { bd.planMode = mode; bdRenderView(); };
      return b;
    };
    bar.append(mk("real", "실도면"), mk("schem", "약식+마커"), Object.assign(
      document.createElement("span"),
      { textContent: bd.planMode === "real"
        ? " 실 배치도 (DXF 변환) — 휠=확대, 드래그=이동, 마커 클릭=선택 · 주황=유출, 파랑=유입"
        : " 약식 평면 (C-002 지오메트리) — 휠=확대, 드래그=이동, 마커 클릭=선택 · 주황=유출, 파랑=유입" }));
  } else {
    bar.textContent = "약식 평면 (C-002 지오메트리) — DXF 변환본이 없으면 이 화면이 기본입니다";
  }
  host.appendChild(bar);

  if (real && bd.planMode === "real") {
    bdRenderReal(host, real, sheetId);
    return;
  }
  bdRenderSchematic(host);
}

/* ---- 공용 팬줌: 휠=커서 중심 확대/축소, 좌드래그=패닝 ---- */
function bdPanZoom(host, content, fitScale = 1) {
  const vp = document.createElement("div");
  vp.className = "bd-vp";
  const inner = document.createElement("div");
  inner.className = "bd-vp-inner";
  inner.appendChild(content);
  vp.appendChild(inner);
  host.appendChild(vp);
  let s = fitScale, tx = 0, ty = 0;
  const apply = () => inner.style.transform = `translate(${tx}px,${ty}px) scale(${s})`;
  apply();
  vp.addEventListener("wheel", e => {
    e.preventDefault();
    const r = vp.getBoundingClientRect();
    const mx = e.clientX - r.left, my = e.clientY - r.top;
    const k = e.deltaY < 0 ? 1.2 : 1 / 1.2;
    const ns = Math.min(12, Math.max(0.2, s * k));
    tx = mx - (mx - tx) * (ns / s);
    ty = my - (my - ty) * (ns / s);
    s = ns; apply();
  }, { passive: false });
  let drag = null, moved = false;
  vp.addEventListener("mousedown", e => {
    if (e.button !== 0) return;
    drag = { x: e.clientX - tx, y: e.clientY - ty }; moved = false;
    vp.classList.add("grabbing");
  });
  window.addEventListener("mousemove", e => {
    if (!drag) return;
    tx = e.clientX - drag.x; ty = e.clientY - drag.y;
    if (Math.abs(e.movementX) + Math.abs(e.movementY) > 1) moved = true;
    apply();
  });
  window.addEventListener("mouseup", () => { drag = null; vp.classList.remove("grabbing"); });
  // 드래그 직후 발생하는 click은 마커 선택으로 오인되지 않게 흡수
  vp.addEventListener("click", e => { if (moved) { e.stopPropagation(); moved = false; } }, true);
  return vp;
}

/* ---- 선택 장비의 feeds 전/후 관계 (같은 층 좌표 보유분) ---- */
function bdFeedsOfSel() {
  if (!bd.sel) return { uri: null, out: new Set(), inn: new Set() };
  const uri = assetUri(bd.sel);
  const out = new Set(), inn = new Set();
  if (uri) graphData.edges.forEach(e => {
    if (e.data.rel !== "feeds") return;
    if (e.data.source === uri) out.add(e.data.target);
    if (e.data.target === uri) inn.add(e.data.source);
  });
  return { uri, out, inn };
}

/* 약식 평면 (C-002 벡터 + 마커 + 전후관계 화살표) */
function bdRenderSchematic(host) {
  const P = bd.proj;
  const W = P.maxX - P.minX, H = P.maxY - P.minY;
  const S = 8; // px per meter
  const svgNS = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(svgNS, "svg");
  svg.setAttribute("viewBox", `0 0 ${W * S} ${H * S}`);
  svg.id = "bd-plan-svg";
  const gx = x => (x - P.minX) * S;
  const gy = y => (P.maxY - y) * S;

  // 화살표 머리 정의
  svg.innerHTML = `<defs>
    <marker id="bd-arr-out" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
      <path d="M0,0 L10,5 L0,10 z" fill="#e65100"/></marker>
    <marker id="bd-arr-in" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
      <path d="M0,0 L10,5 L0,10 z" fill="#1565c0"/></marker>
  </defs>`;

  // 시설 지오메트리 벡터 도면
  bd.fac.forEach(f => {
    const g = f.geometry;
    const draw = coords => {
      const pts = coords.map(bd.proj.toM).filter(p => inBox(p[0], p[1]));
      if (pts.length < 2) return;
      const pl = document.createElementNS(svgNS, "polyline");
      pl.setAttribute("points", coords.map(bd.proj.toM)
        .map(p => `${gx(p[0])},${gy(p[1])}`).join(" "));
      pl.setAttribute("fill", "none");
      pl.setAttribute("stroke", "#90a4ae");
      pl.setAttribute("stroke-width", "1");
      svg.appendChild(pl);
    };
    if (g.type === "LineString") draw(g.coordinates);
    else if (g.type === "Polygon") draw(g.coordinates[0].concat([g.coordinates[0][0]]));
  });

  // 전후관계 화살표 (마커보다 아래층에 먼저)
  const rel = bdFeedsOfSel();
  const posOf = {};
  bdAssets().forEach(f => {
    const [x, y] = bd.proj.toM(f.geometry.coordinates);
    if (inBox(x, y)) posOf[assetUri(f.id)] = [gx(x), gy(y)];
  });
  if (rel.uri && posOf[rel.uri]) {
    const [sx, sy] = posOf[rel.uri];
    const arrow = (toUri, cls) => {
      const p = posOf[toUri]; if (!p) return;
      const ln = document.createElementNS(svgNS, "line");
      const from = cls === "out" ? [sx, sy] : p;
      const to = cls === "out" ? p : [sx, sy];
      ln.setAttribute("x1", from[0]); ln.setAttribute("y1", from[1]);
      ln.setAttribute("x2", to[0]); ln.setAttribute("y2", to[1]);
      ln.setAttribute("stroke", cls === "out" ? "#e65100" : "#1565c0");
      ln.setAttribute("stroke-width", "2.5");
      ln.setAttribute("stroke-dasharray", "6 4");
      ln.setAttribute("marker-end", `url(#bd-arr-${cls})`);
      svg.appendChild(ln);
    };
    rel.out.forEach(u => arrow(u, "out"));
    rel.inn.forEach(u => arrow(u, "in"));
  }

  // 장비 마커 (해당 층)
  bdAssets().forEach(f => {
    const [x, y] = bd.proj.toM(f.geometry.coordinates);
    if (!inBox(x, y)) return;
    const uri = assetUri(f.id);
    const isSel = bd.sel === f.id;
    const isOut = rel.out.has(uri), isIn = rel.inn.has(uri);
    const c = document.createElementNS(svgNS, "circle");
    c.setAttribute("cx", gx(x)); c.setAttribute("cy", gy(y));
    c.setAttribute("r", isSel ? 9 : (isOut || isIn) ? 8 : 6);
    c.setAttribute("fill", bd.sysColor[assetSystem(f.id)] || "#999");
    c.setAttribute("stroke", isSel ? "#d500f9" : isOut ? "#e65100" : isIn ? "#1565c0" : "#fff");
    c.setAttribute("stroke-width", (isSel || isOut || isIn) ? 3 : 1.5);
    c.classList.add("bd-marker");
    c.addEventListener("click", () => bdSelect(f.id));
    const t = document.createElementNS(svgNS, "title");
    t.textContent = `${f.properties.label} [${f.properties.tag}]`;
    c.appendChild(t);
    svg.appendChild(c);
    if (isSel || isOut || isIn) {
      const lb = document.createElementNS(svgNS, "text");
      lb.setAttribute("x", gx(x) + 11); lb.setAttribute("y", gy(y) + 4);
      lb.setAttribute("class", "bd-marker-label" + (isSel ? "" : " nb"));
      lb.textContent = f.properties.label;
      svg.appendChild(lb);
    }
  });
  bdPanZoom(host, svg);
}

/* 실도면: DXF-SVG 배경 + 로컬좌표 마커 오버레이 (calib 프레임 = localXY 프레임) */
function bdRenderReal(host, real, sheetId) {
  const [x0, y0, x1, y1] = real.calib.extents;
  const wrap = document.createElement("div");
  wrap.className = "bd-real-wrap";
  const img = document.createElement("img");
  img.src = real.url;
  img.className = "bd-real-img2";
  img.draggable = false;
  wrap.appendChild(img);

  const rel = bdFeedsOfSel();
  const pct = f => {
    const l = f.properties.local; if (!l) return null;
    const u = (l[0] - x0) / (x1 - x0), v = (l[1] - y0) / (y1 - y0);
    if (u < 0 || u > 1 || v < 0 || v > 1) return null;
    return [u * 100, (1 - v) * 100];
  };
  // 전후관계 연결선 (%: SVG 오버레이)
  const lay = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  lay.setAttribute("class", "bd-real-lines");
  const posOf = {};
  bdAssets().forEach(f => { const p = pct(f); if (p) posOf[assetUri(f.id)] = p; });
  if (rel.uri && posOf[rel.uri]) {
    const [sx, sy] = posOf[rel.uri];
    const line = (u, color) => {
      const p = posOf[u]; if (!p) return;
      const ln = document.createElementNS("http://www.w3.org/2000/svg", "line");
      ln.setAttribute("x1", sx + "%"); ln.setAttribute("y1", sy + "%");
      ln.setAttribute("x2", p[0] + "%"); ln.setAttribute("y2", p[1] + "%");
      ln.setAttribute("stroke", color); ln.setAttribute("stroke-width", "2.5");
      ln.setAttribute("stroke-dasharray", "6 4");
      lay.appendChild(ln);
    };
    rel.out.forEach(u => line(u, "#e65100"));
    rel.inn.forEach(u => line(u, "#1565c0"));
  }
  wrap.appendChild(lay);

  // 마커
  bdAssets().forEach(f => {
    const p = pct(f); if (!p) return;
    const uri = assetUri(f.id);
    const isSel = bd.sel === f.id;
    const isOut = rel.out.has(uri), isIn = rel.inn.has(uri);
    const d = document.createElement("div");
    d.className = "bd-real-dot" + (isSel ? " sel" : isOut ? " out" : isIn ? " in" : "");
    d.style.left = p[0] + "%"; d.style.top = p[1] + "%";
    d.style.background = bd.sysColor[assetSystem(f.id)] || "#999";
    d.title = `${f.properties.label} [${f.properties.tag}]`;
    d.onclick = () => bdSelect(f.id);
    wrap.appendChild(d);
    if (isSel || isOut || isIn) {
      const lb = document.createElement("div");
      lb.className = "bd-real-lbl" + (isSel ? "" : " nb");
      lb.style.left = `calc(${p[0]}% + 10px)`; lb.style.top = p[1] + "%";
      lb.textContent = f.properties.label;
      wrap.appendChild(lb);
    }
  });

  img.onload = () => {
    const vpw = host.clientWidth || 800;
    wrap.style.width = vpw + "px";   // 화면 폭 기준 맞춤 → 팬줌으로 확대
  };
  bdPanZoom(host, wrap);
}

/* 계통도 탭: [흐름그래프] + 실도면 시트 칩(M-006~011) */
const FLOW_SHEETS = ["M-006", "M-007", "M-008", "M-009", "M-010", "M-011"];
function bdRenderFlow(host) {
  if (!bd.flowSheet) bd.flowSheet = "graph";
  const bar = document.createElement("div");
  bar.className = "bd-note";
  const mk = (key, lbl) => {
    const b = document.createElement("button");
    b.className = "bd-chip" + (bd.flowSheet === key ? " on" : "");
    b.textContent = lbl;
    b.onclick = () => { bd.flowSheet = key; bdRenderView(); };
    return b;
  };
  bar.appendChild(mk("graph", "흐름그래프"));
  FLOW_SHEETS.forEach(s => bar.appendChild(mk(s, s)));
  host.appendChild(bar);

  if (bd.flowSheet !== "graph") {
    const url = `/static/drawings/${bd.flowSheet}.svg`;
    const img = document.createElement("img");
    img.src = url; img.className = "bd-real-img";
    img.title = "클릭: 원본 크기로 새 탭";
    img.onclick = () => window.open(url, "_blank");
    img.onerror = () => {
      host.appendChild(Object.assign(document.createElement("div"),
        { className: "bd-empty", textContent: `${bd.flowSheet}.svg 미생성 — dxf_to_svg.py 실행 필요` }));
      img.remove();
    };
    host.appendChild(img);
    return;
  }
  bdRenderFlowGraph(host);
}

/* 흐름그래프: 건물 내 장비 간 feeds (cytoscape, 좌→우) */
function bdRenderFlowGraph(host) {
  const ids = new Set(bd.eq.map(f => assetUri(f.id)).filter(Boolean));
  const nodes = graphData.nodes.filter(n => ids.has(n.data.id));
  const edges = graphData.edges.filter(e =>
    e.data.rel === "feeds" && ids.has(e.data.source) && ids.has(e.data.target));
  const div = document.createElement("div");
  div.id = "bd-flow-cy";
  host.appendChild(div);
  const fcy = cytoscape({
    container: div,
    elements: nodes.concat(edges),
    style: [
      { selector: "node", style: {
        "background-color": ele => bd.sysColor[ele.data("system")] || "#999",
        "label": "data(label)", "font-size": "10px", "width": 22, "height": 22,
        "text-valign": "bottom", "text-margin-y": 4, "color": "#333",
        "text-background-color": "#fff", "text-background-opacity": 0.75,
        "text-background-padding": "1px" } },
      { selector: "node.nolbl", style: { "label": "" } },
      { selector: "edge", style: {
        "curve-style": "bezier", "target-arrow-shape": "triangle",
        "line-color": "#8aa4b8", "target-arrow-color": "#8aa4b8", "width": 2,
        "label": "data(media)", "font-size": "8px", "color": "#8a5a2b" } },
      { selector: "edge.nolbl", style: { "label": "" } },
      { selector: ".hl", style: { "border-width": 4, "border-color": "#d500f9" } },
    ],
    layout: { name: "breadthfirst", directed: true, spacingFactor: 1.1 },
  });
  // 라벨은 확대해야 표시 (겹침 방지): 줌 임계 이하에서 숨김
  const LBL_ZOOM = 0.9;
  const syncLabels = () => {
    const off = fcy.zoom() < LBL_ZOOM;
    fcy.nodes().toggleClass("nolbl", off);
    fcy.edges().toggleClass("nolbl", off);
  };
  fcy.on("zoom", syncLabels);
  fcy.ready(syncLabels);
  fcy.on("tap", "node", evt => {
    const id = evt.target.data("id").split("/").pop();
    bdSelect(id);
  });
  bd.flowCy = fcy;
  if (bd.sel) {
    const u = assetUri(bd.sel);
    if (u) {
      const n = fcy.$(`node[id = "${u}"]`);
      n.addClass("hl");
      if (n.length) fcy.animate({ center: { eles: n }, zoom: Math.max(fcy.zoom(), 1.0) }, { duration: 250 });
    }
  }
}

/* 우측: 선택 장비 이웃 서브그래프 */
function bdRenderCy(selId) {
  const div = document.getElementById("bd-cy");
  if (bd.cy) { bd.cy.destroy(); bd.cy = null; }
  div.innerHTML = "";
  if (!selId) {
    div.innerHTML = `<div class="bd-empty">장비를 선택하면<br>연결 관계가 표시됩니다</div>`;
    return;
  }
  const uri = assetUri(selId);
  if (!uri) return;
  const keep = new Set([uri]);
  graphData.edges.forEach(e => {
    if (e.data.source === uri) keep.add(e.data.target);
    if (e.data.target === uri) keep.add(e.data.source);
  });
  const nodes = graphData.nodes.filter(n => keep.has(n.data.id));
  const edges = graphData.edges.filter(e =>
    keep.has(e.data.source) && keep.has(e.data.target) &&
    (e.data.source === uri || e.data.target === uri));
  bd.cy = cytoscape({
    container: div,
    elements: nodes.concat(edges),
    style: [
      { selector: "node", style: {
        "background-color": ele => ele.data("kind") === "system" ? "#b0bec5"
          : (bd.sysColor[ele.data("system")] || "#999"),
        "shape": ele => ele.data("kind") === "system" ? "round-rectangle" : "ellipse",
        "label": "data(label)", "font-size": "9px", "width": 20, "height": 20,
        "text-valign": "bottom", "text-margin-y": 3, "color": "#333",
        "text-wrap": "wrap", "text-max-width": "80px",
        "text-background-color": "#fff", "text-background-opacity": 0.8,
        "text-background-padding": "1px" } },
      { selector: `node[id = "${uri}"]`, style: {
        "border-width": 4, "border-color": "#d500f9", "width": 30, "height": 30 } },
      { selector: "edge", style: {
        "curve-style": "bezier", "target-arrow-shape": "triangle",
        "line-color": "#aebfcc", "target-arrow-color": "#aebfcc", "width": 1.5 } },
    ],
    layout: { name: "concentric", concentric: n => n.data("id") === uri ? 2 : 1,
              levelWidth: () => 1, minNodeSpacing: 45, padding: 18 },
  });
  bd.cy.on("tap", "node", evt => {
    const d = evt.target.data();
    if (d.kind === "asset") bdSelect(d.id.split("/").pop());
  });
}

/* 선택 동기화: 리스트·도면·관계도·카드 */
async function bdSelect(id, silent) {
  bd.sel = id || null;
  // 다른 층의 장비를 선택하면 층 자동 전환
  if (id) {
    const f = bd.eq.find(f => f.id === id);
    if (f && f.properties.sheet !== bd.floor) { bd.floor = f.properties.sheet; bdRenderTabs(); }
  }
  bdRenderList(); bdRenderView(); bdRenderCy(id);
  const cardBox = document.getElementById("bd-card");
  cardBox.innerHTML = "";
  if (!id) {
    if (!silent) cardBox.innerHTML = `<div class="bd-empty">장비를 선택하세요</div>`;
    return;
  }
  try {
    const resp = await fetch("/api/asset_card", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ key: assetUri(id) || id }),
    });
    const c = await resp.json();
    if (resp.ok) {
      cardBox.appendChild(buildAssetCardEl(c, q => bdAsk(q)));
    }
  } catch (e) { /* 카드 실패는 치명 아님 */ }
}

/* bd-modal 내 질의: 모달을 닫지 않고 카드 아래에 답변 표시 */
async function bdAsk(q) {
  const cardBox = document.getElementById("bd-card");
  let box = document.getElementById("bd-answer");
  if (!box) {
    box = document.createElement("div");
    box.id = "bd-answer";
    cardBox.appendChild(box);
  }
  box.textContent = `"${q}" 질의 중…`;
  try {
    const r = await (await fetch("/api/query", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: q }),
    })).json();
    box.textContent = r.answer || JSON.stringify(r);
  } catch (err) {
    box.textContent = "질의 실패: " + err;
  }
}

document.addEventListener("DOMContentLoaded", () => {
  const m = document.getElementById("bd-modal");
  if (!m) return;
  document.getElementById("bd-close").onclick = closeBuildingModal;
  m.addEventListener("click", e => { if (e.target === m) closeBuildingModal(); });
  document.getElementById("bd-search").addEventListener("input", bdRenderList);
});

/* ---------- 계획평면도 뷰어 (지도 → 상세도면, v7) ----------
 * calib extents(EPSG:5186) = SVG 최종 뷰포트. 도곽 링(WGS84) 3꼭짓점으로
 * WGS84→시트 단위좌표 아핀 역변환을 풀어 마커를 % 위치로 얹는다.
 * 300m 폭에서 TM 투영은 사실상 아핀 → 오차 mm 수준. */
const SV_SOURCES = { equipment: "eq", manholes: "mh", pumpstations: "ps" };
let svSheet = null;   // 현재 열람 중인 도곽 feature
let svZoom = 2;

function svAffine(ring) {
  // ring: [[lon,lat] x0y0, x1y0, x1y1, x0y1, x0y0]
  const [p0, p1, , p3] = ring;
  const ax = p1[0] - p0[0], ay = p1[1] - p0[1];   // u축 (x0→x1)
  const bx = p3[0] - p0[0], by = p3[1] - p0[1];   // v축 (y0→y1)
  const det = ax * by - ay * bx;
  return (lon, lat) => {
    const dx = lon - p0[0], dy = lat - p0[1];
    const u = (dx * by - dy * bx) / det;          // 0..1 (좌→우)
    const v = (ax * dy - ay * dx) / det;          // 0..1 (하→상)
    return [u, v];
  };
}

async function openSheetViewer(feature) {
  svSheet = feature;
  const p = feature.properties;
  document.getElementById("sv-title").textContent = p.title;
  const orig = document.getElementById("sv-orig");
  orig.href = `/static/${p.svg}`;
  const img = document.getElementById("sv-img");
  img.src = `/static/${p.svg}`;
  document.getElementById("sv-modal").hidden = false;
  svApplyZoom();
  img.onload = () => svRenderMarkers();
  if (img.complete) svRenderMarkers();
}

function svApplyZoom() {
  const body = document.getElementById("sv-body");
  document.getElementById("sv-img").style.width = (body.clientWidth * svZoom) + "px";
  svRenderMarkers();
}

async function svRenderMarkers() {
  if (!svSheet) return;
  const ov = document.getElementById("sv-overlay");
  ov.innerHTML = "";
  const toUV = svAffine(svSheet.geometry.coordinates[0]);
  const checks = document.querySelectorAll("#sv-marks input");
  let n = 0;
  for (const chk of checks) {
    if (!chk.checked) continue;
    const src = chk.dataset.src;
    let gj;
    try { gj = await loadGeojson(`${src}.geojson`); } catch (e) { continue; }
    for (const f of gj.features) {
      if (f.geometry.type !== "Point") continue;
      const [lon, lat] = f.geometry.coordinates;
      const [u, v] = toUV(lon, lat);
      if (u < 0 || u > 1 || v < 0 || v > 1) continue;
      const d = document.createElement("div");
      d.className = `sv-dot ${SV_SOURCES[src]}`;
      d.style.left = (u * 100) + "%";
      d.style.top = ((1 - v) * 100) + "%";
      const t = featureText(f);
      d.title = t;
      if (src === "equipment") d.onclick = () => {
        const key = (f.properties.tag || "").split(" ")[0] || f.properties.label;
        document.getElementById("sv-modal").hidden = true;
        showAssetCard(key);
      };
      ov.appendChild(d); n++;
    }
  }
  document.getElementById("sv-status").textContent =
    `마커 ${n}개 (extents ${svSheet.properties.extents.map(x => Math.round(x).toLocaleString()).join(", ")} · EPSG:5186)`;
}

/* 스크립트가 #sv-modal 마크업보다 먼저 실행되므로 DOM 로드 후 바인딩 */
document.addEventListener("DOMContentLoaded", () => {
  if (!document.getElementById("sv-modal")) return;  // 마크업 없으면 조용히 통과
  document.getElementById("sv-close").onclick = () =>
    document.getElementById("sv-modal").hidden = true;
  document.getElementById("sv-modal").addEventListener("click", e => {
    if (e.target.id === "sv-modal") document.getElementById("sv-modal").hidden = true;
  });
  document.querySelectorAll("#sv-marks input").forEach(c =>
    c.addEventListener("change", svRenderMarkers));
  document.querySelectorAll("#sv-zoom button").forEach(b =>
    b.addEventListener("click", () => {
      svZoom = Number(b.dataset.z);
      document.querySelectorAll("#sv-zoom button").forEach(x => x.classList.toggle("on", x === b));
      svApplyZoom();
    }));
});
