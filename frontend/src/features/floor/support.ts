// What the overview needs to know about the 3D floor without loading three.js.
import type { OverviewLine, OverviewStation } from '@/features/overview/types';

/**
 * True when this browser can make a WebGL context (WebGL 2, else WebGL 1), even a slow or software one;
 * the throwaway context is released at once. False only when both fail or throw.
 */
export function webglAvailable(): boolean {
  const options: WebGLContextAttributes = { failIfMajorPerformanceCaveat: false };
  for (const kind of ['webgl2', 'webgl'] as const) {
    try {
      const gl = document.createElement('canvas').getContext(kind, options) as WebGLRenderingContext | null;
      if (gl) {
        gl.getExtension('WEBGL_lose_context')?.loseContext();
        return true;
      }
    } catch {
      // try the next kind
    }
  }
  return false;
}

export type StationChange = { line: string; name: string; before: OverviewStation; after: OverviewStation };

const key = (line: string, name: string) => `${line}\u0000${name}`;

/** Stations, matched by line and station name, whose count or needs_person differ. New or gone stations are not changes. */
export function diffCounts(prev: readonly OverviewLine[], next: readonly OverviewLine[]): StationChange[] {
  const before = new Map(prev.flatMap((l) => l.stations.map((s) => [key(l.line, s.name), s] as const)));
  const changes: StationChange[] = [];
  for (const l of next) {
    for (const after of l.stations) {
      const old = before.get(key(l.line, after.name));
      if (old && (old.count !== after.count || old.needs_person !== after.needs_person)) {
        changes.push({ line: l.line, name: after.name, before: old, after });
      }
    }
  }
  return changes;
}

/** The 3D floor's readout and station label: "Line · Station · N items · needs a person". */
export const describeStation = (line: string, s: OverviewStation) =>
  `${line} · ${s.name} · ${s.count} ${s.count === 1 ? 'item' : 'items'} · ${s.needs_person ? 'needs a person' : 'no person needed'}`;

export const floorLabel = (lines: number) =>
  `3D factory floor: ${lines} ${lines === 1 ? 'line' : 'lines'}. The same figures are listed in the flat view below.`;

/** Props of the default export of Floor3D, which the overview loads only once 3D is chosen. */
export type FloorProps = { lines: readonly OverviewLine[]; onFailure: () => void };
