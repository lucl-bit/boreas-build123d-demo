// Modus ④ Vergleich: build123d (B-rep) und PicoGK (Voxel) nebeneinander.
import { StlViewer, partColor, hex } from "/gui/stlview.js";
import { $, $$, api, esc, toast } from "/gui/ui.js";

// ------------------------------------------------------------------ Konstanten
const TOOL_KEYS = ["brep", "voxel"];
const TOOLS = {
  brep: { name: "build123d", sub: "B-rep · Python · OpenCascade", short: "B-rep", color: "#3a8fd8" },
  voxel: { name: "PicoGK", sub: "Voxel · C# · .NET", short: "Voxel", color: "#f2852e" },
};
const STATUS = {
  ok: { label: "ok", icon: "✔", cls: "ok", can: true },
  partial: { label: "teilweise", icon: "◐", cls: "partial", can: true },
  unsupported: { label: "nicht unterstützt", icon: "⊘", cls: "unsup", can: false },
  failed: { label: "fehlgeschlagen", icon: "✘", cls: "failed", can: false },
  not_run: { label: "noch nicht gelaufen", icon: "○", cls: "notrun", can: false },
};
const stat = (s) => STATUS[s] || { label: String(s || "unbekannt"), icon: "?", cls: "notrun", can: false };
const SUPPORT = {
  native: { sym: "●", label: "nativ", cls: "s-native" },
  possible: { sym: "◐", label: "möglich", cls: "s-possible" },
  workaround: { sym: "△", label: "Umweg", cls: "s-workaround" },
  none: { sym: "✕", label: "nicht vorhanden", cls: "s-none" },
};
const sup = (s) => SUPPORT[s] || { sym: "?", label: String(s || "–"), cls: "s-none" };
const BETTER = { brep: "build123d besser", voxel: "PicoGK besser", tie: "Gleichstand" };
const GROUPS = { common: "gemeinsam", brep_only: "nur B-rep", voxel_only: "nur Voxel" };
const SECTIONS = [
  ["common", "Gemeinsame Aufgaben"], ["brep_only", "Nur / besser in B-rep"], ["voxel_only", "Nur / besser in Voxel"],
  ["api", "API & Pipeline"], ["other", "Weitere Aufgaben"],
];

// ------------------------------------------------------------------ Zustand
const C = {
  inited: false, idx: 0, pages: [], index: null, matrix: null, run: null, fill: true, visited: new Set(),
  cache: new Map(), viewers: null, sync: true, syncLock: false, wire: false, seq: 0, abort: null,
  pane: { brep: {}, voxel: {} }, mf: { q: "", cat: "", group: "", brep: "", voxel: "", better: "", diff: false }, lb: { items: [], i: 0 },
};

window.__compare = C;   // Debug-Zugriff in der Browser-Konsole

// ------------------------------------------------------------------ Format-Helfer
const isNum = (v) => typeof v === "number" && isFinite(v);
const fx = (v, d) => isNum(v) ? v.toLocaleString("de-CH", { minimumFractionDigits: d, maximumFractionDigits: d }) : "–";
function auto(v) {
  if (!isNum(v)) return "–";
  if (Number.isInteger(v)) return fx(v, 0);
  const a = Math.abs(v);
  return fx(v, a >= 100 ? 1 : a >= 10 ? 1 : a >= 1 ? 2 : 3);
}
function bytesFmt(b) {
  if (!isNum(b)) return "–";
  return b >= 1048576 ? `${fx(b / 1048576, 1)} MB` : b >= 1024 ? `${fx(b / 1024, 0)} kB` : `${b} B`;
}
const trisFmt = (n) => !isNum(n) ? "–" : n >= 1e6 ? `${fx(n / 1e6, 2)} Mio.` : n >= 1e4 ? `${fx(n / 1e3, 0)} k` : fx(n, 0);
const stripMock = (s) => String(s || "").replace(/^MOCK:\s*/i, "");

// ------------------------------------------------------------------ Daten
async function getJson(url) { return await (await api(url)).json(); }

async function loadIndex() {
  const q = `?${C.run ? `run=${encodeURIComponent(C.run)}&` : ""}fill=${C.fill ? 1 : 0}`;
  C.index = await getJson("/api/compare/index" + q);
  C.run = C.index.run;
  C.cache.clear();
  const sel = $("#cmpRun");
  sel.innerHTML = C.index.runs.map(r => `<option value="${esc(r.id)}" ${r.id === C.run ? "selected" : ""}>${esc(r.label)}</option>`).join("");
  const anyMock = Object.values(C.index.summary).some(r => TOOL_KEYS.some(t => r[t].mock));
  $("#cmpMockChip").style.display = anyMock ? "" : "none";
  $("#chipTime").textContent = C.run ? `Lauf: ${C.run} · ${Object.values(C.index.summary).filter(r => TOOL_KEYS.some(t => r[t].status !== "not_run")).length} Aufgaben mit Ergebnis` : "kein Lauf";
  buildPages();
}

async function loadMatrix() { if (!C.matrix) C.matrix = await getJson("/api/compare/matrix"); return C.matrix; }

async function fetchResult(task, tool) {
  const key = `${C.run}|${C.fill}|${task}|${tool}`;
  if (!C.cache.has(key)) {
    C.cache.set(key, getJson(`/api/compare/result?run=${encodeURIComponent(C.run || "mock")}&task=${task}&tool=${tool}&fill=${C.fill ? 1 : 0}`)
      .catch(e => ({ task, tool, status: "failed", notes: "Ergebnis konnte nicht geladen werden: " + e.message, metrics: {}, files: {}, _meta: { files: [] } })));
  }
  return await C.cache.get(key);
}

function buildPages() {
  const tasks = C.index.tasks;
  const pages = [
    { kind: "doc", id: "overview", chapter: "Übersicht", title: "B-rep vs. Voxel" },
    { kind: "doc", id: "matrix", chapter: "Übersicht", title: "Feature-Matrix" },
  ];
  for (const [key, title] of SECTIONS) {
    for (const t of tasks.filter(t => t.section_key === key)) pages.push({ kind: "task", id: t.id, chapter: title, title: t.title || t.id, task: t });
  }
  pages.push({ kind: "doc", id: "fazit", chapter: "Fazit", title: "Fazit & Empfehlung" });
  C.pages = pages;
}

const pageStatus = (id) => C.index.summary[id] || { brep: { status: "not_run" }, voxel: { status: "not_run" } };

// ------------------------------------------------------------------ Navigation links
function renderNav() {
  let chapter = null, html = "";
  C.pages.forEach((p, i) => {
    if (p.chapter !== chapter) { chapter = p.chapter; html += `<div class="chapter">${esc(chapter)}</div>`; }
    const cls = ["tstep", "cstep", i === C.idx ? "active" : "", C.visited.has(i) && i !== C.idx ? "done" : ""].join(" ");
    const id = p.kind === "task" ? p.id : (p.id === "matrix" ? "▦" : p.id === "fazit" ? "Σ" : "i");
    let dots = "";
    if (p.kind === "task") {
      const st = pageStatus(p.id);
      dots = `<span class="dots">${TOOL_KEYS.map(t => `<i class="dot d-${stat(st[t].status).cls} t-${t}" title="${esc(TOOLS[t].name)}: ${esc(stat(st[t].status).label)}"></i>`).join("")}</span>`;
    }
    html += `<div class="${cls}" data-i="${i}"><span class="num">${esc(id)}</span><span>${esc(p.title)}</span>${dots}</div>`;
  });
  const box = $("#cmpList"); box.innerHTML = html;
  $$(".cstep", box).forEach(el => el.addEventListener("click", () => goPage(+el.dataset.i)));
  $("#cmpProgress").style.width = `${(C.idx + 1) / C.pages.length * 100}%`;
  $("#cmpPrev").disabled = C.idx === 0;
  $("#cmpNext").disabled = C.idx === C.pages.length - 1;
  $("#cmpStepInfo").textContent = `Seite ${C.idx + 1} / ${C.pages.length}`;
}

export function goTask(id) {
  const i = C.pages.findIndex(p => p.id === id);
  if (i >= 0) goPage(i);
}

