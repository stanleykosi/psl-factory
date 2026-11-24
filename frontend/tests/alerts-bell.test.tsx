// @vitest-environment jsdom
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { AppShell } from '@/shell/AppShell';

import { ALERT_READ_EVENT } from '@/features/alerts/useAlertsFeed';

import { alert, body, settle, until } from './alerts-helpers';
import { isRoleDashboard, roleDashboard } from './bell-feed';

// @ts-expect-error plain ESM module without type declarations
import { createAlertsMock } from '../mock/alerts.mjs';

// The alert bell and its drawer (F-15, F-61) on the alerts mock (live 1.24.0 shapes), scenario board: six alerts, five
// unread, three needing the person (a1, a2, a5), a5 with only a django_url, a6 with no link at all.
const nav = vi.hoisted(() => ({ pathname: '/my-work', push: vi.fn() }));
vi.mock('next/navigation', () => ({
  usePathname: () => nav.pathname,
  useRouter: () => ({ push: nav.push, replace: vi.fn(), prefetch: vi.fn() }),
}));

const me = JSON.parse(readFileSync(join(__dirname, '../mock/fixtures/me.finance_lead.json'), 'utf8'));
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });

type Call = { method: string; url: URL; csrf: string | null; raw: string };
let mock: { handle: (args: object) => [number, unknown] };
let scenario: string;
let calls: Call[];
let meAnswer: () => Response | Promise<Response>;
/** Per-test override of the alerts answers; undefined uses the mock. */
let hook: (call: Call) => Response | Promise<Response | undefined> | undefined;

function fromMock(call: Call) {
  const [status, answer] = mock.handle({ method: call.method.toLowerCase(), url: call.url, raw: call.raw, persona: 'finance_lead', cookies: { psl_mock_alerts: scenario } });
  return json(status, answer);
}

beforeEach(() => {
  mock = createAlertsMock();
  scenario = 'board';
  calls = [];
  hook = () => undefined;
  meAnswer = () => json(200, me);
  nav.pathname = '/my-work';
  nav.push.mockClear();
  vi.stubGlobal(
    'fetch',
    vi.fn(async (request: Request) => {
      const url = new URL(request.url);
      if (url.pathname === '/api/v1/me') return meAnswer();
      // The frame's own reads beside /me (F-57), not the alerts': answered here so `calls` holds only the alerts' requests.
      if (isRoleDashboard(request)) return roleDashboard();
      if (url.pathname === '/api/v1/session') return json(200, { csrf_token: 't', signed_in: false, next_url: '/' });
      const call = { method: request.method, url, csrf: request.headers.get('X-CSRFToken'), raw: request.method === 'POST' ? await request.text() : '' };
      calls.push(call);
      return (await hook(call)) ?? fromMock(call);
    }),
  );
});
afterEach(() => {
  vi.unstubAllGlobals();
});


const lists = () => calls.filter((c) => c.method === 'GET');
const posts = () => calls.filter((c) => c.method === 'POST');
const topBar = () => document.querySelector('nav.psl-nav') as HTMLElement;
const phoneBar = () => document.querySelector('header.psl-phonebar') as HTMLElement;
const bell = () => within(topBar()).getByRole('button', { name: /^Alerts/ });
const badge = () => bell().querySelector('.shell-bellbadge')?.textContent ?? null;
const chip = () => topBar().querySelector('.shell-bellchip')?.textContent ?? null;
const dialog = () => screen.queryByRole('dialog', { name: 'Alerts' });
const groupHeads = () => [...dialog()!.querySelectorAll('h3')].map((h) => h.textContent);
const openLinks = () => within(dialog()!).queryAllByRole('link', { name: /^Open:/ });

function Page() {
  return <h1 className="shell-title">My work</h1>;
}

async function mount() {
  const view = render(
    <AppShell>
      <Page />
    </AppShell>,
  );
  await until(() => expect(screen.queryByRole('heading', { level: 1, name: 'My work' })).toBeTruthy());
  await until(() => expect(lists().length).toBeGreaterThan(0));
  await settle();
  return view;
}

async function openDrawer(button = bell()) {
  fireEvent.click(button);
  await until(() => expect(dialog()).toBeTruthy());
  await settle();
}

const PROJECT = '/projects/6c2f1d3e-1a4b-4b8e-9d0a-0a1b2c3d4e5f';

