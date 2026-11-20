// The three.js factory floor, concept 1 "isometric conveyor" (decision D-152; reference: the CONVEYOR scene in
// design/concepts/floor-3d-concepts.html). Only Floor3D imports this file.
// A fixed orthographic camera looks down at an angle. Each line is a belt, running left to right, and each station a
// machine on it, in returned order. The stack of white blocks on a machine is the waiting count (at most 8, so tall
// stacks stay readable; the label above carries the exact number). A station that needs a person is an orange
// machine with a lamp. Boxes ride the belts left to right while the tab is visible; with reduced motion nothing moves.
// No agents are drawn: E-OVERVIEW does not say where an agent works.
import {
  BoxGeometry,
  BoxHelper,
  Color,
  DirectionalLight,
  EdgesGeometry,
  Group,
  HemisphereLight,
  LineBasicMaterial,
  LineSegments,
  Mesh,
  MeshBasicMaterial,
  MeshLambertMaterial,
  Object3D,
  OrthographicCamera,
  PCFSoftShadowMap,
  Raycaster,
  Scene,
  Vector2,
  Vector3,
  WebGLRenderer,
  type Material,
} from 'three';

import { tagTone } from '@/features/overview/lines';
import type { OverviewLine, OverviewStation } from '@/features/overview/types';

import { describeStation } from './support';

/** Design tokens read from CSS custom properties at mount. */
export type FloorStyle = {
  ink: string;
  belt: string;
  signal: string;
  signalTint: string;
  surface: string;
  board: string;
  plate: string;
  muted: string;
  focus: string;
};

const SPAN = 13.2; // first to last station, in scene units
const GAP = 3.3; // between belts
const BELT = SPAN + 2.8;
const MAX_BLOCKS = 8;
const BLOCK = 0.6;
const SLATS = 18;
const VIEW = { yaw: 0.42, pitch: 0.72, yawMin: -0.3, yawMax: 1.2, pitchMin: 0.32, pitchMax: 1.2 };
const STEP = 0.16; // one key press: yaw moves 1.5 steps, pitch one

type Machine = {
  key: string;
  line: string;
  value: OverviewStation;
  parts: Group;
  hits: Mesh[];
  body: Mesh | null;
  lamp: Mesh | null;
  x: number;
  z: number;
  anchor: Object3D;
  chip: HTMLButtonElement;
};
type Label = { el: HTMLElement; anchor: Object3D; align: 'bottom' | 'right' };
type Mover = { mesh: Mesh; x1: number; x2: number; k: number };
type Slat = { mesh: Mesh; k: number };

const stationKey = (line: string, name: string) => `${line}\u0000${name}`;
const shapeOf = (lines: readonly OverviewLine[]) => JSON.stringify(lines.map((l) => [l.line, l.stations.map((s) => s.name)]));
const stationX = (i: number, n: number) => -SPAN / 2 + (n < 2 ? 0 : (i / (n - 1)) * SPAN);
const frac = (x: number) => x - Math.floor(x);
const reducedMotion = () => typeof window.matchMedia === 'function' && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
const clampView = (v: { yaw: number; pitch: number }) => ({
  yaw: Math.max(VIEW.yawMin, Math.min(VIEW.yawMax, v.yaw)),
  pitch: Math.max(VIEW.pitchMin, Math.min(VIEW.pitchMax, v.pitch)),
});

export type FloorCallbacks = { onReadout: (text: string | null, needsPerson: boolean) => void };