function goPage(i) {
  C.idx = Math.max(0, Math.min(C.pages.length - 1, i));
  C.visited.add(C.idx);
  renderNav();
  $(".cstep.active")?.scrollIntoView({ block: "nearest" });
  const p = C.pages[C.idx];
  try { history.replaceState(null, "", "#vergleich/" + p.id); } catch { /* egal */ }
  abortLoads();
  const wide = p.kind === "doc";
  document.body.dataset.cmp = wide ? "wide" : "task";
  $("#cmpTask").style.display = wide ? "none" : "";
  $("#cmpDoc").style.display = wide ? "" : "none";
  if (wide) { renderDoc(p); $("#cmpPanel").innerHTML = ""; } else showTask(p);
}

// ------------------------------------------------------------------ Bausteine
function badge(status, extra = "") {
  const s = stat(status);
  return `<span class="sbadge s-${s.cls} ${extra}"><i>${s.icon}</i>${esc(s.label)}</span>`;
}
const toolTag = (t) => `<span class="ttag t-${t}">${esc(TOOLS[t].name)}</span>`;

function verdict(sa, sb) {
  const a = stat(sa), b = stat(sb);
  if (a.can && b.can) {
    if (sa === sb) return { cls: "both", text: "Beide Tools lösen die Aufgabe" };
    const full = sa === "ok" ? "brep" : "voxel", part = full === "brep" ? "voxel" : "brep";
    return { cls: "both-part", text: `${TOOLS[full].name} vollständig, ${TOOLS[part].name} nur teilweise` };
  }
  if (a.can !== b.can) {
    const yes = a.can ? "brep" : "voxel", no = a.can ? "voxel" : "brep", sn = a.can ? sb : sa;
    const text = sn === "unsupported" ? `Nur ${TOOLS[yes].name} unterstützt das`
      : sn === "failed" ? `${TOOLS[no].name} scheitert, ${TOOLS[yes].name} löst die Aufgabe`
        : `${TOOLS[no].name}: noch kein Ergebnis, ${TOOLS[yes].name} liefert`;
    return { cls: "only-" + yes, text };
  }
  return sa === "not_run" && sb === "not_run" ? { cls: "none", text: "Noch nicht gelaufen" } : { cls: "none", text: "Kein Tool hat ein gültiges Ergebnis" };
}

function rich(v) {
  if (v == null || v === "") return "";
  if (typeof v === "string") return `<p>${esc(v)}</p>`;
  if (Array.isArray(v)) return `<ul>${v.map(x => `<li>${typeof x === "string" ? esc(x) : esc(JSON.stringify(x))}</li>`).join("")}</ul>`;
  if (typeof v === "object") return `<ul>${Object.entries(v).map(([k, x]) => `<li><b>${esc(k)}:</b> ${esc(typeof x === "string" ? x : JSON.stringify(x))}</li>`).join("")}</ul>`;
  return `<p>${esc(v)}</p>`;
}

// ------------------------------------------------------------------ Aufgaben-Seite
function ensureViewers() {
  if (C.viewers) return;
  C.viewers = {};
  for (const t of TOOL_KEYS) C.viewers[t] = new StlViewer($(`.cmp-pane[data-tool="${t}"] canvas`), { smooth: t === "brep" });
  for (const [a, b] of [["brep", "voxel"], ["voxel", "brep"]]) {
    C.viewers[a].controls.addEventListener("change", () => {
      if (!C.sync || C.syncLock) return;
      C.syncLock = true;
      try { C.viewers[b].setCam(C.viewers[a].camState()); } finally { C.syncLock = false; }
    });
  }
}

function abortLoads() { C.seq++; C.abort?.abort(); C.abort = null; }

function pickMeshes(res) {
  const m = (res._meta?.files || []).filter(f => f.kind === "mesh" && f.exists);
  const parts = m.filter(f => /^parts\./.test(f.key)).map(f => ({ name: f.key.slice(6), url: f.url, size: f.size, tris: f.tris }));
  if (parts.length) return parts;
  const main = m.find(f => f.key === "mesh");
  if (main) return [{ name: "Modell", url: main.url, size: main.size, tris: main.tris }];
  return m.slice(0, 6).map(f => ({ name: f.key, url: f.url, size: f.size, tris: f.tris }));
}
const pickImages = (res) => {
  const seen = new Set();
  return (res._meta?.files || []).filter(f => (f.kind === "image" || f.kind === "pdf") && f.exists && !seen.has(f.url) && seen.add(f.url));
};

async function showTask(page) {
  ensureViewers();
  const seq = C.seq;
  const t = page.task;
  for (const tool of TOOL_KEYS) {
    C.viewers[tool].clearModel();
    C.pane[tool] = { tab: "info", res: null, meshes: [], images: [], info: null, hidden: new Set() };
    renderPaneShell(tool, null);
  }
  $("#cmpVerdict").innerHTML = `<span class="muted">lädt…</span>`;
  $("#cmpPanel").innerHTML = `<div class="muted small">${esc(page.chapter)} · ${esc(t.id)}</div><h2>${esc(t.title)}</h2><p class="muted">lädt…</p>`;
  const [rb, rv] = await Promise.all(TOOL_KEYS.map(tool => fetchResult(t.id, tool)));
  if (seq !== C.seq) return;
  await loadMatrix().catch(() => null);
  if (seq !== C.seq) return;
  const res = { brep: rb, voxel: rv };
  for (const tool of TOOL_KEYS) {
    const p = C.pane[tool], r = res[tool];
    p.res = r; p.meshes = pickMeshes(r); p.images = pickImages(r);
    const imageFirst = /^(R01|V04)$/.test(t.id);        // Zeichnung bzw. Slices sind hier das eigentliche Ergebnis
    p.tab = p.images.length && (imageFirst || !p.meshes.length) ? "img" : p.meshes.length ? "3d" : "info";
    renderPaneShell(tool, r);
  }
  const v = verdict(rb.status, rv.status);
  $("#cmpVerdict").innerHTML = `<span class="verdict v-${v.cls}">${esc(v.text)}</span>`;
  renderTaskPanel(page, res);
  loadMeshes(seq);
}

/** Lädt die Meshes eines Panes erst, wenn dessen 3D-Tab sichtbar ist (lazy). */
async function loadPane(tool, seq, ctl) {
  const p = C.pane[tool];
  if (!p.meshes.length || p.info || p.loading) return;
  p.loading = true; setLoading(tool, "lädt …");
  try {
    const info = await C.viewers[tool].load(p.meshes, {
      signal: ctl.signal,
      onProgress: (got, total) => setLoading(tool, `lädt ${bytesFmt(got)}${total ? " / " + bytesFmt(total) : ""}`),
    });
    if (seq !== C.seq) return;
    p.info = info; setLoading(tool, null); renderFoot(tool);
  } catch (e) {
    if (e.name === "AbortError" || seq !== C.seq) return;
    setLoading(tool, null); p.error = e.message; renderFoot(tool);
  } finally { p.loading = false; }
}

async function loadMeshes(seq) {
  const ctl = C.abort = new AbortController();
  await Promise.all(TOOL_KEYS.filter(t => C.pane[t].tab === "3d").map(t => loadPane(t, seq, ctl)));
  if (seq === C.seq) fitAll("iso");
}

function fitAll(kind) {
  let box = null;
  for (const t of TOOL_KEYS) { const b = C.viewers[t].bbox(); if (b) box = box ? box.union(b) : b.clone(); }
  if (!box) return;
  C.syncLock = true;
  try { for (const t of TOOL_KEYS) if (C.viewers[t].bbox()) C.viewers[t].fitBox(kind, box); } finally { C.syncLock = false; }
}

function setLoading(tool, text) {
  const el = $(`.cmp-pane[data-tool="${tool}"] .cmp-loading`);
  el.style.display = text ? "" : "none"; el.textContent = text || "";
}

// --- Pane (Kopf, Tabs, Körper, Fuss)
function renderPaneShell(tool, res) {
  const pane = $(`.cmp-pane[data-tool="${tool}"]`), p = C.pane[tool], T = TOOLS[tool];
  const st = res ? res.status : "not_run", s = stat(st);
  pane.className = `cmp-pane cap-${res ? (s.can ? "yes" : "no") : "wait"}`;
  pane.dataset.tool = tool;
  const tabs = [];
  if (p.meshes?.length) tabs.push(["3d", "3D"]);
  if (p.images?.length) tabs.push(["img", `Bilder (${p.images.length})`]);
  tabs.push(["info", "Info"]);
  $(".cmp-head", pane).innerHTML = `
    <span class="tname" style="--tc:${T.color}"><b>${esc(T.name)}</b><small>${esc(T.sub)}</small></span>
    <span class="spacer"></span>
    ${res ? badge(st) : ""}${res?._meta?.mock ? `<span class="mockbadge" title="Beispielwerte, keine Messung">MOCK</span>` : ""}
    <span class="ptabs">${res ? tabs.map(([k, l]) => `<button data-ptab="${k}" class="${p.tab === k ? "on" : ""}">${esc(l)}</button>`).join("") : ""}</span>`;
  $$("[data-ptab]", pane).forEach(b => b.addEventListener("click", async () => {
    p.tab = b.dataset.ptab; applyTab(tool); $$("[data-ptab]", pane).forEach(x => x.classList.toggle("on", x === b)); renderFoot(tool);
    if (p.tab === "3d" && !p.info && C.abort) { const seq = C.seq; await loadPane(tool, seq, C.abort); if (seq === C.seq) fitAll("iso"); }
  }));
  applyTab(tool);
  renderFoot(tool);
}

