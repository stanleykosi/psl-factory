// @vitest-environment jsdom
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { setImmediate as realImmediate } from 'node:timers';

import { act, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { OverviewPage } from '@/features/overview/OverviewPage';
import type { Overview, WorkCounts } from '@/features/overview/types';
import { AppShell } from '@/shell/AppShell';

process.env.TZ = 'Africa/Lagos';

vi.mock('next/navigation', () => ({
  usePathname: () => '/overview',
  useRouter: () => ({ replace: vi.fn(), push: vi.fn(), prefetch: vi.fn() }),
}));

const support = vi.hoisted(() => ({ webgl: true }));
vi.mock('@/features/floor/support', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/features/floor/support')>()),
  webglAvailable: () => support.webgl,
}));

const fixtures = join(__dirname, '../mock/fixtures');
const read = (path: string) => JSON.parse(readFileSync(join(fixtures, path), 'utf8'));
const OVERVIEW: Overview = read('floor/overview.json');
const COUNTS: WorkCounts = read('floor/counts.json');
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
const ERR = { code: 'server_error', message: 'x' };

let persona: string;
let overview: () => Response | Promise<Response>;
let counts: () => Response | Promise<Response>;
let calls: URL[];
let media: Record<string, boolean>;

beforeEach(() => {
  persona = 'finance_lead';
  overview = () => json(200, OVERVIEW);
  counts = () => json(200, COUNTS);
  calls = [];
  media = {};
  support.webgl = true;
  vi.stubGlobal('matchMedia', (q: string) => ({ matches: media[q] ?? false, media: q, addEventListener: () => {}, removeEventListener: () => {} }));
  vi.stubGlobal(
    'fetch',
    vi.fn(async (request: Request) => {
      const url = new URL(request.url);
      if (url.pathname === '/api/v1/me') return json(200, read(`me.${persona}.json`));
      calls.push(url);
      return url.pathname === '/api/v1/work/counts' ? counts() : overview();
    }),
  );
});
afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

/** Lets fetches and React settle; works with real and fake timers. */
async function until(check: () => void, tries = 100) {
  for (let i = 0; ; i++) {
    try {
      check();
      return;
    } catch (error) {
      if (i >= tries) throw error;
    }
    await act(async () => {
      await new Promise((r) => realImmediate(r));
    });
  }
}

const overviewCalls = () => calls.filter((u) => u.pathname === '/api/v1/overview');
const countsCalls = () => calls.filter((u) => u.pathname === '/api/v1/work/counts');
const linesSection = () => screen.queryByRole('region', { name: 'Lines' });
const floorBlocks = () => [...document.querySelectorAll('.overview__floor-block')] as HTMLElement[];
const lineRows = () => [...document.querySelectorAll('.overview__lines-of > .overview__row')] as HTMLElement[];
const lineRow = (title: string) => lineRows().find((r) => r.querySelector('.overview__name')!.textContent === title)!;
const squares = (title: string) => within(lineRow(title)).queryAllByRole('listitem');
const said = (li: Element) => li.querySelector('button')?.getAttribute('aria-label') ?? li.querySelector('.cmp-sr')?.textContent ?? li.textContent ?? '';
const tiles = () => [...document.querySelectorAll('dl.overview__totals > div')].map((d) => [d.querySelector('dt')!.textContent, d.querySelector('dd')!.textContent]);
const COMMERCIAL = 'Costing and commercial submission';
const NOT_YET = 'Totals are not available yet.';

async function open() {
  render(
    <AppShell>
      <OverviewPage />
    </AppShell>,
  );
  await until(() => expect(screen.queryByRole('status')).toBeNull());
}

