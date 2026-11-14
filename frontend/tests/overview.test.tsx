// @vitest-environment jsdom
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { setImmediate as realImmediate } from 'node:timers';

import { act, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { Overview } from '@/features/overview/types';
import { OverviewPage } from '@/features/overview/OverviewPage';
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
const DEFAULT: Overview = read('E-OVERVIEW.json');
const ZERO: Overview = read('overview/zero.json');
const STATUS: Overview = read('overview/status.json');
const EMPTY: Overview = read('overview/empty.json');
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });

let persona: string;
let overview: () => Response | Promise<Response>;
let calls: URL[];
let media: Record<string, boolean>;

beforeEach(() => {
  persona = 'finance_lead';
  overview = () => json(200, DEFAULT);
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
      return overview();
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
const linesSection = () => screen.queryByRole('region', { name: 'Lines' });
const rows = () => within(within(linesSection()!).getAllByRole('list')[0]).getAllByRole('listitem').filter((el) => el.classList.contains('overview__row'));
const stations = (line: string) => within(screen.getByRole('list', { name: `${line} stations` })).getAllByRole('listitem');
const station = (line: string, name: string) => stations(line).find((li) => li.querySelector('.overview__sr')!.textContent!.startsWith(`${name}: `))!;
const tiles = () =>
  [...document.querySelectorAll('dl.overview__totals > div')].map((d) => [d.querySelector('dt')!.textContent, d.querySelector('dd')!.textContent]);
const settle = (body: Overview) => {
  overview = () => json(200, body);
};

async function open() {
  render(
    <AppShell>
      <OverviewPage />
    </AppShell>,
  );
  await until(() => expect(screen.queryByRole('status')).toBeNull());
}

describe('totals, lines and stations exactly as returned (A-OVERVIEW)', () => {
  it('renders the four totals as returned, although the station counts sum to another number', async () => {
    await open();
    expect(tiles()).toEqual([
      ['IN PROGRESS', '18'],
      ['NEED A PERSON', '5'],
      ['STOPPED', '3'],
      ['VERIFIED THIS MONTH', '28'],
    ]);
    const sum = DEFAULT.lines.flatMap((l) => l.stations).reduce((a, s) => a + s.count, 0);
    expect(sum).not.toBe(DEFAULT.totals.in_progress);
  });

  it('zero totals with non-zero stations show four 0s', async () => {
    settle({ ...DEFAULT, totals: { in_progress: 0, need_a_person: 0, stopped: 0, verified_this_month: 0 } });
    await open();
    expect(tiles().map(([, v]) => v)).toEqual(['0', '0', '0', '0']);
    expect(station('Invoices', 'Milestone').querySelector('.overview__sq')!.textContent).toBe('3');
  });

  it('shows every line in order and every station with its exact count, singular and plural', async () => {
    await open();
    expect(rows().map((li) => li.querySelector('.overview__name')!.textContent)).toEqual(DEFAULT.lines.map((l) => l.line));
    expect(rows()).toHaveLength(8);
    for (const l of DEFAULT.lines) {
      const items = stations(l.line);
      expect(items).toHaveLength(l.stations.length);
      l.stations.forEach((s, i) => expect(items[i].textContent).toContain(`${s.name}: ${s.count} ${s.count === 1 ? 'item' : 'items'}`));
    }
    expect(station('Pre-sale', 'Brief').textContent).toContain('Brief: 1 item');
    expect(station('Planning', 'Scope').textContent).toContain('Scope: 2 items');
    expect(station('Pre-sale', 'Qualify').textContent).toContain('Qualify: 0 items');
  });

  it('square state follows count and needs_person; without a status the tag tone follows needs_person only', async () => {
    await open();
    const person = station('Pre-sale', 'Proposal');
    expect(person.className).toContain('overview__station--person');
    expect(person.textContent).toContain('Proposal: 0 items, needs a person');
    const work = station('Invoices', 'Milestone');
    expect(work.className).toContain('overview__station--work');
    expect(work.querySelector('.overview__sq')!.textContent).toBe('3');
    expect(work.textContent).not.toContain('needs a person');
    const empty = station('Pre-sale', 'Qualify');
    expect(empty.className).toContain('overview__station--empty');
    expect(empty.querySelector('.overview__sq')!.textContent).toBe('');

    const tag = (i: number) => rows()[i].querySelector('.psl-tag')!;
    expect(tag(0).textContent).toBe('1 WAITING');
    expect(tag(0).className).toBe('psl-tag psl-tag--person');
    expect(tag(3).textContent).toBe('ON TRACK');
    expect(tag(3).className).toBe('psl-tag psl-tag--neutral');
  });

  it('a line status tone sets the board tag: verified green, neutral grey, stopped, uncertain and person red', async () => {
    settle(STATUS);
    await open();
    expect(rows().map((li) => [li.querySelector('.psl-tag')!.textContent, li.querySelector('.psl-tag')!.className])).toEqual([
      ['1 WAITING', 'psl-tag psl-tag--neutral'],
      ['1 STOPPED', 'psl-tag psl-tag--person'],
      ['1 UNCERTAIN', 'psl-tag psl-tag--person'],
      ['ON TRACK', 'psl-tag psl-tag--done'],
      ['2 WAITING', 'psl-tag psl-tag--neutral'],
      ['ON TRACK', 'psl-tag psl-tag--done'],
      ['ON TRACK', 'psl-tag psl-tag--done'],
      ['2 PROBLEMS', 'psl-tag psl-tag--person'],
    ]);
  });

  it('the tone never comes from the note text', async () => {
    settle({ ...DEFAULT, lines: [{ ...DEFAULT.lines[0], note: 'ON TRACK', status: { label: 'Stopped', tone: 'stopped' } }, { ...DEFAULT.lines[3], note: '1 STOPPED' }] });
    await open();
    expect(rows().map((li) => li.querySelector('.psl-tag')!.className)).toEqual(['psl-tag psl-tag--person', 'psl-tag psl-tag--neutral']);
  });

  it('each board line shows its agent avatar and subtitle; an unknown line shows neither', async () => {
    settle({ ...DEFAULT, lines: [DEFAULT.lines[0], DEFAULT.lines[4], DEFAULT.lines[7], { ...DEFAULT.lines[3], line: 'Something new' }] });
    await open();
    const avatar = (li: HTMLElement) => li.querySelector('img.overview__avatar');
    expect(rows().map((li) => [avatar(li)?.getAttribute('src') ?? null, avatar(li)?.getAttribute('alt') ?? null, li.querySelector('.overview__sub')?.textContent ?? null])).toEqual([
      ['/agents/tola.png', 'Tola · PMO agent', 'RFP · commercial'],
      ['/agents/chidi.png', 'Chidi · Finance agent', 'Milestone to verified'],
      ['/agents/zainab.png', 'Zainab · HR agent', 'Restricted'],
      [null, null, null],
    ]);
    expect(avatar(rows()[0])!.className).toBe('psl-avatar psl-avatar--tola overview__avatar');
  });

  it('shows a note word for word, unparsed and not re-cased', async () => {
    settle({ ...DEFAULT, lines: [{ ...DEFAULT.lines[3], note: 'all good' }] });
    await open();
    expect(rows()[0].querySelector('.psl-tag')!.textContent).toBe('all good');
  });

  it('shows the coverage time from as_of', async () => {
    await open();
    const eyebrow = document.querySelector('.overview__eyebrow')!;
    expect(eyebrow.textContent).toBe('FACTORY FLOOR · UPDATED 14 Nov 16:40 WAT');
    expect(eyebrow.querySelector('time')!.getAttribute('datetime')).toBe('2026-11-14T15:40:00Z');
    expect(screen.getByRole('heading', { level: 1, name: 'Factory floor' })).toBeTruthy();
  });

  it('empty lines: totals still show, the empty message replaces the lines, no switch and no legend', async () => {
    settle(EMPTY);
    await open();
    expect(tiles().map(([, v]) => v)).toEqual(['0', '0', '0', '0']);
    expect(screen.getByRole('heading', { name: 'No lines to show yet.' })).toBeTruthy();
    expect(screen.getByText('Lines appear here when work you can see starts.')).toBeTruthy();
    expect(linesSection()).toBeNull();
    expect(screen.queryByRole('radiogroup', { name: 'View' })).toBeNull();
    expect(screen.queryByText(/Each square is a station/)).toBeNull();
    expect(screen.getByRole('link', { name: 'See all exceptions' })).toBeTruthy();
  });

  it('all-zero lines: every square is empty-styled, no numerals, tags verbatim', async () => {
    settle(ZERO);
    await open();
    const all = [...document.querySelectorAll('.overview__station')];
    expect(all).toHaveLength(ZERO.lines.flatMap((l) => l.stations).length);
    expect(all.every((li) => li.className.includes('overview__station--empty'))).toBe(true);
    expect([...document.querySelectorAll('.overview__sq')].map((sq) => sq.textContent).join('')).toBe('');
    expect(rows().map((li) => li.querySelector('.psl-tag')!.textContent)).toEqual(ZERO.lines.map((l) => l.note));
    expect([...document.querySelectorAll('.overview__row .psl-tag--neutral')]).toHaveLength(8);
  });

  it('exceptions place: heading, link to /exceptions and the My work line; no exceptions request', async () => {
    await open();
    const place = screen.getByRole('region', { name: 'All exceptions · everyone’s' });
    expect(within(place).getByRole('heading', { level: 2 }).id).toBe('overview-exceptions-title');
    expect(within(place).getByRole('link', { name: 'See all exceptions' }).getAttribute('href')).toBe('/exceptions');
    expect(within(place).getByText('Your own exceptions also appear in My work · Needs me, marked Fix.')).toBeTruthy();
    expect(calls.some((u) => u.pathname.startsWith('/api/v1/exceptions'))).toBe(false);
    // Board order: lines, then the exceptions place, then the legend.
    expect(linesSection()!.nextElementSibling).toBe(place);
    expect(place.nextElementSibling!.textContent).toMatch(/^Each square is a station; dark squares hold work, orange ones need a person/);
  });
});

describe('who may see it and what fails', () => {
  it('a person without overview gets the not-open state and no E-OVERVIEW request', async () => {
    persona = 'pm';
    await open();
    expect(screen.getByText('This section isn’t open to your role.')).toBeTruthy();
    expect(within(screen.getByRole('main')).getByRole('link').getAttribute('href')).toBe('/my-work');
    expect(overviewCalls()).toHaveLength(0);
  });

  it('401 shows the signed-out callout for /overview and stops polling', async () => {
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout', 'setInterval', 'clearInterval', 'Date'] });
    overview = () => json(401, { code: 'not_signed_in', message: 'Sign in to continue.' });
    await open();
    await until(() => expect(screen.getByText('You’re signed out.')).toBeTruthy());
    expect(screen.getByRole('link', { name: 'Sign in' }).getAttribute('href')).toBe('/accounts/login/?next=%2Foverview');
    await act(() => vi.advanceTimersByTimeAsync(30_000));
    expect(overviewCalls()).toHaveLength(1);
  });

  it.each([
    [403, { code: 'forbidden', message: 'Your role does not allow this.' }],
    [404, { code: 'not_found', message: 'We could not find that record.' }],
  ])('%s shows the floor is not open with the server message, no figures, and stops polling', async (status, body) => {
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout', 'setInterval', 'clearInterval', 'Date'] });
    overview = () => json(status, body);
    await open();
    await until(() => expect(screen.getByRole('heading', { name: 'The factory floor isn’t open to your role.' })).toBeTruthy());
    expect(screen.getByText(body.message)).toBeTruthy();
    expect(document.querySelector('dl')).toBeNull();
    expect(linesSection()).toBeNull();
    await act(() => vi.advanceTimersByTimeAsync(30_000));
    expect(overviewCalls()).toHaveLength(1);
  });

  it.each([
    ['500', () => json(500, { code: 'server_error', message: 'x' })],
    ['network', () => Promise.reject(new TypeError('Failed to fetch'))],
  ])('a failed poll (%s) hides the figures behind the error card; Try again restores them', async (_, fail) => {
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout', 'setInterval', 'clearInterval', 'Date'] });
    await open();
    expect(document.querySelector('dl')).not.toBeNull();
    overview = fail as () => Promise<Response>;
    await act(() => vi.advanceTimersByTimeAsync(15_000));
    await until(() => expect(screen.getByRole('alert')).toBeTruthy());
    const alert = screen.getByRole('alert');
    expect(alert.textContent).toContain('ERROR · COULDN’T LOAD');
    expect(alert.textContent).toContain('We couldn’t load the factory floor. Your work is safe; nothing was changed.');
    expect(alert.textContent).toContain('Last loaded 14 Nov 16:40 WAT.');
    expect(alert.textContent).toMatch(/Reference (server_error|network_error) for support\./);
    expect(document.querySelector('dl')).toBeNull();
    expect(linesSection()).toBeNull();
    settle(DEFAULT);
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
    await until(() => expect(tiles()).toHaveLength(4));
    expect(screen.queryByRole('alert')).toBeNull();
    expect(rows()).toHaveLength(8);
  });

  it('a failed first load says nothing about a last load', async () => {
    overview = () => json(500, { code: 'server_error', message: 'x' });
    await open();
    await until(() => expect(screen.getByRole('alert')).toBeTruthy());
    expect(screen.getByRole('alert').textContent).not.toContain('Last loaded');
    expect(screen.getByRole('alert').textContent).toContain('Reference server_error for support.');
  });
});

describe('staying current (D-UPDATES r2)', () => {
  let visibility: DocumentVisibilityState;
  beforeEach(() => {
    visibility = 'visible';
    Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => visibility });
  });
  const setVisibility = (v: DocumentVisibilityState) => {
    visibility = v;
    document.dispatchEvent(new Event('visibilitychange'));
  };

  it('polls every 15 s while visible, never while hidden, and at once on return after 15 s', async () => {
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout', 'setInterval', 'clearInterval', 'Date'] });
    await open();
    expect(overviewCalls()).toHaveLength(1);
    await act(() => vi.advanceTimersByTimeAsync(14_999));
    expect(overviewCalls()).toHaveLength(1);
    await act(() => vi.advanceTimersByTimeAsync(1));
    await until(() => expect(overviewCalls()).toHaveLength(2));

    act(() => setVisibility('hidden'));
    await act(() => vi.advanceTimersByTimeAsync(60_000));
    expect(overviewCalls()).toHaveLength(2);
    act(() => setVisibility('visible'));
    await until(() => expect(overviewCalls()).toHaveLength(3));
    await act(() => vi.advanceTimersByTimeAsync(14_999));
    expect(overviewCalls()).toHaveLength(3);
  });

  it('never has two requests in flight: a slow response plus a tick is one request', async () => {
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout', 'setInterval', 'clearInterval', 'Date'] });
    await open();
    let release!: () => void;
    overview = () => new Promise<Response>((resolve) => (release = () => resolve(json(200, DEFAULT))));
    await act(() => vi.advanceTimersByTimeAsync(15_000));
    expect(overviewCalls()).toHaveLength(2);
    await act(() => vi.advanceTimersByTimeAsync(30_000));
    expect(overviewCalls()).toHaveLength(2);
    await act(async () => release());
    settle(DEFAULT);
    await act(() => vi.advanceTimersByTimeAsync(15_000));
    await until(() => expect(overviewCalls()).toHaveLength(3));
  });

  it('a slow older response never replaces a newer one', async () => {
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout', 'setInterval', 'clearInterval', 'Date'] });
    await open();
    // A poll fails, the next poll (A) is slow, and Try again (B) answers first with a later as_of.
    overview = () => json(500, { code: 'server_error', message: 'x' });
    await act(() => vi.advanceTimersByTimeAsync(15_000));
    await until(() => expect(screen.getByRole('alert')).toBeTruthy());
    let releaseA!: () => void;
    overview = () => new Promise<Response>((resolve) => (releaseA = () => resolve(json(200, DEFAULT))));
    await act(() => vi.advanceTimersByTimeAsync(15_000));
    expect(overviewCalls()).toHaveLength(3);
    const newer: Overview = { ...DEFAULT, as_of: '2026-11-14T15:41:00Z', totals: { ...DEFAULT.totals, in_progress: 99 } };
    settle(newer);
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
    await until(() => expect(tiles()[0]).toEqual(['IN PROGRESS', '99']));
    await act(async () => releaseA());
    await until(() => expect(overviewCalls()).toHaveLength(4));
    for (let i = 0; i < 5; i++) await act(async () => new Promise((r) => realImmediate(r)));
    expect(tiles()[0]).toEqual(['IN PROGRESS', '99']);
    expect(document.querySelector('.overview__eyebrow')!.textContent).toBe('FACTORY FLOOR · UPDATED 14 Nov 16:41 WAT');
  });
});