function applyTab(tool) {
  const pane = $(`.cmp-pane[data-tool="${tool}"]`), p = C.pane[tool];
  const is3d = p.tab === "3d";
  $(".cmp-stage", pane).style.display = is3d ? "" : "none";
  const alt = $(".cmp-alt", pane); alt.style.display = is3d ? "none" : "";
  if (is3d) { C.viewers[tool].resize(); C.viewers[tool].requestRender(); return; }
  alt.innerHTML = !p.res ? `<div class="ph"><div class="ph-title muted">lädt …</div></div>` : p.tab === "img" ? galleryHtml(p) : infoHtml(tool);
  $$("[data-lb]", alt).forEach(el => el.addEventListener("click", () => openLightbox(p.images, +el.dataset.lb)));
}

function galleryHtml(p) {
  const one = p.images.length === 1;
  return `<div class="gallery ${one ? "one" : ""}">${p.images.map((f, i) => f.kind === "pdf"
    ? `<div class="gitem pdf" data-lb="${i}"><div class="pdfico">PDF</div><div class="cap">${esc(f.name)}</div><div class="cap muted">anklicken zum Ansehen</div></div>`
    : `<figure class="gitem" data-lb="${i}"><img src="${f.url}" alt="${esc(f.name)}"><figcaption>${esc(f.name)}</figcaption></figure>`).join("")}</div>`;
}

function relatedFeatures(taskId) { return (C.matrix?.features || []).filter(f => f.task === taskId); }

function infoHtml(tool) {
  const p = C.pane[tool], res = p.res, T = TOOLS[tool];
  const st = res?.status || "not_run", s = stat(st);
  const other = TOOL_KEYS.find(x => x !== tool);
  const oth = C.pane[other].res;
  const hasGeo = p.meshes.length || p.images.length;
  const heads = {
    unsupported: `${T.name} unterstützt diese Aufgabe nicht`,
    failed: `Der Lauf mit ${T.name} ist fehlgeschlagen`,
    not_run: `Für ${T.name} liegt noch kein Ergebnis vor`,
    partial: `${T.name} löst die Aufgabe nur teilweise`,
    ok: hasGeo ? `Notizen zu ${T.name}` : "Diese Aufgabe erzeugt keine Geometrie",
  };
  const generic = {
    unsupported: "Für diese Aufgabe gibt es in diesem Werkzeug keine Funktion; das Ergebnis ist bewusst „nicht unterstützt“ (kein Fehler).",
    failed: "Der Lauf brach ab; es liegt keine verwertbare Geometrie vor. Details in den Notizen oder im Log des Runners.",
    not_run: "Die Aufgabe wurde mit diesem Werkzeug noch nicht gerechnet. Ein Lauf des Benchmark-Runners oder „Neu rechnen“ (rechte Spalte) erzeugt das Ergebnis.",
    partial: "", ok: "Nur Kennzahlen und Notizen, siehe rechte Spalte.",
  };
  const notes = stripMock(res?.notes) || generic[st] || "";
  const rel = relatedFeatures(res?.task || C.pages[C.idx].id).filter(f => f[tool]);
  const otherCan = oth && stat(oth.status).can;
  return `<div class="ph ph-${s.cls}">
    <div class="ph-icon">${s.icon}</div>
    <div class="ph-title">${esc(heads[st] || heads.ok)}</div>
    ${badge(st, "big")}
    ${notes ? `<p class="ph-text">${esc(notes)}</p>` : ""}
    ${!s.can && otherCan ? `<p class="ph-contrast">${esc(TOOLS[other].name)} liefert hier ein Ergebnis (${esc(stat(oth.status).label)}). Der Unterschied ist Teil des Vergleichs.</p>` : ""}
    ${rel.length ? `<div class="ph-rel"><div class="muted small">Feature-Matrix zu dieser Aufgabe</div>${rel.map(f => `<div class="ph-feat"><span class="sup ${sup(f[tool].support).cls}" title="${esc(sup(f[tool].support).label)}">${sup(f[tool].support).sym}</span><b>${esc(f.name)}</b>${f[tool].how ? `<span class="muted"> – ${esc(f[tool].how)}</span>` : ""}</div>`).join("")}</div>` : ""}
  </div>`;
}

function renderFoot(tool) {
  const pane = $(`.cmp-pane[data-tool="${tool}"]`), p = C.pane[tool], foot = $(".cmp-foot", pane);
  let html = "";
  if (p.error) html += `<span class="bad">Ladefehler: ${esc(p.error)}</span>`;
  if (p.meshes?.length && p.tab === "3d") {
    html += p.meshes.length > 1 || p.meshes[0].name !== "Modell"
      ? p.meshes.map((m, i) => { const c = partColor(m.name, i); return `<span class="pchip ${p.hidden?.has(m.name) ? "off" : ""}" data-part="${esc(m.name)}"><i style="background:${hex(c)}"></i>${esc(m.name)}</span>`; }).join("")
      : "";
    if (p.info) html += `<span class="fstat">${trisFmt(p.info.tris)} Dreiecke · ${p.meshes.reduce((a, m) => a + (m.size || 0), 0) ? bytesFmt(p.meshes.reduce((a, m) => a + (m.size || 0), 0)) + " · " : ""}geladen in ${fx(p.info.ms, 0)} ms</span>`;
    else if (p.meshes.some(m => m.tris)) html += `<span class="fstat">${trisFmt(p.meshes.reduce((a, m) => a + (m.tris || 0), 0))} Dreiecke</span>`;
  }
  const missing = (p.res?._meta?.files || []).filter(f => !f.exists);
  if (missing.length) html += `<span class="bad" title="${esc(missing.map(f => f.path).join(", "))}">Datei fehlt: ${esc(missing[0].path)}${missing.length > 1 ? ` (+${missing.length - 1})` : ""}</span>`;
  foot.innerHTML = html;
  $$("[data-part]", foot).forEach(el => el.addEventListener("click", () => {
    const n = el.dataset.part, off = !p.hidden.has(n);
    off ? p.hidden.add(n) : p.hidden.delete(n);
    el.classList.toggle("off", off); C.viewers[tool].setPartVisible(n, !off);
  }));
}

// --- Kennzahlen
const ROWS = [
  ["Geometrie", "volume", "Volumen", "cm³", false], ["Geometrie", "area", "Fläche", "cm²", false], ["Geometrie", "mass", "Masse", "g", false],
  ["Ausführung", "runtime_s", "Laufzeit", "s", true], ["Ausführung", "peak_mem_mb", "RAM (Peak)", "MB", true], ["Ausführung", "code_loc", "Codezeilen", "", true],
  ["Dateien", "tris", "Dreiecke (STL)", "", false], ["Dateien", "stl_size", "Dateigrösse STL", "", true], ["Dateien", "step_size", "Dateigrösse STEP", "", true],
];
const UNIT_SFX = { mm3: "mm³", mm2: "mm²", mm: "mm", pct: "%", g: "g", s: "s", mb: "MB", kg: "kg", n: "N" };