describe('success, with the live fixtures', () => {
  it('reads GET /overview and GET /work/counts, with no parameters', async () => {
    await open();
    expect(overviewCalls()).toHaveLength(1);
    expect(countsCalls()).toHaveLength(1);
    expect(overviewCalls()[0].search).toBe('');
    expect(countsCalls()[0].search).toBe('');
  });

  it('shows UPDATED, the as_of time with WAT, floors in order with their open work, and each line with its total', async () => {
    await open();
    const eyebrow = document.querySelector('.overview__eyebrow')!;
    expect(eyebrow.textContent).toBe('FACTORY FLOOR · UPDATED 23 Nov 10:30 WAT');
    expect(eyebrow.querySelector('time')!.getAttribute('datetime')).toBe('2026-11-23T09:30:00Z');
    expect(screen.getByRole('heading', { level: 1, name: 'Factory floor' })).toBeTruthy();
    expect(floorBlocks().map((b) => [b.querySelector('.overview__name')!.textContent, b.querySelector('.overview__open-total')!.textContent])).toEqual([
      ['Pre-sale', '4 open work'],
      ['Invoices', '4 open work'],
      ['Other lines', '7 open work'],
    ]);
    expect(lineRow(COMMERCIAL).querySelector('.overview__count')!.textContent).toBe('3 open work');
    expect(lineRows().map((r) => r.querySelector('.overview__name')!.textContent)).toEqual([
      COMMERCIAL,
      'RFP response and project handoff',
      'Invoice preparation and delivery',
      'Formal minutes and action handoff',
      'A line added later',
    ]);
  });

  it('keeps a line the map does not know under "Other lines", with a subtitle and no avatar', async () => {
    await open();
    const other = floorBlocks()[2];
    expect(other.querySelector('.overview__row--floor .overview__sub')!.textContent).toBe('Not on a floor yet');
    expect(other.querySelector('.overview__row--floor img.psl-avatar')).toBeNull();
    expect(within(other).getByText('A line added later')).toBeTruthy();
    expect(within(other).getByText('5 open work')).toBeTruthy();
    const avatar = floorBlocks()[0].querySelector('.overview__row--floor img.psl-avatar')!;
    expect(avatar.getAttribute('src')).toBe('/agents/tola.png');
  });

  it('the four totals are the sums over the counts lines, with the coverage line and the month', async () => {
    await open();
    expect(tiles()).toEqual([
      ['IN PROGRESS', '10'],
      ['NEED A PERSON', '4'],
      ['STOPPED', '1'],
      ['VERIFIED THIS MONTH', '3'],
    ]);
    expect(document.querySelector('.overview__total small')!.textContent).toBe('Nov 2026');
    expect(screen.getByText('Counted from all 15 items you can see')).toBeTruthy();
    expect(screen.getByText(/^Open work is work you can see that isn’t verified or cancelled\. Station figures come from your most recent items and can be lower than the total\./)).toBeTruthy();
  });

  it('draws five squares with their counts, the Decision square marked "needs a person"; a line with no one needed has none marked', async () => {
    await open();
    const items = squares(COMMERCIAL);
    expect(items.map((li) => said(li))).toEqual([
      'Intake: 1 item',
      'Execution: 1 item',
      'Decision: 1 item, needs a person',
      'Delivery: 0 items',
      'Verified: 1 item',
    ]);
    expect(items.map((li) => li.querySelector('.overview__sq')!.textContent)).toEqual(['1', '1', '1', '', '1']);
    expect(items.map((li) => li.className.includes('overview__station--person'))).toEqual([false, false, true, false, false]);
    expect(squares('RFP response and project handoff').some((li) => li.className.includes('person'))).toBe(false);
    expect(squares('RFP response and project handoff').some((li) => said(li).includes('needs a person'))).toBe(false);
  });

  it('shows the neutral "Not available yet" tag on every line and no Stopped, Waiting or Verified tag', async () => {
    await open();
    const tags = lineRows().map((r) => [r.querySelector('.psl-tag')!.textContent, r.querySelector('.psl-tag')!.className]);
    expect(tags).toHaveLength(5);
    for (const [text, cls] of tags) {
      expect(text).toBe('Not available yet');
      expect(cls).toBe('psl-tag psl-tag--neutral');
    }
    expect([...document.querySelectorAll('.psl-tag')].some((t) => /^(stopped|waiting|verified)$/i.test(t.textContent!))).toBe(false);
  });

  it('an absent line is five known 0 squares when the counts are not limited', async () => {
    await open();
    expect(squares('A line added later').map((li) => said(li))).toEqual(['Intake: 0 items', 'Execution: 0 items', 'Decision: 0 items', 'Delivery: 0 items', 'Verified: 0 items']);
  });

  it('"Open work" on a line links to its queue, URL-encoded', async () => {
    await open();
    expect(within(lineRow(COMMERCIAL)).getByRole('link', { name: /Open work/ }).getAttribute('href')).toBe('/my-work?line=commercial%2Fv1');
    expect(within(lineRow('A line added later')).getByRole('link', { name: /Open work/ }).getAttribute('href')).toBe('/my-work?line=future-line%2Fv1');
  });

  it('exceptions place and the legend stay', async () => {
    await open();
    const place = screen.getByRole('region', { name: 'All exceptions · everyone’s' });
    expect(within(place).getByRole('link', { name: 'See all exceptions' }).getAttribute('href')).toBe('/exceptions');
    expect(linesSection()!.nextElementSibling).toBe(place);
  });
});

