import { Viewer } from "/gui/viewer.js";
import { $, $$, api, css, esc, fmt, highlight, kvHtml, renderResult, tableHtml, toast } from "/gui/ui.js";

const S = {
  cfg: null, mode: "tour", preset: null, material: "PETG", req: null, params: null,
  tour: { idx: 0, opts: {}, visited: new Set(), seq: 0, payload: null },
  werk: { last: null, tog: { edges: true, orig: false, lower: false, props: true, payload: false, section: false }, fitted: false },
  pipe: { result: null, sel: null },
};
const viewer = new Viewer($("#canvas"));
const busy = (on, text = "build123d rechnet…") => { $("#busy").textContent = text; $("#busy").classList.toggle("on", on); };

// ================================================================ Allgemein
function loadPreset(name) {
  const pr = S.cfg.presets[name];
  S.preset = name; S.req = { ...pr.req }; S.material = pr.material;
  $("#preset").value = name; $("#material").value = pr.material;
  buildReqFields();
}

function setMode(mode) {
  S.mode = mode;
  document.body.className = "mode-" + mode;
  $$(".modes button").forEach(b => b.classList.toggle("active", b.dataset.mode === mode));
  $$(".mode-pane").forEach(p => p.classList.toggle("active", p.dataset.pane === mode));
  $("#explodeBox").style.display = mode === "pipeline" ? "none" : "";
  if (mode === "werkbank") {
    applyWerkToggles();
    if (!S.werk.last) runBuild(); else renderLegend([["Rumpf", [.30, .72, .42]], ["Gondeln", [.2, .55, .85]], ["Nasenkappe", [.95, .52, .18]]]);
  } else if (mode === "tour") {
    viewer.show(["scene"]); runTour(true);
  } else {
    viewer.show(["scene"]); renderPipeFlow();
    if (S.pipe.result) selectStage(S.pipe.sel || "cad"); else { viewer.setItems([]); renderLegend([]); }
  }
}

function renderLegend(list) {
  $("#legend").innerHTML = (list || []).map(([l, c]) => `<span><i style="background:${css(c)}"></i>${esc(l)}</span>`).join("");
}

async function exportFile(fmtName) {
  busy(true, `Export ${fmtName.toUpperCase()}…`);
  try {
    const blob = await (await api("/api/export", { params: S.params, format: fmtName, material: S.material, preset: S.preset })).blob();
    const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = `boreas_oberteil.${fmtName}`; a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 5000);
  } catch (e) { toast("Export-Fehler: " + e.message); } finally { busy(false); }
}

async function showDrawing() {
  busy(true, "Zeichnung wird projiziert & bemaßt…");
  try {
    const blob = await (await api("/api/export", { params: S.params, format: "svg", material: S.material, preset: S.preset })).blob();
    const url = URL.createObjectURL(blob);
    $("#drawingImg").src = url; $("#dlDrawing").href = url; $("#modal").classList.add("on");
  } catch (e) { toast("Zeichnungs-Fehler: " + e.message); } finally { busy(false); }
}

// ================================================================ Tour
function renderTourList() {
  const box = $("#tourList"); let chapter = null, html = "";
  S.cfg.tour.forEach((st, i) => {
    if (st.chapter !== chapter) { chapter = st.chapter; html += `<div class="chapter">${esc(chapter)}</div>`; }
    const cls = ["tstep", i === S.tour.idx ? "active" : "", S.tour.visited.has(i) && i !== S.tour.idx ? "done" : ""].join(" ");
    html += `<div class="${cls}" data-i="${i}"><span class="num">${i + 1}</span><span>${esc(st.title)}</span></div>`;
  });
  box.innerHTML = html;
  $$(".tstep", box).forEach(el => el.addEventListener("click", () => goStep(+el.dataset.i)));
  $("#tourProgress").style.width = `${(S.tour.idx + 1) / S.cfg.tour.length * 100}%`;
  $("#tourPrev").disabled = S.tour.idx === 0;
  $("#tourNext").textContent = S.tour.idx === S.cfg.tour.length - 1 ? "Zur Pipeline →" : "Weiter →";
}

function goStep(i) {
  S.tour.idx = Math.max(0, Math.min(S.cfg.tour.length - 1, i));
  renderTourList(); runTour(true);
  $(".tstep.active")?.scrollIntoView({ block: "nearest" });
}

