import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { LineSegments2 } from "three/addons/lines/LineSegments2.js";
import { LineSegmentsGeometry } from "three/addons/lines/LineSegmentsGeometry.js";
import { LineMaterial } from "three/addons/lines/LineMaterial.js";

const col = (c) => new THREE.Color(c[0], c[1], c[2]);

export class Viewer {
  constructor(canvas) {
    this.canvas = canvas;
    this.renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
    this.renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
    this.scene = new THREE.Scene();
    this.camera = new THREE.PerspectiveCamera(35, 1, 1, 50000);
    this.camera.up.set(0, 0, 1);
    this.controls = new OrbitControls(this.camera, canvas);
    this.controls.enableDamping = true;
    this.scene.add(new THREE.HemisphereLight(0xdfe8f5, 0x20252c, 1.1));
    const sun = new THREE.DirectionalLight(0xffffff, 1.6); sun.position.set(300, -400, 600); this.scene.add(sun);
    const fill = new THREE.DirectionalLight(0xffffff, 0.5); fill.position.set(-400, 300, 200); this.scene.add(fill);
    this.grid = new THREE.GridHelper(1600, 80, 0x33404d, 0x222a33);
    this.grid.rotation.x = Math.PI / 2; this.grid.position.z = -0.5; this.scene.add(this.grid);
    this.groups = {};
    for (const k of ["scene", "werk", "orig", "lower", "props", "payload"]) { this.groups[k] = new THREE.Group(); this.scene.add(this.groups[k]); }
    this.spinners = []; this.spin = true; this.explode = 40; this.showEdges = true;
    this.lineMats = new Set();
    this.clock = new THREE.Clock();
    new ResizeObserver(() => this.resize()).observe(canvas.parentElement);
    this.resize();
    const loop = () => {
      const dt = this.clock.getDelta();
      if (this.spin) for (const s of this.spinners) s.pivot.rotateOnAxis(s.axis, s.dir * dt * 14);
      this.controls.update(); this.renderer.render(this.scene, this.camera); requestAnimationFrame(loop);
    };
    loop();
  }

  resize() {
    const r = this.canvas.parentElement.getBoundingClientRect();
    if (!r.width || !r.height) return;
    this.renderer.setSize(r.width, r.height, false);
    this.camera.aspect = r.width / r.height; this.camera.updateProjectionMatrix();
    for (const m of this.lineMats) m.resolution.set(r.width, r.height);
  }