function knownValues(res) {
  const m = res?.metrics || {}, files = res?._meta?.files || [];
  const meshes = files.filter(f => f.kind === "mesh" && f.exists);
  const steps = files.filter(f => /\.(step|stp)$/.test(f.ext) && f.exists);
  const uniq = (arr) => [...new Map(arr.map(f => [f.url, f])).values()];
  const sum = (arr, k) => arr.length ? uniq(arr).reduce((a, f) => a + (f[k] || 0), 0) : null;
  return {
    volume: isNum(m.volume_mm3) ? m.volume_mm3 / 1000 : null, area: isNum(m.area_mm2) ? m.area_mm2 / 100 : null, mass: isNum(m.mass_g) ? m.mass_g : null,
    runtime_s: res?.status === "not_run" || res?.status === "unsupported" ? null : res?.runtime_s, peak_mem_mb: res?.peak_mem_mb, code_loc: res?.code_loc,
    tris: sum(meshes, "tris") || null, stl_size: sum(meshes, "size"), step_size: sum(steps, "size"),
  };
}
const SKIP_EXTRA = new Set(["volume_mm3", "area_mm2", "mass_g", "bbox_mm", "parts"]);
function humanKey(k) {
  const m = k.match(/^(.*?)_(mm3|mm2|mm|pct|g|s|mb|kg|n)$/);
  const base = (m ? m[1] : k).replace(/_/g, " ");
  return { label: base.charAt(0).toUpperCase() + base.slice(1), unit: m ? UNIT_SFX[m[2]] : "" };
}
const fmtVal = (v, unitKind) => unitKind === "size" ? bytesFmt(v) : isNum(v) ? auto(v) : v == null ? "–" : String(v);

function delta(a, b) {
  if (!isNum(a) || !isNum(b)) return "";
  const d = b - a;
  if (Math.abs(d) < 1e-9 * Math.max(1, Math.abs(a))) return `<span class="muted">=</span>`;
  const sign = d > 0 ? "+" : "−";
  if (a !== 0) { const p = Math.abs(d / a * 100); return `${sign}${p < 10 ? fx(p, 1) : fx(p, 0)} %`; }
  return `${sign}${auto(Math.abs(d))}`;
}

function metricsHtml(A, B) {
  const ka = knownValues(A), kb = knownValues(B);
  const rows = ROWS.map(r => ({ group: r[0], key: r[1], label: r[2], unit: r[3], lower: r[4], a: ka[r[1]], b: kb[r[1]], size: /_size$/.test(r[1]) }));
  const extras = new Set([...Object.keys(A.metrics || {}), ...Object.keys(B.metrics || {})].filter(k => !SKIP_EXTRA.has(k)));
  for (const k of extras) {
    const va = A.metrics?.[k], vb = B.metrics?.[k], h = humanKey(k);
    if ((va != null && typeof va === "object") || (vb != null && typeof vb === "object")) continue;
    rows.push({ group: "Aufgabenspezifisch", key: k, label: h.label, unit: h.unit, lower: /dev|abw|err|fehler/i.test(k), a: va, b: vb });
  }
  const bb = (r) => Array.isArray(r.metrics?.bbox_mm) && r.metrics.bbox_mm.length === 6 ? r.metrics.bbox_mm : null;
  const ba = bb(A), bv = bb(B);
  const dims = (b) => b ? [0, 1, 2].map(i => b[i + 3] - b[i]) : null;
  let html = `<table class="mtable"><tr><th>Kennzahl</th><th class="n ct-brep">build123d</th><th class="n ct-voxel">PicoGK</th><th class="n" title="PicoGK relativ zu build123d">Δ</th></tr>`;
  let group = null;
  const line = (label, unit, a, b, dl, lower, cells) => {
    let ca = cells ? cells[0] : fmtVal(a, null), cb = cells ? cells[1] : fmtVal(b, null);
    const win = lower && isNum(a) && isNum(b) && a !== b ? (a < b ? "a" : "b") : "";
    return `<tr><td>${esc(label)}${unit ? ` <span class="u">${esc(unit)}</span>` : ""}</td>
      <td class="n ${a == null ? "muted" : ""} ${win === "a" ? "win" : ""}">${ca}</td><td class="n ${b == null ? "muted" : ""} ${win === "b" ? "win" : ""}">${cb}</td><td class="n dl">${dl}</td></tr>`;
  };
  let any = false;
  for (const r of rows) {
    if (r.a == null && r.b == null) continue;
    any = true;
    if (r.group !== group) { group = r.group; html += `<tr class="grp"><td colspan="4">${esc(group)}</td></tr>`; }
    const cells = r.size ? [r.a == null ? "–" : bytesFmt(r.a), r.b == null ? "–" : bytesFmt(r.b)] : null;
    html += line(r.label, r.unit, r.a, r.b, delta(r.a, r.b), r.lower, cells);
    if (r.key === "mass") {
      const da = dims(ba), dv = dims(bv);
      if (da || dv) html += line("Bauraum X×Y×Z", "mm", null, null, "", false, [da ? da.map(x => fx(x, 0)).join(" × ") : "–", dv ? dv.map(x => fx(x, 0)).join(" × ") : "–"]);
    }
  }
  html += "</table>";
  const pa = A.metrics?.parts || {}, pb = B.metrics?.parts || {};
  const names = [...new Set([...Object.keys(pa), ...Object.keys(pb)])];
  let parts = "";
  if (names.length) {
    parts = `<h3>Teile · Volumen</h3><table class="mtable"><tr><th>Teil</th><th class="n ct-brep">build123d</th><th class="n ct-voxel">PicoGK</th><th class="n">Δ</th></tr>` +
      names.map((n, i) => {
        const a = pa[n]?.volume_mm3, b = pb[n]?.volume_mm3;
        return `<tr><td><i class="pdot" style="background:${hex(partColor(n, i))}"></i>${esc(n)} <span class="u">cm³</span></td><td class="n ${a == null ? "muted" : ""}">${a == null ? "–" : fx(a / 1000, 2)}</td>
          <td class="n ${b == null ? "muted" : ""}">${b == null ? "–" : fx(b / 1000, 2)}</td><td class="n dl">${delta(a, b)}</td></tr>`;
      }).join("") + "</table>";
  }
  return (any ? html : `<p class="muted">Keine Kennzahlen vorhanden (die Aufgabe liefert keine Zahlen oder ist nicht gelaufen).</p>`) + parts;
}

// --- Rechte Spalte einer Aufgabe
function filesHtml(tool, res) {
  const files = res._meta?.files || [];
  const seen = new Set(), list = files.filter(f => !seen.has(f.url) && seen.add(f.url));
  if (!list.length) return `<div class="muted small">keine Dateien</div>`;
  return list.map(f => {
    if (!f.exists) return `<div class="frow missing"><span class="fk">${esc(f.key)}</span><span class="fn">${esc(f.name)}</span><span class="bad">fehlt</span></div>`;
    const view = f.kind === "image" || f.kind === "pdf";
    return `<div class="frow"><span class="fk">${esc(f.key.replace(/^parts\./, "Teil: "))}</span>
      <a class="fn" href="${f.url}?dl=1" download title="Herunterladen">${esc(f.name)}</a>
      <span class="muted">${bytesFmt(f.size)}${f.tris ? " · " + trisFmt(f.tris) + " △" : ""}</span>
      ${view ? `<a href="#" class="view" data-open="${esc(f.url)}">ansehen</a>` : ""}</div>`;
  }).join("");
}

const GOALS = { 1: "Funktionsvergleich", 2: "Limitierungen", 3: "B-rep vs. Voxel, Aero und Kühlung", 4: "API und KI-Agents", 5: "Design-Automation-Pipeline" };
const goalList = (t) => [].concat(t.plan_goals ?? t.plan_goal ?? []).flatMap(g => typeof g === "string" ? g.match(/\d/g) || [] : [g]).map(Number).filter(g => g > 0);
const expectOf = (t, tool) => { const e = t.expected?.[tool]; return e && typeof e === "object" ? e : null; };

function procHtml(p) {
  if (!p || typeof p !== "object" || Array.isArray(p)) return rich(p);
  const lab = { common: "Gemeinsam", brep: toolTag("brep"), voxel: toolTag("voxel") };
  return `<ul>${Object.entries(p).map(([k, v]) => `<li>${lab[k] || `<b>${esc(k)}</b>`} ${esc(typeof v === "string" ? v : JSON.stringify(v))}</li>`).join("")}</ul>`;
}
function expectedHtml(t) {
  if (!t.expected || typeof t.expected !== "object") return rich(t.expected);
  return `<ul>${TOOL_KEYS.filter(k => t.expected[k]).map(k => { const e = t.expected[k];
    return `<li>${toolTag(k)} ${e.status ? badge(e.status) : ""} ${esc(e.reasoning || (typeof e === "string" ? e : ""))}</li>`; }).join("")}</ul>
    <div class="muted small">Hypothese aus der Recherche; der Benchmark bestätigt oder widerlegt sie.</div>`;
}
function linksHtml(list) {
  return `<ul>${[].concat(list).map(s => /^https?:\/\//.test(s) ? `<li><a href="${esc(s)}" target="_blank" rel="noopener noreferrer">${esc(s)}</a></li>` : `<li>${esc(s)}</li>`).join("")}</ul>`;
}