describe('limited and missing counts: unknown is not 0', () => {
  const limited = (): WorkCounts => ({ ...COUNTS, limited: true, evaluated: 50, queues: [{ key: 'needs_me', observed: 4, total: null }] });

  it('limited: every total reads "at least N" with the most-recent coverage line', async () => {
    counts = () => json(200, limited());
    await open();
    expect(tiles().map(([, v]) => v)).toEqual(['at least 10', 'at least 4', 'at least 1', 'at least 3']);
    expect(screen.getByText('Counted from the 50 most recent items you can see')).toBeTruthy();
    expect(tiles().some(([, v]) => /^\d+$/.test(v!))).toBe(false);
  });

  it('limited and commercial missing: its row says "Not available yet" in place of squares, never 0 squares', async () => {
    counts = () => json(200, { ...limited(), lines: COUNTS.lines.filter((l) => l.key !== 'commercial/v1') });
    await open();
    const row = lineRow(COMMERCIAL);
    expect(within(row).queryAllByRole('listitem')).toHaveLength(0);
    expect(row.querySelector('.overview__unknown')!.textContent).toBe('Not available yet');
    expect(row.textContent).not.toContain('0 items');
    expect(squares('RFP response and project handoff')).toHaveLength(5);
    expect(squares('A line added later')).toHaveLength(0);
  });

  it('not limited and commercial missing: five 0 squares, a known zero', async () => {
    counts = () => json(200, { ...COUNTS, lines: COUNTS.lines.filter((l) => l.key !== 'commercial/v1') });
    await open();
    expect(squares(COMMERCIAL).map((li) => said(li))).toEqual(['Intake: 0 items', 'Execution: 0 items', 'Decision: 0 items', 'Delivery: 0 items', 'Verified: 0 items']);
  });

  it('counts 503: rows with totals, "Totals are not available yet.", "Not available yet" for squares, and no 0 total', async () => {
    counts = () => json(503, { code: 'read_limited', message: 'Try again later.' });
    await open();
    expect(screen.getByText(NOT_YET)).toBeTruthy();
    expect(document.querySelector('dl.overview__totals')).toBeNull();
    expect(screen.queryByText(/Counted from/)).toBeNull();
    expect(lineRows()).toHaveLength(5);
    expect(lineRow(COMMERCIAL).querySelector('.overview__count')!.textContent).toBe('3 open work');
    expect(lineRows().every((r) => r.querySelector('.overview__unknown')!.textContent === 'Not available yet' && within(r).queryAllByRole('listitem').length === 0)).toBe(true);
    expect(floorBlocks().map((b) => b.querySelector('.overview__open-total')!.textContent)).toEqual(['4 open work', '4 open work', '7 open work']);
    expect(screen.queryByRole('alert')).toBeNull();
  });

  it('counts failing keeps polling and recovers when it answers again', async () => {
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout', 'setInterval', 'clearInterval', 'Date'] });
    counts = () => json(500, ERR);
    await open();
    expect(screen.getByText(NOT_YET)).toBeTruthy();
    counts = () => json(200, COUNTS);
    await act(() => vi.advanceTimersByTimeAsync(15_000));
    await until(() => expect(tiles()).toHaveLength(4));
    expect(screen.queryByText(NOT_YET)).toBeNull();
  });
});

