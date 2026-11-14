// What the overview needs to know about the 3D floor without loading three.js.
import type { OverviewLine, OverviewStation } from '@/features/overview/types';

/** True when this browser can make a WebGL context; the throwaway context is released at once. */
export function webglAvailable(): boolean {
  try {
    const canvas = document.createElement('canvas');
    const gl = (canvas.getContext('webgl2') ?? canvas.getContext('webgl')) as WebGLRenderingContext | null;
    if (!gl) return false;
    gl.getExtension('WEBGL_lose_context')?.loseContext();
    return true;
  } catch {
    return false;
  }
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

export const floorLabel = (lines: number) =>
  `3D factory floor: ${lines} ${lines === 1 ? 'line' : 'lines'}. The same figures are listed in the flat view below.`;

/** Props of the default export of Floor3D, which the overview loads only once 3D is chosen. */
export type FloorProps = { lines: readonly OverviewLine[]; onFailure: () => void };
