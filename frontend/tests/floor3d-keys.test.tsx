// @vitest-environment jsdom
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { fireEvent, render, screen } from '@testing-library/react';
import { expect, it, vi } from 'vitest';

import Floor3D from '@/features/floor/Floor3D';
import type { SceneLine } from '@/features/floor/support';
import { floorsOf, STATION_LABEL } from '@/features/overview/model';

// The conveyor scene needs WebGL; here it is a recorder, so the test covers what Floor3D wires around it.
const scene = vi.hoisted(() => ({ calls: [] as unknown[][], style: undefined as Record<string, string> | undefined }));
vi.mock('@/features/floor/scene', () => ({
  FloorScene: class {
    constructor(_canvas: unknown, _overlay: unknown, style: Record<string, string>) {
      scene.style = style;
    }
    resize() {}
    update(lines: unknown) {
      scene.calls.push(['update', lines]);
    }
    turn(dx: number, dy: number) {
      scene.calls.push(['turn', dx, dy]);
    }
    reset() {
      scene.calls.push(['reset']);
    }
    setPinned() {}
    dispose() {}
  },
}));
vi.stubGlobal('ResizeObserver', class { observe() {} disconnect() {} });

const read = (path: string) => JSON.parse(readFileSync(join(__dirname, '../mock/fixtures/floor', path), 'utf8'));
const lines: SceneLine[] = floorsOf(read('overview.json'), read('counts.json')).flatMap((f) => f.lines.map((l) => ({ key: l.key, title: l.title, note: 'Not available yet', stations: l.stations ?? [] })));

it('gives the lines to the scene as given, and arrows turn and tilt while R and Reset view reset', () => {
  expect(Object.values(STATION_LABEL)).toEqual(['Intake', 'Execution', 'Decision', 'Delivery', 'Verified']);
  render(<Floor3D lines={lines} onFailure={() => {}} />);
  expect(scene.calls[0]).toEqual(['update', lines]);
  const stage = screen.getByRole('group', { name: /3D floor view/ });
  expect(stage.tabIndex).toBe(0);
  scene.calls.length = 0;
  for (const key of ['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown', 'r', 'R']) fireEvent.keyDown(stage, { key });
  expect(scene.calls).toEqual([['turn', -1, 0], ['turn', 1, 0], ['turn', 0, 1], ['turn', 0, -1], ['reset'], ['reset']]);
  fireEvent.keyDown(stage, { key: 'x' });
  fireEvent.click(screen.getByRole('button', { name: 'Reset view' }));
  expect(scene.calls).toHaveLength(7);
  expect(scene.calls[6]).toEqual(['reset']);
});
