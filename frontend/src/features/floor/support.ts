// What the overview needs to know about the 3D floor without loading three.js.
import type { Station } from '@/features/overview/model';

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

/** One line as the 3D floor draws it: a belt with its stations. A line whose counts are unknown has no stations. */
export type SceneLine = { key: string; title: string; note: string; stations: Station[] };

/** The 3D floor's readout and station label: "Line · Station · N items", and "needs a person" only when the count says so. */
export const describeStation = (title: string, s: Station) =>
  `${title} · ${s.name} · ${s.count} ${s.count === 1 ? 'item' : 'items'}${s.needs_person > 0 ? ' · needs a person' : ''}`;

export const floorLabel = (lines: number) =>
  `3D factory floor: ${lines} ${lines === 1 ? 'line' : 'lines'}. The same figures are listed in the flat view below.`;

/** Props of the default export of Floor3D, which the overview loads only once 3D is chosen. */
export type FloorProps = { lines: readonly SceneLine[]; onFailure: () => void };
