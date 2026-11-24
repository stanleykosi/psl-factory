// @vitest-environment jsdom
import { act, fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import Floor3D from '@/features/floor/Floor3D';
import type { SceneLine } from '@/features/floor/support';

// D-182 Q6: the strip under the 3D floor gives a station's count and a link into the line's queue. The scene is a recorder that
// hands its callbacks to the test, so "pointing at" and "clicking" a station are calls to them.
const scene = vi.hoisted(() => ({
  callbacks: undefined as undefined | { onPreview: (s: { line: string; name: string } | null) => void; onPin: (s: { line: string; name: string }) => void },
  pinned: [] as unknown[],
}));
vi.mock('@/features/floor/scene', () => ({
  FloorScene: class {
    constructor(_canvas: unknown, _overlay: unknown, _style: unknown, callbacks: NonNullable<typeof scene.callbacks>) {
      scene.callbacks = callbacks;
    }
    resize() {}
    update() {}
    turn() {}
    reset() {}
    setPinned(station: unknown) {
      scene.pinned.push(station);
    }
    dispose() {}
  },
}));
vi.stubGlobal('ResizeObserver', class { observe() {} disconnect() {} });
vi.mock('next/navigation', () => ({ usePathname: () => '/overview', useRouter: () => ({ replace: vi.fn(), push: vi.fn(), prefetch: vi.fn() }) }));

const station = (key: string, name: string, count: number, needs_person = 0) => ({ key, name, count, needs_person });
const lines: SceneLine[] = [
  {
    key: 'commercial/v1',
    title: 'Costing and commercial submission',
    note: 'Not available yet',
    stations: [station('intake', 'Intake', 1), station('execution', 'Execution', 1), station('decision', 'Decision', 1, 2), station('delivery', 'Delivery', 0), station('verified', 'Verified', 1)],
  },
  { key: 'future-line/v1', title: 'A line added later', note: 'Not available yet', stations: [] },
];
const DECISION = { line: 'commercial/v1', name: 'Decision' };
const DELIVERY = { line: 'commercial/v1', name: 'Delivery' };

beforeEach(() => {
  scene.callbacks = undefined;
  scene.pinned = [];
});

const preview = (s: { line: string; name: string } | null) => act(() => scene.callbacks!.onPreview(s));
const pin = (s: { line: string; name: string }) => act(() => scene.callbacks!.onPin(s));
const strip = () => document.querySelector('.floor__strip') as HTMLElement | null;
const mount = () => render(<Floor3D lines={lines} onFailure={() => {}} />);
const HINT = /^Point at, tap or tab to a station/;

describe('preview', () => {
  it('shows the hint until a station is pointed at, then its count and a link to the line queue; "needs a person" only above 0', async () => {
    mount();
    expect(screen.getByText(HINT)).toBeTruthy();
    expect(strip()).toBeNull();

    await preview(DECISION);
    expect(strip()!.textContent).toContain('Costing and commercial submission · Decision');
    expect(strip()!.textContent).toContain('1 item, 2 need a person');
    expect(screen.getByRole('link', { name: 'Open work' }).getAttribute('href')).toBe('/my-work?line=commercial%2Fv1');

    await preview(DELIVERY);
    expect(strip()!.textContent).toContain('0 items');
    expect(strip()!.textContent).not.toContain('needs a person');
    expect(strip()!.textContent).not.toContain('need a person');

    await preview(null);
    expect(strip()).toBeNull();
    expect(screen.getByText(HINT)).toBeTruthy();
  });

  it('makes no request: the strip reads nothing', async () => {
    const fetch = vi.fn();
    vi.stubGlobal('fetch', fetch);
    mount();
    await preview(DECISION);
    expect(fetch).not.toHaveBeenCalled();
    vi.unstubAllGlobals();
    vi.stubGlobal('ResizeObserver', class { observe() {} disconnect() {} });
  });
});

describe('pinning', () => {
  it('pins on click, stays while the pointer moves elsewhere, and clicking another station pins that one', async () => {
    mount();
    await pin(DECISION);
    expect(strip()!.textContent).toContain('Pinned');
    expect(scene.pinned.at(-1)).toEqual(DECISION);
    await preview(DELIVERY);
    expect(strip()!.textContent).toContain('Decision');
    await preview(null);
    expect(strip()!.textContent).toContain('Decision');
    await pin(DELIVERY);
    expect(strip()!.textContent).toContain('Delivery');
    expect(scene.pinned.at(-1)).toEqual(DELIVERY);
  });

  it('lets go with the close button and gives the strip back to the pointer', async () => {
    mount();
    await pin(DECISION);
    fireEvent.click(screen.getByRole('button', { name: 'Unpin station' }));
    expect(strip()).toBeNull();
    expect(scene.pinned.at(-1)).toBeNull();
    await preview(DELIVERY);
    expect(strip()!.textContent).toContain('Delivery');
    expect(strip()!.textContent).not.toContain('Pinned');
  });

  it('lets go on Esc from the floor, and Esc does nothing when nothing is pinned', async () => {
    mount();
    fireEvent.keyDown(screen.getByRole('group', { name: /3D floor view/ }), { key: 'Escape' });
    await pin(DECISION);
    fireEvent.keyDown(screen.getByRole('group', { name: /3D floor view/ }), { key: 'Escape' });
    expect(strip()).toBeNull();
    expect(scene.pinned.at(-1)).toBeNull();
  });

  it('a station that leaves the floor lets go; a line without counts has no station to point at', async () => {
    const view = mount();
    await pin(DECISION);
    view.rerender(<Floor3D lines={[lines[1]]} onFailure={() => {}} />);
    expect(strip()).toBeNull();
    await preview({ line: 'future-line/v1', name: 'Intake' });
    expect(strip()).toBeNull();
  });
});