/** Page 1 from `items`, with a server-side unread total (the whole inbox, not the loaded rows). */
const serve = (items: ReturnType<typeof alert>[], patch: Record<string, unknown> = {}) => {
  hook = (c) => (c.method === 'GET' ? json(200, body(items, patch)) : undefined);
};

describe('the bell in the top bar', () => {
  it('board: badge 5, chip "3 need you", name "Alerts, 5 unread, 3 need you", left of the name and before Start work', async () => {
    await mount();
    expect(bell().getAttribute('aria-label')).toBe('Alerts, 5 unread, 3 need you');
    expect([bell().getAttribute('aria-haspopup'), bell().getAttribute('aria-expanded'), bell().getAttribute('aria-controls')]).toEqual(['dialog', 'false', 'alerts-drawer']);
    expect(badge()).toBe('5');
    expect(chip()).toBe('3 need you');
    const order = [...topBar().querySelector('.psl-nav__in')!.children].map((el) => el.className);
    expect(order).toEqual(['psl-brand', 'psl-nav__links', 'shell-bellwrap', 'psl-nav__who', 'shell-navend']);
    const focusable = [...topBar().querySelectorAll('a, button')].map((el) => el.getAttribute('aria-label') ?? el.textContent);
    expect(focusable.at(-4)).toBe('Alerts, 5 unread, 3 need you');
    expect(focusable.at(-3)).toMatch(/^Account menu: /);
    expect(focusable.slice(-2)).toEqual(['Start work', 'More ways to start']);
    expect(lists()).toHaveLength(1);
    expect([...lists()[0].url.searchParams.keys()]).toEqual([]);
  });

  it('the badge is the server total, not the loaded rows: 60 unread with 40 loaded reads 60', async () => {
    serve(Array.from({ length: 40 }, (_, i) => alert({ n: i + 1 })), { unread: 60 });
    await mount();
    expect(badge()).toBe('60');
    expect(bell().getAttribute('aria-label')).toBe('Alerts, 60 unread');
  });

  it('unread 0 hides the badge; above 99 it reads 99+; the name keeps the number', async () => {
    serve([alert({ n: 1, read: true })], { unread: 0 });
    const view = await mount();
    expect(badge()).toBeNull();
    expect(bell().getAttribute('aria-label')).toBe('Alerts');
    view.unmount();
    serve([alert({ n: 1, group: 'action' })], { unread: 120 });
    await mount();
    expect(badge()).toBe('99+');
    expect(bell().getAttribute('aria-label')).toBe('Alerts, 120 unread, 1 need you');
  });

  it('every needs-you alert read: no chip, and Needs you still lists them with the count', async () => {
    serve([alert({ n: 1, group: 'action', read: true }), alert({ n: 2, group: 'action', read: true }), alert({ n: 3 })]);
    await mount();
    expect(chip()).toBeNull();
    expect(bell().getAttribute('aria-label')).toBe('Alerts, 1 unread');
    await openDrawer();
    expect(groupHeads()).toEqual(['Needs you, 2', 'For information, 1']);
  });

  it('before the first load, and after a failed one, there is no badge (unknown is not zero)', async () => {
    hook = () => new Promise<Response>(() => {});
    const view = render(
      <AppShell>
        <Page />
      </AppShell>,
    );
    await until(() => expect(lists()).toHaveLength(1));
    expect(badge()).toBeNull();
    expect(bell().getAttribute('aria-label')).toBe('Alerts');
    view.unmount();
    hook = () => json(500, { code: 'server_error', message: 'Down.' });
    await mount();
    expect(badge()).toBeNull();
    expect(chip()).toBeNull();
    expect(bell().getAttribute('aria-label')).toBe('Alerts');
  });

  it('a body without an items array or an unread number is a failed load, not "no alerts"', async () => {
    hook = (c) => (c.method === 'GET' ? json(200, { as_of: '2026-11-23T10:42:00Z', page: 1, next_page: null, unread: 0 }) : undefined);
    await mount();
    await openDrawer();
    expect(dialog()!.textContent).toContain('We couldn’t load your alerts.');
    expect(dialog()!.textContent).not.toContain('No alerts');
    expect(badge()).toBeNull();
  });

  it('a mark-read made on the Notifications page lowers the badge by one, once', async () => {
    await mount();
    act(() => {
      window.dispatchEvent(new CustomEvent(ALERT_READ_EVENT, { detail: 'a1'.padEnd(64, '0') }));
      window.dispatchEvent(new CustomEvent(ALERT_READ_EVENT, { detail: 'a1'.padEnd(64, '0') }));
    });
    expect(badge()).toBe('4');
    expect(chip()).toBe('2 need you');
  });

  for (const [label, answer] of [
    ['loading', () => new Promise<Response>(() => {})],
    ['signed out', () => json(401, { code: 'unauthenticated', message: 'Sign in.' })],
    ['errored', () => json(500, { code: 'server_error', message: 'Down.' })],
    ['without sections', () => json(200, { ...me, destinations: [] })],
  ] as const) {
    it(`/me ${label}: no bell and no notifications request`, async () => {
      meAnswer = answer;
      render(
        <AppShell>
          <Page />
        </AppShell>,
      );
      await settle();
      await settle();
      expect(screen.queryByRole('button', { name: /^Alerts/ })).toBeNull();
      expect(calls).toHaveLength(0);
    });
  }
});