function stepOpts(st) {
  if (!S.tour.opts[st.id]) S.tour.opts[st.id] = Object.fromEntries(st.controls.map(c => [c.key, c.value]));
  return S.tour.opts[st.id];
}

async function runTour(fit) {
  const st = S.cfg.tour[S.tour.idx];
  const seq = ++S.tour.seq;
  S.tour.visited.add(S.tour.idx);
  if (fit) $("#tourPanel").innerHTML = `<div class="muted small">${esc(st.chapter)} · Schritt ${S.tour.idx + 1}/${S.cfg.tour.length}</div>
    <h2>${esc(st.title)}</h2><p class="lead">${esc(st.lead)}</p><p class="muted">build123d rechnet…</p>`;
  busy(true, `„${st.title}“ – build123d rechnet…`);
  try {
    const pl = await (await api("/api/tour", { id: st.id, params: S.params, req: S.req, material: S.material, opts: stepOpts(st) })).json();
    if (seq !== S.tour.seq) return;
    S.tour.payload = pl;
    viewer.setItems(pl.items, { markers: pl.markers || [], explode: !!pl.explode, fit });
    renderLegend(pl.legend || []);
    renderTourPanel(st, pl);
    $("#chipTime").textContent = `Schritt ${fmt(pl.ms, 0)} ms`;
  } catch (e) { if (seq === S.tour.seq) toast(`Fehler in „${st.title}“: ${e.message}`); }
  finally { if (seq === S.tour.seq) busy(false); }
}

function controlHtml(c, value) {
  if (c.type === "select")
    return `<div class="ctrl"><div class="rl">${esc(c.label)}</div><select data-key="${c.key}">${c.options.map(([v, l]) =>
      `<option value="${v}" ${v === value ? "selected" : ""}>${esc(l)}</option>`).join("")}</select></div>`;
  if (c.type === "toggle")
    return `<div class="ctrl"><label class="t"><input type="checkbox" data-key="${c.key}" ${value ? "checked" : ""}> ${esc(c.label)}</label></div>`;
  if (c.type === "range")
    return `<div class="ctrl"><div class="rl"><span>${esc(c.label)}</span><span class="rv">${value} ${c.unit || ""}</span></div>
      <input type="range" data-key="${c.key}" min="${c.min}" max="${c.max}" step="${c.step}" value="${value}"></div>`;
  return "";
}

function renderTourPanel(st, pl) {
  const opts = stepOpts(st);
  const controls = [...st.controls, ...(pl.controls_dynamic || [])];
  let html = `<div class="muted small">${esc(st.chapter)} · Schritt ${S.tour.idx + 1}/${S.cfg.tour.length}</div>
    <h2>${esc(st.title)}</h2><p class="lead">${esc(st.lead)}</p>`;
  if (pl.slider) {
    const s = pl.slider;
    html += `<div class="ctrl"><div class="rl"><span>Bauschritt</span><span>${s.value + 1} / ${s.max + 1}</span></div>
      <input type="range" data-key="${s.key}" data-live="1" min="${s.min}" max="${s.max}" step="1" value="${s.value}">
      <div class="steplabel">${esc(s.labels[s.value])}</div></div>
      <div class="grid2"><button class="btn" data-hist="-1">◀ Schritt</button><button class="btn" data-hist="1">Schritt ▶</button></div>`;
  }
  controls.forEach(c => { html += controlHtml(c, opts[c.key] ?? c.value); });
  (pl.controls_client || []).forEach(c => { html += `<div class="ctrl"><label class="t"><input type="checkbox" data-client="${c.key}" ${viewer.spin ? "checked" : ""}> ${esc(c.label)}</label></div>`; });
  if (pl.actions?.length) {
    html += `<div class="actions ${pl.actions.length > 3 ? "grid" : ""}">${pl.actions.map((a, i) =>
      `<button class="btn ${a.apply || a.mode ? "primary" : ""}" data-act="${i}">${esc(a.label)}</button>`).join("")}</div>`;
  }
  html += `<div id="tourResult"></div>`;
  if (pl.code) html += `<details class="codebox" open><summary>build123d-Code zu diesem Schritt</summary><pre class="code">${highlight(pl.code)}</pre></details>`;
  html += `<div class="timing">Serverseitig berechnet in ${fmt(pl.ms, 0)} ms · Parameter aus Datensatz „${esc(S.preset)}“</div>`;
  const panel = $("#tourPanel"); panel.innerHTML = html;
  renderResult($("#tourResult"), pl);

  const set = (key, v) => { opts[key] = v; runTour(false); };
  $$("select[data-key]", panel).forEach(el => el.addEventListener("change", () => set(el.dataset.key, el.value)));
  $$("input[type=checkbox][data-key]", panel).forEach(el => el.addEventListener("change", () => set(el.dataset.key, el.checked)));
  $$("input[type=range][data-key]", panel).forEach(el => {
    const lbl = el.parentElement.querySelector(".rv, .steplabel");
    el.addEventListener("input", () => {
      if (pl.slider && el.dataset.key === pl.slider.key) lbl.textContent = pl.slider.labels[+el.value];
      else if (lbl) lbl.textContent = el.value;
      if (el.dataset.live) { clearTimeout(el._t); el._t = setTimeout(() => set(el.dataset.key, +el.value), 120); }
    });
    if (!el.dataset.live) el.addEventListener("change", () => set(el.dataset.key, +el.value));
  });
  $$("[data-hist]", panel).forEach(b => b.addEventListener("click", () => {
    const s = pl.slider; set(s.key, Math.max(s.min, Math.min(s.max, s.value + +b.dataset.hist)));
  }));
  $$("[data-client]", panel).forEach(el => el.addEventListener("change", () => { viewer.spin = el.checked; }));
  $$("[data-act]", panel).forEach(b => b.addEventListener("click", () => {
    const a = pl.actions[+b.dataset.act];
    if (a.apply) { S.params = { ...S.params, ...a.apply }; syncParamFields(); toast("Übernommen – gilt jetzt auch in Werkbank & Export."); runTour(false); }
    else if (a.mode) setMode(a.mode);
    else if (a.export) exportFile(a.export);
    else if (a.drawing) showDrawing();
  }));
}