function renderTaskPanel(page, res) {
  const t = page.task, A = res.brep, B = res.voxel;
  const v = verdict(A.status, B.status);
  const mockTools = TOOL_KEYS.filter(k => res[k]._meta?.mock);
  const feats = relatedFeatures(t.id);
  const av = C.index.tools;
  const rerun = (tool) => {
    const a = av[tool];
    return `<span title="${a.available ? "" : esc(a.reason + " – Berechnung nicht möglich")}"><button class="btn bt-${tool}" data-rerun="${tool}" ${a.available ? "" : "disabled"}>${esc(TOOLS[tool].name)} neu rechnen</button></span>`;
  };
  const html = `
    <div class="muted small">${esc(page.chapter)} · ${esc(t.id)}</div>
    <h2>${esc(t.title)}</h2>
    ${goalList(t).length ? `<div class="goals">${goalList(t).map(g => `<span class="gchip" title="Projektziel ${g}: ${esc(GOALS[g] || "")}">Ziel ${g}${GOALS[g] ? ` · ${esc(GOALS[g])}` : ""}</span>`).join("")}</div>` : ""}
    ${t.goal ? `<p class="lead">${esc(t.goal)}</p>` : ""}
    ${mockTools.length ? `<div class="mockbanner"><b>Mock-Daten</b> – ${mockTools.map(k => TOOLS[k].name).join(" und ")}: Beispielwerte zur Demonstration der Oberfläche, keine Messung.</div>` : ""}
    <div class="statusrow">
      ${TOOL_KEYS.map(k => { const ex = expectOf(t, k)?.status, st = res[k].status;
        const exl = !ex ? "" : st === "not_run" ? `<div class="expect">erwartet: ${esc(stat(ex).label)}</div>`
          : ex === st ? `<div class="expect ok">erwartet: ${esc(stat(ex).label)} · bestätigt</div>` : `<div class="expect diff">erwartet: ${esc(stat(ex).label)} · weicht ab</div>`;
        return `<div class="scard t-${k}"><div class="sc-h">${toolTag(k)}<span class="muted small">${esc(res[k].tool_version || "")}</span></div>${badge(st, "big")}${exl}</div>`; }).join("")}
    </div>
    <div class="verdict v-${v.cls} wide">${esc(v.text)}</div>
    <h3>Kennzahlen im Vergleich</h3>
    ${metricsHtml(A, B)}
    <h3>Notizen</h3>
    ${TOOL_KEYS.map(k => `<div class="note-t t-${k}"><div class="nt-h">${toolTag(k)}</div>${esc(res[k].notes || (res[k].status === "not_run" ? "Noch kein Ergebnis." : "–"))}</div>`).join("")}
    <h3>Dateien</h3>
    ${TOOL_KEYS.map(k => `<div class="files t-${k}"><div class="nt-h">${toolTag(k)}</div>${filesHtml(k, res[k])}</div>`).join("")}
    ${feats.length ? `<h3>Feature-Matrix zu ${esc(t.id)}</h3>${feats.map(f => `<div class="mxmini"><div class="mxm-n"><b>${esc(f.name)}</b> ${f.better ? `<span class="better b-${f.better}">${esc(BETTER[f.better] || f.better)}</span>` : ""}</div>
      <div class="mxm-r">${TOOL_KEYS.map(k => `<span class="sup ${sup(f[k]?.support).cls}" title="${esc(sup(f[k]?.support).label)}">${sup(f[k]?.support).sym}</span> ${esc(TOOLS[k].short)}: ${esc(f[k]?.how || sup(f[k]?.support).label)}`).join("<br>")}</div></div>`).join("")}` : ""}
    <details class="codebox"><summary>Aufgabenstellung (Vorgehen, Metriken, Erfolgskriterium)</summary>
      ${t.procedure ? `<div class="rich"><b>Vorgehen</b>${procHtml(t.procedure)}</div>` : ""}
      ${t.metrics ? `<div class="rich"><b>Metriken</b>${rich(t.metrics)}</div>` : ""}
      ${(t.success_criteria ?? t.success) ? `<div class="rich"><b>Erfolgskriterium</b>${rich(t.success_criteria ?? t.success)}</div>` : ""}
      ${t.expected ? `<div class="rich"><b>Erwartung</b>${expectedHtml(t)}</div>` : ""}
      ${t.depends_on?.length ? `<div class="rich"><b>Abhängig von</b> ${t.depends_on.map(d => `<a href="#" data-goto="${esc(d)}">${esc(d)}</a>`).join(", ")}</div>` : ""}
      ${t.evidence?.length ? `<div class="rich"><b>Belege</b>${linksHtml(t.evidence)}</div>` : ""}
      ${t._mock ?`<div class="muted small">Aufgabendefinition aus der Mock-Kopie (spec/benchmark_tasks.json enthält diese ID nicht).</div>` : ""}
    </details>
    <details class="codebox rerun"><summary>Neu rechnen (CLI-Aufruf)</summary>
      <label class="rr">Überschreibungen <span class="muted">(gruppe.param=wert, durch Komma getrennt)</span><input id="rrSets" type="text" placeholder="body_fins.profile_chord=60"></label>
      <label class="rr">Voxelgrösse [mm] <input id="rrVox" type="number" step="0.05" min="0.05" value="${esc(B.params?.voxel_size_mm ?? 0.5)}"></label>
      <div class="grid2">${rerun("brep")}${rerun("voxel")}</div>
      <div class="muted small" id="rrOut">Ergebnisse landen in bench/results/live/${esc(t.id)}/… und erscheinen im Lauf „live“.</div>
    </details>
    <div class="timing">Lauf: ${esc(C.run || "–")} · Laufzeit build123d ${A.runtime_s != null ? fx(A.runtime_s, 2) + " s" : "–"} · PicoGK ${B.runtime_s != null ? fx(B.runtime_s, 2) + " s" : "–"}</div>`;
  const panel = $("#cmpPanel"); panel.innerHTML = html;
  $$("[data-open]", panel).forEach(a => a.addEventListener("click", e => {
    e.preventDefault();
    const items = pickImages(A).concat(pickImages(B)); const i = items.findIndex(f => f.url === a.dataset.open);
    openLightbox(items, Math.max(0, i));
  }));
  $$("[data-rerun]", panel).forEach(b => b.addEventListener("click", () => rerunTool(t.id, b.dataset.rerun)));
  bindDoc(panel);
}

async function rerunTool(task, tool) {
  const sets = ($("#rrSets")?.value || "").split(",").map(s => s.trim()).filter(Boolean);
  const btns = $$("[data-rerun]"); btns.forEach(b => b.disabled = true);
  $("#rrOut").textContent = `${TOOLS[tool].name} rechnet … (kann mehrere Minuten dauern)`;
  $("#busy").textContent = `${TOOLS[tool].name} rechnet ${task} …`; $("#busy").classList.add("on");
  try {
    const r = await (await api("/api/compare/run", { task, tool, sets, voxel: tool === "voxel" ? +$("#rrVox").value : undefined })).json();
    if (!r.has_result) { toast(`${TOOLS[tool].name}: kein result.json erzeugt (Exit ${r.returncode}). ${r.stderr.slice(-300)}`); $("#rrOut").textContent = r.stderr || r.stdout; return; }
    C.run = "live"; await loadIndex(); goPage(C.idx);
    toast(`Neu gerechnet in ${r.seconds.toFixed(1)} s (Lauf „live“).`);
  } catch (e) { toast("Neu rechnen: " + e.message); $$("[data-rerun]").forEach(b => { b.disabled = false; }); }
  finally { $("#busy").classList.remove("on"); }
}

// ------------------------------------------------------------------ Lightbox
function openLightbox(items, i) {
  C.lb = { items, i };
  $("#cmpLightbox").classList.add("on"); drawLightbox();
}
function drawLightbox() {
  const { items, i } = C.lb, f = items[i]; if (!f) return;
  $("#lbTitle").textContent = `${f.name}  (${i + 1}/${items.length})`;
  $("#lbDl").href = f.url + "?dl=1";
  $("#lbBody").innerHTML = f.kind === "pdf" ? `<iframe src="${f.url}" title="${esc(f.name)}"></iframe>` : `<img src="${f.url}" alt="${esc(f.name)}">`;
  $("#lbPrev").style.visibility = $("#lbNext").style.visibility = items.length > 1 ? "visible" : "hidden";
}
const lbStep = (d) => { C.lb.i = (C.lb.i + d + C.lb.items.length) % C.lb.items.length; drawLightbox(); };
const lbClose = () => { $("#cmpLightbox").classList.remove("on"); $("#lbBody").innerHTML = ""; };

