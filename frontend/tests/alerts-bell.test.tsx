// @vitest-environment jsdom
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { setImmediate as realImmediate } from 'node:timers';

import { act, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { AppShell } from '@/shell/AppShell';

// @ts-expect-error plain ESM module without type declarations
import { createAlertsMock } from '../mock/alerts.mjs';
// @ts-expect-error plain ESM module without type declarations
import { OPENAPI_PATH } from '../mock/server.mjs';

// The alert bell and its drawer (F-15) on the alerts mock: scenario needs-you (PROPOSAL needs_you) and board.
const nav = vi.hoisted(() => ({ pathname: '/my-work', push: vi.fn() }));
vi.mock('next/navigation', () => ({
  usePathname: () => nav.pathname,
  useRouter: () => ({ push: nav.push, replace: vi.fn(), prefetch: vi.fn() }),
}));

const openapi = JSON.parse(readFileSync(OPENAPI_PATH, 'utf8'));
const me = JSON.parse(readFileSync(join(__dirname, '../mock/fixtures/me.finance_lead.json'), 'utf8'));
const proposal = () => {
  const list = JSON.parse(readFileSync(join(__dirname, '../mock/proposals/alerts-needs-you.json'), 'utf8'));
  delete list.$comment;
  return list as { items: Record<string, unknown>[]; as_of: string; unread_count?: number };
};
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });

type Call = { method: string; url: URL; csrf: string | null };
let mock: { handle: (args: object) => { status: number; body: unknown } };
let scenario: string;
let calls: Call[];
let meAnswer: () => Response | Promise<Response>;
/** Per-test override of the alerts answers; undefined uses the mock. */
let hook: (call: Call) => Response | Promise<Response | undefined> | undefined;

function fromMock(call: Call) {
  const operationId = call.url.pathname.endsWith('/read') ? 'E-NOTIFICATION-READ' : 'E-NOTIFICATIONS';
  const r = mock.handle({ operationId, url: call.url, raw: '', persona: 'finance_lead', cookies: { psl_mock_alerts: scenario } });
  return json(r.status, r.body);
}

