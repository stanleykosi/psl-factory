// @vitest-environment jsdom
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { setImmediate as realImmediate } from 'node:timers';

import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { MyWorkPage } from '@/features/my-work/MyWorkPage';
import { AppShell } from '@/shell/AppShell';

// @ts-expect-error plain ESM module without type declarations
import { liveWorkCounts, liveWorkList } from '../mock/live-work.mjs';
import { bellFeed, isBellFeed, isRoleDashboard, roleDashboard } from './bell-feed';
import { optionsOf, pick } from './controls';
import { page as basePage, row as baseRow } from './work-list-rows';

process.env.TZ = 'Africa/Lagos';

// next/navigation: the search params live in a small store that router.replace updates, like the app router.
const nav = vi.hoisted(() => {
  const listeners = new Set<() => void>();
  let params = new URLSearchParams();
  const set = (search: string) => {
    params = new URLSearchParams(search);
    window.history.replaceState(null, '', `/my-work${search}`);
    listeners.forEach((l) => l());
  };
  const router = {
    replace: vi.fn((url: string) => set(new URL(url, 'http://localhost').search)),
    push: vi.fn(),
    prefetch: vi.fn(),
  };
  return { listeners, get: () => params, set, router };
});
vi.mock('next/navigation', async () => {
  const { useSyncExternalStore } = await import('react');
  const subscribe = (cb: () => void) => {
    nav.listeners.add(cb);
    return () => nav.listeners.delete(cb);
  };
  return {
    usePathname: () => '/my-work',
    useRouter: () => nav.router,
    useSearchParams: () => useSyncExternalStore(subscribe, nav.get),
  };
});

type Answer = Response | Promise<Response>;
const me = (persona: string) => JSON.parse(readFileSync(join(__dirname, `../mock/fixtures/me.${persona}.json`), 'utf8'));
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
const fromMock = (url: URL) => liveWorkList({ url, persona }) as { status: number; body: ReturnType<typeof basePage> };
const mockList = (url: URL) => {
  const r = fromMock(url);
  return json(r.status, r.body);
};
const countsBody = () => liveWorkCounts({ persona }).body as { queues: { key: string; observed: number; total: number | null }[]; lines: { open: number }[]; limited: boolean; as_of: string };
const mockCounts = () => json(200, countsBody());
const withCounts = (change: (body: ReturnType<typeof countsBody>) => void) => () => {
  const body = countsBody();
  change(body);
  return json(200, body);
};
const setQueue = (body: ReturnType<typeof countsBody>, key: string, total: number | null, observed: number) => {
  body.queues = body.queues.map((x) => (x.key === key ? { ...x, total, observed } : x));
};

const PROJECT = '7d7c0c9e-2f0a-4c3e-9c61-0f6a8f1a2b99';

let persona = 'finance_lead';
let work: (url: URL) => Answer;
let countsAnswer: () => Answer;
let calls: URL[];
let countsCalls: number;