describe('empty, error, not open, signed out, loading', () => {
  it('lines: [] shows the empty message, no View switch, no totals', async () => {
    overview = () => json(200, { ...OVERVIEW, lines: [] });
    counts = () => json(200, { ...COUNTS, evaluated: 0, lines: [] });
    await open();
    expect(screen.getByRole('heading', { name: 'No lines to show yet.' })).toBeTruthy();
    expect(screen.getByText('Lines appear here when work you can see starts.')).toBeTruthy();
    expect(screen.queryByRole('radiogroup', { name: 'View' })).toBeNull();
    expect(document.querySelector('dl.overview__totals')).toBeNull();
    expect(linesSection()).toBeNull();
    expect(screen.queryByText(/Counted from/)).toBeNull();
    expect(screen.getByRole('link', { name: 'See all exceptions' })).toBeTruthy();
  });

  it('shows LoadingState and no rows before the answers arrive', async () => {
    let release!: () => void;
    const gate = new Promise<void>((resolve) => (release = resolve));
    overview = async () => {
      await gate;
      return json(200, OVERVIEW);
    };
    render(
      <AppShell>
        <OverviewPage />
      </AppShell>,
    );
    await until(() => expect(screen.getByRole('status')).toBeTruthy());
    expect(lineRows()).toHaveLength(0);
    expect(linesSection()).toBeNull();
    await act(async () => release());
    await until(() => expect(screen.queryByRole('status')).toBeNull());
    expect(lineRows()).toHaveLength(5);
  });

  it('a person without overview gets the not-open state and no reads', async () => {
    persona = 'pm';
    await open();
    expect(screen.getByText('This section isn’t open to your role.')).toBeTruthy();
    expect(overviewCalls()).toHaveLength(0);
    expect(countsCalls()).toHaveLength(0);
  });

  it.each([
    ['overview', () => (overview = () => json(401, { code: 'not_signed_in', message: 'Sign in to continue.' }))],
    ['counts', () => (counts = () => json(401, { code: 'not_signed_in', message: 'Sign in to continue.' }))],
  ])('401 on %s shows the signed-out state with a sign-in link and stops polling', async (_, setup) => {
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout', 'setInterval', 'clearInterval', 'Date'] });
    setup();
    await open();
    await until(() => expect(screen.getByText('You’re signed out.')).toBeTruthy());
    expect(screen.getByRole('link', { name: 'Sign in' }).getAttribute('href')).toBe('/sign-in?next=%2Foverview');
    await act(() => vi.advanceTimersByTimeAsync(30_000));
    expect(overviewCalls()).toHaveLength(1);
  });

  it.each([
    [403, { code: 'forbidden', message: 'Your role does not allow this.' }],
    [404, { code: 'not_found', message: 'We could not find that record.' }],
  ])('%s shows the floor is not open to you with the server message, no retry and no more requests', async (status, body) => {
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout', 'setInterval', 'clearInterval', 'Date'] });
    overview = () => json(status, body);
    await open();
    await until(() => expect(screen.getByRole('heading', { name: 'The factory floor isn’t open to you.' })).toBeTruthy());
    expect(screen.getByText(body.message)).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Try again' })).toBeNull();
    expect(document.querySelector('dl')).toBeNull();
    expect(linesSection()).toBeNull();
    await act(() => vi.advanceTimersByTimeAsync(30_000));
    expect(overviewCalls()).toHaveLength(1);
  });

  it.each([
    ['500', () => json(500, ERR)],
    ['network', () => Promise.reject(new TypeError('Failed to fetch'))],
  ])('a failed poll (%s) shows the error card with the last load time; Try again restores the rows', async (_, fail) => {
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout', 'setInterval', 'clearInterval', 'Date'] });
    await open();
    expect(tiles()).toHaveLength(4);
    overview = fail as () => Promise<Response>;
    await act(() => vi.advanceTimersByTimeAsync(15_000));
    await until(() => expect(screen.getByRole('alert')).toBeTruthy());
    const alert = screen.getByRole('alert');
    expect(alert.textContent).toContain('We couldn’t load the factory floor.');
    expect(alert.textContent).toContain('Last loaded 23 Nov 10:30 WAT.');
    expect(alert.textContent).toMatch(/Reference (server_error|network_error) for support\./);
    expect(document.querySelector('dl')).toBeNull();
    expect(linesSection()).toBeNull();
    overview = () => json(200, OVERVIEW);
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
    await until(() => expect(tiles()).toHaveLength(4));
    expect(screen.queryByRole('alert')).toBeNull();
    expect(lineRows()).toHaveLength(5);
  });

  it('a failed first load says nothing about a last load', async () => {
    overview = () => json(500, ERR);
    await open();
    await until(() => expect(screen.getByRole('alert')).toBeTruthy());
    expect(screen.getByRole('alert').textContent).not.toContain('Last loaded');
    expect(screen.getByRole('alert').textContent).toContain('Reference server_error for support.');
  });
});