// ------------------------------------------------------------------ Dokument-Seiten
function renderDoc(p) {
  const el = $("#cmpDoc");
  const done = (html) => { el.innerHTML = `<div class="doc-wrap">${html}</div>`; el.scrollTop = 0; bindDoc(el); };
  const src = C.index.tasks_source;
  const mock = src === "spec" ? "" : `<div class="mockbanner">Aufgabendefinitionen: ${src === "spec+mock"
    ? "aus spec/benchmark_tasks.json, fehlende IDs aus der Mock-Kopie (bench/results/mock/benchmark_tasks.json)."
    : "aus der Mock-Kopie (bench/results/mock/benchmark_tasks.json), weil spec/benchmark_tasks.json noch fehlt."}</div>`;
  const anyMock = Object.values(C.index.summary).some(r => TOOL_KEYS.some(t => r[t].mock));
  const banner = anyMock ? `<div class="mockbanner"><b>Mock-Daten</b> – ein Teil der Ergebnisse stammt aus bench/results/mock/ (Beispielwerte, keine Messung). Echte Läufe ersetzen sie automatisch, sobald bench/results/latest/ befüllt ist.</div>` : "";
  if (p.id === "overview") return loadMatrix().catch(() => null).then(() => done(banner + mock + overviewHtml()));
  if (p.id === "matrix") return loadMatrix().then(m => { done(matrixShell(m)); renderMatrixTable(); }).catch(e => done(`<p class="bad">Feature-Matrix nicht ladbar: ${esc(e.message)}</p>`));
  if (p.id === "fazit") return loadMatrix().catch(() => null).then(() => done(banner + fazitHtml()));
}

function bindDoc(el) {
  $$("[data-goto]", el).forEach(a => a.addEventListener("click", e => { e.preventDefault(); goTask(a.dataset.goto); }));
}

// --- Übersicht
function profilePts(n, t = 0.3) {           // NACA-Tropfenprofil (Halbdicke)
  const yt = (x) => 5 * t * (0.2969 * Math.sqrt(x) - 0.126 * x - 0.3516 * x * x + 0.2843 * x ** 3 - 0.1036 * x ** 4);
  return { yt, pts: Array.from({ length: n + 1 }, (_, i) => { const x = i / n; return [x, yt(x)]; }) };
}
function conceptSvg(kind) {
  const W = 320, H = 130, X0 = 14, L = 290, cy = H / 2, { yt, pts } = profilePts(80);
  const px = (x) => X0 + x * L, py = (y) => cy - y * L;
  const outline = [...pts.map(([x, y]) => `${px(x)},${py(y)}`), ...pts.slice().reverse().map(([x, y]) => `${px(x)},${py(-y)}`)].join(" ");
  if (kind === "brep") {
    const ctrl = [0.04, 0.2, 0.4, 0.62, 0.85].map(x => `<rect x="${px(x) - 3}" y="${py(yt(x)) - 3}" width="6" height="6" class="cp"/>`).join("");
    return `<svg viewBox="0 0 ${W} ${H}" class="concept-svg"><polygon points="${outline}" class="c-fill"/><polyline points="${outline}" class="c-line"/>${ctrl}
      <text x="${W - 6}" y="${H - 6}" text-anchor="end" class="c-txt">exakte Kurve (Spline) – Punkte sind Stützstellen</text></svg>`;
  }
  const h = 10; let cells = "";
  for (let i = 0; i < Math.floor(L / h); i++) for (let j = -6; j < 6; j++) {
    const xc = (i + .5) * h / L, yc = -(j + .5) * h / L;
    if (xc <= 1 && Math.abs(yc) <= yt(xc)) cells += `<rect x="${X0 + i * h}" y="${cy + j * h}" width="${h - 1}" height="${h - 1}"/>`;
  }
  return `<svg viewBox="0 0 ${W} ${H}" class="concept-svg"><g class="v-cells">${cells}</g><polyline points="${outline}" class="c-ghost"/>
    <text x="${W - 6}" y="${H - 6}" text-anchor="end" class="c-txt">Raster aus Zellen (Voxel) – Genauigkeit = Zellgrösse</text></svg>`;
}

function overviewHtml() {
  const feats = C.matrix?.features || [];
  const cats = [...new Set([...(C.matrix?.categories || []), ...feats.map(f => f.category)])];
  const tally = { brep: 0, voxel: 0, tie: 0 };
  feats.forEach(f => { if (tally[f.better] != null) tally[f.better]++; });
  const bars = cats.map(c => {
    const fs = feats.filter(f => f.category === c), n = fs.length || 1;
    const cnt = (b) => fs.filter(f => f.better === b).length;
    return `<div class="mbar"><div class="mb-l">${esc(c)}<span class="muted"> · ${fs.length}</span></div><div class="mb-b">
      ${["brep", "tie", "voxel"].map(b => cnt(b) ? `<span class="seg b-${b}" style="flex:${cnt(b)}" title="${esc(BETTER[b])}: ${cnt(b)}">${cnt(b)}</span>` : "").join("")}</div></div>`;
  }).join("");
  const tiles = C.pages.filter(p => p.kind === "task").map(p => {
    const st = pageStatus(p.id);
    return `<a href="#" class="tile" data-goto="${esc(p.id)}" title="${esc(p.title)}"><b>${esc(p.id)}</b><span>${esc(p.title)}</span>
      <span class="tdots">${TOOL_KEYS.map(t => `<i class="dot d-${stat(st[t].status).cls} t-${t}" title="${esc(TOOLS[t].name)}: ${esc(stat(st[t].status).label)}"></i>`).join("")}</span></a>`;
  }).join("");
  return `
    <h1>Zwei Arten, Geometrie zu beschreiben</h1>
    <p class="lead">Der Benchmark stellt dieselben Aufgaben am Boreas-Rumpf mit einem <b>B-rep-Kernel</b> (build123d) und einem <b>Voxel-Kernel</b> (PicoGK) und legt die Ergebnisse nebeneinander. Links steht immer build123d, rechts PicoGK.</p>
    <div class="concept">
      <div class="ccard t-brep"><h3>${toolTag("brep")} B-rep · Boundary Representation</h3>${conceptSvg("brep")}
        <p>Ein Körper besteht aus <b>Flächen, Kanten und Ecken</b> mit exakter Mathematik (Ebene, Zylinder, Spline). Was gemessen, bemasst oder gefertigt wird, bezieht sich auf diese exakte Beschreibung.</p>
        <ul><li class="pro">exakte Masse, Toleranzen, Passungen</li><li class="pro">bemasste Zeichnung, STEP, Constraints, Baugruppen</li><li class="pro">Änderung einzelner Parameter, inkrementelles Neurechnen</li><li class="con">Booleans, Shells und Fillets können an komplexen Stellen scheitern</li><li class="con">Gitterstrukturen mit tausenden Streben sind langsam</li></ul></div>
      <div class="ccard t-voxel"><h3>${toolTag("voxel")} Voxel · Rasterfeld</h3>${conceptSvg("voxel")}
        <p>Ein Körper ist ein <b>3D-Raster aus Zellen</b> fester Grösse (Signed-Distance-Feld). Formen entstehen durch Rechnen mit Feldern; es gibt keine einzelnen Flächen oder Kanten mehr.</p>
        <ul><li class="pro">Booleans, Offsets und Glättung sind immer definiert</li><li class="pro">Lattice, konforme Kanäle, feldbasierte Wandstärken</li><li class="pro">arbeitet direkt mit Meshes und Scans; Slices für den Druck</li><li class="con">Genauigkeit ≈ Zellgrösse; Speicher wächst kubisch mit der Auflösung</li><li class="con">keine Bemassung, kein STEP mit exakten Flächen, keine Constraints</li></ul></div>
    </div>
    <h3>So liest sich der Vergleich</h3>
    <div class="legendbox">
      <div>${Object.keys(STATUS).map(k => badge(k)).join(" ")}</div>
      <div class="muted small">„nicht unterstützt“ ist ein Ergebnis, kein Fehler: das Werkzeug kann die Aufgabe konzeptionell nicht. „fehlgeschlagen“ heisst: es sollte gehen, der Lauf brach aber ab.</div>
      <div>${toolTag("brep")} blau = build123d (links) · ${toolTag("voxel")} orange = PicoGK (rechts) · <span class="win">grün</span> = besserer Wert (bei Laufzeit, RAM, Codezeilen, Dateigrösse)</div>
    </div>
    <h3>Feature-Matrix auf einen Blick <a href="#" class="more" data-goto="matrix">zur vollständigen Matrix →</a></h3>
    ${feats.length ? `<div class="mbars">${bars}</div>
      <div class="mlegend"><span class="seg b-brep">${tally.brep}</span> build123d besser <span class="seg b-tie">${tally.tie}</span> Gleichstand <span class="seg b-voxel">${tally.voxel}</span> PicoGK besser
      <span class="muted"> · ${feats.length} Merkmale${C.matrix._mock ? " (Mock-Matrix)" : ""}</span></div>` : `<p class="muted">Keine Feature-Matrix gefunden (spec/feature_matrix.json).</p>`}
    <h3>Aufgaben auf einen Blick</h3>
    <div class="tiles">${tiles}</div>`;
}