// ================================================================ Werkbank
function buildParamFields() {
  const box = $("#paramFields"); box.innerHTML = "";
  let group = null;
  for (const [key, [grp, label, unit, min, max, step]] of Object.entries(S.cfg.spec)) {
    if (grp !== group) { group = grp; box.insertAdjacentHTML("beforeend", `<h3>${grp}</h3>`); }
    const row = document.createElement("div"); row.className = "row"; row.dataset.key = key;
    row.innerHTML = `<label><span>${label}</span><span class="u">${unit}</span></label>
      <input type="range" min="${min}" max="${max}" step="${step}"><input type="number" min="${min}" max="${max}" step="${step}">`;
    const [rng, num] = row.querySelectorAll("input");
    const set = (v) => { S.params[key] = Number(v); rng.value = v; num.value = v; markChanged(); scheduleBuild(); };
    rng.addEventListener("input", () => set(rng.value));
    num.addEventListener("change", () => set(num.value));
    box.appendChild(row);
  }
}
function syncParamFields() {
  for (const row of $$("#paramFields .row")) {
    const [rng, num] = row.querySelectorAll("input"); const v = S.params[row.dataset.key];
    rng.value = v; num.value = Math.round(v * 100) / 100;
  }
  markChanged();
}
function markChanged() {
  for (const row of $$("#paramFields .row"))
    row.classList.toggle("changed", Math.abs(S.params[row.dataset.key] - S.cfg.defaults[row.dataset.key]) > 1e-6);
}
function buildReqFields() {
  const box = $("#reqFields"); box.innerHTML = "";
  for (const [key, [label, unit]] of Object.entries(S.cfg.requirement_fields)) {
    const row = document.createElement("div"); row.className = "row";
    row.innerHTML = `<label><span>${label}</span><span class="u">${unit}</span></label><input type="number" step="any" style="grid-column:1/-1">`;
    const inp = row.querySelector("input"); inp.value = S.req[key];
    inp.addEventListener("change", () => { S.req[key] = Number(inp.value); onDataChange(); });
    box.appendChild(row);
  }
}

