// The three.js factory floor (SCR-06 3D, README § Motion). Only Floor3D imports this file.
// Plain three: a fixed angled camera, one strip per line, a square block per station with up to 10
// tokens queued in front of it and a sprite with the exact count. It renders on demand only: a
// 280 ms ease-out runs when a poll changes a station, then rendering stops.
import {
  BoxGeometry,
  CanvasTexture,
  Color,
  EdgesGeometry,
  Group,
  LineBasicMaterial,
  LineSegments,
  Mesh,
  MeshBasicMaterial,
  OrthographicCamera,
  PlaneGeometry,
  Scene,
  Sprite,
  SpriteMaterial,
  SRGBColorSpace,
  Vector3,
  WebGLRenderer,
  type Material,
  type Object3D,
} from 'three';

import type { OverviewLine, OverviewStation } from '@/features/overview/types';

import { diffCounts } from './support';

/** Design tokens read from CSS custom properties at mount: colours and the display and mono font families. */
export type FloorStyle = { ink: string; signal: string; surface: string; steel: string; display: string; mono: string };

const STATION_X = 2.4;
const LINE_Z = 1.5;
const LABEL_W = 3;
const BLOCK = 0.8;
const BLOCK_H = 0.35;
const TOKEN = 0.18;
const TOKEN_GAP = 0.23;
const ELEVATION = (55 * Math.PI) / 180;
const MAX_TOKENS = 10;
const MOVE_MS = 280;
const RISE = 0.3;

type Station = {
  block: Mesh<BoxGeometry, MeshBasicMaterial>;
  count: Sprite;
  tokens: Mesh<BoxGeometry, MeshBasicMaterial>[];
  group: Group;
  value: OverviewStation;
};
type Move = { mesh: Mesh<BoxGeometry, MeshBasicMaterial>; y0: number; y1: number; o0: number; o1: number; remove: boolean };

const stationKey = (line: string, name: string) => `${line}\u0000${name}`;
const shapeOf = (lines: readonly OverviewLine[]) => JSON.stringify(lines.map((l) => [l.line, l.stations.map((s) => s.name)]));
const easeOut = (t: number) => 1 - (1 - t) ** 3;

/** A sprite with text drawn on a 2D canvas; `height` is in scene units. */
function textSprite(text: string, font: (px: number) => string, color: string, height: number, box?: { fill: string; stroke: string }) {
  const px = 96;
  const canvas = document.createElement('canvas');
  const ctx = canvas.getContext('2d')!;
  ctx.font = font(px * 0.62);
  const pad = box ? px * 0.3 : 4;
  canvas.width = Math.max(px, Math.ceil(ctx.measureText(text).width + pad * 2));
  canvas.height = px;
  if (box) {
    ctx.fillStyle = box.fill;
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.strokeStyle = box.stroke;
    ctx.lineWidth = 6;
    ctx.strokeRect(3, 3, canvas.width - 6, canvas.height - 6);
  }
  ctx.font = font(px * 0.62);
  ctx.fillStyle = color;
  ctx.textBaseline = 'middle';
  ctx.textAlign = box ? 'center' : 'left';
  ctx.fillText(text, box ? canvas.width / 2 : pad, canvas.height / 2 + 2);
  const texture = new CanvasTexture(canvas);
  texture.colorSpace = SRGBColorSpace;
  const sprite = new Sprite(new SpriteMaterial({ map: texture, transparent: true }));
  sprite.scale.set((height * canvas.width) / canvas.height, height, 1);
  return sprite;
}

function disposeTree(root: Object3D) {
  root.traverse((node) => {
    const { geometry, material } = node as Partial<Mesh>;
    // Every Sprite shares one geometry that three owns, so only its material and texture are freed.
    if (!(node as Sprite).isSprite) geometry?.dispose();
    for (const m of (Array.isArray(material) ? material : material ? [material] : []) as (Material & { map?: { dispose(): void } })[]) {
      m.map?.dispose();
      m.dispose();
    }
  });
}