// --- Feature-Matrix
function matrixShell(m) {
  const cats = [...new Set([...(m.categories || []), ...m.features.map(f => f.category)])];
  const opt = (arr, all) => `<option value="">${all}</option>` + arr.map(([v, l]) => `<option value="${esc(v)}">${esc(l)}</option>`).join("");
  const supOpts = ["native", "possible", "workaround", "none"].map(k => [k, `${sup(k).sym} ${sup(k).label}`]);
  return `<h1>Feature-Matrix</h1>
    <p class="lead">Welche Funktion bieten die beiden Werkzeuge, wie, und wer ist besser? ${m._mock ? `<b class="warn">Mock-Matrix</b> (bench/results/mock/feature_matrix.json) – wird durch spec/feature_matrix.json ersetzt, sobald vorhanden.` : `Quelle: spec/feature_matrix.json.`}</p>
    <div class="mxlegend">${Object.entries(SUPPORT).map(([k, s]) => `<span class="sup ${s.cls}">${s.sym}</span> ${esc(s.label)}${m.legend?.[k] ? `<span class="muted"> (${esc(typeof m.legend[k] === "string" ? m.legend[k] : JSON.stringify(m.legend[k]))})</span>` : ""}`).join(" &nbsp; ")}</div>
    <div class="mxfilter">
      <input type="search" id="mfQ" placeholder="Suchen (Name, Erklärung, Beleg) …" value="${esc(C.mf.q)}">
      <select id="mfCat">${opt(cats.map(c => [c, c]), "alle Kategorien")}</select>
      <select id="mfGroup">${opt(Object.entries(GROUPS), "alle Gruppen")}</select>
      <select id="mfBrep">${opt(supOpts, "build123d: alle")}</select>
      <select id="mfVoxel">${opt(supOpts, "PicoGK: alle")}</select>
      <select id="mfBetter">${opt(Object.entries(BETTER), "besser: alle")}</select>
      <label class="check-row"><input type="checkbox" id="mfDiff"> nur Unterschiede</label>
      <button class="btn" id="mfReset">Zurücksetzen</button>
    </div>
    <div id="mxCount" class="muted small"></div>
    <div id="mxTable"></div>`;
}