let timer = null, inflight = false, pending = false;
function scheduleBuild() { clearTimeout(timer); timer = setTimeout(runBuild, 220); }
async function runBuild() {
  if (S.mode !== "werkbank") return;
  if (inflight) { pending = true; return; }
  inflight = true; busy(true);
  try {
    const res = await (await api("/api/build", { params: S.params, req: S.req, material: S.material, section: S.werk.tog.section })).json();
    S.werk.last = res; S.params = res.params;
    viewer.setVariant(res.meshes); viewer.setAux(res.params, S.req, res.checks); applyWerkToggles();
    renderWerkInfo(res);
    renderLegend([["Rumpf", [.30, .72, .42]], ["Gondeln", [.2, .55, .85]], ["Nasenkappe", [.95, .52, .18]]]);
    if (!S.werk.fitted) { viewer.fit("iso", viewer.groups.werk); S.werk.fitted = true; }
  } catch (e) { toast("Build-Fehler: " + e.message); }
  finally { inflight = false; busy(false); if (pending) { pending = false; runBuild(); } }
}

function applyWerkToggles() {
  if (S.mode !== "werkbank") return;
  const t = S.werk.tog;
  viewer.show(["werk", ...(t.orig ? ["orig"] : []), ...(t.lower ? ["lower"] : []), ...(t.props ? ["props"] : []), ...(t.payload ? ["payload"] : [])]);
  viewer.setEdges(t.edges);
}

function renderWerkInfo(res) {
  const { props, checks, derived, timing } = res;
  $("#mass").textContent = fmt(props.mass_g, 0) + " g";
  const twr = checks.find(c => c.name.startsWith("Schub"));
  $("#twr").textContent = twr ? fmt(twr.value, 2) : "–"; $("#twr").className = "big " + (twr && !twr.ok ? "bad" : "");
  $("#partsTable").innerHTML = `<tr><th>Teil</th><th class="n">Volumen cm³</th><th class="n">Masse g</th><th class="n">Fläche cm²</th></tr>` +
    Object.entries(props.parts).map(([k, v]) => `<tr><td>${k}</td><td class="n">${fmt(v.volume_cm3)}</td><td class="n">${fmt(v.mass_g)}</td><td class="n">${fmt(v.area_cm2, 0)}</td></tr>`).join("");
  const mat = S.cfg.materials[S.material];
  $("#propsKv").innerHTML = kvHtml([
    ["Material", `${mat.label} · ${mat.density} g/cm³`],
    ["Bauraum B×T×H", props.bbox.map(v => fmt(v, 0)).join(" × ") + " mm"],
    ["Schwerpunkt z", fmt(props.cog[2]) + " mm"],
    ["Abflugmasse (inkl. Mock-Komponenten)", twr ? twr.hint.replace("Abflugmasse ", "") : "–"],
    ["Geometrie gültig", Object.values(res.valid).every(Boolean) ? "✔ BRep valide" : "✘ ungültig"],
  ]).replace(/^<div class="kv">|<\/div>$/g, "");
  const nOk = checks.filter(c => c.ok).length;
  $("#checkSum").textContent = `${nOk}/${checks.length} erfüllt`;
  const chip = $("#chipChecks"); chip.textContent = nOk === checks.length ? "✔ alle Constraints erfüllt" : `✘ ${checks.length - nOk} Constraint(s) verletzt`;
  chip.className = "chip " + (nOk === checks.length ? "ok" : "bad");
  $("#checks").innerHTML = checks.map(c => `<div class="check"><span class="dot ${c.ok ? "ok" : "bad"}"></span>
    <div>${c.name}<div class="lim">Grenze ${c.limit} ${c.unit}</div></div>
    <div class="val ${c.ok ? "" : "bad"}">${fmt(c.value, c.unit === "" ? 2 : 1)} ${c.unit}</div>
    ${!c.ok && c.hint && !c.name.startsWith("Schub") ? `<div class="hint">→ ${c.hint}</div>` : ""}</div>`).join("");
  const dl = { tab_width: "Laschenbreite", tab_height: "Laschenhöhe", spigot_outer_radius: "Zentrierring Radius",
    nose_base_radius: "Nasen-Basisradius", pad_radius: "Motorplatte Radius", inner_diameter: "Innen-Ø Rohr", span: "Spannweite", total_height: "Gesamthöhe" };
  $("#derived").innerHTML = Object.entries(derived).map(([k, v]) => `<div>${dl[k] || k}</div><div>${fmt(v, 2)} mm</div>`).join("");
  $("#chipTime").textContent = timing.cached ? `Cache · Tessellierung ${fmt(timing.mesh_ms, 0)} ms`
    : `build123d ${fmt(timing.build_ms, 0)} ms · Tessellierung ${fmt(timing.mesh_ms, 0)} ms`;
  const om = S.cfg.original_measured;
  const names = Object.fromEntries(Object.entries(S.cfg.spec).map(([k, v]) => [k, v[1]]));
  $("#compare").innerHTML = `<tr><th>Maß</th><th class="n">STEP</th><th class="n">Variante</th><th class="n">Δ</th></tr>` +
    Object.entries(om).filter(([k]) => !k.startsWith("_")).map(([k, v]) => {
      const cur = res.params[k], d = cur - v;
      return `<tr><td>${names[k] || k}</td><td class="n">${fmt(v)}</td><td class="n">${fmt(cur)}</td><td class="n ${Math.abs(d) > 1e-6 ? "" : "muted"}">${d > 0 ? "+" : ""}${fmt(d)}</td></tr>`;
    }).join("");
}

