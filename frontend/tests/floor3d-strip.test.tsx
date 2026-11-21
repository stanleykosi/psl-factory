// @vitest-environment jsdom
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import Floor3D from '@/features/floor/Floor3D';
import { rowMeta, rowTitle, stationCounts, type StationItem } from '@/features/floor/stationWork';
import type { Overview } from '@/features/overview/types';

// D-162: the strip under the 3D floor lists a station's work. The scene is a recorder that hands its callbacks to the test,
// so "pointing at" and "clicking" a station are calls to them; the station read is a stubbed fetch.
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

const overview: Overview = JSON.parse(readFileSync(join(__dirname, '../mock/fixtures/E-OVERVIEW.json'), 'utf8'));
const APPROVE = { line: 'Invoices', name: 'Approve' };
const BRIEF = { line: 'Pre-sale', name: 'Brief' };

const item = (n: number, extra: Partial<StationItem> = {}): StationItem => ({
  work_id: `W-${1000 + n}`,
  title: `Work ${n}`,
  reference: `REF-${n}`,
  state: 'processing',
  needs_person: false,
  held_by: { kind: 'agent', name: 'Chidi' },
  ...extra,
});
const page = (items: StationItem[], extra: Record<string, unknown> = {}) => ({ items, total: items.length, as_of: '2026-11-14T15:40:00Z', ...extra });

let requests: URL[];
let answer: (url: URL) => Response | Promise<Response>;
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });

beforeEach(() => {
  requests = [];
  scene.callbacks = undefined;
  scene.pinned = [];
  answer = () => json(200, page([]));
  vi.stubGlobal('fetch', vi.fn(async (request: Request) => {
    const url = new URL(request.url);
    requests.push(url);
    return answer(url);
  }));
});
afterEach(() => vi.unstubAllGlobals().stubGlobal('ResizeObserver', class { observe() {} disconnect() {} }));

const preview = (station: { line: string; name: string } | null) => act(() => scene.callbacks!.onPreview(station));
const pin = (station: { line: string; name: string }) => act(() => scene.callbacks!.onPin(station));
const strip = () => document.querySelector('.floor__strip') as HTMLElement | null;
const mount = () => render(<Floor3D lines={overview.lines} onFailure={() => {}} />);
const HINT = /^Point at, tap or tab to a station/;