beforeEach(() => {
  persona = 'finance_lead';
  calls = [];
  countsCalls = 0;
  work = (url) => mockList(url);
  countsAnswer = mockCounts;
  nav.router.replace.mockClear();
  nav.set('');
  vi.stubGlobal(
    'fetch',
    vi.fn(async (request: Request) => {
      if (isBellFeed(request)) return bellFeed();
      if (isRoleDashboard(request)) return roleDashboard();
      const url = new URL(request.url);
      if (url.pathname === '/api/v1/me') return json(200, me(persona));
      if (url.pathname === '/api/v1/projects') return json(200, { items: [{ case_id: PROJECT, title: 'Lagoon Health Billing' }], next_cursor: null });
      if (url.pathname === '/api/v1/work/counts') {
        countsCalls += 1;
        return countsAnswer();
      }
      calls.push(url);
      return work(url);
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

const panel = () => document.getElementById('my-work-panel')!;
const rows = () => panel().querySelectorAll('tbody tr');
const tabs = () => screen.getAllByRole('tab');
const tabNames = () => tabs().map((t) => t.firstChild!.textContent);
const lastCall = () => calls[calls.length - 1];
const query = (url: URL) => Object.fromEntries(url.searchParams);
/** Whether the list has asked with exactly these parameters (a narrowed mock list may skip on to later pages after it). */
const asked = (expected: Record<string, string>) => expect(calls.map(query)).toContainEqual(expected);
const resultCount = () => document.querySelector('.psl-resultcount')!.textContent;

async function open(search = '') {
  nav.set(search);
  const result = render(
    <AppShell>
      <MyWorkPage />
    </AppShell>,
  );
  await until(() => expect(screen.queryByText('Loading your queue…')).toBeNull());
  await until(() => expect(countsCalls).toBeGreaterThan(0));
  await act(async () => {
    await new Promise((r) => realImmediate(r));
  });
  return result;
}

const FIXTURE_ROW = baseRow(412, {
  case_id: '7d7c0c9e-2f0a-4c3e-9c61-0f6a8f1a2b11',
  title: 'Harmattan Bank · M2 invoice',
  line: 'finance-ledger/v1',
  state: 'action_needed',
  status_label: 'Review the draft',
  owner: 'Ada Okafor',
  reference: 'INV-0412',
  updated_at: '2026-11-24T09:40:00Z',
  started_at: '2026-11-24T07:00:00Z',
  action_kind: 'decide',
  station: { key: 'decision', index: 3, count: 5, name: 'Approval' },
});
const craft = (items = [FIXTURE_ROW], over: Partial<ReturnType<typeof basePage>> = {}) => basePage(items, { as_of: '2026-11-24T09:42:00Z', page_size: 10, total: items.length, total_coverage: 'complete', ...over });
const serve = (body: ReturnType<typeof basePage>) => (work = () => json(200, body));

describe('what the screen reads (A-1)', () => {
  it('asks the live list and counts, and never the v7 parameters', async () => {
    await open();
    expect(calls).toHaveLength(1);
    expect(calls[0].pathname).toBe('/api/v1/work');
    expect(query(calls[0])).toEqual({ queue: 'needs_me', page: '1', limit: '10' });
    expect(countsCalls).toBe(1);
    for (const url of calls) for (const name of ['cursor', 'waiting_on', 'counts']) expect(url.searchParams.has(name)).toBe(false);
    expect(screen.queryByRole('link', { name: 'Verified outputs' })).toBeNull();
    expect(document.querySelector('.my-work__verified')).toBeNull();
  });
});

describe('queue tabs', () => {
  it('draws the eight tabs in order with counts from /work/counts', async () => {
    await open();
    expect(tabNames()).toEqual(['Needs me', 'Waiting on others', 'Started by me', 'Active', 'Decisions', 'Exceptions', 'Unassigned', 'Verified']);
    expect(tabs().map((t) => t.querySelector('.psl-badge')?.textContent ?? null)).toEqual(['24', '12', '12', '36', '12', '20+', '2', '20+']);
    expect(screen.getByRole('tablist').getAttribute('aria-label')).toBe('My work');
    expect(tabs()[0].getAttribute('aria-selected')).toBe('true');
    expect(tabs()[0].getAttribute('aria-controls')).toBe('my-work-panel');
    expect(panel().getAttribute('role')).toBe('tabpanel');
    expect(panel().getAttribute('aria-label')).toBe('Needs me');
  });

  it('a count the server could not total reads "N+" and is named "at least N"; an unknown one shows nothing; a real 0 shows 0', async () => {
    countsAnswer = withCounts((body) => {
      setQueue(body, 'waiting', null, 2);
      setQueue(body, 'mine', null, 0);
      setQueue(body, 'decisions', 0, 0);
    });
    await open();
    const badge = (i: number) => tabs()[i].querySelector('.psl-badge');
    expect(badge(1)!.textContent).toBe('2+');
    expect(badge(1)!.getAttribute('aria-label')).toBe('at least 2');
    expect(badge(2)).toBeNull();
    expect(badge(4)!.textContent).toBe('0');
    expect(badge(0)!.textContent).toBe('24');
    expect(badge(0)!.getAttribute('aria-label')).toBeNull();
  });

  it('a failed counts read shows no numbers and "Count unavailable" while the rows still load', async () => {
    countsAnswer = () => json(500, { code: 'server_error', message: 'x' });
    await open();
    expect(tabs().map((t) => t.querySelector('.psl-badge'))).toEqual([null, null, null, null, null, null, null]);
    expect(screen.getByText('Count unavailable')).toBeTruthy();
    expect(rows()).toHaveLength(10);
    expect(screen.queryByText(/records you can see/)).toBeNull();
    expect(screen.getByText('Updated 10:42')).toBeTruthy();
  });

  it('a failed list read does not blank the tabs', async () => {
    work = () => json(500, { code: 'server_error', message: 'x' });
    await open();
    await until(() => expect(screen.getByRole('alert')).toBeTruthy());
    expect(tabs()[0].querySelector('.psl-badge')!.textContent).toBe('24');
    expect(tabNames()).toHaveLength(8);
  });

  it('each tab sends its live queue and writes ?queue= to the URL; Unassigned asks no work list', async () => {
    await open();
    const order = ['waiting', 'mine', 'active', 'decisions', 'exceptions', 'verified', 'needs_me'];
    for (const queue of order) {
      fireEvent.click(tabs().find((t) => t.getAttribute('aria-selected') === 'false' && labelOf(queue) === t.firstChild!.textContent)!);
      await until(() => expect(lastCall().searchParams.get('queue')).toBe(queue));
      expect(window.location.search).toBe(queue === 'needs_me' ? '' : `?queue=${queue}`);
    }
    const before = calls.length;
    fireEvent.click(screen.getByRole('tab', { name: /^Unassigned/ }));
    await until(() => expect(window.location.search).toBe('?queue=unassigned'));
    await act(async () => {
      await new Promise((r) => realImmediate(r));
    });
    expect(calls.slice(before)).toEqual([]);
    expect(calls.every((c) => c.searchParams.get('queue') !== 'unassigned')).toBe(true);
    expect(screen.getByRole('heading', { name: 'Unassigned work' })).toBeTruthy();
    expect(screen.queryByRole('search')).toBeNull();
  });

  it('Unassigned is drawn only when something is unassigned, or when the address names it', async () => {
    persona = 'pm';
    await open();
    expect(tabNames()).toEqual(['Needs me', 'Waiting on others', 'Started by me', 'Active', 'Decisions', 'Exceptions', 'Verified']);
    expect(tabs()[5].querySelector('.psl-badge')).toBeNull();
    countsAnswer = withCounts((body) => setQueue(body, 'unassigned', 0, 0));
    persona = 'finance_lead';
    const { unmount } = await open();
    expect(tabNames()).not.toContain('Unassigned');
    unmount();
    const named = await open('?queue=unassigned');
    expect(tabNames()).toContain('Unassigned');
    named.unmount();
  });

  it('the old tab names fall back to Needs me', async () => {
    for (const old of ['done', 'waiting_on_others', 'nope']) {
      const { unmount } = await open(`?queue=${old}`);
      expect(tabs()[0].getAttribute('aria-selected')).toBe('true');
      expect(lastCall().searchParams.get('queue')).toBe('needs_me');
      unmount();
    }
  });

  it('arrow keys, Home and End move focus (one tab stop)', async () => {
    await open();
    tabs()[0].focus();
    expect(tabs().map((t) => t.tabIndex)).toEqual([0, -1, -1, -1, -1, -1, -1, -1]);
    fireEvent.keyDown(tabs()[0], { key: 'ArrowRight' });
    await waitFor(() => expect(document.activeElement).toBe(tabs()[1]));
    fireEvent.keyDown(tabs()[1], { key: 'End' });
    await waitFor(() => expect(document.activeElement).toBe(tabs()[7]));
    fireEvent.keyDown(tabs()[7], { key: 'Home' });
    await waitFor(() => expect(document.activeElement).toBe(tabs()[0]));
  });
});

const LABELS: Record<string, string> = { needs_me: 'Needs me', waiting: 'Waiting on others', mine: 'Started by me', active: 'Active', decisions: 'Decisions', exceptions: 'Exceptions', verified: 'Verified' };
const labelOf = (queue: string) => LABELS[queue];

describe('records you can see and the clock', () => {
  it('adds up the open records of every line, with the list clock', async () => {
    await open();
    const open_ = countsBody().lines.reduce((sum, l) => sum + l.open, 0);
    expect(screen.getByText(`${open_} open records you can see · updated 10:42`)).toBeTruthy();
  });

  it('says "at least" when the server could not check everything', async () => {
    countsAnswer = withCounts((body) => {
      body.limited = true;
    });
    await open();
    expect(screen.getByText(/^at least \d+ open records you can see · updated 10:42$/)).toBeTruthy();
  });
});

describe('rows', () => {
  it('shows kind, title link, line, reference, station, state, owner, start age and update time', async () => {
    serve(craft());
    await open();
    const cells = [...rows()[0].querySelectorAll('td')];
    expect(cells[0].querySelector('.psl-tag')!.textContent).toBe('DECIDE');
    const link = cells[0].querySelector('a')!;
    expect(link.textContent).toBe('Harmattan Bank · M2 invoice');
    expect(link.getAttribute('href')).toBe('/work/412');
    expect(cells[0].querySelector('.my-work__meta')!.textContent).toContain('Finance ledger · INV-0412');
    expect(cells[1].textContent).toBe('Station 3 of 5 · Approval');
    expect(cells[1].querySelectorAll('.psl-mini__bar i')).toHaveLength(5);
    expect(cells[2].querySelector('.psl-tag')!.textContent).toBe('Action needed');
    expect(cells[2].textContent).toContain('Review the draft');
    expect(cells[2].textContent).toContain('Ada Okafor');
    // started 07:00Z, listed as of 09:42Z
    expect(cells[3].querySelector('time')!.textContent).toBe('2h');
    expect(cells[3].textContent).toContain('Updated 24 Nov 10:40');
    for (const a of document.querySelectorAll('a')) expect(a.getAttribute('href') ?? '').not.toMatch(/\/work\/\d+\/$|api\/v1/);
  });

  it('draws a row with nothing optional: no kind tag, no reference, no bar; the owner reads Unassigned', async () => {
    serve(craft([baseRow(7, { title: 'Bare row', state: 'processing', status_label: 'Drafting', owner: null, reference: null, action_kind: null, station: null })]));
    await open();
    const text = rows()[0].textContent!;
    expect(rows()[0].querySelector('td .psl-tag.my-work__kind')).toBeNull();
    expect(rows()[0].querySelector('.psl-mini__bar')).toBeNull();
    expect(text).not.toMatch(/Station|null|undefined/);
    expect(rows()[0].querySelector('.my-work__meta')!.textContent!.trim()).toBe('Finance ledger');
    expect(text).toContain('Unassigned');
    expect(text).toContain('Drafting');
  });

  it('a verified row says all its stations are done', async () => {
    serve(craft([baseRow(8, { action_kind: 'started', station: { key: 'verified', index: 5, count: 5, name: 'Verified' } })]));
    await open();
    expect(rows()[0].querySelectorAll('td')[1].textContent).toBe('All 5 stations done');
  });

  it('shows the sample label on sample rows when the build shows it', async () => {
    vi.stubEnv('NEXT_PUBLIC_SHOW_SAMPLE_LABEL', '1');
    serve(craft([baseRow(9, { sample: true }), baseRow(10)]));
    await open();
    expect(rows()[0].querySelector('.psl-sample')).toBeTruthy();
    expect(rows()[1].querySelector('.psl-sample')).toBeNull();
    vi.unstubAllEnvs();
  });

  it('on a phone each card is one link with the bar, state and owner (SCR-01-mobile)', async () => {
    vi.stubGlobal('matchMedia', (q: string) => ({ matches: q.includes('max-width'), media: q, addEventListener: () => {}, removeEventListener: () => {}, addListener: () => {}, removeListener: () => {} }));
    serve(craft());
    await open();
    const card = panel().querySelector('a.my-work__card')!;
    expect(card.getAttribute('href')).toBe('/work/412');
    expect(card.querySelector('.psl-tag')!.textContent).toBe('DECIDE');
    expect(card.querySelectorAll('.psl-mini__bar i')).toHaveLength(5);
    expect(card.textContent).toContain('Action needed');
    expect(card.textContent).toContain('Ada Okafor');
    expect(card.querySelector('.my-work__age')!.textContent).toBe('2h');
  });
});

describe('search', () => {
  it('sends one q request after the last keystroke, trimmed; the box stops at 120; clearing drops q', async () => {
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout', 'setInterval', 'clearInterval', 'Date'] });
    await open();
    const box = screen.getByRole('searchbox', { name: 'Search' });
    expect(box.getAttribute('maxlength')).toBe('120');
    box.focus();
    for (const text of ['l', 'la', 'lag', ' lagoon ']) {
      fireEvent.change(box, { target: { value: text } });
      await act(() => vi.advanceTimersByTimeAsync(100));
    }
    expect(calls).toHaveLength(1);
    await act(() => vi.advanceTimersByTimeAsync(200));
    await until(() => expect(calls).toHaveLength(2));
    expect(query(calls[1])).toEqual({ queue: 'needs_me', page: '1', limit: '10', q: 'lagoon' });
    expect(document.activeElement).toBe(box);
    fireEvent.change(box, { target: { value: '   ' } });
    await act(() => vi.advanceTimersByTimeAsync(300));
    await until(() => expect(calls).toHaveLength(3));
    expect(calls[2].searchParams.has('q')).toBe(false);
  });

  it('a slow answer to the first search never replaces the newer one', async () => {
    await open();
    const release: Record<string, () => void> = {};
    work = (url) => new Promise<Response>((resolve) => (release[url.searchParams.get('q') ?? ''] = () => resolve(url.searchParams.get('q') === 'aaa' ? json(200, craft([baseRow(1, { title: 'Old answer' })])) : json(200, craft([baseRow(2, { title: 'New answer' })])))));
    const box = screen.getByRole('searchbox', { name: 'Search' });
    fireEvent.change(box, { target: { value: 'aaa' } });
    fireEvent.submit(box.closest('form')!);
    await until(() => expect(release.aaa).toBeTruthy());
    fireEvent.change(box, { target: { value: 'bbb' } });
    fireEvent.submit(box.closest('form')!);
    await until(() => expect(release.bbb).toBeTruthy());
    await act(async () => release.bbb());
    await until(() => expect(screen.getByText('New answer')).toBeTruthy());
    await act(async () => release.aaa());
    await act(async () => {
      await new Promise((r) => realImmediate(r));
    });
    expect(screen.queryByText('Old answer')).toBeNull();
    expect(screen.getByText('New answer')).toBeTruthy();
  });

  it('a search with no match shows No work matches; Clear filters clears q, line, project and state', async () => {
    await open('?q=zzz&state=ready');
    await until(() => expect(screen.getByRole('heading', { name: 'No work matches' })).toBeTruthy());
    expect(screen.getByText('Nothing in Needs me matches your search and filters.')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Clear filters' }));
    await until(() => expect(rows()).toHaveLength(10));
    expect(query(lastCall())).toEqual({ queue: 'needs_me', page: '1', limit: '10' });
    expect(window.location.search).toBe('');
  });
});

describe('filters (CMP-22, SCR-01-*-filter)', () => {
  it('offers Line, Project and the 11 states, no Waiting on; Show N items comes from a one-page preview; applying adds chips', async () => {
    await open();
    const filter = screen.getByRole('button', { name: /^Filter/ });
    fireEvent.click(filter);
    const dialog = screen.getByRole('dialog', { name: 'Filter' });
    expect(within(dialog).queryByText(/Waiting on/)).toBeNull();
    const states = optionsOf('State', within(dialog));
    expect(states).toHaveLength(12);
    expect(states[0].text).toBe('Any state');
    expect(optionsOf('Project', within(dialog)).map((o) => o.text)).toEqual(['Any project', 'Lagoon Health Billing']);

    pick('State', 'waiting', within(dialog));
    pick('Project', PROJECT, within(dialog));
    const show = await within(dialog).findByRole('button', { name: /^Show \d+ items?$/ });
    const preview = calls.find((c) => c.searchParams.get('limit') === '8');
    expect(query(preview!)).toMatchObject({ queue: 'needs_me', page: '1', limit: '8' });
    fireEvent.click(show);
    await until(() => asked({ queue: 'needs_me', page: '1', limit: '10', project: PROJECT, state: 'waiting' }));
    expect(new URLSearchParams(window.location.search).get('state')).toBe('waiting');
    expect(filter.querySelector('.cmp-badge--ink')!.textContent).toBe('2');
    expect([...document.querySelectorAll('.psl-chip')].map((c) => c.textContent)).toEqual(['ProjectLagoon Health Billing×', 'StateWaiting×']);

    fireEvent.click(screen.getByRole('button', { name: 'Remove State filter' }));
    await until(() => asked({ queue: 'needs_me', page: '1', limit: '10', project: PROJECT }));
    const before = calls.length;
    fireEvent.click(screen.getByRole('button', { name: 'Clear all' }));
    await until(() => expect(calls.slice(before).map(query)).toContainEqual({ queue: 'needs_me', page: '1', limit: '10' }));
  });

  it('the Line choices are the lines of the first page; picking one sends line=<key>', async () => {
    await open();
    fireEvent.click(screen.getByRole('button', { name: /^Filter/ }));
    const dialog = screen.getByRole('dialog', { name: 'Filter' });
    const first = within(dialog).getAllByRole('checkbox')[0];
    fireEvent.click(first);
    fireEvent.click(await within(dialog).findByRole('button', { name: /^Show \d+ items?$/ }));
    await until(() => expect(lastCall().searchParams.get('line')).toMatch(/\/v1$/));
    expect(document.querySelectorAll('.psl-chip')).toHaveLength(1);
  });

  it('Esc discards the draft and returns focus to Filter', async () => {
    await open();
    const filter = screen.getByRole('button', { name: /^Filter/ });
    fireEvent.click(filter);
    pick('State', 'ready', within(screen.getByRole('dialog', { name: 'Filter' })));
    fireEvent.keyDown(document.activeElement ?? document.body, { key: 'Escape' });
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
    await waitFor(() => expect(document.activeElement).toBe(filter));
    expect(window.location.search).toBe('');
  });
});

describe('address rules', () => {
  it('sends exactly the values in the address and nothing else', async () => {
    await open(`?queue=active&q=lagoon&line=finance-ledger/v1&project=${PROJECT}&state=ready&limit=20`);
    expect(query(calls[0])).toEqual({ queue: 'active', page: '1', limit: '20', q: 'lagoon', line: 'finance-ledger/v1', project: PROJECT, state: 'ready' });
  });

  it('drops values the contract does not take', async () => {
    await open('?project=not-a-uuid&line=nope&state=nope&queue=nope&limit=15');
    expect(query(calls[0])).toEqual({ queue: 'needs_me', page: '1', limit: '10' });
  });
});

describe('result count, paging and rows per page', () => {
  it('a complete total reads "10 OF 24 ITEMS"; Show 10 more asks page 2 and focuses the first new row', async () => {
    await open();
    expect(resultCount()).toBe('10 OF 24 ITEMS');
    expect(document.querySelector('.psl-showmore > span')!.textContent).toBe('10 of 24 showing');
    fireEvent.click(screen.getByRole('button', { name: 'Show 10 more' }));
    await until(() => expect(rows()).toHaveLength(20));
    expect(query(lastCall())).toEqual({ queue: 'needs_me', page: '2', limit: '10' });
    await waitFor(() => expect(document.activeElement).toBe(rows()[10].querySelector('a')));
    fireEvent.click(screen.getByRole('button', { name: 'Show 4 more' }));
    await until(() => expect(rows()).toHaveLength(24));
    expect(resultCount()).toBe('24 ITEMS');
    expect(document.querySelector('.psl-showmore > span')!.textContent).toBe('All 24 showing');
  });

  it('an unknown total reads "N+ ITEMS" while more pages exist, never "OF"; an incomplete total is unknown even as a number', async () => {
    serve(craft([baseRow(1), baseRow(2)], { next_page: 2, total: 40, total_coverage: 'incomplete' }));
    await open();
    expect(resultCount()).toBe('2+ ITEMS');
    expect(document.querySelector('.psl-showmore > span')!.textContent).toBe('2 showing');
    expect(screen.getByRole('button', { name: 'Show more' })).toBeTruthy();
    serve(craft([baseRow(1), baseRow(2)], { next_page: null, total: null, total_coverage: 'incomplete' }));
    fireEvent.click(tabs()[1]);
    await until(() => expect(resultCount()).toBe('2 ITEMS'));
  });

  it('choosing 20 restarts from page 1 with limit=20 and keeps the choice in the address; 10 leaves it out', async () => {
    await open();
    fireEvent.click(screen.getByRole('radio', { name: '20' }));
    await until(() => expect(query(lastCall())).toEqual({ queue: 'needs_me', page: '1', limit: '20' }));
    expect(window.location.search).toBe('?limit=20');
    await until(() => expect(rows()).toHaveLength(20));
    fireEvent.click(screen.getByRole('radio', { name: '10' }));
    await until(() => expect(query(lastCall())).toEqual({ queue: 'needs_me', page: '1', limit: '10' }));
    expect(window.location.search).toBe('');
  });

  it('Show more skips empty pages and shows rows as soon as a page has some', async () => {
    work = (url) => {
      const n = Number(url.searchParams.get('page'));
      return json(200, n === 1 ? craft([baseRow(1)], { next_page: 2, total: null, total_coverage: 'incomplete' }) : n === 2 ? craft([], { page: 2, next_page: 3 }) : craft([baseRow(3)], { page: 3, next_page: null }));
    };
    await open();
    fireEvent.click(screen.getByRole('button', { name: 'Show more' }));
    await until(() => expect(rows()).toHaveLength(2));
    expect(calls.map((c) => c.searchParams.get('page'))).toEqual(['1', '2', '3']);
  });

  it('ten empty pages in a row end with "Keep looking", never an empty state', async () => {
    work = (url) => json(200, craft([], { page: Number(url.searchParams.get('page')), next_page: Number(url.searchParams.get('page')) + 1, total: null, total_coverage: 'incomplete' }));
    await open();
    await until(() => expect(screen.getByRole('button', { name: 'Keep looking' })).toBeTruthy());
    expect(calls).toHaveLength(10);
    expect(screen.queryByText(/all caught up|No work matches|Nothing/)).toBeNull();
  });

  it('a failed Show more keeps the rows and retries the same page', async () => {
    await open();
    work = () => json(500, { code: 'boom', message: 'x' });
    fireEvent.click(screen.getByRole('button', { name: 'Show 10 more' }));
    await until(() => expect(screen.getByText('We couldn’t load more. Choose Show more to try again.')).toBeTruthy());
    expect(rows()).toHaveLength(10);
    work = (url) => mockList(url);
    fireEvent.click(screen.getByRole('button', { name: /^Show (more|\d+ more)$/ }));
    await until(() => expect(rows()).toHaveLength(20));
    expect(lastCall().searchParams.get('page')).toBe('2');
  });
});

describe('coverage notes', () => {
  it('always says as of; says incomplete and still being checked when the server does', async () => {
    serve(craft([baseRow(1)], { limited: true, deferred: [{ id: 1, url: '/work/1/' }, { id: 2, url: '/work/2/' }, { id: 3, url: '/work/3/' }] as never }));
    await open();
    const notes = [...panel().querySelectorAll('.wl-note')].map((n) => n.textContent);
    expect(notes).toEqual(['As of 24 Nov 10:42', 'This list may be incomplete. Some work could not be checked yet.', '3 more items are still being checked.']);
  });
});

describe('Needs me caught up', () => {
  it('says so with Start work and See what you started, naming the started count when the server gave one', async () => {
    serve(craft([]));
    countsAnswer = withCounts((body) => setQueue(body, 'mine', 9, 9));
    await open();
    expect(screen.getByRole('heading', { name: 'You’re all caught up' })).toBeTruthy();
    expect(screen.getByText(/^9 things you started are moving\./)).toBeTruthy();
    expect(within(panel()).getByRole('button', { name: /Start/ })).toBeTruthy();
    expect(screen.queryByRole('region', { name: 'Where your work is' })).toBeNull();
    expect(screen.queryByText('While you’re free')).toBeNull();
    expect(screen.queryByRole('searchbox')).toBeNull();
    expect(calls.every((c) => !c.searchParams.has('waiting_on'))).toBe(true);
    fireEvent.click(screen.getByRole('button', { name: 'See what you started' }));
    await until(() => expect(window.location.search).toBe('?queue=mine'));
    await until(() => expect(lastCall().searchParams.get('queue')).toBe('mine'));
  });

  it('never says 0 when the started count is unknown', async () => {
    serve(craft([]));
    countsAnswer = withCounts((body) => setQueue(body, 'mine', null, 0));
    await open();
    expect(screen.getByText(/^Things you started keep moving\./)).toBeTruthy();
    expect(panel().textContent).not.toMatch(/\b0\b/);
  });

  it('other empty queues say so', async () => {
    serve(craft([]));
    await open('?queue=waiting');
    expect(screen.getByRole('heading', { name: 'Nothing is waiting on others' })).toBeTruthy();
    expect(screen.getByText('New work will appear here.')).toBeTruthy();
  });
});

describe('errors', () => {
  it('403 says the queue is closed, with a way back and no Try again', async () => {
    work = () => json(403, { code: 'queue_not_open', message: 'This list is not open to your role.' });
    await open('?queue=exceptions');
    await until(() => expect(screen.getByRole('heading', { name: 'This queue isn’t open to your role.' })).toBeTruthy());
    expect(screen.getByRole('link', { name: 'Go to Needs me' }).getAttribute('href')).toBe('/my-work');
    expect(screen.queryByRole('button', { name: 'Try again' })).toBeNull();
    expect(screen.getByRole('tablist')).toBeTruthy();
  });

  it('403 on Needs me has no Go to Needs me link', async () => {
    work = () => json(403, { code: 'forbidden', message: 'Your role does not allow this.' });
    await open();
    await until(() => expect(screen.getByRole('heading', { name: 'This queue isn’t open to your role.' })).toBeTruthy());
    expect(screen.queryByRole('link', { name: 'Go to Needs me' })).toBeNull();
  });

  it('401 shows the signed-out state with the way back to My work', async () => {
    work = () => json(401, { code: 'not_signed_in', message: 'Sign in to continue.' });
    await open();
    await until(() => expect(screen.getByText('You’re signed out.')).toBeTruthy());
    expect(screen.getByRole('link', { name: 'Sign in' }).getAttribute('href')).toBe('/sign-in?next=%2Fmy-work');
  });

  it.each([
    ['500', () => json(500, { code: 'server_error', message: 'x' }), 'server_error'],
    ['network', () => Promise.reject(new TypeError('Failed to fetch')), 'network_error'],
  ])('%s shows the error card; Try again repeats the request and recovers', async (_, fail, code) => {
    work = fail as () => Answer;
    await open();
    await until(() => expect(screen.getByRole('alert')).toBeTruthy());
    expect([...screen.getByRole('alert').children].map((el) => el.textContent)).toEqual([
      'ERROR · COULDN’T LOAD',
      'We couldn’t load your queue. Your work is safe; nothing was changed.',
      `Reference ${code} for support.`,
      'Try again',
    ]);
    expect(screen.getByRole('tablist')).toBeTruthy();
    work = (url) => mockList(url);
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
    await until(() => expect(rows()).toHaveLength(10));
  });

  it('after an earlier load the error card says when it last loaded', async () => {
    await open();
    work = () => json(500, { code: 'server_error', message: 'x' });
    fireEvent.click(tabs()[1]);
    await until(() => expect(screen.getByRole('alert')).toBeTruthy());
    expect(screen.getByRole('alert').querySelector('.shell-reference')!.textContent).toBe('Last loaded 10:42. Reference server_error for support.');
  });

  it('loading shows the skeleton and status; a late answer for an older view is ignored', async () => {
    const pending: Record<string, () => void> = {};
    work = (url) => new Promise<Response>((resolve) => (pending[url.searchParams.get('queue')!] = () => resolve(mockList(url))));
    nav.set('');
    render(
      <AppShell>
        <MyWorkPage />
      </AppShell>,
    );
    await until(() => expect(pending.needs_me).toBeTruthy());
    expect(document.querySelector('.psl-loading')!.textContent).toBe('Loading your queue…');
    fireEvent.click(tabs().find((t) => t.firstChild!.textContent === 'Waiting on others')!);
    await until(() => expect(pending.waiting).toBeTruthy());
    await act(async () => pending.waiting());
    await until(() => expect(rows().length + panel().querySelectorAll('.my-work__started').length).toBeGreaterThan(0));
    const shown = rows().length;
    await act(async () => pending.needs_me());
    await act(async () => {
      await new Promise((r) => realImmediate(r));
    });
    expect(rows()).toHaveLength(shown);
    expect(tabs()[1].getAttribute('aria-selected')).toBe('true');
  });
});

describe('staying current (D-UPDATES)', () => {
  let visibility: DocumentVisibilityState;
  beforeEach(() => {
    visibility = 'visible';
    Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => visibility });
  });
  const setVisibility = (v: DocumentVisibilityState) => {
    visibility = v;
    document.dispatchEvent(new Event('visibilitychange'));
  };
  const fake = () => vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout', 'setInterval', 'clearInterval', 'Date'] });

  it('re-reads page 1 and the counts every 15 s while visible, never while hidden, and at once on return after 15 s', async () => {
    fake();
    await open();
    expect([calls.length, countsCalls]).toEqual([1, 1]);
    await act(() => vi.advanceTimersByTimeAsync(14_999));
    expect(calls).toHaveLength(1);
    await act(() => vi.advanceTimersByTimeAsync(1));
    await until(() => expect([calls.length, countsCalls]).toEqual([2, 2]));
    expect(query(calls[1])).toEqual({ queue: 'needs_me', page: '1', limit: '10' });
    act(() => setVisibility('hidden'));
    await act(() => vi.advanceTimersByTimeAsync(60_000));
    expect(calls).toHaveLength(2);
    act(() => setVisibility('visible'));
    await until(() => expect(calls).toHaveLength(3));
  });

  it('a refresh keeps the rows loaded with Show more and moves nothing else', async () => {
    fake();
    await open();
    fireEvent.click(screen.getByRole('button', { name: 'Show 10 more' }));
    await until(() => expect(rows()).toHaveLength(20));
    const link = rows()[15].querySelector('a')!;
    link.focus();
    const firstId = rows()[0].querySelector('a')!.getAttribute('href');
    work = (url) => {
      const { status, body } = fromMock(url);
      if (url.searchParams.get('page') === '1') body.as_of = '2026-11-10T09:57:00Z';
      return json(status, body);
    };
    await act(() => vi.advanceTimersByTimeAsync(15_000));
    await until(() => expect(screen.getByText(/updated 10:57$/)).toBeTruthy());
    expect(query(lastCall())).toEqual({ queue: 'needs_me', page: '1', limit: '10' });
    expect(rows()).toHaveLength(20);
    expect(rows()[0].querySelector('a')!.getAttribute('href')).toBe(firstId);
    expect(document.activeElement).toBe(link);
    expect(document.querySelector('.psl-loading')).toBeNull();
  });

  it.each([
    ['network', () => Promise.reject(new TypeError('Failed to fetch'))],
    ['500', () => json(500, { code: 'server_error', message: 'x' })],
  ])('a failed refresh (%s) keeps the rows and says it could not refresh', async (_, fail) => {
    fake();
    await open();
    work = fail as () => Answer;
    await act(() => vi.advanceTimersByTimeAsync(15_000));
    await until(() => expect(document.querySelector('.my-work__updated[role="status"]')!.textContent).toMatch(/Couldn’t refresh · updated 10:42$/));
    expect(rows()).toHaveLength(10);
    expect(screen.queryByRole('alert')).toBeNull();
    work = (url) => mockList(url);
    await act(() => vi.advanceTimersByTimeAsync(15_000));
    await until(() => expect(document.querySelector('.my-work__updated[role="status"]')).toBeNull());
  });

  it('a failed counts refresh keeps the numbers and says it could not refresh', async () => {
    fake();
    await open();
    countsAnswer = () => json(500, { code: 'server_error', message: 'x' });
    await act(() => vi.advanceTimersByTimeAsync(15_000));
    await until(() => expect(document.querySelector('.my-work__updated[role="status"]')).toBeTruthy());
    expect(tabs()[0].querySelector('.psl-badge')!.textContent).toBe('24');
    expect(screen.queryByText('Count unavailable')).toBeNull();
  });

  it('a 401 on refresh shows the signed-out state', async () => {
    fake();
    await open();
    work = () => json(401, { code: 'not_signed_in', message: 'x' });
    await act(() => vi.advanceTimersByTimeAsync(15_000));
    await until(() => expect(screen.getByText('You’re signed out.')).toBeTruthy());
  });
});