describe('the drawer', () => {
  it('summary, groups, rows, as-of line and footer in order; Open is the only action, filled in Needs you; no NEW tag', async () => {
    await mount();
    await openDrawer();
    expect(bell().getAttribute('aria-expanded')).toBe('true');
    expect(bell().className).toContain('is-open');
    const d = dialog()!;
    expect(d.getAttribute('aria-modal')).toBe('true');
    expect(groupHeads()).toEqual(['Needs you, 3', 'For information, 3']);
    expect(d.querySelector('.alerts-grp--need')!.textContent).toBe('Needs you, 3');
    expect(d.querySelector('.alerts-summary')!.textContent).toMatch(/^Today, \d{1,2} [A-Z][a-z]{2}: 3 need you, \d+ new updates?, \d+ older unread\.$/);
    expect(d.querySelector('.alerts-asof')!.textContent).toMatch(/^As of \d\d:\d\d WAT$/);
    const rows = [...d.querySelectorAll('li')];
    expect(rows.map((r) => r.querySelector('.alerts-text')!.textContent)).toEqual([
      'Invoice ready for review',
      'Project plan to sign off',
      'Invoice review',
      'Assistant reply',
      'Milestone 2 is complete',
      'Reminder: month-end close',
    ]);
    expect(rows[0].querySelector('.alerts-sub')!.textContent).toBe('Lagoon Health · INV-LH-002');
    expect(rows[0].querySelector('.alerts-meta')!.textContent).toMatch(/^Chidi · /);
    // a5 and a6 have neither agent nor time: no meta line, a neutral avatar
    expect(rows[2].querySelector('.alerts-meta')).toBeNull();
    expect(rows[5].querySelector('.alerts-meta')).toBeNull();
    expect(rows[2].querySelector('.psl-avatar')!.textContent).toBe('');
    expect(rows.map((r) => r.classList.contains('alerts-row--unread'))).toEqual([true, true, true, true, false, true]);
    expect(d.querySelector('.psl-tag')).toBeNull();
    expect(d.textContent).not.toContain('NEW');
    const opens = openLinks();
    expect(opens.map((a) => a.getAttribute('href'))).toEqual(['/work/4103', '/work/4102', '/work/4105', '/assistant/7', PROJECT]);
    expect(opens[0].getAttribute('aria-label')).toBe('Open: Invoice ready for review');
    expect(opens.map((a) => !a.classList.contains('psl-btn--secondary'))).toEqual([true, true, true, false, false]);
    // the row with no link has Mark as read instead of Open
    expect(within(rows[5] as HTMLElement).getByRole('button', { name: /^Mark as read/ })).toBeTruthy();
    expect(rows.map((r) => r.querySelectorAll('a, button').length)).toEqual([1, 1, 1, 1, 1, 1]);
    expect(document.querySelector('a[href*="/accounts/"], a[href^="http"], a[href^="//"]')).toBeNull();
    const foot = [...d.querySelectorAll('.psl-drawer__foot a')].map((a) => [a.textContent, a.getAttribute('href')]);
    expect(foot).toEqual([
      ['See all alerts (5 unread)', '/notifications'],
      ['Alert settings', '/settings/alerts'],
    ]);
    // The shared Drawer takes focus on the panel itself when it holds no field (the trap starts there).
    await waitFor(() => expect(document.activeElement).toBe(d));
    expect(document.querySelector('main')!.hasAttribute('inert')).toBe(true);
  });

  it('Escape, Close and the scrim close it and focus goes back to the bell', async () => {
    await mount();
    for (const close of [
      // Escape is pressed where focus is, as a keyboard user does
      () => fireEvent.keyDown(document.activeElement!, { key: 'Escape' }),
      () => fireEvent.click(within(dialog()!).getByRole('button', { name: 'Close' })),
      () => fireEvent.click(document.querySelector('.psl-scrim')!),
    ]) {
      await openDrawer();
      close();
      await until(() => expect(dialog()).toBeNull());
      await waitFor(() => expect(document.activeElement).toBe(bell()));
      expect(bell().getAttribute('aria-expanded')).toBe('false');
      expect(document.querySelector('main')!.hasAttribute('inert')).toBe(false);
    }
  });

  it('Tab and Shift+Tab stay inside: Close, five Open links, Mark as read, See all alerts, Alert settings', async () => {
    await mount();
    await openDrawer();
    const d = dialog()!;
    const close = within(d).getByRole('button', { name: 'Close' });
    const settings = within(d).getByRole('link', { name: 'Alert settings' });
    settings.focus();
    fireEvent.keyDown(settings, { key: 'Tab' });
    await waitFor(() => expect(document.activeElement).toBe(close));
    fireEvent.keyDown(close, { key: 'Tab', shiftKey: true });
    await waitFor(() => expect(document.activeElement).toBe(settings));
    expect([...d.querySelectorAll('a[href], button')]).toHaveLength(9);
  });

  it('a page load reads once and each opening once more; marking read does not re-read', async () => {
    await mount();
    expect(lists()).toHaveLength(1);
    await openDrawer();
    expect(lists()).toHaveLength(2);
    fireEvent.click(openLinks()[0], { button: 0 });
    await until(() => expect(nav.push).toHaveBeenCalledWith('/work/4103'));
    expect(lists()).toHaveLength(2);
  });

  it('opening twice quickly leaves one request in flight', async () => {
    await mount();
    let release!: () => void;
    const gate = new Promise<void>((r) => (release = r));
    hook = async () => {
      await gate;
      return undefined;
    };
    await openDrawer();
    fireEvent.keyDown(dialog()!, { key: 'Escape' });
    await until(() => expect(dialog()).toBeNull());
    await openDrawer();
    expect(lists()).toHaveLength(2);
    release();
    await settle();
    expect(lists()).toHaveLength(2);
  });
});

