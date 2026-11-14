// The three.js factory floor, concept 3 "tilted swimlane board" (decision D-01; reference: concept 3 in
// design/concepts/floor-3d-concepts.html). Only Floor3D imports this file.
// The approved flat board leaned back like a drafting table: lines are rows top to bottom, stations are
// cards left to right in returned order, and work items are dark tiles stacked on each card (at most 10;
// the label above the card carries the exact count). The card under the pointer or keyboard focus lifts,
// and the board leans gently toward the pointer. Rendering is on demand: frames run only while something
// moves (a lift, the lean, a drag, or the 280 ms change when a poll alters a station) and then stop.
// No agents are drawn: E-OVERVIEW does not say where an agent works.
import {
  BoxGeometry,
  Color,
  DirectionalLight,
  EdgesGeometry,
  Group,
  HemisphereLight,
  LineBasicMaterial,
  LineSegments,
  Mesh,
  MeshLambertMaterial,
  Object3D,
  PCFSoftShadowMap,
  PerspectiveCamera,
  Raycaster,
  Scene,
  Vector2,
  Vector3,
  WebGLRenderer,
  type Material,
} from 'three';

import { tagTone } from '@/features/overview/lines';
import type { OverviewLine, OverviewStation } from '@/features/overview/types';

import { describeStation, diffCounts } from './support';

/** Design tokens read from CSS custom properties at mount. */
export type FloorStyle = {
  ink: string;
  signal: string;
  signalTint: string;
  surface: string;
  steel: string;
  ruleSoft: string;
  board: string;
  plate: string;
  tileEdge: string;
};

const SPAN = 13.2; // first to last station, in scene units
const GAP = 1.95; // between lines
const LIFT = 0.55;
const TILE_STEP = 0.13;
const MAX_TILES = 10;
const MOVE_MS = 280;
const RISE = 0.3;
const VIEW = { fov: 28, yaw: -0.2, pitch: 0.98, yawMin: -0.6, yawMax: 0.6, pitchMin: 0.62, pitchMax: 1.32 };

type Card = {
  key: string;
  line: string;
  value: OverviewStation;
  group: Group;
  base: Mesh<BoxGeometry, MeshLambertMaterial>;
  edges: LineSegments<EdgesGeometry, LineBasicMaterial>;
  stripe: Mesh | null;
  tiles: Mesh<BoxGeometry, MeshLambertMaterial>[];
  anchor: Object3D;
  chip: HTMLButtonElement;
};
type Label = { el: HTMLElement; anchor: Object3D; align: 'bottom' | 'center' };
type Move = { mesh: Mesh<BoxGeometry, MeshLambertMaterial>; y0: number; y1: number; o0: number; o1: number; remove: boolean };

const stationKey = (line: string, name: string) => `${line}\u0000${name}`;
const shapeOf = (lines: readonly OverviewLine[]) => JSON.stringify(lines.map((l) => [l.line, l.stations.map((s) => s.name)]));
const stationX = (i: number, n: number) => -SPAN / 2 + (n < 2 ? 0 : (i / (n - 1)) * SPAN);
const easeOut = (t: number) => 1 - (1 - t) ** 3;
const reducedMotion = () => typeof window.matchMedia === 'function' && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

function disposeTree(root: Object3D) {
  root.traverse((node) => {
    const { geometry, material } = node as Partial<Mesh>;
    geometry?.dispose();
    for (const m of (Array.isArray(material) ? material : material ? [material] : []) as Material[]) m.dispose();
  });
}

export type FloorCallbacks = { onReadout: (text: string | null, needsPerson: boolean) => void };