describe('preview', () => {
  it('shows the hint until a station is pointed at, then reads it: head line, counts and rows that link to the work', async () => {
    let release!: () => void;
    const gate = new Promise<void>((resolve) => (release = resolve));
    answer = async () => {
      await gate;
      return json(200, page([
      item(1, { needs_person: true, held_by: { kind: 'role', name: 'Finance Lead' }, project_title: 'Lagoon Health · patient app', state: 'waiting' }),
      item(2, { client: 'Harmattan Bank', held_by: { kind: 'role', name: 'Finance Lead' }, waiting_since: new Date(Date.now() - 3 * 86_400_000).toISOString() }),
      item(3),
    ], { needs_person_count: 1 }));
    };
    mount();
    expect(screen.getByText(HINT)).toBeTruthy();
    expect(strip()).toBeNull();

    await preview(APPROVE);
    expect(screen.getByRole('status').textContent).toContain('Reading this station');
    expect(strip()!.textContent).toContain('1 here');
    release();
    await screen.findByRole('link', { name: 'Lagoon Health · patient app' });
    expect(strip()!.textContent).toContain('Invoices · Approve');
    expect(strip()!.textContent).toContain('3 here · 1 needs a person');
    const links = within(strip()!).getAllByRole('link');
    expect(links.map((a) => [a.textContent, a.getAttribute('href')])).toEqual([
      ['Lagoon Health · patient app', '/work/W-1001'],
      ['Harmattan Bank', '/work/W-1002'],
      ['Work 3', '/work/W-1003'],
    ]);
    const meta = [...strip()!.querySelectorAll('.floor__meta')].map((m) => [m.textContent, m.classList.contains('floor__meta--person')]);
    expect(meta).toEqual([['needs a person', true], ['REF-2 · waiting 3d', false], ['Chidi working', false]]);
    expect(requests[0].searchParams.get('line')).toBe('Invoices');
    expect(requests[0].searchParams.get('station')).toBe('Approve');
    expect(requests[0].searchParams.get('limit')).toBe('5');

    await preview(null);
    expect(strip()).toBeNull();
    expect(screen.getByText(HINT)).toBeTruthy();
  });

  it('reads a station once per session: pointing at it again shows the same rows without a new read', async () => {
    answer = () => json(200, page([item(1)]));
    mount();
    await preview(APPROVE);
    await screen.findByRole('link', { name: 'Work 1' });
    await preview(BRIEF);
    await screen.findByRole('link', { name: 'Work 1' });
    expect(requests).toHaveLength(2);
    await preview(APPROVE);
    expect(screen.getByRole('link', { name: 'Work 1' })).toBeTruthy();
    expect(requests).toHaveLength(2);
  });

  it('says so when a station has nothing', async () => {
    mount();
    await preview(BRIEF);
    expect(await screen.findByText('Nothing here right now.')).toBeTruthy();
    expect(strip()!.textContent).toContain('0 here');
  });

  it('says it could not load, and Try again reads it again', async () => {
    answer = () => json(500, { code: 'server_error', message: 'Something went wrong on our side.' });
    mount();
    await preview(APPROVE);
    expect(await screen.findByText(/We couldn’t load this station’s work\./)).toBeTruthy();
    answer = () => json(200, page([item(1)]));
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
    expect(await screen.findByRole('link', { name: 'Work 1' })).toBeTruthy();
    expect(screen.queryByText(/We couldn’t load/)).toBeNull();
  });

  it('shows the strip before the page below it and the rows after the chips and the Reset view button comes last', async () => {
    answer = () => json(200, page([item(1)]));
    mount();
    await preview(APPROVE);
    const link = await screen.findByRole('link', { name: 'Work 1' });
    const reset = screen.getByRole('button', { name: 'Reset view' });
    expect(link.compareDocumentPosition(reset) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(document.querySelector('.floor__stage')!.compareDocumentPosition(link) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });
});

describe('pinning', () => {
  beforeEach(() => {
    answer = (url) => json(200, page([item(url.searchParams.get('station') === 'Approve' ? 1 : 2)]));
  });

  it('pins on click, stays while the pointer moves elsewhere, and clicking another station pins that one', async () => {
    mount();
    await pin(APPROVE);
    await screen.findByRole('link', { name: 'Work 1' });
    expect(strip()!.textContent).toContain('Pinned');
    expect(scene.pinned.at(-1)).toEqual(APPROVE);
    await preview(BRIEF);
    expect(strip()!.textContent).toContain('Invoices · Approve');
    expect(screen.getByRole('link', { name: 'Work 1' })).toBeTruthy();
    await preview(null);
    expect(strip()!.textContent).toContain('Invoices · Approve');
    await pin(BRIEF);
    await screen.findByRole('link', { name: 'Work 2' });
    expect(strip()!.textContent).toContain('Pre-sale · Brief');
    expect(scene.pinned.at(-1)).toEqual(BRIEF);
  });

  it('lets go with the close button and gives the strip back to the pointer', async () => {
    mount();
    await pin(APPROVE);
    await screen.findByRole('link', { name: 'Work 1' });
    fireEvent.click(screen.getByRole('button', { name: 'Unpin station' }));
    expect(strip()).toBeNull();
    expect(screen.queryByText('Pinned')).toBeNull();
    expect(scene.pinned.at(-1)).toBeNull();
    await preview(BRIEF);
    expect(strip()!.textContent).toContain('Pre-sale · Brief');
    expect(strip()!.textContent).not.toContain('Pinned');
  });

  it('lets go on Esc from the floor and from a row in the strip, and Esc does nothing when nothing is pinned', async () => {
    mount();
    fireEvent.keyDown(screen.getByRole('group', { name: /3D floor view/ }), { key: 'Escape' });
    await pin(APPROVE);
    const link = await screen.findByRole('link', { name: 'Work 1' });
    fireEvent.keyDown(link, { key: 'Escape' });
    expect(strip()).toBeNull();
    await pin(BRIEF);
    await screen.findByRole('link', { name: 'Work 2' });
    fireEvent.keyDown(screen.getByRole('group', { name: /3D floor view/ }), { key: 'Escape' });
    expect(strip()).toBeNull();
    expect(scene.pinned.at(-1)).toBeNull();
  });
});

describe('show all', () => {
  it('shows five rows and Show all N, then reads the rest into the strip', async () => {
    const all = Array.from({ length: 12 }, (_, i) => item(i + 1));
    answer = (url) => json(200, url.searchParams.get('cursor') ? page(all.slice(5), { total: 12 }) : page(all.slice(0, 5), { total: 12, next_cursor: 'o5' }));
    mount();
    await pin(APPROVE);
    await screen.findByRole('link', { name: 'Work 1' });
    expect(within(strip()!).getAllByRole('link')).toHaveLength(5);
    expect(strip()!.textContent).toContain('12 here');
    fireEvent.click(screen.getByRole('button', { name: 'Show all 12' }));
    await waitFor(() => expect(within(strip()!).getAllByRole('link')).toHaveLength(12));
    expect(requests[1].searchParams.get('cursor')).toBe('o5');
    expect(requests[1].searchParams.get('limit')).toBe('50');
    expect(screen.queryByRole('button', { name: /Show all/ })).toBeNull();
    expect(strip()!.querySelector('.floor__rows--scroll')).toBeNull();
  });

  it('scrolls the list inside the strip past 20 rows', async () => {
    const all = Array.from({ length: 30 }, (_, i) => item(i + 1));
    answer = (url) => json(200, url.searchParams.get('cursor') ? page(all.slice(5), { total: 30 }) : page(all.slice(0, 5), { total: 30, next_cursor: 'o5' }));
    mount();
    await pin(APPROVE);
    await screen.findByRole('link', { name: 'Work 1' });
    expect(strip()!.querySelector('.floor__rows--scroll')).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: 'Show all 30' }));
    await waitFor(() => expect(within(strip()!).getAllByRole('link')).toHaveLength(30));
    expect(strip()!.querySelector('.floor__rows--scroll')).not.toBeNull();
  });
});

describe('the words', () => {
  it('names a row by project, then client, then its own title; and counts in plain words', () => {
    expect(rowTitle(item(1, { project_title: 'P', client: 'C' }))).toBe('P');
    expect(rowTitle(item(1, { client: 'C' }))).toBe('C');
    expect(rowTitle(item(1))).toBe('Work 1');
    expect(rowMeta(item(1, { held_by: { kind: 'role', name: 'PMO Lead' } })).text).toBe('REF-1');
    expect(stationCounts(1, 0)).toBe('1 here');
    expect(stationCounts(4, 1)).toBe('4 here · 1 needs a person');
    expect(stationCounts(4, 2)).toBe('4 here · 2 need a person');
  });
});