export class FloorScene {
  private readonly renderer: WebGLRenderer;
  private readonly scene = new Scene();
  private readonly camera = new OrthographicCamera(-10, 10, 10, -10, 0.1, 400);
  private readonly raycaster = new Raycaster();
  private readonly c: Record<keyof FloorStyle, Color>;
  private root = new Group();
  private geometries = new Map<string, BoxGeometry>();
  private edgeGeometries = new Map<BoxGeometry, EdgesGeometry>();
  private materials = new Map<string, Material>();
  private machines = new Map<string, Machine>();
  private rows: Machine[][] = [];
  private lineTags: HTMLElement[] = [];
  private labels: Label[] = [];
  private slats: Slat[] = [];
  private movers: Mover[] = [];
  private moverGroup = new Group();
  private prev: readonly OverviewLine[] | null = null;
  private shape = '';
  private view = { yaw: VIEW.yaw, pitch: VIEW.pitch };
  private target = new Vector3();
  private dist = 80;
  private fitPoints: Vector3[] = [];
  private size = { width: 1, height: 1 };
  private hover: Machine | null = null;
  private focus: Machine | null = null;
  private outline: BoxHelper | null = null;
  private drag: { x: number; y: number; moved: boolean } | null = null;
  private time = 0;
  private frame = 0;
  private last = 0;
  private readonly unbind: () => void;

  /** Throws when WebGL cannot start; the caller falls back to the flat view. */
  constructor(
    private readonly canvas: HTMLCanvasElement,
    private readonly overlay: HTMLElement,
    style: FloorStyle,
    private readonly callbacks: FloorCallbacks,
  ) {
    this.renderer = new WebGLRenderer({ canvas, antialias: true, powerPreference: 'low-power' });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    this.renderer.shadowMap.enabled = true;
    this.renderer.shadowMap.type = PCFSoftShadowMap;
    this.c = Object.fromEntries(Object.entries(style).map(([k, v]) => [k, new Color(v)])) as Record<keyof FloorStyle, Color>;
    this.scene.background = this.c.board;
    // three's lights are physical since r155; PI keeps the reference's r128 brightness.
    this.scene.add(new HemisphereLight(0xffffff, this.c.plate, 0.78 * Math.PI));
    const sun = new DirectionalLight(0xffffff, 0.5 * Math.PI);
    sun.position.set(-6, 14, 9);
    sun.castShadow = true;
    sun.shadow.mapSize.set(1024, 1024);
    Object.assign(sun.shadow.camera, { left: -22, right: 22, top: 22, bottom: -22, near: 1, far: 50 });
    sun.shadow.bias = -0.0008;
    this.scene.add(sun);
    this.scene.add(this.root);
    this.unbind = this.bind();
  }

  private mat(color: keyof FloorStyle) {
    let m = this.materials.get(color) as MeshLambertMaterial | undefined;
    if (!m) this.materials.set(color, (m = new MeshLambertMaterial({ color: this.c[color] })));
    return m;
  }

  private edgeMat(color: keyof FloorStyle) {
    const key = `edge:${color}`;
    let m = this.materials.get(key) as LineBasicMaterial | undefined;
    if (!m) this.materials.set(key, (m = new LineBasicMaterial({ color: this.c[color] })));
    return m;
  }

  private box(parent: Object3D, w: number, h: number, d: number, x: number, y: number, z: number, color: keyof FloorStyle, edge?: keyof FloorStyle, cast = true) {
    const key = `${w}|${h}|${d}`;
    let geometry = this.geometries.get(key);
    if (!geometry) {
      geometry = new BoxGeometry(w, h, d);
      geometry.translate(0, h / 2, 0);
      this.geometries.set(key, geometry);
      this.edgeGeometries.set(geometry, new EdgesGeometry(geometry));
    }
    const mesh = new Mesh(geometry, this.mat(color));
    mesh.position.set(x, y, z);
    mesh.castShadow = cast;
    mesh.receiveShadow = true;
    if (edge) mesh.add(new LineSegments(this.edgeGeometries.get(geometry)!, this.edgeMat(edge)));
    parent.add(mesh);
    return mesh;
  }

  /** Frees every shared geometry and material; the meshes that used them must be gone. */
  private freeShared() {
    for (const g of this.geometries.values()) g.dispose();
    for (const g of this.edgeGeometries.values()) g.dispose();
    for (const m of this.materials.values()) m.dispose();
    this.geometries.clear();
    this.edgeGeometries.clear();
    this.materials.clear();
  }