export class FloorScene {
  private readonly renderer: WebGLRenderer;
  private readonly scene = new Scene();
  private readonly camera = new PerspectiveCamera(VIEW.fov, 1, 0.1, 400);
  private readonly raycaster = new Raycaster();
  private readonly c: Record<keyof FloorStyle, Color>;
  private root = new Group();
  private cards = new Map<string, Card>();
  private labels: Label[] = [];
  private prev: readonly OverviewLine[] | null = null;
  private shape = '';
  private view = { yaw: VIEW.yaw, pitch: VIEW.pitch };
  private target = new Vector3();
  private dist = 30;
  private fitPoints: Vector3[] = [];
  private size = { width: 1, height: 1 };
  private hover: Card | null = null;
  private focus: Card | null = null;
  private pointer: { x: number; y: number } | null = null;
  private drag: { x: number; y: number; moved: boolean } | null = null;
  private tilt = { x: 0, z: 0 };
  private moves: Move[] = [];
  private moveStart = 0;
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
    Object.assign(sun.shadow.camera, { left: -18, right: 18, top: 18, bottom: -18, near: 1, far: 50 });
    sun.shadow.bias = -0.0008;
    this.scene.add(sun);
    this.scene.add(this.root);
    this.unbind = this.bind();
  }

  private box(parent: Object3D, w: number, h: number, d: number, x: number, y: number, z: number, color: Color, edge?: Color) {
    const geometry = new BoxGeometry(w, h, d);
    geometry.translate(0, h / 2, 0);
    const mesh = new Mesh(geometry, new MeshLambertMaterial({ color }));
    mesh.position.set(x, y, z);
    mesh.castShadow = true;
    mesh.receiveShadow = true;
    if (edge) mesh.add(new LineSegments(new EdgesGeometry(geometry), new LineBasicMaterial({ color: edge })));
    parent.add(mesh);
    return mesh;
  }

  private anchor(parent: Object3D, x: number, y: number, z: number) {
    const o = new Object3D();
    o.position.set(x, y, z);
    parent.add(o);
    return o;
  }

  private chipFor(card: Pick<Card, 'line' | 'value'>, chip = document.createElement('button')) {
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

  private addTile(card: Card, i: number) {
    const tile = this.box(card.group, 1.0, 0.09, 0.72, i * 0.06, 0.15 + i * TILE_STEP, 0.05, card.value.needs_person ? this.c.signal : this.c.ink, this.c.tileEdge);
    tile.material.transparent = true;
    card.tiles.push(tile);
    return tile;
  }

  private paintCard(card: Card) {
    const s = card.value;
    card.base.material.color.copy(s.needs_person ? this.c.signalTint : this.c.surface);
    card.edges.material.color.copy(s.needs_person ? this.c.signal : this.c.ink);
    if (s.needs_person && !card.stripe) card.stripe = this.box(card.group, 1.5, 0.04, 0.26, 0, 0.14, -0.47, this.c.signal);
    if (!s.needs_person && card.stripe) {
      card.group.remove(card.stripe);
      disposeTree(card.stripe);
      card.stripe = null;
    }
    for (const t of card.tiles) t.material.color.copy(s.needs_person ? this.c.signal : this.c.ink);
    // The label is fixed to the board, not the card, so a lift never moves it from under the pointer.
    card.anchor.position.y = 0.3 + Math.min(s.count, MAX_TILES) * TILE_STEP;
    this.chipFor(card, card.chip);
  }

  /** Builds the board, every line and every card as given, with no animation. */
  private build(lines: readonly OverviewLine[]) {
    this.scene.remove(this.root);
    disposeTree(this.root);
    this.overlay.replaceChildren();
    this.root = new Group();
    this.scene.add(this.root);
    this.cards.clear();
    this.labels = [];
    this.hover = this.focus = null;

    const n = Math.max(1, lines.length);
    const z0 = (-(n - 1) * GAP) / 2;
    const left = -SPAN / 2 - 4.1;
    const right = SPAN / 2 + 1.1;
    const cx = (left + right) / 2;
    const width = right - left;
    this.box(this.root, width, 0.35, (n - 1) * GAP + 2.2, cx, -0.35, 0, this.c.surface, this.c.ink).castShadow = false;
    lines.forEach((l, li) => {
      const z = z0 + li * GAP;
      this.box(this.root, width - 0.3, 0.02, GAP - 0.12, cx, 0, z, li % 2 ? this.c.steel : this.c.surface).castShadow = false;
      this.box(this.root, 2.9, 0.16, GAP - 0.4, -SPAN / 2 - 2.45, 0, z, this.c.ink);
      this.box(this.root, SPAN, 0.03, 0.06, 0, 0.02, z, this.c.ruleSoft).castShadow = false;

      const label = document.createElement('div');
      label.className = 'floor__line';
      label.setAttribute('aria-hidden', 'true');
      const name = document.createElement('strong');
      name.textContent = l.line;
      const tag = document.createElement('span');
      tag.className = `psl-tag ${tagTone(l)}`;
      tag.textContent = l.note;
      label.append(name, tag);
      this.addLabel(label, this.anchor(this.root, -SPAN / 2 - 2.45, 0.2, z), 'center');

      l.stations.forEach((s, i) => {
        const group = new Group();
        group.position.set(stationX(i, l.stations.length), 0, z);
        this.root.add(group);
        const base = this.box(group, 1.5, 0.12, 1.2, 0, 0.02, 0, this.c.surface, this.c.ink) as Mesh<BoxGeometry, MeshLambertMaterial>;
        const card: Card = {
          key: stationKey(l.line, s.name),
          line: l.line,
          value: s,
          group,
          base,
          edges: base.children[0] as LineSegments<EdgesGeometry, LineBasicMaterial>,
          stripe: null,
          tiles: [],
          anchor: this.anchor(this.root, group.position.x, 0, z),
          chip: document.createElement('button'),
        };
        for (let t = 0; t < Math.min(s.count, MAX_TILES); t++) this.addTile(card, t);
        this.paintCard(card);
        base.userData.card = card;
        for (const t of card.tiles) t.userData.card = card;
        card.chip.addEventListener('pointerenter', () => this.setHover(card));
        card.chip.addEventListener('pointerleave', () => this.setHover(null));
        card.chip.addEventListener('focus', () => this.setFocus(card));
        card.chip.addEventListener('blur', () => this.setFocus(null));
        this.cards.set(card.key, card);
        this.addLabel(card.chip, card.anchor, 'bottom');
      });
    });
    this.root.updateMatrixWorld(true);
    this.fitPoints = this.labels.map((label) => label.anchor.getWorldPosition(new Vector3()));
    this.fit();
  }

  private addLabel(el: HTMLElement, anchor: Object3D, align: Label['align']) {
    const wrap = document.createElement('div');
    wrap.className = 'floor__label';
    wrap.append(el);
    this.overlay.append(wrap);
    this.labels.push({ el: wrap, anchor, align });
  }

  /** Centres the board and finds the camera distance at which every label anchor is in view, at the default angle. */
  private fit() {
    if (!this.fitPoints.length) return;
    const lo = new Vector3(Infinity, Infinity, Infinity);
    const hi = new Vector3(-Infinity, -Infinity, -Infinity);
    for (const p of this.fitPoints) {
      lo.min(p);
      hi.max(p);
    }
    this.target.copy(lo).add(hi).multiplyScalar(0.5);
    this.target.y *= 0.5;
    this.camera.aspect = this.size.width / this.size.height;
    this.camera.updateProjectionMatrix();
    const saved = { ...this.view };
    this.view = { yaw: VIEW.yaw, pitch: VIEW.pitch };
    const v = new Vector3();
    let near = 4;
    let far = 200;
    for (let i = 0; i < 28; i++) {
      this.dist = (near + far) / 2;
      this.place();
      const fits = this.fitPoints.every((p) => {
        v.copy(p).project(this.camera);
        return v.z < 1 && Math.abs(v.x) <= 0.86 && v.y <= 0.82 && v.y >= -0.86;
      });
      if (fits) far = this.dist;
      else near = this.dist;
    }
    this.dist = far;
    this.place();
    this.contain();
    this.view = saved;
    this.place();
  }

  /** Pans and zooms so the labels themselves, not only their anchor points, fill the stage. */
  private contain() {
    const { width, height } = this.size;
    const pad = 14;
    const right = new Vector3();
    const up = new Vector3();
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
      const perPixel = (2 * this.dist * Math.tan((this.camera.fov * Math.PI) / 360)) / height;
      right.setFromMatrixColumn(this.camera.matrixWorld, 0);
      up.setFromMatrixColumn(this.camera.matrixWorld, 1);
      this.target.addScaledVector(right, dx * perPixel).addScaledVector(up, -dy * perPixel);
      this.dist *= scale;
      this.place();
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
      const shift = label.align === 'center' ? 'translate(-50%, -50%)' : 'translate(-50%, -100%)';
      label.el.style.transform = `translate3d(${x.toFixed(1)}px, ${y.toFixed(1)}px, 0) ${shift}`;
      label.el.style.zIndex = String(Math.round((1 - v.z) * 5000));
    }
  }

  private readout() {
    const card = this.focus ?? this.hover;
    this.callbacks.onReadout(card ? describeStation(card.line, card.value) : null, Boolean(card?.value.needs_person));
  }

  private setHover(card: Card | null) {
    if (this.hover === card) return;
    this.hover?.chip.classList.remove('floor__chip--hot');
    this.hover = card;
    card?.chip.classList.add('floor__chip--hot');
    this.readout();
    this.kick();
  }

  private setFocus(card: Card | null) {
    this.focus = card;
    this.readout();
    this.kick();
  }

  private pick(event: PointerEvent): Card | null {
    const rect = this.canvas.getBoundingClientRect();
    const at = new Vector2(((event.clientX - rect.left) / rect.width) * 2 - 1, -((event.clientY - rect.top) / rect.height) * 2 + 1);
    this.raycaster.setFromCamera(at, this.camera);
    const meshes = [...this.cards.values()].flatMap((c) => [c.base, ...c.tiles]);
    return (this.raycaster.intersectObjects(meshes, false)[0]?.object.userData.card as Card | undefined) ?? null;
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
      const rect = el.getBoundingClientRect();
      this.pointer = { x: ((e.clientX - rect.left) / rect.width) * 2 - 1, y: ((e.clientY - rect.top) / rect.height) * 2 - 1 };
      if (this.drag) {
        const dx = e.clientX - this.drag.x;
        const dy = e.clientY - this.drag.y;
        if (!this.drag.moved && Math.abs(dx) + Math.abs(dy) > 4) this.drag.moved = true;
        if (this.drag.moved) {
          this.view.yaw = Math.max(VIEW.yawMin, Math.min(VIEW.yawMax, this.view.yaw - dx * 0.006));
          this.view.pitch = Math.max(VIEW.pitchMin, Math.min(VIEW.pitchMax, this.view.pitch + dy * 0.005));
          this.drag.x = e.clientX;
          this.drag.y = e.clientY;
          this.place();
        }
      } else if (e.pointerType === 'mouse') this.setHover(this.pick(e));
      this.kick();
    };
    const up = (e: PointerEvent) => {
      if (this.drag && !this.drag.moved) this.setHover(this.pick(e));
      this.drag = null;
    };
    const leave = (e: PointerEvent) => {
      if (this.drag) return;
      this.pointer = null;
      if (e.pointerType === 'mouse') this.setHover(null);
      this.kick();
    };
    const cancel = () => {
      this.drag = null;
    };
    el.addEventListener('pointerdown', down);
    el.addEventListener('pointermove', move);
    el.addEventListener('pointerup', up);
    el.addEventListener('pointerleave', leave);
    el.addEventListener('pointercancel', cancel);
    return () => {
      el.removeEventListener('pointerdown', down);
      el.removeEventListener('pointermove', move);
      el.removeEventListener('pointerup', up);
      el.removeEventListener('pointerleave', leave);
      el.removeEventListener('pointercancel', cancel);
    };
  }

  /** Back to the starting angle, with nothing lifted. */
  reset() {
    this.view = { yaw: VIEW.yaw, pitch: VIEW.pitch };
    this.pointer = null;
    this.setHover(null);
    this.place();
    this.kick();
  }

  /** Moves lifts, lean and changes one step; returns true while anything is still moving. */
  private advance(dt: number, now: number) {
    const still = reducedMotion();
    const f = still ? 1 : 1 - Math.exp(-dt * 10);
    let moving = false;
    for (const card of this.cards.values()) {
      const up = card === this.hover || card === this.focus ? LIFT : 0;
      card.group.position.y += (up - card.group.position.y) * f;
      card.group.rotation.x += ((up ? -0.12 : 0) - card.group.rotation.x) * f;
      if (Math.abs(card.group.position.y - up) > 0.002) moving = true;
      else card.group.position.y = up;
    }
    const px = still || !this.pointer ? 0 : this.pointer.x;
    const py = still || !this.pointer ? 0 : this.pointer.y;
    this.tilt.x += (py * 0.05 - this.tilt.x) * f;
    this.tilt.z += (-px * 0.04 - this.tilt.z) * f;
    if (Math.abs(this.tilt.x - py * 0.05) > 0.0005 || Math.abs(this.tilt.z + px * 0.04) > 0.0005) moving = true;
    this.root.rotation.x = this.tilt.x;
    this.root.rotation.z = this.tilt.z;
    if (this.moves.length) {
      const t = still ? 1 : Math.min(1, (now - this.moveStart) / MOVE_MS);
      const e = easeOut(t);
      for (const m of this.moves) {
        m.mesh.position.y = m.y0 + (m.y1 - m.y0) * e;
        m.mesh.material.opacity = m.o0 + (m.o1 - m.o0) * e;
      }
      if (t < 1) moving = true;
      else this.finishMoves();
    }
    return moving;
  }

  /** Starts the frame loop if it is not running; it stops by itself once nothing moves. */
  private kick() {
    if (this.frame) return;
    this.last = performance.now();
    this.frame = requestAnimationFrame(this.step);
  }

  private step = (now: number) => {
    const dt = Math.min(0.25, Math.max(0, (now - this.last) / 1000));
    this.last = now;
    const moving = this.advance(dt, now) || Boolean(this.drag?.moved);
    this.render();
    this.frame = moving ? requestAnimationFrame(this.step) : 0;
  };

  /** Puts any running change at its end state. */
  private finishMoves() {
    for (const m of this.moves) {
      m.mesh.position.y = m.y1;
      m.mesh.material.opacity = m.o1;
      if (m.remove) {
        m.mesh.parent?.remove(m.mesh);
        disposeTree(m.mesh);
      }
    }
    this.moves = [];
  }

  /** Changes one card to its new figures; returns the tile moves to animate. */
  private change(card: Card, next: OverviewStation) {
    const moves: Move[] = [];
    card.value = next;
    const want = Math.min(next.count, MAX_TILES);
    for (let i = card.tiles.length; i < want; i++) {
      const tile = this.addTile(card, i);
      tile.userData.card = card;
      moves.push({ mesh: tile, y0: tile.position.y + RISE, y1: tile.position.y, o0: 0, o1: 1, remove: false });
      tile.position.y += RISE;
      tile.material.opacity = 0;
    }
    for (const tile of card.tiles.splice(want)) moves.push({ mesh: tile, y0: tile.position.y, y1: tile.position.y + RISE, o0: 1, o1: 0, remove: true });
    this.paintCard(card);
    return moves;
  }

  /** Shows the lines. The first call and new or gone stations draw at once; changed stations move. */
  update(lines: readonly OverviewLine[]) {
    const prev = this.prev;
    this.prev = lines;
    const shape = shapeOf(lines);
    if (!prev) {
      this.shape = shape;
      this.build(lines);
      return this.render();
    }
    if (shape !== this.shape) {
      // Rebuild with the old figures for stations that stay, so their change still moves below.
      const old = new Map(prev.flatMap((l) => l.stations.map((s) => [stationKey(l.line, s.name), s] as const)));
      this.shape = shape;
      this.finishMoves();
      this.build(lines.map((l) => ({ ...l, stations: l.stations.map((s) => old.get(stationKey(l.line, s.name)) ?? s) })));
    }
    // Line notes and tones can change without a station change.
    lines.forEach((l, i) => {
      const tag = this.labels.filter((label) => label.align === 'center')[i]?.el.querySelector('.psl-tag');
      if (tag) {
        tag.className = `psl-tag ${tagTone(l)}`;
        tag.textContent = l.note;
      }
    });
    const moves = diffCounts(prev, lines).flatMap((c) => this.change(this.cards.get(stationKey(c.line, c.name))!, c.after));
    this.readout();
    if (moves.length === 0) return this.render();
    this.finishMoves();
    this.moves = moves;
    this.moveStart = performance.now();
    this.kick();
  }

  resize(width: number, height: number) {
    if (width <= 0 || height <= 0) return;
    this.size = { width, height };
    this.renderer.setSize(width, height, false);
    this.fit();
    if (!this.frame) this.render();
  }

  render() {
    this.renderer.render(this.scene, this.camera);
    this.placeLabels();
  }

  /** Frees the renderer, geometries and materials, removes listeners and labels, and gives the WebGL context back. */
  dispose() {
    if (this.frame) cancelAnimationFrame(this.frame);
    this.frame = 0;
    this.finishMoves();
    this.unbind();
    this.overlay.replaceChildren();
    disposeTree(this.scene);
    this.renderer.dispose();
    this.renderer.forceContextLoss();
  }
}