export class FloorScene {
  private readonly renderer: WebGLRenderer;
  private readonly scene = new Scene();
  private readonly camera = new OrthographicCamera();
  private readonly colors: { ink: Color; signal: Color; surface: Color; steel: Color };
  private readonly css: FloorStyle;
  private root = new Group();
  private stations = new Map<string, Station>();
  private prev: readonly OverviewLine[] | null = null;
  private shape = '';
  private extent = { width: 1, depth: 1, center: new Vector3() };
  private moves: Move[] = [];
  private moveStart = 0;
  private frame = 0;
  private size = { width: 1, height: 1 };

  /** Throws when WebGL cannot start; the caller falls back to the flat view. */
  constructor(canvas: HTMLCanvasElement, css: FloorStyle) {
    this.renderer = new WebGLRenderer({ canvas, antialias: true });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    this.css = css;
    this.colors = { ink: new Color(css.ink), signal: new Color(css.signal), surface: new Color(css.surface), steel: new Color(css.steel) };
    this.scene.background = this.colors.surface;
    this.scene.add(this.root);
  }

  private blockColor(s: OverviewStation) {
    return s.needs_person ? this.colors.signal : s.count > 0 ? this.colors.ink : this.colors.surface;
  }

  private tokenColor(s: OverviewStation) {
    return s.needs_person ? this.colors.signal : this.colors.ink;
  }

  private countSprite(s: OverviewStation) {
    const sprite = textSprite(String(s.count), (px) => `500 ${px}px ${this.css.mono}`, this.css.ink, 0.45, { fill: this.css.surface, stroke: this.css.ink });
    sprite.position.set(0, BLOCK_H + 0.7, -0.3);
    return sprite;
  }

  /** Where token i sits in front of its block: two rows of five. */
  private tokenSpot(i: number) {
    const col = i % 5;
    const row = Math.floor(i / 5);
    return new Vector3((col - 2) * TOKEN_GAP, TOKEN / 2, 0.3 + row * TOKEN_GAP);
  }

  private addToken(st: Station, i: number, color: Color) {
    const mesh = new Mesh(new BoxGeometry(TOKEN, TOKEN, TOKEN), new MeshBasicMaterial({ color, transparent: true }));
    mesh.position.copy(this.tokenSpot(i));
    st.group.add(mesh);
    st.tokens.push(mesh);
    return mesh;
  }

  /** Builds every line and station as given, with no animation. */
  private build(lines: readonly OverviewLine[]) {
    this.scene.remove(this.root);
    disposeTree(this.root);
    this.root = new Group();
    this.scene.add(this.root);
    this.stations.clear();

    const most = Math.max(1, ...lines.map((l) => l.stations.length));
    lines.forEach((l, li) => {
      const z = li * LINE_Z;
      const strip = new Mesh(new PlaneGeometry(most * STATION_X, 1.25), new MeshBasicMaterial({ color: this.colors.steel }));
      strip.rotation.x = -Math.PI / 2;
      strip.position.set(((most - 1) * STATION_X) / 2, 0, z);
      this.root.add(strip);

      const label = textSprite(l.line, (px) => `700 ${px}px ${this.css.display}`, this.css.ink, 0.5);
      label.center.set(0, 0.5);
      label.position.set(-STATION_X / 2 - LABEL_W, 0.3, z);
      this.root.add(label);

      // Stations spread along the strip like the flat track: first at the start, last at the end.
      const step = l.stations.length > 1 ? ((most - 1) * STATION_X) / (l.stations.length - 1) : 0;
      l.stations.forEach((s, si) => {
        const group = new Group();
        group.position.set(si * step, 0, z);
        const block = new Mesh(new BoxGeometry(BLOCK, BLOCK_H, BLOCK), new MeshBasicMaterial({ color: this.blockColor(s) }));
        block.position.set(0, BLOCK_H / 2, -0.3);
        const edges = new LineSegments(new EdgesGeometry(block.geometry), new LineBasicMaterial({ color: this.colors.ink }));
        block.add(edges);
        group.add(block);
        const count = this.countSprite(s);
        group.add(count);
        const st: Station = { block, count, tokens: [], group, value: s };
        for (let i = 0; i < Math.min(s.count, MAX_TOKENS); i++) this.addToken(st, i, this.tokenColor(s));
        this.root.add(group);
        this.stations.set(stationKey(l.line, s.name), st);
      });
    });
    this.extent = {
      width: LABEL_W + most * STATION_X,
      depth: Math.max(1, lines.length) * LINE_Z,
      center: new Vector3(((most - 1) * STATION_X - LABEL_W) / 2, 0, ((lines.length - 1) * LINE_Z) / 2),
    };
    this.fit();
  }