  private anchor(parent: Object3D, x: number, y: number, z: number) {
    const o = new Object3D();
    o.position.set(x, y, z);
    parent.add(o);
    return o;
  }

  private chipFor(card: Pick<Machine, 'line' | 'value'>, chip = document.createElement('button')) {
    const s = card.value;
    chip.type = 'button';
    chip.className = `floor__chip${s.needs_person ? ' floor__chip--person' : s.count > 0 ? '' : ' floor__chip--empty'}`;
    // The name starts with the visible words, then reads the station in full.
    const shown = `${s.count} ${s.name}${s.needs_person ? ' PERSON' : ''}`;
    chip.setAttribute('aria-label', `${shown}. ${describeStation(card.line, s)}`);
    chip.replaceChildren();
    const count = document.createElement('b');
    count.textContent = String(s.count);
    const name = document.createElement('span');
    name.textContent = s.name;
    chip.append(count, ' ', name);
    if (s.needs_person) {
      const person = document.createElement('em');
      person.textContent = 'PERSON';
      chip.append(' ', person);
    }
    return chip;
  }


  /** Draws one machine as its station says: body, stack of blocks, and a lamp when a person is needed. */
  private paint(m: Machine) {
    const s = m.value;
    m.parts.clear();
    m.hits = [];
    m.lamp?.geometry.dispose();
    (m.lamp?.material as Material | undefined)?.dispose();
    m.lamp = null;
    const has = s.count > 0;
    const blocks = Math.min(s.count, MAX_BLOCKS);
    m.body = this.box(m.parts, 1.3, 0.55, 1.25, m.x, 0.18, m.z, s.needs_person ? 'signal' : has ? 'ink' : 'surface', s.needs_person ? 'ink' : has ? 'muted' : 'ink');
    m.hits.push(m.body);
    for (let i = 0; i < blocks; i++) m.hits.push(this.box(m.parts, 0.62, 0.56, 0.62, m.x, 0.73 + i * BLOCK, m.z, s.needs_person ? 'signalTint' : 'surface', 'ink'));
    for (const hit of m.hits) hit.userData.machine = m;
    let top = 0.73 + blocks * BLOCK + 0.12;
    if (s.needs_person) {
      this.box(m.parts, 0.07, 1.55, 0.07, m.x + 0.56, 0.73, m.z - 0.53, 'ink');
      m.lamp = new Mesh(new BoxGeometry(0.28, 0.28, 0.28), new MeshBasicMaterial({ color: this.c.signal }));
      m.lamp.position.set(m.x + 0.56, 2.4, m.z - 0.53);
      m.parts.add(m.lamp);
      top = Math.max(top, 0.9);
    }
    m.anchor.position.set(m.x, top, m.z);
    this.chipFor(m, m.chip);
    if (m === (this.focus ?? this.hover)) this.outlineFor(m);
  }

  /** Boxes that ride a belt from each busy station to the next, two at most per station. */
  private rebuildMovers() {
    this.moverGroup.clear();
    this.movers = [];
    this.rows.forEach((row, li) => {
      row.forEach((m, i) => {
        if (m.value.count === 0 || i === row.length - 1) return;
        for (let k = 0; k < Math.min(m.value.count, 2); k++) {
          const mesh = this.box(this.moverGroup, 0.36, 0.3, 0.36, m.x, 0.18, m.z, 'surface', 'ink');
          this.movers.push({ mesh, x1: m.x + 0.85, x2: row[i + 1].x - 0.85, k: k / 2 + li * 0.13 });
        }
      });
    });
    this.animate(0);
  }