  static geom(m) {
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.Float32BufferAttribute(m.vertices, 3));
    if (m.colors) g.setAttribute("color", new THREE.Float32BufferAttribute(m.colors, 3));
    g.setIndex(m.triangles); g.computeVertexNormals(); return g;
  }

  clear(group) {
    for (const c of [...group.children]) {
      group.remove(c);
      c.traverse(o => { o.geometry?.dispose(); if (o.material) { this.lineMats.delete(o.material); o.material.dispose?.(); } });
    }
    if (group === this.groups.scene) this.spinners = [];
  }

  meshObj(m, { edges = true } = {}) {
    const obj = new THREE.Group();
    const opacity = m.opacity ?? 1;
    const mat = new THREE.MeshStandardMaterial({
      color: m.colors ? 0xffffff : col(m.color || [0.6, 0.6, 0.6]), vertexColors: !!m.colors, roughness: .55, metalness: .05,
      side: THREE.DoubleSide, transparent: opacity < 1, opacity, depthWrite: opacity >= 0.99,
      polygonOffset: true, polygonOffsetFactor: 1, polygonOffsetUnits: 1,
    });
    const mesh = new THREE.Mesh(Viewer.geom(m), mat);
    if (opacity < 1) mesh.renderOrder = 2;
    obj.add(mesh);
    if (edges && m.edges && m.edges.length) {
      const eg = new THREE.BufferGeometry(); eg.setAttribute("position", new THREE.Float32BufferAttribute(m.edges, 3));
      const lines = new THREE.LineSegments(eg, new THREE.LineBasicMaterial({ color: 0x0b0e11, transparent: true, opacity: .55 * opacity }));
      lines.name = "edges"; lines.visible = this.showEdges; obj.add(lines);
    }
    return obj;
  }

  lineObj(item) {
    const g = new LineSegmentsGeometry(); g.setPositions(item.segments);
    const mat = new LineMaterial({ color: col(item.color), linewidth: item.width || 2, depthTest: false, transparent: true });
    const r = this.canvas.parentElement.getBoundingClientRect(); mat.resolution.set(r.width, r.height);
    this.lineMats.add(mat);
    const l = new LineSegments2(g, mat); l.computeLineDistances(); l.renderOrder = 5; return l;
  }

  /** Tour-/Pipeline-Szene aus Payload-Items. */
  setItems(items, { markers = [], explode = false, fit = false } = {}) {
    const g = this.groups.scene;
    this.clear(g);
    for (const it of items || []) {
      let obj;
      if (it.segments) obj = this.lineObj(it);
      else if (it.vertices) obj = this.meshObj(it);
      else continue;
      obj.userData.id = it.id;
      if (it.spin) {
        const pivot = new THREE.Group(); pivot.position.set(...it.spin.center);
        obj.position.set(-it.spin.center[0], -it.spin.center[1], -it.spin.center[2]);
        pivot.add(obj); g.add(pivot);
        this.spinners.push({ pivot, axis: new THREE.Vector3(...it.spin.axis).normalize(), dir: it.spin.dir || 1 });
        continue;
      }
      if (explode && /Nasenkappe$/.test(it.id)) obj.userData.explode = true;
      g.add(obj);
    }
    for (const mk of markers) {
      const s = new THREE.Mesh(new THREE.SphereGeometry(mk.radius, 24, 16), new THREE.MeshStandardMaterial({ color: col(mk.color), emissive: col(mk.color), emissiveIntensity: .25 }));
      s.position.set(...mk.pos); s.renderOrder = 4; g.add(s);
    }
    this.applyExplode();
    if (fit) this.fit("iso", g);
  }

  applyExplode() {
    for (const k of ["scene", "werk", "orig"]) this.groups[k].traverse(o => { if (o.userData.explode) o.position.z = this.explode; });
  }

  setExplode(v) { this.explode = v; this.applyExplode(); }

  setEdges(on) {
    this.showEdges = on;
    for (const g of Object.values(this.groups)) g.traverse(o => { if (o.name === "edges") o.visible = on; });
  }

  show(keys) { for (const [k, g] of Object.entries(this.groups)) g.visible = keys.includes(k); }

  fit(kind = "iso", group = null) {
    this.resize();
    const target = group || (this.groups.scene.visible && this.groups.scene.children.length ? this.groups.scene : this.groups.werk);
    const box = new THREE.Box3().setFromObject(target);
    if (box.isEmpty()) return;
    const c = box.getCenter(new THREE.Vector3()), size = box.getSize(new THREE.Vector3()).length();
    const dir = { iso: [1, -1.25, .75], front: [0, -1, 0.02], top: [0.001, -0.001, 1] }[kind];
    const dist = size * 0.62 / Math.tan(this.camera.fov * Math.PI / 360) / Math.min(1, this.camera.aspect);
    this.camera.position.copy(c).add(new THREE.Vector3(...dir).normalize().multiplyScalar(dist));
    this.controls.target.copy(c); this.controls.update();
  }

  // ---------------- Werkbank-spezifisch
  setVariant(meshes) {
    const g = this.groups.werk; this.clear(g);
    for (const [name, m] of Object.entries(meshes)) {
      const obj = this.meshObj(m);
      if (name === "Nasenkappe") obj.userData.explode = true;
      g.add(obj);
    }
    this.applyExplode();
  }

  setOriginal(data) {
    if (this.groups.orig.children.length) return;
    const ghost = new THREE.MeshStandardMaterial({ color: 0xcfd8e3, transparent: true, opacity: .28, depthWrite: false, side: THREE.DoubleSide });
    for (const [name, m] of Object.entries(data)) {
      if (name === "Unterteil") {
        this.groups.lower.add(new THREE.Mesh(Viewer.geom(m), new THREE.MeshStandardMaterial({ color: 0x9aa4b1, roughness: .6, side: THREE.DoubleSide })));
      } else {
        const mesh = new THREE.Mesh(Viewer.geom(m), ghost); mesh.renderOrder = 2;
        if (name === "Nasenkappe") mesh.userData.explode = true;
        this.groups.orig.add(mesh);
      }
    }
    this.applyExplode();
  }

  setAux(p, req, checks) {
    this.clear(this.groups.props); this.clear(this.groups.payload);
    const bad = (prefix) => (checks || []).some(c => c.name.startsWith(prefix) && !c.ok);
    const propBad = bad("Propeller");
    for (let i = 0; i < p.arm_count; i++) {
      const a = (p.arm_angle + i * 360 / p.arm_count) * Math.PI / 180, r = req.prop_diameter / 2;
      const c = propBad ? 0xef5b5b : 0x9fd8ff;
      const disc = new THREE.Mesh(new THREE.CylinderGeometry(r, r, 0.6, 64),
        new THREE.MeshBasicMaterial({ color: c, transparent: true, opacity: .18, depthWrite: false, side: THREE.DoubleSide }));
      disc.rotation.x = Math.PI / 2;
      disc.position.set(p.arm_reach * Math.cos(a), p.arm_reach * Math.sin(a), p.arm_thickness + p.pod_height + 4);
      const ring = new THREE.LineLoop(new THREE.BufferGeometry().setFromPoints(
        Array.from({ length: 65 }, (_, k) => new THREE.Vector3(Math.cos(k / 64 * 2 * Math.PI) * r, Math.sin(k / 64 * 2 * Math.PI) * r, 0))),
        new THREE.LineBasicMaterial({ color: c, transparent: true, opacity: .6 }));
      ring.position.copy(disc.position);
      this.groups.props.add(disc, ring);
    }
    const pl = new THREE.Mesh(new THREE.CylinderGeometry(req.payload_diameter / 2, req.payload_diameter / 2, req.payload_length, 48),
      new THREE.MeshStandardMaterial({ color: bad("Nutzlast") ? 0xef5b5b : 0xb48cff, transparent: true, opacity: .55 }));
    pl.rotation.x = Math.PI / 2; pl.position.z = req.payload_length / 2 + 1;
    this.groups.payload.add(pl);
  }
}
