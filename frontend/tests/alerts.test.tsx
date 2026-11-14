// @vitest-environment jsdom
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { setImmediate as realImmediate } from 'node:timers';

import { act, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { NotificationsPage } from '@/features/alerts/NotificationsPage';
import { AppShell } from '@/shell/AppShell';

// @ts-expect-error plain ESM module without type declarations
import { createAlertsMock } from '../mock/alerts.mjs';

// next/navigation: the search params live in a small store that router.replace updates, like the app router.
const nav = vi.hoisted(() => {
  const listeners = new Set<() => void>();
  let params = new URLSearchParams();
  const set = (search: string) => {
    params = new URLSearchParams(search);
    window.history.replaceState(null, '', `/notifications${search}`);
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
    usePathname: () => '/notifications',
    useRouter: () => nav.router,
    useSearchParams: () => useSyncExternalStore(subscribe, nav.get),
  };
});

const fixtures = join(__dirname, '../mock');
const overlay = JSON.parse(readFileSync(join(fixtures, 'proposals/alerts.json'), 'utf8'));
const me = JSON.parse(readFileSync(join(fixtures, 'fixtures/me.finance_lead.json'), 'utf8'));
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });

type Call = { method: string; url: URL; csrf: string | null };
let mock: { handle: (args: object) => { status: number; body: unknown } };
let scenario: string;
let calls: Call[];
/** Per-test override: return a Response to replace the mock's answer, or undefined to use it. */
let hook: (call: Call) => Response | Promise<Response | undefined> | undefined;

function fromMock(call: Call) {
  const operationId = call.url.pathname.endsWith('/read') ? 'E-NOTIFICATION-READ' : 'E-NOTIFICATIONS';
  const r = mock.handle({ operationId, url: call.url, raw: '', persona: 'finance_lead', cookies: { psl_mock_alerts: scenario } });
  return json(r.status, r.body);
}

beforeEach(() => {
  mock = createAlertsMock({ overlay });
  scenario = 'board';
  calls = [];
  hook = () => undefined;
  nav.router.replace.mockClear();
  nav.router.push.mockClear();
  nav.set('');
  vi.stubGlobal(
    'fetch',
    vi.fn(async (request: Request) => {
      const url = new URL(request.url);
      if (url.pathname === '/api/v1/me') return json(200, me);
      const call = { method: request.method, url, csrf: request.headers.get('X-CSRFToken') };
      calls.push(call);
      return (await hook(call)) ?? fromMock(call);
    }),
  );
});
afterEach(() => {
  vi.unstubAllGlobals();
});

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

const rows = () => [...document.querySelectorAll('ul[aria-label="Alerts"] > li')];
const posts = () => calls.filter((c) => c.method === 'POST');
const lists = () => calls.filter((c) => c.method === 'GET');

async function open(search = '') {
  nav.set(search);
  const result = render(
    <AppShell>
      <NotificationsPage />
    </AppShell>,
  );
  await until(() => expect(screen.queryByRole('status')).toBeNull());
  return result;
}