describe('the 3D option follows reduced motion, WebGL and width', () => {
  it('reduced motion: no View switch and the motion hint', async () => {
    media['(prefers-reduced-motion: reduce)'] = true;
    await open();
    expect(screen.queryByRole('radiogroup', { name: 'View' })).toBeNull();
    expect(screen.getByText('Motion is turned down on this device, so the floor is shown flat.')).toBeTruthy();
    expect(rows()).toHaveLength(8);
  });

  it('reduced motion takes precedence over no WebGL', async () => {
    media['(prefers-reduced-motion: reduce)'] = true;
    support.webgl = false;
    await open();
    expect(screen.getByText('Motion is turned down on this device, so the floor is shown flat.')).toBeTruthy();
    expect(screen.queryByText(/can’t show the 3D floor/)).toBeNull();
  });

  it('no WebGL: no View switch and the device hint', async () => {
    support.webgl = false;
    await open();
    expect(screen.queryByRole('radiogroup', { name: 'View' })).toBeNull();
    expect(screen.getByText('This device can’t show the 3D floor, so it’s shown flat.')).toBeTruthy();
    expect(rows()).toHaveLength(8);
  });

  it('phone (SCR-06-mobile): no View switch, no hint, the board summary line after the h1, the time under the lines', async () => {
    media['(max-width: 719.98px)'] = true;
    media['(prefers-reduced-motion: reduce)'] = true;
    await open();
    expect(screen.queryByRole('radiogroup', { name: 'View' })).toBeNull();
    expect(document.querySelector('.overview__hint')).toBeNull();
    const h1 = screen.getByRole('heading', { level: 1 });
    expect(h1.nextElementSibling!.textContent).toBe('18 in progress · 5 need a person');
    expect(tiles()).toHaveLength(0);
    expect(linesSection()!.nextElementSibling!.textContent).toBe('FACTORY FLOOR · UPDATED 14 Nov 16:40 WAT');
    expect(screen.queryByText(/Each square is a station/)).toBeNull();
    expect(rows()).toHaveLength(8);
  });

  it('otherwise the View switch shows with Flat checked', async () => {
    await open();
    const group = screen.getByRole('radiogroup', { name: 'View' });
    const [flat, floor] = within(group).getAllByRole('radio');
    expect([flat.textContent, floor.textContent]).toEqual(['Flat', '3D floor']);
    expect(flat.getAttribute('aria-checked')).toBe('true');
    expect(floor.getAttribute('aria-checked')).toBe('false');
    expect(document.querySelector('.overview__hint')).toBeNull();
  });
});
