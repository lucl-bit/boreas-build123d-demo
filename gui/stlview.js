import * as THREE from "three";
import { STLLoader } from "three/addons/loaders/STLLoader.js";
import { toCreasedNormals } from "three/addons/utils/BufferGeometryUtils.js";
import { Viewer } from "/gui/viewer.js";

const PALETTE = [0x4cc38a, 0x3a8fd8, 0xf2852e, 0xb48cff, 0xf0b429, 0x5fd0d0, 0xe0669c, 0x9aa4b1];

/** Teilefarbe nach Name (Ober-/Unterteil/Nase/Gondeln …), sonst Palette. */
export function partColor(name, i = 0) {
  const n = String(name).toLowerCase();
  if (/upper|ober|rumpf/.test(n)) return 0x4cc38a;
  if (/lower|unter/.test(n)) return 0x3a8fd8;
  if (/nose|nase/.test(n)) return 0xf2852e;
  if (/pod|gondel|motor/.test(n)) return 0xb48cff;
  if (/fin|flosse/.test(n)) return 0x5fd0d0;
  if (/arm/.test(n)) return 0xf0b429;
  if (/^modell$|^mesh$|^model$/.test(n)) return 0xaab4c0;
  return PALETTE[i % PALETTE.length];
}
export const hex = (c) => "#" + c.toString(16).padStart(6, "0");

const VIEW_DIR = { iso: [1, -1.25, .75], front: [0, -1, 0.02], top: [0.001, -0.001, 1], side: [1, 0, 0.02] };

/** Lädt eine Datei mit Fortschritt; bricht über AbortSignal ab. */
async function fetchBuffer(url, signal, onProgress) {
  const r = await fetch(url, { signal });
  if (!r.ok) throw new Error(`${url}: HTTP ${r.status}`);
  const total = +r.headers.get("Content-Length") || 0;
  if (!r.body?.getReader) return await r.arrayBuffer();
  const reader = r.body.getReader(); const chunks = []; let got = 0;
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    chunks.push(value); got += value.length; onProgress?.(got, total);
  }
  const buf = new Uint8Array(got); let o = 0;
  for (const c of chunks) { buf.set(c, o); o += c.length; }
  return buf.buffer;
}

/** Viewer für STL-Modelle (auch mit Millionen Dreiecken): lazy laden, Teile einfärben, alte Geometrie freigeben. */
export class StlViewer extends Viewer {
  constructor(canvas, { smooth = false } = {}) {
    super(canvas);
    this.demand = true; this.spin = false; this.smooth = smooth; this.wire = false;
    this.model = new THREE.Group(); this.scene.add(this.model);
    this.parts = [];
    this.controls.addEventListener("change", () => this.requestRender());
    this.scene.background = new THREE.Color(0x11151a);
    // Rendern nur auf Anforderung: bei Grössenänderung neu zeichnen; war die Fläche beim Laden unsichtbar, neu einpassen
    this._lastW = canvas.clientWidth;
    new ResizeObserver(() => {
      const w = canvas.clientWidth, wasHidden = !this._lastW;
      this._lastW = w;
      if (!w) return;
      if (wasHidden && this.parts.length) this.fitBox("iso", this.bbox());
      else { this.resize(); this.requestRender(); }
    }).observe(canvas.parentElement || canvas);
  }

  clearModel() {
    for (const c of [...this.model.children]) {
      this.model.remove(c);
      c.geometry?.dispose(); c.material?.dispose?.();
    }
    this.parts = []; this.requestRender();
  }

  /** items: [{name, url}] → { tris, bytes, ms, box }. Wirft bei Abbruch (AbortError). */
  async load(items, { signal, onProgress } = {}) {
    this.clearModel();
    const t0 = performance.now(); let tris = 0, bytes = 0;
    const totals = items.map(() => [0, 0]);
    const report = (i, got, total) => {
      totals[i] = [got, total];
      onProgress?.(totals.reduce((a, t) => a + t[0], 0), totals.reduce((a, t) => a + (t[1] || 0), 0));
    };
    const bufs = await Promise.all(items.map((it, i) => fetchBuffer(it.url, signal, (g, t) => report(i, g, t))));
    if (signal?.aborted) throw new DOMException("abgebrochen", "AbortError");
    await new Promise(r => setTimeout(r, 20));       // UI atmen lassen, bevor grosse Netze geparst werden (kein rAF: pausiert in Hintergrund-Tabs)
    const loader = new STLLoader();
    items.forEach((it, i) => {
      let geo = loader.parse(bufs[i]); bufs[i] = null; bytes += geo.attributes.position.count * 12;
      const nT = geo.attributes.position.count / 3; tris += nT;
      const nrm = geo.attributes.normal;
      if (!nrm || (nrm.getX(0) === 0 && nrm.getY(0) === 0 && nrm.getZ(0) === 0)) geo.computeVertexNormals();
      if (this.smooth && nT < 250000) {
        try { const g2 = toCreasedNormals(geo, Math.PI / 6); geo.dispose(); geo = g2; } catch { /* flache Normalen bleiben */ }
      }
      const color = it.color ?? partColor(it.name, i);
      const mesh = new THREE.Mesh(geo, new THREE.MeshStandardMaterial({
        color, roughness: .55, metalness: .05, side: THREE.DoubleSide, wireframe: this.wire,
        polygonOffset: true, polygonOffsetFactor: 1, polygonOffsetUnits: 1,
      }));
      mesh.name = it.name;
      this.model.add(mesh); this.parts.push({ name: it.name, mesh, color, tris: nT });
    });
    const box = new THREE.Box3().setFromObject(this.model);
    if (!box.isEmpty()) this.grid.position.z = box.min.z - 0.5;
    this.requestRender();
    return { tris, bytes, ms: performance.now() - t0, box };
  }

  setPartVisible(name, on) { for (const p of this.parts) if (p.name === name) p.mesh.visible = on; this.requestRender(); }
  setWire(on) { this.wire = on; for (const p of this.parts) p.mesh.material.wireframe = on; this.requestRender(); }

  bbox() { const b = new THREE.Box3().setFromObject(this.model); return b.isEmpty() ? null : b; }

  fitBox(kind, box) {
    this.resize();
    if (!box || box.isEmpty()) return;
    const c = box.getCenter(new THREE.Vector3()), size = box.getSize(new THREE.Vector3()).length();
    const dist = size * 0.62 / Math.tan(this.camera.fov * Math.PI / 360) / Math.min(1, this.camera.aspect);
    this.camera.position.copy(c).add(new THREE.Vector3(...VIEW_DIR[kind]).normalize().multiplyScalar(dist));
    this.controls.target.copy(c); this.controls.update(); this.requestRender();
  }

  camState() { return { pos: this.camera.position.clone(), target: this.controls.target.clone() }; }
  setCam(s) { this.camera.position.copy(s.pos); this.controls.target.copy(s.target); this.controls.update(); this.requestRender(); }
}