describe('list (SCR-15-desktop)', () => {
  it('board: header, toolbar, count and four rows in order with avatars, meta lines and NEW', async () => {
    await open();
    const main = document.querySelector('main')!;
    expect(main.querySelector('.alerts-eyebrow')!.textContent).toBe('NOTIFICATIONS');
    expect(screen.getByRole('heading', { level: 1 }).textContent).toBe('Notifications');
    expect(screen.getByRole('link', { name: 'Alert settings' }).getAttribute('href')).toBe('/settings/alerts');
    expect(screen.getByRole('searchbox', { name: 'Search' }).getAttribute('placeholder')).toBe('Search notifications');
    const filter = screen.getByRole('button', { name: 'Filter' });
    expect([filter.getAttribute('aria-haspopup'), filter.getAttribute('aria-expanded')]).toEqual(['dialog', 'false']);
    expect(main.querySelector('.alerts-count')!.textContent).toBe('4 ALERTS');
    expect(screen.getByText(', 1 unread').className).toBe('alerts-sr');

    expect(rows().map((r) => [r.querySelector('.alerts-text')!.textContent, r.querySelector('.alerts-meta')!.textContent, r.querySelector('.psl-tag')?.lastChild?.textContent ?? ''])).toEqual([
      ['Invoice for Lagoon Health is waiting for your review', 'Chidi · WhatsApp and email · 10:42', 'NEW'],
      ['The UAT response for Lagoon Health is due tomorrow', 'Tola · Email · 09:00 daily digest', ''],
      ['October payroll has 2 problems for HR', 'Zainab · In app only (you are not HR)', ''],
      ['Milestone 1 invoice was verified', 'Chidi · In app · yesterday', ''],
    ]);
    expect(rows().map((r) => r.querySelector('img')!.getAttribute('src'))).toEqual(['/agents/chidi.png', '/agents/tola.png', '/agents/zainab.png', '/agents/chidi.png']);
    expect(rows().map((r) => r.querySelector('img')!.getAttribute('alt'))).toEqual(['', '', '', '']);
    expect(rows()[0].querySelector('.psl-avatar')!.className).toBe('psl-avatar psl-avatar--40 psl-avatar--chidi');
    expect(rows().map((r) => r.classList.contains('alerts-row--unread'))).toEqual([true, false, false, false]);
    expect(rows()[0].querySelector('.psl-tag')!.className).toContain('psl-tag--person');
    const links = rows().map((r) => r.querySelector('a')!);
    expect(links.map((a) => a.getAttribute('href'))).toEqual(['/work/W-1001', '/work/W-1002', '/work/W-1099', '/work/W-1006']);
    expect(links[0].textContent).toBe('Invoice for Lagoon Health is waiting for your review, Chidi · WhatsApp and email · 10:42, NEW');
    expect(links[1].textContent).toBe('The UAT response for Lagoon Health is due tomorrow, Tola · Email · 09:00 daily digest');
  });

  it('the first read sends no limit and no other parameter', async () => {
    await open();
    expect([...lists()[0].url.searchParams.keys()]).toEqual([]);
  });

  it('an unknown agent gets a neutral circle and its key as the name', async () => {
    hook = (call) => {
      if (call.method !== 'GET') return undefined;
      return json(200, { items: [{ id: 'N-9', work_id: 'W-1', agent: 'kemi', text: 'Hello', at: new Date().toISOString(), read: true }], as_of: new Date().toISOString(), total: 1 });
    };
    await open();
    expect(rows()[0].querySelector('.psl-avatar')!.className).toBe('psl-avatar psl-avatar--40');
    expect(rows()[0].querySelector('img')).toBeNull();
    expect(rows()[0].querySelector('.alerts-meta')!.textContent).toMatch(/^kemi · \d\d:\d\d$/);
    expect(document.querySelector('.alerts-count')!.textContent).toBe('1 ALERT');
    expect(screen.queryByText(/unread/)).toBeNull();
  });
});

describe('opening an alert', () => {
  it('an unread alert: one POST with X-CSRFToken, then /work/W-1001', async () => {
    await open();
    fireEvent.click(rows()[0].querySelector('a')!);
    fireEvent.click(rows()[0].querySelector('a')!);
    await until(() => expect(nav.router.push).toHaveBeenCalledWith('/work/W-1001'));
    expect(posts().map((c) => [c.url.pathname, c.csrf])).toEqual([['/api/v1/notifications/N-0001/read', 'mock-csrf-finance_lead']]);
  });

  for (const [label, failure] of [
    ['500', () => json(500, { code: 'server_error', message: 'Something broke.' })],
    ['a network error', () => Promise.reject(new TypeError('Failed to fetch'))],
  ] as const) {
    it(`mark-read failing with ${label} still navigates, sends one POST and keeps NEW`, async () => {
      hook = (call) => (call.method === 'POST' ? (failure() as Response | Promise<Response>) : undefined);
      const { unmount } = await open();
      fireEvent.click(rows()[0].querySelector('a')!);
      await until(() => expect(nav.router.push).toHaveBeenCalledWith('/work/W-1001'));
      expect(posts()).toHaveLength(1);
      expect(rows()[0].querySelector('.psl-tag')!.lastChild!.textContent).toBe('NEW');
      unmount();
      await open();
      expect(rows()[0].querySelector('.psl-tag')!.lastChild!.textContent).toBe('NEW');
      expect(posts()).toHaveLength(1);
    });
  }

  it('after a successful mark-read the list on return shows no NEW', async () => {
    const { unmount } = await open();
    fireEvent.click(rows()[0].querySelector('a')!);
    await until(() => expect(nav.router.push).toHaveBeenCalled());
    unmount();
    await open();
    expect(rows()[0].querySelector('.psl-tag')).toBeNull();
  });

  it('a read alert and a modifier-click on an unread one send no POST', async () => {
    await open();
    fireEvent.click(rows()[3].querySelector('a')!, { ctrlKey: true });
    fireEvent.click(rows()[0].querySelector('a')!, { metaKey: true });
    fireEvent.click(rows()[0].querySelector('a')!, { button: 1 });
    await until(() => expect(lists().length).toBeGreaterThan(0));
    expect(posts()).toEqual([]);
    expect(nav.router.push).not.toHaveBeenCalled();
  });
});