async function autosize() {
  const r = await (await api("/api/autosize", { req: S.req, material: S.material, params: S.params })).json();
  S.params = r.params; syncParamFields(); S.werk.fitted = false; runBuild();
}

async function runBatch() {
  const b = $("#btnBatch"); b.disabled = true; b.textContent = "rechnet…";
  try {
    const rows = await (await api("/api/batch", {})).json();
    $("#batch").innerHTML = `<table><tr><th>Variante</th><th class="n">n</th><th class="n">Ø</th><th class="n">Spannw.</th><th class="n">Masse</th><th class="n">TWR</th><th class="n">✔</th></tr>` +
      rows.map((r, i) => `<tr class="click" data-i="${i}"><td>${r.name}<div class="muted" style="font-size:11px">${r.material} · ${fmt(r.ms, 0)} ms</div></td>
        <td class="n">${r.params.arm_count}</td><td class="n">${fmt(2 * r.params.body_radius, 0)}</td>
        <td class="n">${fmt(2 * (r.params.arm_reach + r.params.pod_radius + 2), 0)}</td><td class="n">${fmt(r.props.mass_g, 0)}</td>
        <td class="n ${r.twr < 2 ? "bad" : ""}">${fmt(r.twr, 2)}</td><td class="n ${r.ok < r.n_checks ? "bad" : "good"}">${r.ok}/${r.n_checks}</td></tr>`).join("") +
      `</table><p class="note">Zeile anklicken → Variante laden.</p>`;
    $$("#batch tr.click").forEach(tr => tr.addEventListener("click", () => {
      const r = rows[+tr.dataset.i]; loadPreset(r.name); S.params = r.params; syncParamFields(); S.werk.fitted = false; runBuild();
    }));
  } catch (e) { toast("Batch-Fehler: " + e.message); }
  finally { b.disabled = false; b.textContent = "▶ Alle Varianten berechnen"; }
}

// ================================================================ Pipeline
const TARGETS = {
  step: "CAD / FEM-Preprocessing (Ansys, Abaqus, CalculiX, FreeCAD)", stl: "CFD (OpenFOAM) · Slicer", "3mf": "3D-Druck mit Bauteilnamen",
  glb: "Web-Viewer · Unity · Blender · Digital Twin", dxf: "Laser-/Wasserstrahlschneiden · CNC", svg: "Werkstattzeichnung / Doku",
  zip: "URDF-Paket → Gazebo · PX4-SITL · Isaac Sim", json: "Report → Dashboards, CI-Checks, PLM",
};

function renderPipeFlow() {
  const flow = $("#pipeFlow");
  const res = S.pipe.result;
  const byId = Object.fromEntries((res?.stages || []).map(s => [s.id, s]));
  flow.innerHTML = `<svg id="pipeSvg"></svg>` + S.cfg.stages.map(st => {
    const r = byId[st.id];
    const cls = ["pnode", r ? r.status : "", S.pipe.running ? "run" : "", S.pipe.sel === st.id ? "sel" : ""].join(" ");
    const b3d = /build123d/.test(st.tool);
    return `<div class="${cls}" data-id="${st.id}">
      <div class="top"><span class="nm">${esc(st.name)}</span><span class="ms">${r ? fmt(r.ms, 0) + " ms" : ""}</span></div>
      <div><span class="badge ${b3d ? "b3d" : "other"}">${esc(st.tool)}</span></div>
      <div class="${r ? "sum" : "desc"}">${esc(r ? r.summary || "" : st.desc)}</div></div>`;
  }).join("");
  $$(".pnode", flow).forEach(n => n.addEventListener("click", () => { if (S.pipe.result) selectStage(n.dataset.id); }));
  requestAnimationFrame(drawLoopArrow);
}