describe('Open and mark read', () => {
  it('an unread alert: one POST of {} with the CSRF token, then its work; the drawer closes; badge 4 and chip "2 need you" only after the 200', async () => {
    await mount();
    await openDrawer();
    let release!: () => void;
    const gate = new Promise<void>((r) => (release = r));
    hook = async (c) => {
      if (c.method === 'POST') await gate;
      return undefined;
    };
    const open = openLinks()[0];
    fireEvent.click(open, { button: 0 });
    fireEvent.click(open, { button: 0 });
    await settle();
    expect(badge()).toBe('5');
    expect(nav.push).not.toHaveBeenCalled();
    release();
    await until(() => expect(nav.push).toHaveBeenCalledWith('/work/4103'));
    expect(posts().map((c) => [c.url.pathname, c.csrf, c.raw])).toEqual([[`/api/v1/notifications/${'a1'.padEnd(64, '0')}/read`, 'mock-csrf-finance_lead', '{}']]);
    expect(dialog()).toBeNull();
    expect(badge()).toBe('4');
    expect(chip()).toBe('2 need you');
    expect(bell().getAttribute('aria-label')).toBe('Alerts, 4 unread, 2 need you');
  });

  it('a read alert sends no POST', async () => {
    await mount();
    await openDrawer();
    fireEvent.click(openLinks()[4], { button: 0 });
    await settle();
    expect(posts()).toHaveLength(0);
    expect(dialog()).toBeNull();
  });

  it('a 500 leaves the row unread and the badge as it was, says so, and still goes to the work', async () => {
    hook = (c) => (c.method === 'POST' ? json(500, { code: 'server_error', message: 'Down.' }) : undefined);
    await mount();
    await openDrawer();
    fireEvent.click(openLinks()[0], { button: 0 });
    await until(() => expect(nav.push).toHaveBeenCalledWith('/work/4103'));
    expect(posts()).toHaveLength(1);
    expect(badge()).toBe('5');
    expect(within(dialog()!).getByText('Couldn’t mark as read. Try again.')).toBeTruthy();
    expect(dialog()!.querySelector('li')!.classList.contains('alerts-row--unread')).toBe(true);
  });

  for (const status of [403, 404]) {
    it(`a ${status} says "no longer available", reads the list again and does not open the work`, async () => {
      hook = (c) => (c.method === 'POST' ? json(status, { code: 'not_found', message: 'Gone.' }) : undefined);
      await mount();
      await openDrawer();
      fireEvent.click(openLinks()[0], { button: 0 });
      await until(() => expect(lists()).toHaveLength(3));
      expect(nav.push).not.toHaveBeenCalled();
      expect(badge()).toBe('5');
    });
  }

  it('Mark as read on a row with no link marks it in place and the badge drops by one', async () => {
    await mount();
    await openDrawer();
    const row = dialog()!.querySelectorAll('li')[5] as HTMLElement;
    fireEvent.click(within(row).getByRole('button', { name: /^Mark as read/ }));
    await until(() => expect(badge()).toBe('4'));
    expect(row.classList.contains('alerts-row--unread')).toBe(false);
    expect(within(row).queryByRole('button', { name: /^Mark as read/ })).toBeNull();
    expect(nav.push).not.toHaveBeenCalled();
    expect(posts()).toHaveLength(1);
  });

  it('a list that was read before the mark-read and arrives after it does not bring the alert back as unread', async () => {
    await mount();
    let release!: () => void;
    const gate = new Promise<void>((r) => (release = r));
    hook = async (c) => {
      if (c.method !== 'GET') return undefined;
      const stale = fromMock(c);
      await gate;
      return stale;
    };
    await openDrawer();
    fireEvent.click(openLinks()[0], { button: 0 });
    await until(() => expect(nav.push).toHaveBeenCalledWith('/work/4103'));
    expect(badge()).toBe('4');
    release();
    await settle();
    await settle();
    expect(badge()).toBe('4');
    expect(chip()).toBe('2 need you');
  });

  it('a 401 on the mark-read stops further reads and shows the signed-out state', async () => {
    hook = (c) => (c.method === 'POST' ? json(401, { code: 'unauthenticated', message: 'Sign in.' }) : undefined);
    await mount();
    await openDrawer();
    fireEvent.click(openLinks()[0], { button: 0 });
    await until(() => expect(dialog()!.textContent).toContain('You’re signed out.'));
    expect(lists()).toHaveLength(2);
    await act(async () => fireEvent.click(bell()));
    await settle();
    expect(lists()).toHaveLength(2);
  });

  for (const [label, init] of [
    ['Ctrl', { button: 0, ctrlKey: true }],
    ['Cmd', { button: 0, metaKey: true }],
    ['Shift', { button: 0, shiftKey: true }],
    ['middle', { button: 1 }],
  ] as const) {
    it(`${label} click is a normal link: no POST, no push, the drawer stays`, async () => {
      await mount();
      await openDrawer();
      const event = fireEvent.click(openLinks()[0], init);
      await settle();
      expect(event).toBe(true);
      expect(posts()).toHaveLength(0);
      expect(nav.push).not.toHaveBeenCalled();
      expect(dialog()).toBeTruthy();
    });
  }
});