function renderMatrixTable() {
  const m = C.matrix, f = C.mf;
  for (const [id, key] of [["mfQ", "q"], ["mfCat", "cat"], ["mfGroup", "group"], ["mfBrep", "brep"], ["mfVoxel", "voxel"], ["mfBetter", "better"]]) {
    const el = $("#" + id); if (!el) return;
    el.value = f[key];
    if (!el._bound) { el._bound = true; el.addEventListener(el.tagName === "INPUT" ? "input" : "change", () => { f[key] = el.value; renderMatrixTable(); }); }
  }
  const d = $("#mfDiff"); d.checked = f.diff;
  if (!d._bound) { d._bound = true; d.addEventListener("change", () => { f.diff = d.checked; renderMatrixTable(); }); }
  const rb = $("#mfReset");
  if (!rb._bound) { rb._bound = true; rb.addEventListener("click", () => { Object.assign(C.mf, { q: "", cat: "", group: "", brep: "", voxel: "", better: "", diff: false }); renderMatrixTable(); }); }
  const q = f.q.trim().toLowerCase();
  const list = m.features.filter(x =>
    (!f.cat || x.category === f.cat) && (!f.group || x.group === f.group) && (!f.brep || x.brep?.support === f.brep) && (!f.voxel || x.voxel?.support === f.voxel) &&
    (!f.better || x.better === f.better) && (!f.diff || x.brep?.support !== x.voxel?.support) &&
    (!q || [x.id, x.name, x.why, x.brep?.how, x.voxel?.how, x.task, ...(x.sources || [])].join(" ").toLowerCase().includes(q)));
  $("#mxCount").textContent = `${list.length} von ${m.features.length} Merkmalen`;
  const cats = [...new Set([...(m.categories || []), ...m.features.map(x => x.category)])].filter(c => list.some(x => x.category === c));
  const cell = (s) => `<td class="mxc"><span class="sup ${sup(s?.support).cls}" title="${esc(sup(s?.support).label)}">${sup(s?.support).sym}</span> <span class="mx-l">${esc(sup(s?.support).label)}</span>${s?.how ? `<div class="mx-how">${esc(s.how)}</div>` : ""}</td>`;
  let html = `<table class="mxt"><tr><th>ID</th><th>Merkmal</th><th>Aufg.</th><th class="ct-brep">build123d</th><th class="ct-voxel">PicoGK</th><th>Besser</th></tr>`;
  for (const c of cats) {
    html += `<tr class="grp"><td colspan="6">${esc(c)}</td></tr>`;
    for (const x of list.filter(x => x.category === c)) {
      const diff = x.brep?.support !== x.voxel?.support;
      html += `<tr class="mxr ${diff ? "diff" : ""}" data-f="${esc(x.id)}"><td class="muted">${esc(x.id)}</td>
        <td><b>${esc(x.name)}</b>${x.group ? `<div><span class="gchip g-${esc(x.group)}">${esc(GROUPS[x.group] || x.group)}</span></div>` : ""}</td>
        <td>${x.task ? `<a href="#" data-goto="${esc(x.task)}">${esc(x.task)}</a>` : `<span class="muted">–</span>`}</td>
        ${cell(x.brep)}${cell(x.voxel)}
        <td>${x.better ? `<span class="better b-${esc(x.better)}">${esc(BETTER[x.better] || x.better)}</span>` : ""}</td></tr>
        <tr class="mxd" data-d="${esc(x.id)}" style="display:none"><td></td><td colspan="5"><div class="mxwhy">${x.why ? `<p>${esc(x.why)}</p>` : ""}${(x.sources || []).length ? `<div class="muted small">Belege: ${x.sources.map(s => /^https?:\/\//.test(s) ? `<a href="${esc(s)}" target="_blank" rel="noopener noreferrer">${esc(s)}</a>` : esc(s)).join(" · ")}</div>` : `<div class="muted small">keine Belege hinterlegt</div>`}</div></td></tr>`;
    }
  }
  html += "</table>";
  if (!list.length) html = `<p class="muted">Keine Merkmale für diese Filter.</p>`;
  $("#mxTable").innerHTML = html;
  $$(".mxr", $("#mxTable")).forEach(tr => tr.addEventListener("click", e => {
    if (e.target.closest("a")) return;
    const d = $(`.mxd[data-d="${tr.dataset.f}"]`); d.style.display = d.style.display === "none" ? "" : "none"; tr.classList.toggle("open");
  }));
  bindDoc($("#mxTable"));
}

// --- Fazit
function fazitHtml() {
  const tasks = C.pages.filter(p => p.kind === "task");
  const sum = (tool, keys) => {
    const c = { ok: 0, partial: 0, unsupported: 0, failed: 0, not_run: 0 };
    tasks.filter(p => !keys || keys.includes(p.task.section_key)).forEach(p => { const s = pageStatus(p.id)[tool].status; c[s in c ? s : "failed"]++; });
    return c;
  };
  const cnt = (tool, keys) => { const c = sum(tool, keys); return { ...c, n: Object.values(c).reduce((a, b) => a + b, 0) }; };
  const statBar = (c) => `<div class="sbar">${Object.keys(STATUS).map(k => c[k] ? `<span class="seg s-${STATUS[k].cls}" style="flex:${c[k]}" title="${esc(STATUS[k].label)}: ${c[k]}">${c[k]}</span>` : "").join("")}</div>`;
  const rows = TOOL_KEYS.map(t => `<div class="fz-row"><div class="fz-l">${toolTag(t)}</div>${statBar(cnt(t))}</div>`).join("");
  const common = ["common"], cb = cnt("brep", common), cv = cnt("voxel", common);
  const ob = cnt("brep", ["brep_only"]), ov = cnt("voxel", ["voxel_only"]);
  const feats = C.matrix?.features || [];
  const tally = { brep: 0, voxel: 0, tie: 0 }; feats.forEach(f => { if (tally[f.better] != null) tally[f.better]++; });
  const both = tasks.filter(p => { const s = pageStatus(p.id); return isNum(s.brep.runtime_s) && isNum(s.voxel.runtime_s) && s.brep.runtime_s > 0 && s.voxel.runtime_s > 0; });
  const maxRt = Math.max(1e-9, ...both.flatMap(p => TOOL_KEYS.map(t => pageStatus(p.id)[t].runtime_s)));
  const bars = both.map(p => { const s = pageStatus(p.id); return `<div class="rt"><a href="#" data-goto="${esc(p.id)}" class="rt-id">${esc(p.id)}</a><div class="rt-b">
    ${TOOL_KEYS.map(t => `<div class="rt-row"><span class="rt-bar t-${t}" style="width:${Math.max(1.5, s[t].runtime_s / maxRt * 100)}%"></span><span class="rt-v">${fx(s[t].runtime_s, 2)} s</span></div>`).join("")}</div></div>`; }).join("");
  const table = tasks.map(p => { const s = pageStatus(p.id), v = verdict(s.brep.status, s.voxel.status);
    return `<tr class="click"><td><a href="#" data-goto="${esc(p.id)}"><b>${esc(p.id)}</b></a></td><td>${esc(p.title)}</td><td>${badge(s.brep.status)}</td><td>${badge(s.voxel.status)}</td><td><span class="verdict v-${v.cls}">${esc(v.text)}</span></td></tr>`; }).join("");
  const okShare = (c) => `${c.ok + c.partial} von ${c.n}`;
  return `<h1>Fazit</h1>
    <p class="lead">Zusammenfassung aus den geladenen Ergebnissen (Lauf „${esc(C.run || "–")}“) und der Feature-Matrix. Die Zahlen aktualisieren sich mit jedem neuen Lauf.</p>
    <h3>Erledigte Aufgaben (ok + teilweise)</h3>${rows}
    <div class="legendbox small"><div>${Object.keys(STATUS).map(k => badge(k)).join(" ")}</div></div>
    <h3>Was die Zahlen sagen</h3>
    <ul class="fz-list">
      <li><b>Gemeinsame Aufgaben (B01–B10):</b> build123d löst ${okShare(cb)}, PicoGK ${okShare(cv)}.</li>
      <li><b>Nur / besser in B-rep (R01–R04):</b> build123d löst ${okShare(ob)}; PicoGK: ${cnt("voxel", ["brep_only"]).ok + cnt("voxel", ["brep_only"]).partial} davon ganz oder teilweise.</li>
      <li><b>Nur / besser in Voxel (V01–V04):</b> PicoGK löst ${okShare(ov)}; build123d: ${cnt("brep", ["voxel_only"]).ok + cnt("brep", ["voxel_only"]).partial} davon ganz oder teilweise.</li>
      ${(() => { const tl = TOOL_KEYS.map(tool => { let n = 0, ok = 0;
        for (const p of tasks) { const e = expectOf(p.task, tool)?.status, s = pageStatus(p.id)[tool].status; if (e && s !== "not_run") { n++; if (e === s) ok++; } }
        return { tool, n, ok }; });
        return tl.some(x => x.n) ? `<li><b>Erwartungen aus der Recherche:</b> ${tl.map(x => `${TOOLS[x.tool].name} ${x.ok} von ${x.n} bestätigt`).join(", ")} (nur Aufgaben mit Ergebnis).</li>` : ""; })()}
      ${feats.length ? `<li><b>Feature-Matrix (${feats.length} Merkmale):</b> build123d besser bei ${tally.brep}, PicoGK besser bei ${tally.voxel}, Gleichstand bei ${tally.tie}.</li>` : ""}
    </ul>
    <h3>Vorläufige Einordnung (Arbeitshypothese, mit echten Ergebnissen zu prüfen)</h3>
    <div class="notes"><div><b>Hybrid statt Entweder-oder.</b> B-rep ist der parametrische Master: Skelett, exakte Masse, STEP, Zeichnung, Passungen. Voxel ist das Spezialwerkzeug für Gitter-Infill, Kühlluftkanäle, robuste Offsets/Übergänge und Druck-Slices. Die Übergabe erfolgt über Meshes (STL), die Rückgabe der Ergebnisse als Kennzahlen.</div>
    <div><b>Für die Pipeline:</b> beide Werkzeuge sind per CLI und Code steuerbar. Entscheidend sind Regenerationszeit pro Parameteränderung (B03), Robustheit an Übergängen (B05/B06) und die Skalierung mit der Auflösung (B10).</div></div>
    ${both.length ? `<h3>Laufzeit je Aufgabe</h3><div class="rtchart">${bars}</div><div class="muted small">${toolTag("brep")} und ${toolTag("voxel")}; kürzer ist besser.</div>` : ""}
    <h3>Alle Aufgaben</h3>
    <table class="mtable fz-table"><tr><th>ID</th><th>Aufgabe</th><th>build123d</th><th>PicoGK</th><th>Einordnung</th></tr>${table}</table>`;
}

// ------------------------------------------------------------------ Eintritt & Events
export async function enterCompare() {
  if (!C.inited) {
    C.inited = true;
    bindStatic();
    try {
      await loadIndex();
    } catch (e) {
      C.inited = false; toast("Vergleich: " + e.message); return;
    }
    const m = location.hash.match(/^#vergleich\/(\w+)/);
    const i = m ? C.pages.findIndex(p => p.id === m[1]) : -1;
    C.idx = i >= 0 ? i : 0;
  }
  goPage(C.idx);
  if (C.viewers) for (const t of TOOL_KEYS) { C.viewers[t].resize(); C.viewers[t].requestRender(); }
}
export function leaveCompare() {
  abortLoads(); delete document.body.dataset.cmp;
  try { if (location.hash.startsWith("#vergleich")) history.replaceState(null, "", location.pathname + location.search); } catch { /* egal */ }
}
export const compareActive = () => document.body.classList.contains("mode-vergleich");

function bindStatic() {
  $("#cmpPrev").addEventListener("click", () => goPage(C.idx - 1));
  $("#cmpNext").addEventListener("click", () => goPage(C.idx + 1));
  $("#cmpRun").addEventListener("change", async e => { C.run = e.target.value; await loadIndex(); goPage(C.idx); });
  $("#cmpFill").addEventListener("change", async e => { C.fill = e.target.checked; await loadIndex(); goPage(C.idx); });
  $("#cmpSync").addEventListener("click", () => {
    C.sync = !C.sync; $("#cmpSync").classList.toggle("on", C.sync);
    if (C.sync && C.viewers) { C.syncLock = true; try { C.viewers.voxel.setCam(C.viewers.brep.camState()); } finally { C.syncLock = false; } }
  });
  $("#cmpWire").addEventListener("click", () => { C.wire = !C.wire; $("#cmpWire").classList.toggle("on", C.wire); if (C.viewers) for (const t of TOOL_KEYS) C.viewers[t].setWire(C.wire); });
  $$("[data-cview]").forEach(b => b.addEventListener("click", () => fitAll(b.dataset.cview)));
  $("#lbPrev").addEventListener("click", () => lbStep(-1));
  $("#lbNext").addEventListener("click", () => lbStep(1));
  $("#lbClose").addEventListener("click", lbClose);
  $("#cmpLightbox").addEventListener("click", e => { if (e.target.id === "cmpLightbox") lbClose(); });
  document.addEventListener("keydown", e => {
    if (!compareActive()) return;
    if ($("#cmpLightbox").classList.contains("on")) {
      if (e.key === "Escape") lbClose(); else if (e.key === "ArrowRight") lbStep(1); else if (e.key === "ArrowLeft") lbStep(-1);
      return;
    }
    if (/INPUT|SELECT|TEXTAREA/.test(document.activeElement?.tagName)) return;
    if (e.key === "ArrowRight") goPage(C.idx + 1);
    if (e.key === "ArrowLeft") goPage(C.idx - 1);
  });
}