function drawLoopArrow() {
  const flow = $("#pipeFlow"), svg = $("#pipeSvg");
  if (!flow || !svg) return;
  const [from, to] = S.cfg.loop;
  const a = $(`.pnode[data-id="${from}"]`, flow), b = $(`.pnode[data-id="${to}"]`, flow);
  if (!a || !b) return;
  const fr = flow.getBoundingClientRect(), ar = a.getBoundingClientRect(), br = b.getBoundingClientRect();
  const y1 = ar.top - fr.top + ar.height / 2, y2 = br.top - fr.top + br.height / 2, x = 16, xe = ar.left - fr.left;
  svg.setAttribute("height", flow.scrollHeight);
  svg.innerHTML = `<defs><marker id="ah" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 z" fill="#4cc38a"/></marker></defs>
    <path d="M${xe},${y1} H${x} V${y2} H${xe - 2}" fill="none" stroke="#4cc38a" stroke-width="1.6" stroke-dasharray="4 3" marker-end="url(#ah)"/>
    <text x="${x - 4}" y="${(y1 + y2) / 2}" fill="#4cc38a" font-size="10" transform="rotate(-90 ${x - 4} ${(y1 + y2) / 2})" text-anchor="middle">CAD im Loop</text>`;
}

async function runPipeline() {
  const btn = $("#btnPipe"); btn.disabled = true;
  S.pipe.running = true; S.pipe.result = null; renderPipeFlow();
  busy(true, "Pipeline läuft (≈ 20–40 s) – build123d + Simulationen…");
  try {
    const res = await (await api("/api/pipeline", { req: S.req, material: S.material, name: S.preset, optimize: $("#pipeOpt").checked })).json();
    S.pipe.running = false; S.pipe.result = { stages: [] , out_dir: res.out_dir, total_ms: res.total_ms };
    for (const st of res.stages) {           // Stufen nacheinander einblenden
      S.pipe.result.stages.push(st); renderPipeFlow();
      await new Promise(r => setTimeout(r, 90));
    }
    S.pipe.result = res;
    const lastParams = res.stages.find(s => s.id === "size")?.params;
    if (lastParams) S.params = { ...lastParams };
    selectStage("cad");
    $("#chipTime").textContent = `Pipeline ${fmt(res.total_ms / 1000, 1)} s`;
  } catch (e) { toast("Pipeline-Fehler: " + e.message); S.pipe.running = false; renderPipeFlow(); }
  finally { btn.disabled = false; busy(false); }
}

function selectStage(id) {
  const res = S.pipe.result; if (!res) return;
  S.pipe.sel = id; renderPipeFlow();
  const st = res.stages.find(s => s.id === id); if (!st) return;
  let items = st.items;
  if (!items) {                               // keine eigene Geometrie → letzte davor zeigen
    const idx = res.stages.indexOf(st);
    for (let i = idx; i >= 0 && !items; i--) items = res.stages[i].items;
  }
  const isNew = S.pipe.lastItems !== items;
  S.pipe.lastItems = items;
  viewer.setItems(items || [], { fit: isNew });
  renderLegend(id === "mfg" ? [["Überhang > 45°", [.93, .25, .25]]] : [["Rumpf", [.30, .72, .42]], ["Gondeln", [.2, .55, .85]], ["Nasenkappe", [.95, .52, .18]]]);
  const panel = $("#pipePanel");
  let extra = "";
  if (id === "export" && st.downloads) {
    extra = `<h3>Wohin gehen die Dateien?</h3><table class="targets">${st.downloads.map(d => {
      const ext = (d.url.split(".").pop() || "").toLowerCase();
      return `<tr><td>.${esc(ext)}</td><td>${esc(TARGETS[ext] || "")}</td></tr>`;
    }).join("")}</table>`;
  }
  panel.innerHTML = `<div class="muted small">Pipeline-Stufe · <span class="badge ${/build123d/.test(st.tool) ? "b3d" : "other"}">${esc(st.tool)}</span></div>
    <h2>${esc(st.name)}</h2><p class="lead">${esc(st.summary || st.desc)}</p>
    ${st.loop ? `<div class="notes"><div>↺ Diese Stufe baut das CAD-Modell mit den optimierten Parametern neu – alle folgenden Stufen rechnen mit der optimierten Geometrie.</div></div>` : ""}
    <div id="pipeResult"></div>${extra}
    <div class="timing">Stufe ${fmt(st.ms, 0)} ms · Gesamtlauf ${fmt(res.total_ms / 1000, 1)} s · Ausgabe: ${esc(res.out_dir)}</div>`;
  renderResult($("#pipeResult"), st);
}