  /** A fixed camera angled down at the floor, sized so every line and station is in view. */
  private fit() {
    const aspect = this.size.width / this.size.height;
    const tilt = ELEVATION;
    const tall = this.extent.depth * Math.sin(tilt) + (BLOCK_H + 0.9) * Math.cos(tilt);
    const half = Math.max(tall / 2, (this.extent.width + 0.6) / 2 / aspect) * 1.04;
    Object.assign(this.camera, { left: -half * aspect, right: half * aspect, top: half, bottom: -half, near: 0.1, far: 200 });
    const c = this.extent.center;
    this.camera.position.set(c.x, c.y + 40 * Math.sin(tilt), c.z + 40 * Math.cos(tilt));
    this.camera.lookAt(c.x, c.y + 0.4, c.z);
    this.camera.updateProjectionMatrix();
  }

  /** Changes one station to its new figures; returns the token moves to animate. */
  private change(st: Station, next: OverviewStation) {
    st.block.material.color.copy(this.blockColor(next));
    st.group.remove(st.count);
    disposeTree(st.count);
    st.count = this.countSprite(next);
    st.group.add(st.count);
    const color = this.tokenColor(next);
    for (const t of st.tokens) t.material.color.copy(color);
    const have = st.tokens.length;
    const want = Math.min(next.count, MAX_TOKENS);
    const moves: Move[] = [];
    for (let i = have; i < want; i++) {
      const mesh = this.addToken(st, i, color);
      moves.push({ mesh, y0: mesh.position.y - RISE, y1: mesh.position.y, o0: 0, o1: 1, remove: false });
      mesh.position.y -= RISE;
      mesh.material.opacity = 0;
    }
    for (const mesh of st.tokens.splice(want)) moves.push({ mesh, y0: mesh.position.y, y1: mesh.position.y, o0: 1, o1: 0, remove: true });
    st.value = next;
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
    const moves = diffCounts(prev, lines).flatMap((c) => this.change(this.stations.get(stationKey(c.line, c.name))!, c.after));
    if (moves.length === 0) return this.render();
    this.finishMoves();
    this.moves = moves;
    this.moveStart = performance.now();
    this.frame = requestAnimationFrame(this.step);
  }

  private step = (now: number) => {
    const t = Math.min(1, (now - this.moveStart) / MOVE_MS);
    const e = easeOut(t);
    for (const m of this.moves) {
      m.mesh.position.y = m.y0 + (m.y1 - m.y0) * e;
      m.mesh.material.opacity = m.o0 + (m.o1 - m.o0) * e;
    }
    if (t < 1) {
      this.render();
      this.frame = requestAnimationFrame(this.step);
    } else {
      this.frame = 0;
      this.finishMoves();
      this.render();
    }
  };

  /** Puts any running move at its end state and stops the frame loop. */
  private finishMoves() {
    if (this.frame) cancelAnimationFrame(this.frame);
    this.frame = 0;
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

  resize(width: number, height: number) {
    if (width <= 0 || height <= 0) return;
    this.size = { width, height };
    this.renderer.setSize(width, height, false);
    this.fit();
    if (!this.frame) this.render();
  }

  render() {
    this.renderer.render(this.scene, this.camera);
  }

  /** Frees the renderer, geometries, materials and textures, and gives the WebGL context back. */
  dispose() {
    this.finishMoves();
    disposeTree(this.scene);
    this.renderer.dispose();
    this.renderer.forceContextLoss();
  }
}