describe('staying current', () => {
  let visibility: DocumentVisibilityState;
  beforeEach(() => {
    visibility = 'visible';
    Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => visibility });
  });
  const setVisibility = (v: DocumentVisibilityState) => {
    visibility = v;
    document.dispatchEvent(new Event('visibilitychange'));
  };

  it('both reads go out again every 15 s while visible, never while hidden, and at once on return after 15 s', async () => {
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout', 'setInterval', 'clearInterval', 'Date'] });
    await open();
    expect([overviewCalls().length, countsCalls().length]).toEqual([1, 1]);
    await act(() => vi.advanceTimersByTimeAsync(14_999));
    expect(overviewCalls()).toHaveLength(1);
    await act(() => vi.advanceTimersByTimeAsync(1));
    await until(() => expect([overviewCalls().length, countsCalls().length]).toEqual([2, 2]));

    act(() => setVisibility('hidden'));
    await act(() => vi.advanceTimersByTimeAsync(60_000));
    expect(overviewCalls()).toHaveLength(2);
    act(() => setVisibility('visible'));
    await until(() => expect([overviewCalls().length, countsCalls().length]).toEqual([3, 3]));
  });

  it('never has two rounds in flight', async () => {
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout', 'setInterval', 'clearInterval', 'Date'] });
    await open();
    let release!: () => void;
    overview = () => new Promise<Response>((resolve) => (release = () => resolve(json(200, OVERVIEW))));
    await act(() => vi.advanceTimersByTimeAsync(15_000));
    await act(() => vi.advanceTimersByTimeAsync(30_000));
    expect(overviewCalls()).toHaveLength(2);
    await act(async () => release());
    overview = () => json(200, OVERVIEW);
    await act(() => vi.advanceTimersByTimeAsync(15_000));
    await until(() => expect(overviewCalls()).toHaveLength(3));
  });

  it('a slow older round never replaces a newer one', async () => {
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout', 'setInterval', 'clearInterval', 'Date'] });
    await open();
    overview = () => json(500, ERR);
    await act(() => vi.advanceTimersByTimeAsync(15_000));
    await until(() => expect(screen.getByRole('alert')).toBeTruthy());
    let releaseA!: () => void;
    overview = () => new Promise<Response>((resolve) => (releaseA = () => resolve(json(200, OVERVIEW))));
    await act(() => vi.advanceTimersByTimeAsync(15_000));
    expect(overviewCalls()).toHaveLength(3);
    overview = () => json(200, { ...OVERVIEW, as_of: '2026-11-23T09:31:00Z' });
    counts = () => json(200, { ...COUNTS, lines: [{ ...COUNTS.lines[0], open: 99 }] });
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
    await until(() => expect(tiles()[0]).toEqual(['IN PROGRESS', '99']));
    await act(async () => releaseA());
    for (let i = 0; i < 5; i++) await act(async () => new Promise((r) => realImmediate(r)));
    expect(tiles()[0]).toEqual(['IN PROGRESS', '99']);
    expect(document.querySelector('.overview__eyebrow')!.textContent).toBe('FACTORY FLOOR · UPDATED 23 Nov 10:31 WAT');
  });
});