// ================================================================ Init & Events
function onDataChange() {
  if (S.mode === "werkbank") scheduleBuild();
  else if (S.mode === "tour") runTour(false);
}

$$(".modes button").forEach(b => b.addEventListener("click", () => setMode(b.dataset.mode)));
$("#tourPrev").addEventListener("click", () => goStep(S.tour.idx - 1));
$("#tourNext").addEventListener("click", () => S.tour.idx === S.cfg.tour.length - 1 ? setMode("pipeline") : goStep(S.tour.idx + 1));
document.addEventListener("keydown", e => {
  if (S.mode !== "tour" || /INPUT|SELECT|TEXTAREA/.test(document.activeElement?.tagName)) return;
  if (e.key === "ArrowRight") goStep(S.tour.idx + 1);
  if (e.key === "ArrowLeft") goStep(S.tour.idx - 1);
});
$$(".tabs button").forEach(b => b.addEventListener("click", () => {
  $$(".tabs button").forEach(x => x.classList.toggle("active", x === b));
  $$('[data-pane="werkbank"] .pane').forEach(p => p.classList.toggle("active", p.id === "pane-" + b.dataset.tab));
  if (b.dataset.tab === "code" && $("#srcCode").textContent === "lädt…")
    api("/api/source").then(r => r.text()).then(t => $("#srcCode").innerHTML = highlight({ lang: "python", text: t }));
}));
$$(".tog").forEach(t => t.addEventListener("click", async () => {
  const k = t.dataset.t; S.werk.tog[k] = !S.werk.tog[k]; t.classList.toggle("on", S.werk.tog[k]);
  if (k === "edges") { viewer.setEdges(S.werk.tog.edges); return; }
  if ((k === "orig" || k === "lower") && S.werk.tog[k]) {
    busy(true, "STEP-Original wird geladen…");
    try { viewer.setOriginal(await (await api("/api/original")).json()); } catch (e) { toast("STEP-Fehler: " + e.message); } finally { busy(false); }
  }
  if (k === "section") runBuild(); else applyWerkToggles();
}));
$$("[data-view]").forEach(b => b.addEventListener("click", () => viewer.fit(b.dataset.view, S.mode === "werkbank" ? viewer.groups.werk : viewer.groups.scene)));
$$("[data-exp]").forEach(b => b.addEventListener("click", () => exportFile(b.dataset.exp)));
$$("[data-drawing]").forEach(b => b.addEventListener("click", showDrawing));
$("#explode").addEventListener("input", e => viewer.setExplode(+e.target.value));
$("#btnAuto").addEventListener("click", autosize);
$("#btnAuto2").addEventListener("click", autosize);
$("#btnReset").addEventListener("click", () => { S.params = { ...S.cfg.defaults }; syncParamFields(); S.werk.fitted = false; runBuild(); });
$("#btnBatch").addEventListener("click", runBatch);
$("#btnPipe").addEventListener("click", runPipeline);
$("#closeModal").addEventListener("click", () => $("#modal").classList.remove("on"));
$("#preset").addEventListener("change", async e => {
  loadPreset(e.target.value);
  const r = await (await api("/api/autosize", { req: S.req, material: S.material, params: S.params })).json();
  S.params = r.params; syncParamFields(); S.werk.fitted = false; onDataChange();
});
$("#material").addEventListener("change", e => { S.material = e.target.value; onDataChange(); });
window.addEventListener("resize", () => requestAnimationFrame(drawLoopArrow));

(async function init() {
  S.cfg = await (await api("/api/config")).json();
  $("#preset").innerHTML = Object.keys(S.cfg.presets).map(n => `<option>${esc(n)}</option>`).join("");
  $("#material").innerHTML = Object.entries(S.cfg.materials).map(([k, m]) => `<option value="${k}">${esc(m.label)}</option>`).join("");
  S.params = { ...S.cfg.defaults };
  loadPreset(Object.keys(S.cfg.presets)[0]);
  buildParamFields(); syncParamFields(); renderTourList();
  $("#chipChecks").textContent = "Mock-Daten";
  setMode("tour");
})();