  /** Builds the floor, every belt and every machine as given. */
  private build(lines: readonly OverviewLine[]) {
    this.scene.remove(this.root);
    this.disposeOutline();
    this.disposeLamps();
    this.root = new Group();
    this.freeShared();
    this.scene.add(this.root);
    this.overlay.replaceChildren();
    this.machines.clear();
    this.rows = [];
    this.lineTags = [];
    this.labels = [];
    this.slats = [];
    this.moverGroup = new Group();
    this.root.add(this.moverGroup);
    this.hover = this.focus = null;

    const n = Math.max(1, lines.length);
    const z0 = (-(n - 1) * GAP) / 2;
    this.box(this.root, SPAN + 6.4, 0.4, (n - 1) * GAP + 3.2, 0, -0.4, 0, 'plate', 'ink', false);
    lines.forEach((l, li) => {
      const z = z0 + li * GAP;
      this.box(this.root, BELT, 0.18, 0.9, 0, 0, z, 'belt', undefined, false);
      this.box(this.root, BELT, 0.3, 0.08, 0, 0, z - 0.49, 'ink');
      this.box(this.root, BELT, 0.3, 0.08, 0, 0, z + 0.49, 'ink');
      for (let s = 0; s < SLATS; s++) this.slats.push({ mesh: this.box(this.root, 0.1, 0.02, 0.82, 0, 0.18, z, 'muted', undefined, false), k: s / SLATS });

      const label = document.createElement('div');
      label.className = 'floor__line';
      label.setAttribute('aria-hidden', 'true');
      const name = document.createElement('strong');
      name.textContent = l.line;
      const tag = document.createElement('span');
      tag.className = `psl-tag psl-tag--${tagTone(l)}`;
      tag.textContent = l.note;
      label.append(name, tag);
      this.lineTags.push(tag);
      this.addLabel(label, this.anchor(this.root, -BELT / 2 - 0.9, 0.1, z), 'right');

      const row: Machine[] = [];
      l.stations.forEach((s, i) => {
        const parts = new Group();
        this.root.add(parts);
        const m: Machine = {
          key: stationKey(l.line, s.name),
          line: l.line,
          value: s,
          parts,
          hits: [],
          body: null,
          lamp: null,
          x: stationX(i, l.stations.length),
          z,
          anchor: this.anchor(this.root, 0, 0, 0),
          chip: document.createElement('button'),
        };
        this.paint(m);
        m.chip.addEventListener('pointerenter', () => this.setHover(m));
        m.chip.addEventListener('pointerleave', () => this.setHover(null));
        m.chip.addEventListener('focus', () => this.setFocus(m));
        m.chip.addEventListener('blur', () => this.setFocus(null));
        this.machines.set(m.key, m);
        row.push(m);
        this.addLabel(m.chip, m.anchor, 'bottom');
      });
      this.rows.push(row);
    });
    this.rebuildMovers();
    this.root.updateMatrixWorld(true);
    // Fit to the tallest stack so a count change never moves the view.
    this.fitPoints = this.labels.map((label) => {
      const p = label.anchor.getWorldPosition(new Vector3());
      if (label.align === 'bottom') p.y = 0.73 + MAX_BLOCKS * BLOCK + 0.12;
      return p;
    });
    this.fit();
  }

  private disposeLamps() {
    for (const m of this.machines.values()) {
      m.lamp?.geometry.dispose();
      (m.lamp?.material as Material | undefined)?.dispose();
    }
  }

  private addLabel(el: HTMLElement, anchor: Object3D, align: Label['align']) {
    const wrap = document.createElement('div');
    wrap.className = 'floor__label';
    wrap.append(el);
    this.overlay.append(wrap);
    this.labels.push({ el: wrap, anchor, align });
  }