describe('the 3D option follows reduced motion, WebGL and width', () => {
  it('reduced motion: no View switch and the motion hint', async () => {
    media['(prefers-reduced-motion: reduce)'] = true;
    await open();
    expect(screen.queryByRole('radiogroup', { name: 'View' })).toBeNull();
    expect(screen.getByText('Motion is turned down on this device, so the floor is shown flat.')).toBeTruthy();
    expect(lineRows()).toHaveLength(5);
  });

  it('no WebGL: no View switch and the device hint', async () => {
    support.webgl = false;
    await open();
    expect(screen.queryByRole('radiogroup', { name: 'View' })).toBeNull();
    expect(screen.getByText('This device can’t show the 3D floor, so it’s shown flat.')).toBeTruthy();
  });

  it('phone: the Updated line above the title, two-figure summary, coverage, rows, no switch and no hint', async () => {
    media['(max-width: 719.98px)'] = true;
    await open();
    expect(screen.queryByRole('radiogroup', { name: 'View' })).toBeNull();
    expect(document.querySelector('.overview__hint')).toBeNull();
    const h1 = screen.getByRole('heading', { level: 1 });
    expect(h1.closest('header')!.nextElementSibling!.textContent).toBe('10 in progress · 4 need a person');
    expect(h1.closest('header')!.nextElementSibling!.nextElementSibling!.textContent).toBe('Counted from all 15 items you can see');
    expect(tiles()).toHaveLength(0);
    expect(h1.closest('header')!.previousElementSibling!.textContent).toBe('FACTORY FLOOR · UPDATED 23 Nov 10:30 WAT');
    expect(lineRows()).toHaveLength(5);
  });

  it('phone, limited: the summary reads "at least N"', async () => {
    media['(max-width: 719.98px)'] = true;
    counts = () => json(200, { ...COUNTS, limited: true, evaluated: 50 });
    await open();
    expect(document.querySelector('.overview__summary')!.textContent).toBe('at least 10 in progress · at least 4 need a person');
  });

  it('phone, counts failed: the summary is replaced by "Totals are not available yet."', async () => {
    media['(max-width: 719.98px)'] = true;
    counts = () => json(503, ERR);
    await open();
    expect(document.querySelector('.overview__summary')).toBeNull();
    expect(screen.getByText(NOT_YET)).toBeTruthy();
  });

  it('desktop: the eyebrow shows above the title and the View switch shows with Flat checked', async () => {
    await open();
    const eyebrow = document.querySelector('.overview__eyebrow')!;
    const h1 = screen.getByRole('heading', { level: 1 });
    expect(eyebrow.compareDocumentPosition(h1) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    const [flat, floor] = within(screen.getByRole('radiogroup', { name: 'View' })).getAllByRole('radio');
    expect([flat.textContent, floor.textContent, flat.getAttribute('aria-checked')]).toEqual(['Flat', '3D floor', 'true']);
  });
});

describe('D-165: a flat square opens its station under the line', () => {
  it('a press opens the count and the link into the queue; the same press, Close or Esc shuts it', async () => {
    await open();
    const square = within(squares(COMMERCIAL)[2]).getByRole('button');
    expect(square.getAttribute('aria-expanded')).toBe('false');
    fireEvent.click(square);
    expect(square.getAttribute('aria-expanded')).toBe('true');
    const strip = document.getElementById(square.getAttribute('aria-controls')!)!;
    expect(strip.textContent).toContain(`${COMMERCIAL} · Decision`);
    expect(strip.textContent).toContain('1 item, 2 need a person');
    expect(within(strip).getByRole('link', { name: 'Open work' }).getAttribute('href')).toBe('/my-work?line=commercial%2Fv1');
    fireEvent.click(square);
    expect(document.querySelector('.overview__open')).toBeNull();
    fireEvent.click(square);
    fireEvent.click(screen.getByRole('button', { name: 'Close station' }));
    expect(document.querySelector('.overview__open')).toBeNull();
    fireEvent.click(square);
    fireEvent.keyDown(square, { key: 'Escape' });
    expect(document.querySelector('.overview__open')).toBeNull();
  });
});