beforeEach(() => {
  mock = createAlertsMock({ openapi });
  scenario = 'needs-you';
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
const settle = () =>
  act(async () => {
    await new Promise((r) => realImmediate(r));
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

describe('the bell in the top bar', () => {
  it('needs-you: badge 4, chip "3 need you", name "Alerts, 4 unread, 3 need you", left of the name and before Start work', async () => {
    await mount();
    expect(bell().getAttribute('aria-label')).toBe('Alerts, 4 unread, 3 need you');
    expect([bell().getAttribute('aria-haspopup'), bell().getAttribute('aria-expanded'), bell().getAttribute('aria-controls')]).toEqual(['dialog', 'false', 'alerts-drawer']);
    expect(badge()).toBe('4');
    expect(chip()).toBe('3 need you');
    const order = [...topBar().querySelector('.psl-nav__in')!.children].map((el) => el.className);
    expect(order).toEqual(['psl-brand', 'psl-nav__links', 'shell-bellwrap', 'psl-nav__who', 'shell-navend']);
    const focusable = [...topBar().querySelectorAll('a, button')].map((el) => el.getAttribute('aria-label') ?? el.textContent);
    expect(focusable.at(-3)).toBe('Alerts, 4 unread, 3 need you');
    expect(focusable.slice(-2)).toEqual(['Start work', 'More ways to start']);
    expect(lists()).toHaveLength(1);
    expect([...lists()[0].url.searchParams.keys()]).toEqual([]);
  });

  it('board (no needs_you anywhere): "Alerts, 1 unread", no chip, only For your information', async () => {
    scenario = 'board';
    await mount();
    expect(bell().getAttribute('aria-label')).toBe('Alerts, 1 unread');
    expect(badge()).toBe('1');
    expect(chip()).toBeNull();
    await openDrawer();
    expect(groupHeads()).toEqual(['For your information, 4']);
    expect(screen.queryByRole('tab')).toBeNull();
  });

  it('every needs-you alert read: no chip, and Needs you still lists its three rows with the count', async () => {
    const list = proposal();
    list.items.forEach((item) => (item.read = item.needs_you === true ? true : item.read));
    list.unread_count = 1;
    hook = (c) => (c.method === 'GET' ? json(200, list) : undefined);
    await mount();
    expect(chip()).toBeNull();
    expect(bell().getAttribute('aria-label')).toBe('Alerts, 1 unread');
    await openDrawer();
    expect(groupHeads()).toEqual(['Needs you, 3', 'For your information, 3']);
  });

  it('no unread_count: no badge (not 0) and the name is "Alerts, 3 need you"', async () => {
    const list = proposal();
    delete list.unread_count;
    hook = (c) => (c.method === 'GET' ? json(200, list) : undefined);
    await mount();
    expect(badge()).toBeNull();
    expect(bell().getAttribute('aria-label')).toBe('Alerts, 3 need you');
  });

  it('above 99 unread the badge reads 99+', async () => {
    hook = (c) => (c.method === 'GET' ? json(200, { ...proposal(), unread_count: 120 }) : undefined);
    await mount();
    expect(badge()).toBe('99+');
    expect(bell().getAttribute('aria-label')).toBe('Alerts, 120 unread, 3 need you');
  });

  it('a failed list: no badge, no chip, name "Alerts"', async () => {
    hook = () => json(500, { code: 'server_error', message: 'Down.' });
    await mount();
    expect(badge()).toBeNull();
    expect(chip()).toBeNull();
    expect(bell().getAttribute('aria-label')).toBe('Alerts');
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
  it('groups, rows and footer in order; Open is the only action, filled in Needs you; no NEW tag', async () => {
    await mount();
    await openDrawer();
    expect(bell().getAttribute('aria-expanded')).toBe('true');
    expect(bell().className).toContain('is-open');
    const d = dialog()!;
    expect(d.getAttribute('aria-modal')).toBe('true');
    expect(groupHeads()).toEqual(['Needs you, 3', 'For your information, 3']);
    expect(d.querySelector('.alerts-grp--need')!.textContent).toBe('Needs you, 3');
    const rows = [...d.querySelectorAll('li')];
    expect(rows.map((r) => r.querySelector('.alerts-text')!.textContent)).toEqual([
      'Invoice for Lagoon Health is waiting for your review',
      'The project plan for Kestrel Logistics needs your sign-off',
      'October payroll has 2 problems for HR',
      'The UAT response for Lagoon Health is due tomorrow',
      'Milestone 1 invoice was verified',
      'Milestone 2 for Kestrel Logistics is complete',
    ]);
    expect(rows[0].querySelector('.alerts-meta')!.textContent).toBe('Chidi · WhatsApp · 09:42');
    expect(rows.map((r) => r.classList.contains('alerts-row--unread'))).toEqual([true, true, true, true, false, false]);
    expect(d.querySelector('.psl-tag')).toBeNull();
    expect(d.textContent).not.toContain('NEW');
    expect(rows.map((r) => r.querySelectorAll('a, button').length)).toEqual([1, 1, 1, 1, 1, 1]);
    const opens = openLinks();
    expect(opens).toHaveLength(6);
    expect(opens[0].getAttribute('aria-label')).toBe('Open: Invoice for Lagoon Health is waiting for your review');
    expect(opens[0].getAttribute('href')).toBe('/work/w-inv-lh-002');
    expect(opens.map((a) => !a.classList.contains('psl-btn--secondary'))).toEqual([true, true, true, false, false, false]);
    const foot = [...d.querySelectorAll('.psl-drawer__foot a')].map((a) => [a.textContent, a.getAttribute('href')]);
    expect(foot).toEqual([
      ['See all alerts', '/notifications'],
      ['Alert settings', '/settings/alerts'],
    ]);
    // The shared Drawer takes focus on the panel itself when it holds no field (the trap starts there).
    expect(document.activeElement).toBe(d);
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
      expect(document.activeElement).toBe(bell());
      expect(bell().getAttribute('aria-expanded')).toBe('false');
      expect(document.querySelector('main')!.hasAttribute('inert')).toBe(false);
    }
  });

  it('Tab and Shift+Tab stay inside: Close, six Open links, See all alerts, Alert settings', async () => {
    await mount();
    await openDrawer();
    const d = dialog()!;
    const close = within(d).getByRole('button', { name: 'Close' });
    const settings = within(d).getByRole('link', { name: 'Alert settings' });
    settings.focus();
    fireEvent.keyDown(settings, { key: 'Tab' });
    expect(document.activeElement).toBe(close);
    fireEvent.keyDown(close, { key: 'Tab', shiftKey: true });
    expect(document.activeElement).toBe(settings);
    expect([...d.querySelectorAll('a[href], button')].map((el) => el.getAttribute('aria-label') ?? el.textContent)).toHaveLength(9);
  });

  it('a page load reads once and each opening once more; marking read does not re-read', async () => {
    await mount();
    expect(lists()).toHaveLength(1);
    await openDrawer();
    expect(lists()).toHaveLength(2);
    fireEvent.click(openLinks()[0], { button: 0 });
    await until(() => expect(nav.push).toHaveBeenCalledWith('/work/w-inv-lh-002'));
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
  it('an unread alert: one POST with the CSRF token, then its work; the drawer closes; badge 3 and chip "2 need you"', async () => {
    await mount();
    await openDrawer();
    const open = openLinks()[0];
    fireEvent.click(open, { button: 0 });
    fireEvent.click(open, { button: 0 });
    await until(() => expect(nav.push).toHaveBeenCalledWith('/work/w-inv-lh-002'));
    expect(posts().map((c) => [c.url.pathname, c.csrf])).toEqual([['/api/v1/notifications/n1/read', 'mock-csrf-finance_lead']]);
    expect(dialog()).toBeNull();
    expect(badge()).toBe('3');
    expect(chip()).toBe('2 need you');
    expect(bell().getAttribute('aria-label')).toBe('Alerts, 3 unread, 2 need you');
  });

  it('a read alert sends no POST', async () => {
    await mount();
    await openDrawer();
    fireEvent.click(openLinks()[4], { button: 0 });
    await settle();
    expect(posts()).toHaveLength(0);
    expect(dialog()).toBeNull();
  });

  it('a failed POST still goes to the work, once, and nothing changes locally', async () => {
    hook = (c) => (c.method === 'POST' ? json(500, { code: 'server_error', message: 'Down.' }) : undefined);
    await mount();
    await openDrawer();
    fireEvent.click(openLinks()[0], { button: 0 });
    await until(() => expect(nav.push).toHaveBeenCalledWith('/work/w-inv-lh-002'));
    expect(posts()).toHaveLength(1);
    expect(badge()).toBe('4');
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
    await until(() => expect(nav.push).toHaveBeenCalledWith('/work/w-inv-lh-002'));
    expect(badge()).toBe('3');
    release();
    await settle();
    await settle();
    expect(badge()).toBe('3');
    expect(chip()).toBe('2 need you');
  });

  it('a 401 on the mark-read goes to the work and stops further reads', async () => {
    hook = (c) => (c.method === 'POST' ? json(401, { code: 'unauthenticated', message: 'Sign in.' }) : undefined);
    await mount();
    await openDrawer();
    fireEvent.click(openLinks()[0], { button: 0 });
    await until(() => expect(nav.push).toHaveBeenCalledWith('/work/w-inv-lh-002'));
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
    const onlyInfo = proposal();
    onlyInfo.items = onlyInfo.items.filter((item) => item.needs_you === false);
    hook = (c) => (c.method === 'GET' ? json(200, onlyInfo) : undefined);
    await mount();
    await openDrawer();
    expect(groupHeads()).toEqual(['Needs you, 0', 'For your information, 3']);
    expect(dialog()!.querySelector('.alerts-grp--need')!.closest('section')!.textContent).toContain('Nothing needs you right now.');
    fireEvent.keyDown(dialog()!, { key: 'Escape' });

    const onlyNeed = proposal();
    onlyNeed.items = onlyNeed.items.filter((item) => item.needs_you === true);
    hook = (c) => (c.method === 'GET' ? json(200, onlyNeed) : undefined);
    await openDrawer();
    await until(() => expect(groupHeads()).toEqual(['Needs you, 3', 'For your information, 0']));
    expect(dialog()!.textContent).toContain('No other alerts.');
  });

  it('no alerts: "No alerts yet." with the footer links, no badge', async () => {
    scenario = 'empty';
    await mount();
    expect(badge()).toBeNull();
    await openDrawer();
    expect(dialog()!.textContent).toContain('No alerts yet.');
    expect(within(dialog()!).getByRole('link', { name: 'See all alerts' })).toBeTruthy();
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
    await until(() => expect(openLinks()).toHaveLength(6));
    expect(lists()).toHaveLength(before + 1);
    expect(badge()).toBe('4');
  });

  it('a 401: signed out with Sign in back to this page, and no more requests', async () => {
    hook = () => json(401, { code: 'unauthenticated', message: 'Sign in.' });
    await mount();
    await openDrawer();
    expect(dialog()!.textContent).toContain('You’re signed out.');
    expect(within(dialog()!).getByRole('link', { name: 'Sign in' }).getAttribute('href')).toBe('/accounts/login/?next=%2Fmy-work');
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
    const list = proposal();
    list.items = [{ ...list.items[3], id: 'x1', text: '<b>needs you</b>', needs_you: false }, list.items[0]];
    hook = (c) => (c.method === 'GET' ? json(200, list) : undefined);
    await mount();
    await openDrawer();
    const info = dialog()!.querySelector('#alerts-grp-info')!.closest('section')!;
    expect(info.querySelector('.alerts-text')!.textContent).toBe('<b>needs you</b>');
    expect(info.querySelector('b')).toBeNull();
    expect(groupHeads()).toEqual(['Needs you, 1', 'For your information, 1']);
  });
});

describe('phone (below 720px)', () => {
  beforeEach(() => {
    vi.stubGlobal('matchMedia', (q: string) => ({ matches: q.includes('max-width'), media: q, addEventListener: () => {}, removeEventListener: () => {} }));
  });
  const phoneBell = () => within(document.querySelector('.shell-phone') as HTMLElement).getByRole('button', { name: /^Alerts/ });

  it('Menu, PSL FACTORY, bell, then + Start; same name; no chip', async () => {
    await mount();
    expect(phoneBell().getAttribute('aria-label')).toBe('Alerts, 4 unread, 3 need you');
    expect(document.querySelector('.shell-phone .shell-bellchip')).toBeNull();
    expect(phoneBar().textContent).toContain('PSL FACTORY');
    const order = [...document.querySelectorAll('.shell-phone button')].map((b) => b.getAttribute('aria-label'));
    expect(order).toEqual(['Menu', 'Alerts, 4 unread, 3 need you', 'Start work']);
  });

  it('the sheet opens on Needs you; arrows and clicks switch tabs; Escape returns focus to the phone bell', async () => {
    await mount();
    await openDrawer(phoneBell());
    const d = dialog()!;
    expect(d.querySelector('.psl-sheet__grab')).toBeTruthy();
    const tabs = within(d).getAllByRole('tab');
    expect(tabs.map((t) => [t.textContent, t.getAttribute('aria-selected')])).toEqual([
      ['Needs you 3', 'true'],
      ['For your information', 'false'],
    ]);
    expect(openLinks().map((a) => a.getAttribute('href'))).toEqual(['/work/w-inv-lh-002', '/work/w-plan-kl-01', '/work/w-pay-oct']);
    expect(groupHeads()).toEqual([]);
    fireEvent.keyDown(tabs[0], { key: 'ArrowRight' });
    // The shared Tabs move focus with the arrows; choosing is a click or Enter.
    expect(document.activeElement).toBe(within(d).getByRole('tab', { name: 'For your information' }));
    fireEvent.click(document.activeElement!);
    expect(openLinks().map((a) => a.getAttribute('href'))).toEqual(['/work/w-uat-lh', '/work/w-inv-lh-001', '/work/w-ms-kl-02']);
    fireEvent.click(within(d).getByRole('tab', { name: /^Needs you/ }));
    expect(openLinks()).toHaveLength(3);
    fireEvent.keyDown(dialog()!, { key: 'Escape' });
    await until(() => expect(dialog()).toBeNull());
    expect(document.activeElement).toBe(phoneBell());
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
    await until(() => expect(nav.push).toHaveBeenCalledWith('/work/w-inv-lh-002'));
    await goTo(view, '/work/w-inv-lh-002');
    expect(before.isConnected).toBe(false);
    expect(document.activeElement).toBe(phoneBell());
  });

  it('Alert settings and See all alerts: focus lands on the new phone bell', async () => {
    for (const [name, path] of [
      ['Alert settings', '/settings/alerts'],
      ['See all alerts', '/notifications'],
    ]) {
      nav.pathname = '/my-work';
      const view = await mount();
      await openDrawer(phoneBell());
      fireEvent.click(within(dialog()!).getByRole('link', { name }), { button: 0 });
      await goTo(view, path);
      expect(document.activeElement).toBe(phoneBell());
      view.unmount();
    }
  });

  it('a link to the page already shown closes the drawer and does not claim focus for a later navigation', async () => {
    nav.pathname = '/notifications';
    const view = await mount();
    await openDrawer(phoneBell());
    fireEvent.click(within(dialog()!).getByRole('link', { name: 'See all alerts' }), { button: 0 });
    await until(() => expect(dialog()).toBeNull());
    expect(document.activeElement).toBe(phoneBell());
    (document.activeElement as HTMLElement).blur();
    await goTo(view, '/my-work');
    expect(document.activeElement).not.toBe(phoneBell());
  });

  it('without needs_you there are no tabs, only For your information', async () => {
    scenario = 'board';
    await mount();
    await openDrawer(phoneBell());
    expect(screen.queryByRole('tab')).toBeNull();
    expect(groupHeads()).toEqual(['For your information, 4']);
  });
});