  /** Frames every label anchor with the orthographic frustum at the default angle, then lets the labels themselves fill the stage. */
  private fit() {
    if (!this.fitPoints.length) return;
    const { width, height } = this.size;
    const saved = { ...this.view };
    this.view = { yaw: VIEW.yaw, pitch: VIEW.pitch };
    const lo = new Vector3(Infinity, Infinity, Infinity);
    const hi = new Vector3(-Infinity, -Infinity, -Infinity);
    for (const p of this.fitPoints) {
      lo.min(p);
      hi.max(p);
    }
    this.target.copy(lo).add(hi).multiplyScalar(0.5);
    this.target.y *= 0.5;
    this.dist = 80;
    this.place();
    let minX = Infinity;
    let maxX = -Infinity;
    let minY = Infinity;
    let maxY = -Infinity;
    const q = new Vector3();
    for (const p of this.fitPoints) {
      q.copy(p).applyMatrix4(this.camera.matrixWorldInverse);
      minX = Math.min(minX, q.x);
      maxX = Math.max(maxX, q.x);
      minY = Math.min(minY, q.y);
      maxY = Math.max(maxY, q.y);
    }
    const margin = 0.86;
    const cx = (minX + maxX) / 2;
    const cy = (minY + maxY) / 2;
    let hw = (maxX - minX) / 2 / margin;
    let hh = ((maxY - minY) / 2 / margin) * 1.08;
    const aspect = width / height;
    if (hw / hh > aspect) hh = hw / aspect;
    else hw = hh * aspect;
    Object.assign(this.camera, { left: cx - hw, right: cx + hw, top: cy + hh, bottom: cy - hh });
    this.camera.updateProjectionMatrix();
    this.contain();
    this.view = saved;
    this.place();
  }

  /** Pans and zooms the frustum so the labels, not only their anchors, fill the stage. */
  private contain() {
    const { width, height } = this.size;
    const pad = 14;
    const cam = this.camera;
    for (let i = 0; i < 4; i++) {
      this.placeLabels();
      const stage = this.overlay.getBoundingClientRect();
      let minX = Infinity;
      let maxX = -Infinity;
      let minY = Infinity;
      let maxY = -Infinity;
      for (const label of this.labels) {
        const r = (label.el.firstElementChild ?? label.el).getBoundingClientRect();
        minX = Math.min(minX, r.left - stage.left);
        maxX = Math.max(maxX, r.right - stage.left);
        minY = Math.min(minY, r.top - stage.top);
        maxY = Math.max(maxY, r.bottom - stage.top);
      }
      if (!Number.isFinite(minX) || maxX - minX <= 0) return;
      const scale = Math.max(0.55, Math.min(3, Math.max((maxX - minX) / (width - 2 * pad), (maxY - minY) / (height - 2 * pad))));
      const dx = (minX + maxX) / 2 - width / 2;
      const dy = (minY + maxY) / 2 - height / 2;
      if (Math.abs(scale - 1) < 0.015 && Math.abs(dx) < 2 && Math.abs(dy) < 2) return;
      const fw = cam.right - cam.left;
      const fh = cam.top - cam.bottom;
      const mx = (cam.left + cam.right) / 2 + (dx / width) * fw;
      const my = (cam.top + cam.bottom) / 2 - (dy / height) * fh;
      Object.assign(cam, { left: mx - (fw * scale) / 2, right: mx + (fw * scale) / 2, top: my + (fh * scale) / 2, bottom: my - (fh * scale) / 2 });
      cam.updateProjectionMatrix();
    }
  }

  private place() {
    const { yaw, pitch } = this.view;
    const t = this.target;
    const d = this.dist;
    this.camera.position.set(t.x + d * Math.sin(yaw) * Math.cos(pitch), t.y + d * Math.sin(pitch), t.z + d * Math.cos(yaw) * Math.cos(pitch));
    this.camera.lookAt(t);
    this.camera.updateMatrixWorld();
  }