describe('search and Filter', () => {
  it('typing narrows by q (300 ms); the URL holds it; the requests carry only v7 parameters', async () => {
    await open();
    fireEvent.change(screen.getByRole('searchbox', { name: 'Search' }), { target: { value: 'payroll' } });
    await act(async () => {
      await new Promise((r) => setTimeout(r, 350));
    });
    await until(() => expect(window.location.search).toBe('?q=payroll'));
    await until(() => expect(rows()).toHaveLength(1));
    expect(document.querySelector('.alerts-count')!.textContent).toBe('1 ALERT');
    expect(Object.fromEntries(lists().at(-1)!.url.searchParams)).toEqual({ q: 'payroll' });
  });

  it('Filter: Agent Chidi and Unread only apply on Show results; the hint reads "1 unread"', async () => {
    await open();
    fireEvent.click(screen.getByRole('button', { name: 'Filter' }));
    const dialog = screen.getByRole('dialog', { name: 'Filter' });
    expect(within(dialog).getAllByRole('radio').map((r) => r.closest('label')!.textContent)).toEqual(['Any agent', 'Tola', 'Chidi', 'Zainab']);
    expect(within(dialog).getByRole('checkbox').closest('label')!.textContent).toBe('Unread only 1 unread');
    fireEvent.click(within(dialog).getByRole('radio', { name: 'Chidi' }));
    fireEvent.click(within(dialog).getByRole('button', { name: 'Show results' }));
    await until(() => expect(rows()).toHaveLength(2));
    expect(window.location.search).toBe('?agent=chidi');
    expect(screen.getByRole('button', { name: 'Filter · 1' })).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Filter · 1' }));
    fireEvent.click(within(screen.getByRole('dialog')).getByRole('checkbox'));
    fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Show results' }));
    await until(() => expect(rows()).toHaveLength(1));
    expect(Object.fromEntries(lists().at(-1)!.url.searchParams)).toEqual({ agent: 'chidi', unread: 'true' });
    expect(screen.getByRole('button', { name: 'Filter · 2' })).toBeTruthy();
  });

  it('Esc discards the draft', async () => {
    await open();
    fireEvent.click(screen.getByRole('button', { name: 'Filter' }));
    fireEvent.click(screen.getByRole('radio', { name: 'Tola' }));
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(screen.queryByRole('dialog')).toBeNull();
    expect(nav.router.replace).not.toHaveBeenCalled();
  });

  it('no results: "No alerts match" and "Clear search and filters" restores the list', async () => {
    await open('?q=zzz');
    expect(screen.getByRole('heading', { name: 'No alerts match' })).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Clear search and filters' }));
    await until(() => expect(rows()).toHaveLength(4));
    expect(window.location.search).toBe('');
  });
});

