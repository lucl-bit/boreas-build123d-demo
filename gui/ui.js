export const $ = (s, root = document) => root.querySelector(s);
export const $$ = (s, root = document) => [...root.querySelectorAll(s)];
export const fmt = (v, d = 1) => (v == null || isNaN(v)) ? "–" :
  Number(v).toLocaleString("de-CH", { minimumFractionDigits: d, maximumFractionDigits: d });
export const css = (c) => `rgb(${Math.round(c[0] * 255)}, ${Math.round(c[1] * 255)}, ${Math.round(c[2] * 255)})`;
export const esc = (s) => String(s).replace(/[&<>"]/g, ch => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[ch]));

export async function api(path, body) {
  const r = await fetch(path, body ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) } : {});
  if (!r.ok) { let m = r.statusText; try { m = (await r.json()).error; } catch { } throw new Error(m); }
  return r;
}

export function toast(msg) {
  const t = $("#toast"); t.textContent = msg; t.style.display = "block";
  clearTimeout(t._h); t._h = setTimeout(() => t.style.display = "none", 7000);
}

const PY_KW = /\b(def|return|for|in|if|elif|else|with|as|import|from|and|or|not|None|True|False|lambda|class|try|except|while|yield|is)\b/g;

export function highlight(code) {
  if (code.lang === "xml") {
    return esc(code.text).replace(/(&lt;\/?[\w:]+)/g, '<span class="tag">$1</span>').replace(/(&quot;[^&]*?&quot;)/g, '<span class="st">$1</span>')
      .replace(/(&lt;!--[\s\S]*?--&gt;)/g, '<span class="cm">$1</span>');
  }
  const tokens = [];
  const stash = (cls) => (m) => { tokens.push(`<span class="${cls}">${esc(m)}</span>`); return String.fromCharCode(0xE000 + tokens.length - 1); };
  let s = code.text
    .replace(/("""[\s\S]*?"""|'''[\s\S]*?'''|f?"[^"\n]*"|f?'[^'\n]*')/g, stash("st"))
    .replace(/#[^\n]*/g, stash("cm"));
  s = esc(s).replace(PY_KW, '<span class="kw">$1</span>')
    .replace(/\b(\d+\.?\d*)\b/g, '<span class="nu">$1</span>')
    .replace(/\b([A-Za-z_]\w*)(?=\()/g, '<span class="fn">$1</span>');
  return s.replace(/[-]/g, ch => tokens[ch.charCodeAt(0) - 0xE000]);
}

export function kvHtml(rows) {
  return `<div class="kv">${rows.map(([a, b]) => `<div>${esc(a)}</div><div>${esc(b)}</div>`).join("")}</div>`;
}

export function tableHtml(t) {
  return `<table><tr>${t.head.map(h => `<th>${esc(h)}</th>`).join("")}</tr>` +
    t.rows.map(r => `<tr>${r.map(c => {
      const s = String(c);
      const cls = s.startsWith("✘") ? ' class="bad"' : s.startsWith("✔") ? ' class="good"' : "";
      return `<td${cls}>${esc(s)}</td>`;
    }).join("")}</tr>`).join("") + `</table>`;
}

const charts = new Map();

export function renderCharts(container, list) {
  (charts.get(container) || []).forEach(c => c.destroy());
  container.innerHTML = "";
  const made = [];
  for (const ch of list || []) {
    const box = document.createElement("div"); box.className = "chart-box";
    const cv = document.createElement("canvas"); box.appendChild(cv); container.appendChild(box);
    const isBar = ch.type === "bar";
    const datasets = ch.datasets.map(d => ({
      label: d.label,
      data: isBar ? d.data.map(p => p[1]) : d.data.map(([x, y]) => ({ x, y })),
      borderColor: css(d.color), backgroundColor: isBar ? css(d.color) : (d.fill ? css(d.color).replace("rgb", "rgba").replace(")", ", .15)") : css(d.color)),
      borderDash: d.dashed ? [5, 4] : [], fill: !!d.fill, tension: 0.15, borderWidth: 2,
      pointRadius: d.points ? (d.label === "Optimum" ? 7 : d.label === "aktuell" ? 6 : 3.5) : 0,
      showLine: !d.points, pointStyle: d.label === "Optimum" ? "star" : "circle",
    }));
    made.push(new Chart(cv, {
      type: isBar ? "bar" : (ch.type === "scatter" ? "scatter" : "line"),
      data: isBar ? { labels: ch.labels, datasets } : { datasets },
      options: {
        responsive: true, maintainAspectRatio: false, animation: false, parsing: isBar ? undefined : false,
        plugins: {
          title: { display: true, text: ch.title, color: "#e6e8eb", font: { size: 12, weight: "600" } },
          legend: { display: datasets.length > 1, labels: { color: "#95a0ac", boxWidth: 10, font: { size: 10.5 } } },
        },
        scales: {
          x: { type: isBar ? "category" : "linear", title: { display: !!ch.xlabel, text: ch.xlabel, color: "#95a0ac" },
               ticks: { color: "#95a0ac", maxRotation: 30, font: { size: 10 } }, grid: { color: "#252c35" } },
          y: { type: ch.ylog ? "logarithmic" : "linear", title: { display: !!ch.ylabel, text: ch.ylabel, color: "#95a0ac" }, ticks: { color: "#95a0ac", font: { size: 10 } }, grid: { color: "#252c35" } },
        },
      },
    }));
  }
  charts.set(container, made);
}

/** Ergebnisblock (Kennzahlen, Farbskala, Hinweise, Diagramme, Bilder, Tabelle, Downloads) für Tour & Pipeline. */
export function renderResult(root, pl) {
  const parts = [];
  if (pl.stats?.length) parts.push(`<h3>Kennzahlen</h3>${kvHtml(pl.stats)}`);
  if (pl.colorbar) parts.push(`<h3>${esc(pl.colorbar.label)}</h3><div class="colorbar"></div>
    <div class="colorbar-l"><span>${fmt(pl.colorbar.min, 1)} ${pl.colorbar.unit}</span><span>${fmt(pl.colorbar.max, 1)} ${pl.colorbar.unit}</span></div>`);
  if (pl.notes?.length) parts.push(`<div class="notes">${pl.notes.map(n => `<div>${esc(n)}</div>`).join("")}</div>`);
  parts.push(`<div class="charts"></div>`);
  if (pl.images?.length) parts.push(`<h3>Projektionen</h3><div class="images">${pl.images.map(i =>
    `<figure><img src="${i.src}" alt=""><figcaption>${esc(i.title)}</figcaption></figure>`).join("")}</div>`);
  if (pl.table) parts.push(`<h3>Details</h3>${tableHtml(pl.table)}`);
  if (pl.downloads?.length) parts.push(`<h3>Dateien</h3><div class="actions">${pl.downloads.map(d =>
    `<a class="btn" href="${d.url}" download>${esc(d.label)}</a>`).join("")}</div>`);
  root.innerHTML = parts.join("");
  renderCharts($(".charts", root), pl.charts);
}