  private placeLabels() {
    const v = new Vector3();
    const { width, height } = this.size;
    for (const label of this.labels) {
      label.anchor.getWorldPosition(v).project(this.camera);
      if (v.z > 1 || v.z < -1) {
        label.el.style.visibility = 'hidden';
        continue;
      }
      label.el.style.visibility = '';
      const x = ((v.x + 1) / 2) * width;
      const y = ((1 - v.y) / 2) * height;
      const shift = label.align === 'right' ? 'translate(-100%, -50%)' : 'translate(-50%, -100%)';
      label.el.style.transform = `translate3d(${x.toFixed(1)}px, ${y.toFixed(1)}px, 0) ${shift}`;
      label.el.style.zIndex = String(Math.round((1 - v.z) * 5000) + (label.align === 'bottom' ? 20000 : 0));
    }
  }

  private readout() {
    const m = this.focus ?? this.hover;
    this.callbacks.onReadout(m ? describeStation(m.line, m.value) : null, Boolean(m?.value.needs_person));
  }

  private disposeOutline() {
    if (!this.outline) return;
    this.scene.remove(this.outline);
    this.outline.geometry.dispose();
    (this.outline.material as Material).dispose();
    this.outline = null;
  }

  private outlineFor(m: Machine | null) {
    this.disposeOutline();
    if (!m?.body) return;
    this.outline = new BoxHelper(m.body, this.c.focus);
    (this.outline.material as LineBasicMaterial).depthTest = false;
    this.outline.renderOrder = 10;
    this.scene.add(this.outline);
  }

  private showing(m: Machine | null) {
    this.outlineFor(m);
    this.readout();
    this.kick();
    this.render();
  }

  private setHover(m: Machine | null) {
    if (this.hover === m) return;
    this.hover?.chip.classList.remove('floor__chip--hot');
    this.hover = m;
    m?.chip.classList.add('floor__chip--hot');
    this.showing(this.focus ?? m);
  }

  private setFocus(m: Machine | null) {
    this.focus = m;
    this.showing(m ?? this.hover);
  }

  private pick(event: PointerEvent): Machine | null {
    const rect = this.canvas.getBoundingClientRect();
    const at = new Vector2(((event.clientX - rect.left) / rect.width) * 2 - 1, -((event.clientY - rect.top) / rect.height) * 2 + 1);
    this.raycaster.setFromCamera(at, this.camera);
    const meshes = [...this.machines.values()].flatMap((m) => m.hits);
    return (this.raycaster.intersectObjects(meshes, false)[0]?.object.userData.machine as Machine | undefined) ?? null;
  }

  private bind() {
    const el = this.canvas;
    const down = (e: PointerEvent) => {
      this.drag = { x: e.clientX, y: e.clientY, moved: false };
      try {
        el.setPointerCapture(e.pointerId);
      } catch {
        // capture is optional
      }
    };
    const move = (e: PointerEvent) => {
      if (this.drag) {
        const dx = e.clientX - this.drag.x;
        const dy = e.clientY - this.drag.y;
        if (!this.drag.moved && Math.abs(dx) + Math.abs(dy) > 4) this.drag.moved = true;
        if (this.drag.moved) {
          this.view = clampView({ yaw: this.view.yaw - dx * 0.006, pitch: this.view.pitch + dy * 0.005 });
          this.drag.x = e.clientX;
          this.drag.y = e.clientY;
          this.place();
          this.kick();
          this.render();
        }
      } else if (e.pointerType === 'mouse') this.setHover(this.pick(e));
    };
    const up = (e: PointerEvent) => {
      if (this.drag && !this.drag.moved) this.setHover(this.pick(e));
      this.drag = null;
    };
    const leave = (e: PointerEvent) => {
      if (!this.drag && e.pointerType === 'mouse') this.setHover(null);
    };
    const cancel = () => {
      this.drag = null;
    };
    const visibility = () => (document.hidden ? this.stop() : this.kick());
    el.addEventListener('pointerdown', down);
    el.addEventListener('pointermove', move);
    el.addEventListener('pointerup', up);
    el.addEventListener('pointerleave', leave);
    el.addEventListener('pointercancel', cancel);
    document.addEventListener('visibilitychange', visibility);
    return () => {
      el.removeEventListener('pointerdown', down);
      el.removeEventListener('pointermove', move);
      el.removeEventListener('pointerup', up);
      el.removeEventListener('pointerleave', leave);
      el.removeEventListener('pointercancel', cancel);
      document.removeEventListener('visibilitychange', visibility);
    };
  }