describe('states', () => {
  it('loading shows LoadingState and no rows', async () => {
    let release!: () => void;
    const gate = new Promise<void>((r) => (release = r));
    hook = async (call) => {
      await gate;
      return fromMock(call);
    };
    nav.set('');
    render(
      <AppShell>
        <NotificationsPage />
      </AppShell>,
    );
    await until(() => expect(calls.length).toBe(1));
    expect(screen.getByRole('status').textContent).toBe('Loading…');
    expect(rows()).toHaveLength(0);
    release();
    await until(() => expect(rows()).toHaveLength(4));
  });

  it('empty: "No alerts yet." with the settings link and "0 ALERTS"', async () => {
    scenario = 'empty';
    await open();
    expect(document.querySelector('.psl-empty h3')!.textContent).toBe('No alerts yet.');
    expect(screen.getByRole('link', { name: 'Alert settings' })).toBeTruthy();
    expect(document.querySelector('.alerts-count')!.textContent).toBe('0 ALERTS');
  });

  it('error: the card with its reference; Try again re-reads the same view', async () => {
    let fail = true;
    hook = () => (fail ? json(404, { code: 'not_found', message: 'We could not find that record.' }) : undefined);
    await open();
    const card = screen.getByRole('alert');
    expect(card.textContent).toBe(
      'ERROR · COULDN’T LOAD' + 'We couldn’t load your alerts. Your work is safe; nothing was changed.' + 'Reference not_found for support.' + 'Try again',
    );
    fail = false;
    fireEvent.click(within(card).getByRole('button', { name: 'Try again' }));
    await until(() => expect(rows()).toHaveLength(4));
  });

  it('a failure after a success says when the list was last loaded', async () => {
    await open();
    hook = () => Promise.reject(new TypeError('offline'));
    fireEvent.change(screen.getByRole('searchbox'), { target: { value: 'x' } });
    fireEvent.submit(screen.getByRole('search'));
    await until(() => expect(screen.getByRole('alert').textContent).toContain('Last loaded 11:00. Reference network_error for support.'));
  });

  it('many: Show more loads rows 21-25 and goes; a failed Show more keeps the 20 rows', async () => {
    scenario = 'many';
    await open();
    expect(rows()).toHaveLength(20);
    hook = () => json(500, { code: 'server_error', message: 'Broke.' });
    fireEvent.click(screen.getByRole('button', { name: 'Show more' }));
    await until(() => expect(screen.getByText('We couldn’t load more. Nothing was changed.')).toBeTruthy());
    expect(rows()).toHaveLength(20);
    hook = () => undefined;
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
    await until(() => expect(rows()).toHaveLength(25));
    expect(screen.queryByRole('button', { name: 'Show more' })).toBeNull();
    expect(lists().at(-1)!.url.searchParams.get('cursor')).toBe('o20');
  });

  it('401 shows the signed-out state with the current path and search as next', async () => {
    hook = () => json(401, { code: 'not_signed_in', message: 'Sign in to continue.' });
    await open('?q=pay');
    await until(() => expect(screen.getByRole('link', { name: 'Sign in' }).getAttribute('href')).toBe('/accounts/login/?next=%2Fnotifications%3Fq%3Dpay'));
  });
});

describe('absent proposal fields are never invented (bare)', () => {
  it('no search, Filter, count or unread text; meta is agent and time', async () => {
    scenario = 'bare';
    await open();
    expect(rows().map((r) => r.querySelector('.alerts-meta')!.textContent)).toEqual(['Chidi · 10:42', 'Tola · 08:30', 'Zainab · 08:10', 'Chidi · yesterday']);
    expect(screen.queryByRole('search')).toBeNull();
    expect(screen.queryByRole('button', { name: /Filter/ })).toBeNull();
    expect(document.body.textContent).not.toMatch(/ALERTS?|unread/);
    expect(rows()[0].querySelector('.psl-tag')!.lastChild!.textContent).toBe('NEW');
  });

  it('filters in the URL without total are dropped and the list is read once more', async () => {
    scenario = 'bare';
    await open('?q=pay&agent=chidi');
    await until(() => expect(rows()).toHaveLength(4));
    expect(nav.router.replace).toHaveBeenCalledWith('/notifications', { scroll: false });
    expect(lists().map((c) => c.url.search)).toEqual(['?q=pay&agent=chidi', '']);
  });
});