describe('states', () => {
  it('loading: the skeleton with "Loading…" and no badge', async () => {
    hook = () => new Promise<Response>(() => {});
    render(
      <AppShell>
        <Page />
      </AppShell>,
    );
    await until(() => expect(lists()).toHaveLength(1));
    expect(badge()).toBeNull();
    await openDrawer();
    expect(within(dialog()!).getByRole('status').textContent).toBe('Loading…');
    expect(lists()).toHaveLength(1);
  });

  it('empty groups say so under their headers', async () => {
    serve([alert({ n: 1 }), alert({ n: 2 })]);
    await mount();
    await openDrawer();
    expect(groupHeads()).toEqual(['Needs you, 0', 'For information, 2']);
    expect(dialog()!.querySelector('.alerts-grp--need')!.closest('section')!.textContent).toContain('Nothing needs you right now.');
    fireEvent.keyDown(dialog()!, { key: 'Escape' });

    serve([alert({ n: 3, group: 'action' })]);
    await openDrawer();
    await until(() => expect(groupHeads()).toEqual(['Needs you, 1', 'For information, 0']));
    expect(dialog()!.textContent).toContain('No other alerts.');
  });

  it('no alerts: "No alerts" with the summary, the footer links and no badge', async () => {
    scenario = 'empty';
    await mount();
    expect(badge()).toBeNull();
    await openDrawer();
    expect(dialog()!.textContent).toContain('No alerts');
    expect(groupHeads()).toEqual([]);
    expect(dialog()!.querySelector('.alerts-summary')!.textContent).toMatch(/^Today, \d{1,2} [A-Z][a-z]{2}: 0 need you, 0 new updates, 0 older unread\.$/);
    expect(within(dialog()!).getByRole('link', { name: /^See all alerts/ })).toBeTruthy();
  });

  it('a 500: the error card, then Try again reads once and shows the list', async () => {
    hook = () => json(500, { code: 'server_error', message: 'Down.' });
    await mount();
    await openDrawer();
    const card = within(dialog()!).getByRole('alert');
    expect(card.textContent).toContain('We couldn’t load your alerts. Your work is safe; nothing was changed.');
    expect(card.textContent).toContain('Reference server_error for support.');
    hook = () => undefined;
    const before = lists().length;
    fireEvent.click(within(dialog()!).getByRole('button', { name: 'Try again' }));
    await until(() => expect(openLinks()).toHaveLength(5));
    expect(lists()).toHaveLength(before + 1);
    expect(badge()).toBe('5');
  });

  it('a 401: signed out with Sign in back to this page, and no more requests', async () => {
    hook = () => json(401, { code: 'unauthenticated', message: 'Sign in.' });
    await mount();
    await openDrawer();
    expect(dialog()!.textContent).toContain('You’re signed out.');
    expect(within(dialog()!).getByRole('link', { name: 'Sign in' }).getAttribute('href')).toBe('/sign-in?next=%2Fmy-work');
    fireEvent.keyDown(dialog()!, { key: 'Escape' });
    await openDrawer();
    expect(lists()).toHaveLength(1);
    expect(badge()).toBeNull();
  });

  it('a 403: "Your account can’t use PSL Factory." with the server message', async () => {
    hook = () => json(403, { code: 'forbidden', message: 'Ask an Admin.' });
    await mount();
    await openDrawer();
    expect(dialog()!.textContent).toContain('Your account can’t use PSL Factory. Ask an Admin.');
  });

  it('alert text is plain text and never moves an alert between groups', async () => {
    serve([alert({ n: 1, group: 'update', title: '<b>needs you</b>', subject: '<i>x</i>' }), alert({ n: 2, group: 'action' })]);
    await mount();
    await openDrawer();
    const info = dialog()!.querySelector('#alerts-grp-info')!.closest('section')!;
    expect(info.querySelector('.alerts-text')!.textContent).toBe('<b>needs you</b>');
    expect(info.querySelector('b, i')).toBeNull();
    expect(groupHeads()).toEqual(['Needs you, 1', 'For information, 1']);
  });

  it('a hostile link is not a link: the row has no Open control', async () => {
    serve([alert({ n: 1, api_url: '//evil.example/x', django_url: 'javascript:alert(1)' })]);
    await mount();
    await openDrawer();
    expect(openLinks()).toHaveLength(0);
    expect(dialog()!.querySelector('a[href*="evil"], a[href^="javascript"]')).toBeNull();
  });
});

