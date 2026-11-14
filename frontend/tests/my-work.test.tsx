// @vitest-environment jsdom
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { setImmediate as realImmediate } from 'node:timers';

import { act, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { MyWorkPage } from '@/features/my-work/MyWorkPage';
import { AppShell } from '@/shell/AppShell';

// @ts-expect-error plain ESM module without type declarations
import { workList } from '../mock/work-list.mjs';

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

type Body = { items: { id: string; state: string; kind: string; sample: boolean }[]; next_cursor?: string; as_of: string; counts?: Record<string, number> };
const me = (persona: string) => JSON.parse(readFileSync(join(__dirname, `../mock/fixtures/me.${persona}.json`), 'utf8'));
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
const fromMock = (url: URL, persona = 'finance_lead') => workList({ url, persona }) as { status: number; body: Body };
const mockResponse = (url: URL, persona = 'finance_lead') => {
  const r = fromMock(url, persona);
  return json(r.status, r.body);
};

let persona = 'finance_lead';
let work: (url: URL) => Response | Promise<Response>;
let calls: URL[];

beforeEach(() => {
  persona = 'finance_lead';
  calls = [];
  work = (url) => mockResponse(url, persona);
  nav.router.replace.mockClear();
  nav.set('');
  vi.stubGlobal(
    'fetch',
    vi.fn(async (request: Request) => {
      const url = new URL(request.url);
      if (url.pathname === '/api/v1/me') return json(200, me(persona));
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
const lastCall = () => calls[calls.length - 1];
const query = (url: URL) => Object.fromEntries(url.searchParams);

async function open(search = '') {
  nav.set(search);
  const result = render(
    <AppShell>
      <MyWorkPage />
    </AppShell>,
  );
  await until(() => expect(screen.queryByText('Loading your queue…')).toBeNull());
  await until(() => expect(calls.length).toBeGreaterThan(0));
  return result;
}

describe('queue tabs (A-MYWORK)', () => {
  it('finance_lead sees Needs me 24, Waiting on others 12, Done 6, Unassigned 2 in .psl-badge', async () => {
    await open();
    expect(tabs().map((t) => [t.firstChild!.textContent, t.querySelector('.psl-badge')!.textContent])).toEqual([
      ['Needs me', '24'],
      ['Waiting on others', '12'],
      ['Done', '6'],
      ['Unassigned', '2'],
    ]);
    expect(screen.getByRole('tablist').getAttribute('aria-label')).toBe('My work');
    expect(tabs()[0].getAttribute('aria-selected')).toBe('true');
    expect(tabs()[0].getAttribute('aria-controls')).toBe('my-work-panel');
    expect(panel().getAttribute('role')).toBe('tabpanel');
    expect(panel().getAttribute('aria-labelledby')).toBe(tabs()[0].id);
    expect(screen.getByText('44 records you can see · updated 10:42')).toBeTruthy();
  });

  it('without counts.unassigned there are three tabs and zero reads 0', async () => {
    persona = 'pm';
    await open();
    expect(tabs().map((t) => t.textContent)).toEqual(['Needs me0', 'Waiting on others3', 'Done2']);
  });

  it('without counts every badge reads – with "Count unavailable"; never 0', async () => {
    work = (url) => {
      const { body } = fromMock(url);
      delete body.counts;
      return json(200, body);
    };
    await open();
    expect(tabs().map((t) => t.querySelector('.psl-badge')!.textContent)).toEqual(['–', '–', '–']);
    expect(screen.getByText('Count unavailable')).toBeTruthy();
    expect(document.querySelector('.psl-resultcount')!.textContent).toBe('20+ ITEMS');
  });

  it('each tab requests its queue with limit=20 and writes ?queue= to the URL', async () => {
    await open();
    expect(query(calls[0])).toEqual({ queue: 'needs_me', limit: '20' });
    for (const [i, queue] of ['waiting_on_others', 'done', 'unassigned', 'needs_me'].entries()) {
      fireEvent.click(tabs()[(i + 1) % 4]);
      await until(() => expect(query(lastCall())).toEqual({ queue, limit: '20' }));
      expect(window.location.search).toBe(queue === 'needs_me' ? '' : `?queue=${queue}`);
    }
    expect(nav.router.replace).toHaveBeenCalledWith('/my-work?queue=done', { scroll: false });
  });

  it('arrow keys, Home and End move the selection with a roving tabindex', async () => {
    await open();
    tabs()[0].focus();
    fireEvent.keyDown(tabs()[0], { key: 'ArrowRight' });
    await until(() => expect(tabs()[1].getAttribute('aria-selected')).toBe('true'));
    expect(document.activeElement).toBe(tabs()[1]);
    expect(tabs().map((t) => t.tabIndex)).toEqual([-1, 0, -1, -1]);
    fireEvent.keyDown(tabs()[1], { key: 'End' });
    await until(() => expect(query(lastCall()).queue).toBe('unassigned'));
    expect(document.activeElement).toBe(tabs()[3]);
    fireEvent.keyDown(tabs()[3], { key: 'Home' });
    await until(() => expect(query(lastCall()).queue).toBe('needs_me'));
    fireEvent.keyDown(tabs()[0], { key: 'ArrowLeft' });
    await until(() => expect(query(lastCall()).queue).toBe('unassigned'));
  });
});

describe('rows', () => {
  const crafted = {
    items: [
      { id: 'W-1001', title: 'Decide row', line: 'L1', reference: 'R1', kind: 'decide', state: 'waiting', station: { index: 4, count: 7, name: 'Finance review' }, waiting_on: 'Finance Lead', age_seconds: 7200, sample: true },
      { id: 'W-2', title: 'Do row', line: 'L1', reference: 'R2', kind: 'do', state: 'ready', station: { index: 1, count: 2, name: 'A' }, waiting_on: 'Me', age_seconds: 30, sample: false },
      { id: 'W-3', title: 'Fix row', line: 'L2', reference: 'R3', kind: 'fix', state: 'effect_uncertain', station: { index: 2, count: 3, name: 'B' }, waiting_on: 'Me', age_seconds: 86400, sample: true },
      { id: 'W-4', title: 'Started row', line: 'L2', reference: 'R4', kind: 'started', state: 'action_needed', station: { index: 1, count: 2, name: 'C' }, waiting_on: 'Agent', age_seconds: 600, sample: false },
    ],
    as_of: '2026-11-10T09:42:00Z',
    counts: { needs_me: 4, waiting_on_others: 0, done: 0 },
  };

  it('kind comes from the API, never from the state', async () => {
    work = () => json(200, crafted);
    await open();
    const kinds = [...rows()].map((r) => r.querySelector('td .psl-tag')!);
    expect(kinds.map((t) => [t.textContent, t.className])).toEqual([
      ['DECIDE', 'psl-tag psl-tag--person my-work__kind'],
      ['DO', 'psl-tag psl-tag--person my-work__kind'],
      ['FIX', 'psl-tag psl-tag--person my-work__kind'],
      ['STARTED', 'psl-tag psl-tag--neutral my-work__kind'],
    ]);
    const state = rows()[3].querySelectorAll('td')[2].querySelector('.psl-tag')!;
    expect([state.textContent, state.className]).toEqual(['Action needed', 'psl-tag psl-tag--person']);
  });

  it('Needs me from the mock shows only DECIDE, DO and FIX', async () => {
    await open();
    const kinds = new Set([...rows()].map((r) => r.querySelector('td .psl-tag')!.textContent));
    expect([...kinds].every((k) => ['DECIDE', 'DO', 'FIX'].includes(k!))).toBe(true);
  });

  it('renders every state with its words and family', async () => {
    const states = Object.entries({
      ready: ['Ready to continue', 'person'],
      processing: ['Processing', 'agent'],
      waiting: ['Waiting', 'waiting'],
      owner_needed: ['Owner needed', 'person'],
      setup_needed: ['Setup needed', 'person'],
      action_needed: ['Action needed', 'person'],
      effect_uncertain: ['Effect uncertain', 'person'],
      awaiting_reconciliation: ['Awaiting reconciliation', 'waiting'],
      verified: ['Verified', 'done'],
      cancelled: ['Cancelled', 'neutral'],
      followup_needed: ['Stopped: invoice follow-up needed', 'person'],
    });
    work = () => json(200, { ...crafted, items: states.map(([state], i) => ({ ...crafted.items[0], id: `W-${i}`, state })) });
    await open();
    const tags = [...rows()].map((r) => r.querySelectorAll('td')[2].querySelector('.psl-tag')!);
    expect(tags.map((t) => [t.textContent, t.className])).toEqual(states.map(([, [words, family]]) => [words, `psl-tag psl-tag--${family}`]));
  });

  it('station bar, age, waiting on, no sample tag and row links', async () => {
    work = () => json(200, crafted);
    await open();
    const first = rows()[0];
    const bar = first.querySelector('.psl-mini__bar')!;
    expect(bar.getAttribute('aria-hidden')).toBe('true');
    expect([...bar.querySelectorAll('i')].map((i) => i.className)).toEqual(['d', 'd', 'd', 'w', '', '', '']);
    expect(first.querySelector('.psl-mini__text')!.textContent).toBe('Station 4 of 7 · Finance review');
    expect([...rows()].map((r) => r.querySelectorAll('td')[3].textContent)).toEqual(['2h', '1m', '1d', '10m']);
    expect(first.querySelectorAll('td')[2].textContent).toBe('WaitingFinance Lead');
    expect(crafted.items.some((i) => i.sample)).toBe(true);
    expect(panel().querySelectorAll('.psl-sample')).toHaveLength(0);
    expect(within(panel()).getByRole('link', { name: 'Decide row' }).getAttribute('href')).toBe('/work/W-1001');
    expect(screen.getAllByRole('columnheader').map((h) => h.textContent)).toEqual(['WORK', 'WHERE ON ITS LINE', 'STATE', 'AGE']);
  });

  it('on a phone each card is one link with the mini bar, state and who it waits on (SCR-01-mobile)', async () => {
    vi.stubGlobal('matchMedia', (q: string) => ({ matches: true, media: q, addEventListener: () => {}, removeEventListener: () => {} }));
    work = () => json(200, crafted);
    await open();
    const cards = panel().querySelectorAll('ul > li > a');
    expect([...cards].map((a) => a.getAttribute('href'))).toEqual(['/work/W-1001', '/work/W-2', '/work/W-3', '/work/W-4']);
    expect(cards[0].querySelectorAll('.psl-mini__bar > i')).toHaveLength(7);
    expect(cards[0].textContent).toContain('Waiting');
    expect(cards[0].textContent).toContain('Finance Lead');
    expect(screen.getByRole('button', { name: 'Filter' }).className).toContain('psl-iconbtn');
    expect(document.querySelector('.psl-seg--phone')).toBeTruthy();
  });
});

describe('search', () => {
  it('sends one q=lagoon request 300 ms after the last keystroke; clearing drops q', async () => {
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout', 'setInterval', 'clearInterval', 'Date'] });
    await open();
    const box = screen.getByRole('searchbox', { name: 'Search' });
    box.focus();
    for (const text of ['l', 'la', 'lag', 'lagoon']) {
      fireEvent.change(box, { target: { value: text } });
      await act(() => vi.advanceTimersByTimeAsync(100));
    }
    expect(calls).toHaveLength(1);
    await act(() => vi.advanceTimersByTimeAsync(200));
    await until(() => expect(calls).toHaveLength(2));
    expect(query(calls[1])).toEqual({ queue: 'needs_me', limit: '20', q: 'lagoon' });
    expect(document.activeElement).toBe(box);
    await until(() => expect(rows()).toHaveLength(2));
    expect(document.querySelector('.psl-resultcount')!.textContent).toBe('2 OF 24 ITEMS');

    fireEvent.change(box, { target: { value: '   ' } });
    await act(() => vi.advanceTimersByTimeAsync(300));
    await until(() => expect(calls).toHaveLength(3));
    expect(calls[2].searchParams.has('q')).toBe(false);
    expect(calls.every((c) => c.searchParams.get('q') !== '')).toBe(true);
  });

  it('Enter applies at once; no match shows No work matches with Clear filters', async () => {
    await open();
    const box = screen.getByRole('searchbox', { name: 'Search' });
    fireEvent.change(box, { target: { value: 'zzz' } });
    fireEvent.submit(box.closest('form')!);
    await until(() => expect(screen.getByRole('heading', { name: 'No work matches' })).toBeTruthy());
    expect(query(lastCall()).q).toBe('zzz');
    expect(screen.getByText('Nothing in Needs me matches your search and filters.')).toBeTruthy();
    expect(document.querySelector('.psl-showmore')).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: 'Clear filters' }));
    await until(() => expect(rows()).toHaveLength(20));
    expect(lastCall().searchParams.has('q')).toBe(false);
    expect((box as HTMLInputElement).value).toBe('');
  });
});

describe('filters (CMP-22, SCR-01-*-filter)', () => {
  it('applies Line (by key), Project, State and Waiting on from the panel, shows the badge and chips, and removes them', async () => {
    await open();
    const filter = screen.getByRole('button', { name: /^Filter/ });
    expect(filter.getAttribute('aria-haspopup')).toBe('dialog');
    fireEvent.click(filter);
    expect(filter.getAttribute('aria-expanded')).toBe('true');
    expect(filter.className).toContain('psl-btn--dark');
    const dialog = screen.getByRole('dialog', { name: 'Filter' });
    expect(dialog.className).toContain('psl-pop');
    // Lines come from the response's filters.lines (A–Z in the mock); four show until "Show all 6 lines".
    const lines = () => within(dialog).getAllByRole('checkbox').map((r) => r.parentElement!.textContent);
    expect(document.activeElement).toBe(within(dialog).getAllByRole('checkbox')[0]);
    expect(lines()).toEqual(['Approve a payment exception', 'Plan a project', 'Prepare an invoice', 'Reconcile a bank statement']);
    fireEvent.click(within(dialog).getByRole('button', { name: 'Show all 6 lines' }));
    expect(lines()).toHaveLength(6);
    expect(within(dialog).getByRole('combobox', { name: 'Project' })).toBeTruthy();
    const state = within(dialog).getByRole('combobox', { name: 'State' }) as HTMLSelectElement;
    expect([...state.options].map((o) => o.textContent)[0]).toBe('Any state');
    expect(state.options).toHaveLength(12);
    const waiting = within(dialog).getByRole('combobox', { name: 'Waiting on' }) as HTMLSelectElement;
    expect([...waiting.options].map((o) => o.value)).toEqual(['', 'me', 'someone_else', 'agent', 'outside_party', 'no_owner']);

    fireEvent.click(within(dialog).getByRole('checkbox', { name: 'Prepare an invoice' }));
    fireEvent.click(within(dialog).getByRole('checkbox', { name: 'Record a receipt' }));
    // One line key at a time: the contract's line parameter takes one value.
    expect(within(dialog).getAllByRole('checkbox', { checked: true }).map((c) => c.parentElement!.textContent)).toEqual(['Record a receipt']);
    fireEvent.click(within(dialog).getByRole('checkbox', { name: 'Prepare an invoice' }));
    fireEvent.change(state, { target: { value: 'action_needed' } });
    // "Show N items" counts the draft with the same list request.
    const show = await within(dialog).findByRole('button', { name: /^Show \d+ items?$/ });
    const preview = calls.find((c) => c.searchParams.get('line') === 'invoice' && c.searchParams.get('limit') === '50');
    expect(query(preview!)).toEqual({ queue: 'needs_me', limit: '50', line: 'invoice', state: 'action_needed' });
    fireEvent.click(show);
    await until(() => expect(query(lastCall())).toEqual({ queue: 'needs_me', limit: '20', line: 'invoice', state: 'action_needed' }));
    expect(screen.queryByRole('dialog')).toBeNull();
    expect(document.activeElement).toBe(filter);
    expect(filter.querySelector('.psl-badge--signal')!.textContent).toBe('2');
    expect(new URLSearchParams(window.location.search).get('line')).toBe('invoice');
    expect(new URLSearchParams(window.location.search).get('state')).toBe('action_needed');
    const chips = [...document.querySelectorAll('.psl-chip')].map((c) => c.textContent);
    expect(chips).toEqual(['LinePrepare an invoice×', 'StateAction needed×']);

    fireEvent.click(screen.getByRole('button', { name: 'Remove Line filter' }));
    await until(() => expect(query(lastCall())).toEqual({ queue: 'needs_me', limit: '20', state: 'action_needed' }));
    expect(filter.querySelector('.psl-badge--signal')!.textContent).toBe('1');
    fireEvent.click(screen.getByRole('button', { name: 'Clear all' }));
    await until(() => expect(query(lastCall())).toEqual({ queue: 'needs_me', limit: '20' }));
    expect(filter.querySelector('.psl-badge')).toBeNull();
    expect(document.querySelector('.psl-chip')).toBeNull();
  });

  it('restores project and waiting_on from the URL as chips', async () => {
    await open('?project=C-LAGOON-HEALTH&waiting_on=me');
    expect(query(lastCall())).toEqual({ queue: 'needs_me', limit: '20', project: 'C-LAGOON-HEALTH', waiting_on: 'me' });
    expect([...document.querySelectorAll('.psl-chip')].map((c) => c.textContent)).toEqual(['ProjectC-LAGOON-HEALTH×', 'Waiting onMe×']);
    expect(rows()).toHaveLength(2);
  });

  it('Esc discards the draft and returns focus to Filter', async () => {
    await open();
    const filter = screen.getByRole('button', { name: /^Filter/ });
    fireEvent.click(filter);
    fireEvent.click(screen.getByRole('checkbox', { name: 'Plan a project' }));
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(screen.queryByRole('dialog')).toBeNull();
    expect(document.activeElement).toBe(filter);
    expect(filter.getAttribute('aria-expanded')).toBe('false');
    expect(calls.filter((c) => c.pathname === '/api/v1/work' && c.searchParams.get('limit') === '20')).toHaveLength(1);
    fireEvent.click(filter);
    expect(screen.queryAllByRole('checkbox', { checked: true })).toHaveLength(0);
    fireEvent.mouseDown(document.body);
    expect(screen.queryByRole('dialog')).toBeNull();
  });

  it('on a phone the panel is a bottom sheet with Clear in its head; the scrim closes it', async () => {
    vi.stubGlobal('matchMedia', (q: string) => ({ matches: true, media: q, addEventListener: () => {}, removeEventListener: () => {} }));
    await open();
    const filter = screen.getByRole('button', { name: 'Filter' });
    fireEvent.click(filter);
    const sheet = screen.getByRole('dialog', { name: 'Filter' });
    expect(sheet.className).toContain('psl-sheet');
    // SCR-01-mobile-filter: no grab handle; the head is FILTER with Clear.
    expect(sheet.querySelector('.psl-sheet__grab')).toBeNull();
    expect(within(sheet.querySelector('.psl-sheet__head') as HTMLElement).getByRole('button', { name: 'Clear' })).toBeTruthy();
    expect(within(sheet).getByRole('button', { name: /^Show / }).className).toContain('psl-btn--xl psl-btn--block');
    expect(within(sheet).getByRole('button', { name: 'All 6 lines' })).toBeTruthy();
    fireEvent.mouseDown(sheet.parentElement!);
    expect(screen.queryByRole('dialog')).toBeNull();
    expect(document.activeElement).toBe(filter);
  });
});

describe('paging (D-PAGING r2)', () => {
  it('20 of 24, Show 4 more appends with the cursor and focuses the first new row', async () => {
    await open();
    expect(rows()).toHaveLength(20);
    expect(document.querySelector('.psl-showmore > span')!.textContent).toBe('20 of 24 showing');
    const group = screen.getByRole('radiogroup', { name: 'Rows per page' });
    expect(within(group).getAllByRole('radio').map((r) => [r.textContent, r.getAttribute('aria-checked')])).toEqual([
      ['10', 'false'],
      ['20', 'true'],
      ['50', 'false'],
    ]);
    const more = screen.getByRole('button', { name: 'Show 4 more' });
    fireEvent.click(more);
    expect(more.getAttribute('aria-busy')).toBe('true');
    expect((more as HTMLButtonElement).disabled).toBe(true);
    await until(() => expect(rows()).toHaveLength(24));
    expect(query(lastCall())).toEqual({ queue: 'needs_me', limit: '20', cursor: 'o20' });
    expect(document.activeElement).toBe(rows()[20].querySelector('a'));
    expect(document.querySelector('.psl-showmore > span')!.textContent).toBe('All 24 showing');
    expect(screen.queryByRole('button', { name: /^Show .*more$/ })).toBeNull();
  });

  it('choosing 10 reloads page 1 with limit=10 and keeps it in the URL', async () => {
    await open();
    fireEvent.click(screen.getByRole('radio', { name: '10' }));
    await until(() => expect(rows()).toHaveLength(10));
    expect(query(lastCall())).toEqual({ queue: 'needs_me', limit: '10' });
    expect(window.location.search).toBe('?limit=10');
    expect(screen.getByRole('button', { name: 'Show 10 more' })).toBeTruthy();
  });

  it('a failed Show more keeps the rows and retries the same cursor', async () => {
    await open();
    work = () => json(500, { code: 'boom', message: 'x' });
    fireEvent.click(screen.getByRole('button', { name: 'Show 4 more' }));
    await until(() => expect(screen.getByText('We couldn’t load more. Your work is safe; nothing was changed.')).toBeTruthy());
    expect(document.querySelector('.psl-callout--problem')).toBeTruthy();
    expect(rows()).toHaveLength(20);
    work = (url) => mockResponse(url);
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
    await until(() => expect(rows()).toHaveLength(24));
    expect(lastCall().searchParams.get('cursor')).toBe('o20');
  });
});

describe('URL restore', () => {
  it('sends exactly the values in the URL and stores nothing', async () => {
    const cookie = document.cookie;
    const stored = [localStorage.length, sessionStorage.length];
    await open('?queue=done&q=lagoon&state=verified&limit=50');
    expect(query(calls[0])).toEqual({ queue: 'done', q: 'lagoon', state: 'verified', limit: '50' });
    expect((screen.getByRole('searchbox') as HTMLInputElement).value).toBe('lagoon');
    expect(tabs()[2].getAttribute('aria-selected')).toBe('true');
    expect([localStorage.length, sessionStorage.length]).toEqual(stored);
    expect(document.cookie).toBe(cookie);
  });

  it('invalid values fall back to needs_me, 20 and no state', async () => {
    await open('?queue=bogus&limit=7&state=nope');
    expect(query(calls[0])).toEqual({ queue: 'needs_me', limit: '20' });
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

  it('polls page 1 every 15 s while visible, never while hidden, and at once on return after 15 s', async () => {
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout', 'setInterval', 'clearInterval', 'Date'] });
    await open();
    expect(calls).toHaveLength(1);
    await act(() => vi.advanceTimersByTimeAsync(14_999));
    expect(calls).toHaveLength(1);
    await act(() => vi.advanceTimersByTimeAsync(1));
    await until(() => expect(calls).toHaveLength(2));
    expect(query(calls[1])).toEqual({ queue: 'needs_me', limit: '20' });

    act(() => setVisibility('hidden'));
    await act(() => vi.advanceTimersByTimeAsync(60_000));
    expect(calls).toHaveLength(2);
    act(() => setVisibility('visible'));
    await until(() => expect(calls).toHaveLength(3));
    await act(() => vi.advanceTimersByTimeAsync(15_000));
    await until(() => expect(calls).toHaveLength(4));
  });

  it('a refresh keeps the rows loaded with Show more, focus and no loading text', async () => {
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout', 'setInterval', 'clearInterval', 'Date'] });
    await open();
    fireEvent.click(screen.getByRole('button', { name: 'Show 4 more' }));
    await until(() => expect(rows()).toHaveLength(24));
    const link = rows()[21].querySelector('a')!;
    link.focus();
    const firstId = rows()[0].querySelector('a')!.getAttribute('href');
    work = (url) => {
      const { status, body } = fromMock(url);
      if (!url.searchParams.has('cursor')) {
        body.items[0] = { ...body.items[0], state: 'verified' };
        body.counts = { ...body.counts, needs_me: 25 };
        body.as_of = '2026-11-10T09:57:00Z';
      }
      return json(status, body);
    };
    await act(() => vi.advanceTimersByTimeAsync(15_000));
    await until(() => expect(screen.getByText('45 records you can see · updated 10:57')).toBeTruthy());
    expect(query(lastCall())).toEqual({ queue: 'needs_me', limit: '20' });
    expect(rows()).toHaveLength(24);
    expect(rows()[0].querySelector('a')!.getAttribute('href')).toBe(firstId);
    expect(rows()[0].querySelectorAll('td')[2].querySelector('.psl-tag')!.textContent).toBe('Verified');
    expect(document.activeElement).toBe(link);
    expect(screen.queryByRole('status')).toBeNull();
    expect(tabs()[0].querySelector('.psl-badge')!.textContent).toBe('25');
  });

  it.each([
    ['network', () => Promise.reject(new TypeError('Failed to fetch'))],
    ['500', () => json(500, { code: 'server_error', message: 'x' })],
  ])('a failed refresh (%s) keeps the rows and says it could not refresh', async (_, fail) => {
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout', 'setInterval', 'clearInterval', 'Date'] });
    await open();
    work = fail as () => Promise<Response>;
    await act(() => vi.advanceTimersByTimeAsync(15_000));
    await until(() => expect(screen.getByRole('status').textContent).toBe('44 records you can see · Couldn’t refresh · updated 10:42'));
    expect(rows()).toHaveLength(20);
    expect(screen.queryByRole('alert')).toBeNull();
    work = (url) => mockResponse(url);
    await act(() => vi.advanceTimersByTimeAsync(15_000));
    await until(() => expect(screen.getByText('44 records you can see · updated 10:42')).toBeTruthy());
    expect(screen.queryByRole('status')).toBeNull();
  });

  it('a 401 on refresh shows the signed-out callout', async () => {
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout', 'setInterval', 'clearInterval', 'Date'] });
    await open();
    work = () => json(401, { code: 'not_signed_in', message: 'Sign in to continue.' });
    await act(() => vi.advanceTimersByTimeAsync(15_000));
    await until(() => expect(screen.getByRole('link', { name: 'Sign in' }).getAttribute('href')).toBe('/accounts/login/?next=%2Fmy-work'));
    expect(screen.queryByRole('tablist')).toBeNull();
  });
});

describe('screen states', () => {
  it('pm Needs me is empty (SCR-01-desktop-empty): caught up, where the started work is, no search bar', async () => {
    persona = 'pm';
    await open();
    expect(screen.getByRole('heading', { name: 'Nothing needs you right now' })).toBeTruthy();
    expect(screen.getByText('3 things you started are moving. We’ll alert you on WhatsApp when one needs you.')).toBeTruthy();
    expect(document.querySelector('.psl-showmore')).toBeNull();
    expect(screen.queryByRole('searchbox')).toBeNull();
    // Grouped by who the work waits on, one E-WORK-LIST request per group.
    const where = await screen.findByRole('region', { name: 'Where your work is' });
    await until(() => expect(where.querySelectorAll('.my-work__group')).toHaveLength(2));
    expect([...where.querySelectorAll('.my-work__grouphead')].map((g) => g.textContent)).toEqual(['Tola is drafting1', 'Other people are reviewing2']);
    // Agents show their mascot image (public/agents/), never initials.
    expect(screen.getByRole('img', { name: 'Tola, the PMO agent' }).getAttribute('src')).toContain('agents%2Ftola.png');
    expect(within(where).getByRole('img', { name: 'Tola · PMO agent' })).toBeTruthy();
    expect(within(where).getByRole('link', { name: 'See all 3' }).getAttribute('href')).toBe('/my-work?queue=waiting_on_others');
    expect(calls.filter((c) => c.searchParams.has('waiting_on')).map((c) => c.searchParams.get('waiting_on'))).toEqual(['agent', 'outside_party', 'someone_else']);
    fireEvent.click(screen.getByRole('button', { name: 'See what you started' }));
    await until(() => expect(tabs()[1].getAttribute('aria-selected')).toBe('true'));
    await until(() => expect(rows()).toHaveLength(3));
  });

  it('While you\'re free shows the proposed suggestions when present; Not now hides one; absent means no panel', async () => {
    persona = 'pm';
    const suggestions = [
      { id: 'S-1', agent: 'tola', title: 'Draft the weekly report', detail: 'Due Friday', action: 'Draft it', href: '/assistant' },
      { id: 'S-2', agent: 'tola', title: 'Write up the call', detail: 'Notes added', action: 'Draft minutes', href: '/assistant' },
    ];
    work = (url) => {
      const { status, body } = fromMock(url, 'pm');
      return json(status, url.searchParams.get('queue') === 'needs_me' ? { ...body, suggestions } : body);
    };
    await open();
    const free = await screen.findByRole('complementary', { name: 'While you’re free' });
    expect(free.textContent).toContain('Tola can get these ready. You check each one before it goes anywhere.');
    expect(within(free).getByRole('img', { name: 'Tola · PMO agent' })).toBeTruthy();
    expect(within(free).getByRole('link', { name: 'Draft it' }).getAttribute('href')).toBe('/assistant');
    fireEvent.click(within(free).getAllByRole('button', { name: 'Not now' })[0]);
    expect(within(free).queryByText('Draft the weekly report')).toBeNull();
    expect(within(free).getByText('Write up the call')).toBeTruthy();
  });

  it('without suggestions there is no While you\'re free panel', async () => {
    persona = 'pm';
    await open();
    expect(screen.queryByRole('complementary', { name: /free/ })).toBeNull();
  });

  it('other empty queues say so', async () => {
    work = () => json(200, { items: [], as_of: '2026-11-10T09:42:00Z', counts: { needs_me: 0, waiting_on_others: 0, done: 0 } });
    await open('?queue=done');
    expect(screen.getByRole('heading', { name: 'Nothing done yet' })).toBeTruthy();
    expect(screen.queryByRole('button', { name: /waiting on others/ })).toBeNull();
  });

  it('pm unassigned: the queue is not open, with the API message and a way back', async () => {
    persona = 'pm';
    await open('?queue=unassigned');
    expect(screen.getByRole('heading', { name: 'This queue isn’t open to your role.' })).toBeTruthy();
    expect(screen.getByText('Only Leads can see unassigned work.')).toBeTruthy();
    expect(screen.getByRole('link', { name: 'Go to Needs me' }).getAttribute('href')).toBe('/my-work');
    expect(rows()).toHaveLength(0);
    expect(screen.getByRole('tablist')).toBeTruthy();
    expect(panel().getAttribute('aria-label')).toBe('Unassigned');
  });

  it.each([
    ['404', () => json(404, { code: 'invalid_query', message: 'We could not read that list request.' }), 'invalid_query'],
    ['500', () => new Response('<html></html>', { status: 500 }), 'unexpected_response'],
    ['network', () => Promise.reject(new TypeError('Failed to fetch')), 'network_error'],
  ])('%s shows the error card; Try again repeats the request and recovers', async (_, fail, code) => {
    work = fail as () => Promise<Response>;
    await open();
    await until(() => expect(screen.getByRole('alert')).toBeTruthy());
    const card = screen.getByRole('alert');
    expect(card.className).toBe('shell-errorcard');
    expect([...card.children].map((el) => el.textContent)).toEqual([
      'ERROR · COULDN’T LOAD',
      'We couldn’t load your queue. Your work is safe; nothing was changed.',
      `Reference ${code} for support.`,
      'Try again',
    ]);
    expect(screen.getByRole('tablist')).toBeTruthy();
    expect(screen.getByRole('search')).toBeTruthy();
    work = (url) => mockResponse(url);
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
    await until(() => expect(rows()).toHaveLength(20));
    expect(query(lastCall())).toEqual(query(calls[0]));
  });

  it('after an earlier load the error card says when it last loaded', async () => {
    await open();
    work = () => json(500, { code: 'server_error', message: 'x' });
    fireEvent.click(tabs()[2]);
    await until(() => expect(screen.getByRole('alert')).toBeTruthy());
    expect(screen.getByRole('alert').querySelector('.shell-reference')!.textContent).toBe('Last loaded 10:42. Reference server_error for support.');
  });

  it('401 shows the shell signed-out callout', async () => {
    work = () => json(401, { code: 'not_signed_in', message: 'Sign in to continue.' });
    await open();
    await until(() => expect(screen.getByText('You’re signed out.')).toBeTruthy());
    expect(screen.getByRole('link', { name: 'Sign in' }).getAttribute('href')).toBe('/accounts/login/?next=%2Fmy-work');
  });

  it('loading shows skeleton bars and status; a late response for an older view is ignored', async () => {
    const pending: Record<string, (r: Response) => void> = {};
    work = (url) => new Promise<Response>((resolve) => (pending[url.searchParams.get('queue')!] = () => resolve(mockResponse(url))));
    nav.set('');
    render(
      <AppShell>
        <MyWorkPage />
      </AppShell>,
    );
    await until(() => expect(pending.needs_me).toBeTruthy());
    expect(screen.getByRole('status').textContent).toBe('Loading your queue…');
    expect(document.querySelectorAll('.psl-panel.shell-loading .psl-skel')).toHaveLength(3);
    expect(tabs().map((t) => t.querySelector('.psl-badge')!.textContent)).toEqual(['–', '–', '–']);
    fireEvent.click(tabs()[2]);
    await until(() => expect(pending.done).toBeTruthy());
    await act(async () => pending.done(new Response()));
    await until(() => expect(rows()).toHaveLength(6));
    await act(async () => pending.needs_me(new Response()));
    await act(async () => {
      await new Promise((r) => realImmediate(r));
    });
    expect(rows()).toHaveLength(6);
    expect(tabs()[2].getAttribute('aria-selected')).toBe('true');
  });

  it('a page-1 reload drops the old rows and shows the skeleton', async () => {
    await open();
    let release!: () => void;
    work = (url) => new Promise<Response>((resolve) => (release = () => resolve(mockResponse(url))));
    fireEvent.click(tabs()[1]);
    await until(() => expect(screen.getByRole('status').textContent).toBe('Loading your queue…'));
    expect(rows()).toHaveLength(0);
    expect(tabs()[0].querySelector('.psl-badge')!.textContent).toBe('24');
    await act(async () => release());
    await until(() => expect(rows()).toHaveLength(12));
  });
});