  /** Back to the starting angle. */
  reset() {
    this.view = { yaw: VIEW.yaw, pitch: VIEW.pitch };
    this.place();
    this.kick();
    this.render();
  }

  /** Turns (dx: right is positive) and tilts (dy: up looks from higher) the view by key steps. */
  turn(dx: number, dy: number) {
    this.view = clampView({ yaw: this.view.yaw + dx * STEP * 1.5, pitch: this.view.pitch + dy * STEP });
    this.place();
    this.kick();
    this.render();
  }

  /** Moves belts, boxes and lamps to time t; with reduced motion they stand still and the boxes are hidden. */
  private animate(dt: number) {
    const still = reducedMotion();
    if (!still) this.time += dt;
    const t = this.time;
    for (const s of this.slats) s.mesh.position.x = -BELT / 2 + 0.1 + frac(s.k + (still ? 0 : t * 0.045)) * (BELT - 0.2);
    for (const m of this.movers) {
      m.mesh.visible = !still;
      if (!still) m.mesh.position.x = m.x1 + (m.x2 - m.x1) * frac(m.k + t * 0.12);
    }
    const pulse = still ? 1 : 1 + 0.18 * Math.sin(t * 3);
    for (const m of this.machines.values()) m.lamp?.scale.set(pulse, pulse, pulse);
    this.outline?.update();
  }

  /** Starts the frame loop if it is not running; it stops by itself under reduced motion or while the tab is hidden. */
  private kick() {
    if (this.frame || document.hidden) return;
    this.last = performance.now();
    this.frame = requestAnimationFrame(this.step);
  }

  private stop() {
    if (this.frame) cancelAnimationFrame(this.frame);
    this.frame = 0;
  }

  private step = (now: number) => {
    const dt = Math.min(0.25, Math.max(0, (now - this.last) / 1000));
    this.last = now;
    this.animate(dt);
    this.render();
    this.frame = reducedMotion() || document.hidden ? 0 : requestAnimationFrame(this.step);
  };

  /** Shows the lines. The first call and a changed set of lines or stations rebuild; changed figures repaint their machine. */
  update(lines: readonly OverviewLine[]) {
    const prev = this.prev;
    this.prev = lines;
    const shape = shapeOf(lines);
    if (!prev || shape !== this.shape) {
      this.shape = shape;
      this.build(lines);
      this.kick();
      return this.render();
    }
    // Line notes and tones can change without a station change.
    lines.forEach((l, i) => {
      const tag = this.lineTags[i];
      tag.className = `psl-tag psl-tag--${tagTone(l)}`;
      tag.textContent = l.note;
    });
    let changed = false;
    for (const l of lines) {
      for (const s of l.stations) {
        const m = this.machines.get(stationKey(l.line, s.name))!;
        if (m.value.count === s.count && m.value.needs_person === s.needs_person) continue;
        m.value = s;
        this.paint(m);
        changed = true;
      }
    }
    if (changed) this.rebuildMovers();
    this.readout();
    this.kick();
    this.render();
  }

  resize(width: number, height: number) {
    if (width <= 0 || height <= 0) return;
    this.size = { width, height };
    this.renderer.setSize(width, height, false);
    this.fit();
    this.render();
  }

  render() {
    this.renderer.render(this.scene, this.camera);
    this.placeLabels();
  }

  /** Frees the renderer, geometries and materials, removes listeners and labels, and gives the WebGL context back. */
  dispose() {
    this.stop();
    this.unbind();
    this.overlay.replaceChildren();
    this.disposeOutline();
    this.disposeLamps();
    this.scene.remove(this.root);
    this.freeShared();
    this.renderer.dispose();
    this.renderer.forceContextLoss();
  }
}