describe('phone (below 720px)', () => {
  beforeEach(() => {
    vi.stubGlobal('matchMedia', (q: string) => ({ matches: q.includes('max-width'), media: q, addEventListener: () => {}, removeEventListener: () => {} }));
  });
  const phoneBell = () => within(document.querySelector('.shell-phone') as HTMLElement).getByRole('button', { name: /^Alerts/ });

  it('Menu, PSL FACTORY, bell, then + Start; same name; no chip', async () => {
    await mount();
    expect(phoneBell().getAttribute('aria-label')).toBe('Alerts, 5 unread, 3 need you');
    expect(document.querySelector('.shell-phone .shell-bellchip')).toBeNull();
    expect(phoneBar().textContent).toContain('PSL FACTORY');
    const order = [...document.querySelectorAll('.shell-phone button')].map((b) => b.getAttribute('aria-label'));
    expect(order).toEqual(['Menu', 'Alerts, 5 unread, 3 need you', 'Start work']);
  });

  it('the sheet opens on Needs you; arrows and clicks switch tabs; Escape returns focus to the phone bell', async () => {
    await mount();
    await openDrawer(phoneBell());
    const d = dialog()!;
    expect(d.querySelector('.psl-sheet__grab')).toBeTruthy();
    const tabs = within(d).getAllByRole('tab');
    expect(tabs.map((t) => [t.textContent, t.getAttribute('aria-selected')])).toEqual([
      ['Needs you 3', 'true'],
      ['For information', 'false'],
    ]);
    expect(openLinks().map((a) => a.getAttribute('href'))).toEqual(['/work/4103', '/work/4102', '/work/4105']);
    expect(groupHeads()).toEqual([]);
    fireEvent.keyDown(tabs[0], { key: 'ArrowRight' });
    // The shared Tabs move focus with the arrows; choosing is a click or Enter.
    await waitFor(() => expect(document.activeElement).toBe(within(d).getByRole('tab', { name: 'For information' })));
    fireEvent.click(document.activeElement!);
    expect(openLinks().map((a) => a.getAttribute('href'))).toEqual(['/assistant/7', PROJECT]);
    fireEvent.click(within(d).getByRole('tab', { name: /^Needs you/ }));
    expect(openLinks()).toHaveLength(3);
    fireEvent.keyDown(dialog()!, { key: 'Escape' });
    await until(() => expect(dialog()).toBeNull());
    await waitFor(() => expect(document.activeElement).toBe(phoneBell()));
  });

  /** The phone bar remounts on a route change (key={pathname}): the page changes and the bell there takes focus. */
  async function goTo(view: Awaited<ReturnType<typeof mount>>, path: string) {
    nav.pathname = path;
    view.rerender(
      <AppShell>
        <Page />
      </AppShell>,
    );
    await until(() => expect(dialog()).toBeNull());
  }

  it('Open on an alert: the phone bar remounts and focus lands on the new bell', async () => {
    const view = await mount();
    const before = phoneBell();
    await openDrawer(before);
    fireEvent.click(openLinks()[0], { button: 0 });
    await until(() => expect(nav.push).toHaveBeenCalledWith('/work/4103'));
    await goTo(view, '/work/4103');
    expect(before.isConnected).toBe(false);
    await waitFor(() => expect(document.activeElement).toBe(phoneBell()));
  });

  it('Alert settings and See all alerts: focus lands on the new phone bell', async () => {
    for (const [name, path] of [
      [/^Alert settings/, '/settings/alerts'],
      [/^See all alerts/, '/notifications'],
    ] as const) {
      nav.pathname = '/my-work';
      const view = await mount();
      await openDrawer(phoneBell());
      fireEvent.click(within(dialog()!).getByRole('link', { name }), { button: 0 });
      await goTo(view, path);
      await waitFor(() => expect(document.activeElement).toBe(phoneBell()));
      view.unmount();
    }
  });

  it('a link to the page already shown closes the drawer and does not claim focus for a later navigation', async () => {
    nav.pathname = '/notifications';
    const view = await mount();
    await openDrawer(phoneBell());
    fireEvent.click(within(dialog()!).getByRole('link', { name: /^See all alerts/ }), { button: 0 });
    await until(() => expect(dialog()).toBeNull());
    await waitFor(() => expect(document.activeElement).toBe(phoneBell()));
    (document.activeElement as HTMLElement).blur();
    await goTo(view, '/my-work');
    await waitFor(() => expect(document.activeElement).not.toBe(phoneBell()));
  });

  it('with no needs-you alert the Needs you tab is empty and For information is one tap away', async () => {
    serve([alert({ n: 1 }), alert({ n: 2 })]);
    await mount();
    await openDrawer(phoneBell());
    const tabs = within(dialog()!).getAllByRole('tab');
    expect(tabs.map((t) => [t.textContent, t.getAttribute('aria-selected')])).toEqual([
      ['Needs you', 'false'],
      ['For information', 'true'],
    ]);
    expect(openLinks()).toHaveLength(2);
  });
});
