// @vitest-environment jsdom
import { fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { setCsrfToken } from '@/api/client';
import { NotificationsPage } from '@/features/alerts/NotificationsPage';

import { alert, body, hex, json, settle, until } from './alerts-helpers';

// /notifications (SCR-15) on the live 1.24.0 shapes: grouping, links, paging, mark-read and states.
const nav = vi.hoisted(() => ({ push: vi.fn() }));
vi.mock('next/navigation', () => ({
  usePathname: () => '/notifications',
  useRouter: () => ({ push: nav.push, replace: vi.fn(), prefetch: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
}));

type Call = { method: string; url: URL; csrf: string | null; raw: string };
let calls: Call[];
/** The answer to a call; the default is page 1 of `list`. */
let answer: (call: Call) => Response | Promise<Response>;
let list: ReturnType<typeof body>;

beforeEach(() => {
  setCsrfToken('csrf-1');
  calls = [];
  nav.push.mockClear();
  list = body([
    alert({ n: 1, group: 'action', title: 'Invoice review', agent: 'chidi' }),
    alert({ n: 2, group: 'action', read: true, agent: 'tola' }),
    alert({ n: 3, group: 'update', agent: null, at: null, title: 'Assistant reply' }),
    alert({ n: 4, group: 'update', django_url: '/reminders/9/', api_url: null, title: 'Reminder' }),
  ]);
  answer = () => json(200, list);
  vi.stubGlobal(
    'fetch',
    vi.fn(async (request: Request) => {
      const call = { method: request.method, url: new URL(request.url), csrf: request.headers.get('X-CSRFToken'), raw: request.method === 'POST' ? await request.text() : '' };
      calls.push(call);
      return answer(call);
    }),
  );
});
afterEach(() => {
  vi.unstubAllGlobals();
  setCsrfToken(null);
});

const gets = () => calls.filter((c) => c.method === 'GET');
const posts = () => calls.filter((c) => c.method === 'POST');
const rows = () => [...document.querySelectorAll('.alerts-list > li')];

async function open() {
  const view = render(<NotificationsPage />);
  await until(() => expect(screen.queryByRole('heading', { name: /^Needs you/ })).toBeTruthy());
  return view;
}

describe('the list', () => {
  it('groups by `group` with loaded counts, the as-of line, the summary and the loaded and unread line', async () => {
    await open();
    expect([...document.querySelectorAll('h2')].map((h) => h.textContent)).toEqual(['Needs you, 2', 'For information, 2']);
    expect(document.querySelector('.alerts-summary')!.textContent).toBe('Today, 23 Nov: 3 need you, 2 new updates, 1 older unread.');
    expect(document.querySelector('.alerts-asof')!.textContent).toBe('As of 11:42 WAT. 4 loaded, 3 unread.');
    expect(rows().map((r) => r.querySelector('.alerts-text')!.textContent)).toEqual(['Invoice review', 'Invoice review 2', 'Assistant reply', 'Reminder']);
    expect(gets().map((c) => c.url.search)).toEqual(['?page=1']);
  });

  it('shows agent and time when the alert has them and neither, nor a placeholder, when it does not', async () => {
    await open();
    const [first, , third, fourth] = rows();
    expect(first.querySelector('.alerts-meta')!.textContent).toBe('Chidi · 12 Nov');
    expect(first.querySelector('.alerts-sub')!.textContent).toBe('Ojo Foods · INV-0001');
    expect(first.querySelector('.psl-avatar img, .psl-avatar svg, .psl-avatar')).toBeTruthy();
    expect(third.querySelector('.alerts-meta')).toBeNull();
    expect(third.querySelector('.psl-avatar')!.textContent).toBe('');
    expect(fourth.querySelector('.alerts-meta')!.textContent).toBe('Chidi · 12 Nov');
    expect(third.textContent).not.toMatch(/earlier|unknown|—/i);
  });

  it('has no search box, agent filter, Filter button, unread filter or total, and sends no q, agent or unread', async () => {
    await open();
    expect(screen.queryByRole('search')).toBeNull();
    expect(screen.queryByRole('searchbox')).toBeNull();
    expect(screen.queryByRole('button', { name: /filter/i })).toBeNull();
    expect(document.body.textContent).not.toMatch(/\d+ ALERTS?\b/);
    for (const call of calls) expect([...call.url.searchParams.keys()]).toEqual(['page']);
  });

  it('opens each row at its typed link and never at the retired Django page', async () => {
    await open();
    const hrefs = [...document.querySelectorAll('.alerts-list a')].map((a) => a.getAttribute('href'));
    expect(hrefs).toEqual(['/work/1', '/work/2', '/work/3']);
    expect(document.querySelector('a[href*="/accounts/"]')).toBeNull();
    expect(document.querySelector('a[href^="http"], a[href^="//"], a[href^="javascript"]')).toBeNull();
  });

  it('a hostile link is not a link: no href, and a Mark as read button while unread', async () => {
    list = body([
      alert({ n: 1, api_url: '//evil.example/x', django_url: 'https://evil.example/work/1/' }),
      alert({ n: 2, api_url: 'javascript:alert(1)', django_url: 'javascript:alert(1)', read: true }),
      alert({ n: 3, api_url: '/api/v1/work/a/b', django_url: '/work/%2e%2e/' }),
    ]);
    render(<NotificationsPage />);
    await until(() => expect(rows()).toHaveLength(3));
    expect(document.querySelectorAll('.alerts-list a')).toHaveLength(0);
    expect(screen.getAllByRole('button', { name: /^Mark as read/ })).toHaveLength(2);
  });

  it('empty: "No alerts", no group headings, and the summary still shows', async () => {
    list = body([]);
    render(<NotificationsPage />);
    await until(() => expect(screen.queryByText('No alerts')).toBeTruthy());
    expect(document.querySelectorAll('h2')).toHaveLength(0);
    expect(document.querySelector('.alerts-summary')).toBeTruthy();
  });
});

describe('Load more', () => {
  const page = (n: number, from: number, count: number, next: number | null) =>
    body(Array.from({ length: count }, (_, i) => alert({ n: from + i, group: 'update' })), { page: n, next_page: next, unread: 52 });

  it('requests next_page, appends without duplicates, and goes away at next_page null', async () => {
    answer = (call) => {
      const p = call.url.searchParams.get('page');
      if (p === '2') return json(200, page(2, 24, 25, 3)); // 24 and 25 repeat the last two rows of page 1
      if (p === '3') return json(200, page(3, 49, 5, null));
      return json(200, page(1, 1, 25, 2));
    };
    render(<NotificationsPage />);
    await until(() => expect(rows()).toHaveLength(25));
    expect(document.querySelector('.alerts-asof')!.textContent).toContain('25 loaded, 52 unread');
    fireEvent.click(screen.getByRole('button', { name: 'Load more' }));
    await until(() => expect(rows()).toHaveLength(48));
    fireEvent.click(screen.getByRole('button', { name: 'Load more' }));
    await until(() => expect(rows()).toHaveLength(53));
    expect(screen.queryByRole('button', { name: 'Load more' })).toBeNull();
    expect(gets().map((c) => c.url.search)).toEqual(['?page=1', '?page=2', '?page=3']);
    expect(new Set(rows().map((r) => r.querySelector('.alerts-text')!.textContent)).size).toBe(53);
    expect(document.querySelector('.alerts-asof')!.textContent).toContain('53 loaded');
  });

  it('a failed page keeps the rows, says so and retries the same page', async () => {
    let fail = true;
    answer = (call) => {
      if (call.url.searchParams.get('page') === '2') return fail ? json(500, { code: 'server_error', message: 'Down.' }) : json(200, page(2, 26, 3, null));
      return json(200, page(1, 1, 25, 2));
    };
    render(<NotificationsPage />);
    await until(() => expect(rows()).toHaveLength(25));
    fireEvent.click(screen.getByRole('button', { name: 'Load more' }));
    await until(() => expect(screen.queryByText('Couldn’t load more alerts. Try again.')).toBeTruthy());
    expect(rows()).toHaveLength(25);
    fail = false;
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
    await until(() => expect(rows()).toHaveLength(28));
    expect(gets().map((c) => c.url.search)).toEqual(['?page=1', '?page=2', '?page=2']);
    expect(screen.queryByText('Couldn’t load more alerts. Try again.')).toBeNull();
  });
});

describe('opening and marking read', () => {
  it('an unread alert: POST {} with the CSRF token, then the work; the unread count drops by one only after the 200', async () => {
    let release!: () => void;
    const gate = new Promise<void>((r) => (release = r));
    answer = async (call) => {
      if (call.method === 'POST') {
        await gate;
        return json(200, { id: hex(1), read: true });
      }
      return json(200, list);
    };
    await open();
    fireEvent.click(rows()[0].querySelector('a')!, { button: 0 });
    await settle();
    expect(document.querySelector('.alerts-asof')!.textContent).toContain('3 unread');
    expect(nav.push).not.toHaveBeenCalled();
    release();
    await until(() => expect(nav.push).toHaveBeenCalledWith('/work/1'));
    expect(posts().map((c) => [c.url.pathname, c.csrf, c.raw])).toEqual([[`/api/v1/notifications/${hex(1)}/read`, 'csrf-1', '{}']]);
    expect(document.querySelector('.alerts-asof')!.textContent).toContain('2 unread');
    expect(rows()[0].classList.contains('alerts-row--unread')).toBe(false);
  });

  it('a read alert sends no POST and a second click sends no second one', async () => {
    answer = (call) => (call.method === 'POST' ? json(200, { id: hex(1), read: true }) : json(200, list));
    await open();
    fireEvent.click(rows()[1].querySelector('a')!, { button: 0 });
    await settle();
    expect(posts()).toHaveLength(0);
    fireEvent.click(rows()[0].querySelector('a')!, { button: 0 });
    fireEvent.click(rows()[0].querySelector('a')!, { button: 0 });
    await until(() => expect(nav.push).toHaveBeenCalled());
    expect(posts()).toHaveLength(1);
  });

  for (const status of [500, 503]) {
    it(`a ${status} leaves the row unread, says "Couldn’t mark as read", and still goes to the work`, async () => {
      answer = (call) => (call.method === 'POST' ? json(status, { code: 'server_error', message: 'Down.' }) : json(200, list));
      await open();
      fireEvent.click(rows()[0].querySelector('a')!, { button: 0 });
      await until(() => expect(nav.push).toHaveBeenCalledWith('/work/1'));
      expect(rows()[0].classList.contains('alerts-row--unread')).toBe(true);
      expect(within(rows()[0] as HTMLElement).getByRole('status').textContent).toBe('Couldn’t mark as read. Try again.');
      expect(document.querySelector('.alerts-asof')!.textContent).toContain('3 unread');
      // retry: the same row posts again
      fireEvent.click(rows()[0].querySelector('a')!, { button: 0 });
      await until(() => expect(posts()).toHaveLength(2));
    });
  }

  for (const status of [403, 404]) {
    it(`a ${status} says the alert is no longer available, refreshes the list and does not open it`, async () => {
      answer = (call) => (call.method === 'POST' ? json(status, { code: 'not_found', message: 'Gone.' }) : json(200, list));
      await open();
      fireEvent.click(rows()[0].querySelector('a')!, { button: 0 });
      await until(() => expect(gets()).toHaveLength(2));
      await until(() => expect(screen.queryByText('This alert is no longer available.')).toBeTruthy());
      expect(nav.push).not.toHaveBeenCalled();
    });
  }

  it('a stale session token says to try again, changes nothing and does not open the work', async () => {
    answer = (call) => {
      if (call.method === 'POST') return json(403, { code: 'csrf_failed', message: 'Reload.' });
      if (call.url.pathname === '/api/v1/session') return json(200, { csrf_token: 'csrf-2', signed_in: true, next_url: '/' });
      return json(200, list);
    };
    await open();
    fireEvent.click(rows()[0].querySelector('a')!, { button: 0 });
    await until(() => expect(screen.queryByText(/Your session was refreshed\. Try again/)).toBeTruthy());
    expect(nav.push).not.toHaveBeenCalled();
    expect(posts()).toHaveLength(1);
  });

  it('a row with no link has Mark as read, which marks it read in place', async () => {
    answer = (call) => (call.method === 'POST' ? json(200, { id: hex(4), read: true }) : json(200, list));
    await open();
    const button = within(rows()[3] as HTMLElement).getByRole('button', { name: /^Mark as read/ });
    fireEvent.click(button);
    await until(() => expect(rows()[3].classList.contains('alerts-row--unread')).toBe(false));
    expect(posts().map((c) => c.url.pathname)).toEqual([`/api/v1/notifications/${hex(4)}/read`]);
    expect(within(rows()[3] as HTMLElement).queryByRole('button', { name: /^Mark as read/ })).toBeNull();
    expect(nav.push).not.toHaveBeenCalled();
  });

  it('a 401 on the mark-read shows the signed-out state', async () => {
    answer = (call) => (call.method === 'POST' ? json(401, { code: 'unauthenticated', message: 'Sign in.' }) : json(200, list));
    await open();
    fireEvent.click(rows()[0].querySelector('a')!, { button: 0 });
    await until(() => expect(screen.queryByText(/signed out/i)).toBeTruthy());
    expect(gets()).toHaveLength(1);
  });

  it('a Ctrl click is a normal link: no POST, no push', async () => {
    await open();
    fireEvent.click(rows()[0].querySelector('a')!, { button: 0, ctrlKey: true });
    await settle();
    expect(posts()).toHaveLength(0);
    expect(nav.push).not.toHaveBeenCalled();
  });
});

describe('states', () => {
  it('loading shows the skeleton', async () => {
    answer = () => new Promise<Response>(() => {});
    render(<NotificationsPage />);
    await until(() => expect(screen.queryByText('Loading…')).toBeTruthy());
  });

  it('a 500 shows the error card; Try again reads page 1 again', async () => {
    answer = () => json(500, { code: 'server_error', message: 'Down.' });
    render(<NotificationsPage />);
    await until(() => expect(screen.queryByText(/We couldn’t load your alerts/)).toBeTruthy());
    expect(document.body.textContent).toContain('Reference server_error for support.');
    answer = () => json(200, list);
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
    await until(() => expect(rows()).toHaveLength(4));
    expect(gets()).toHaveLength(2);
  });

  it('a 403 and a network failure show the error card', async () => {
    answer = () => json(403, { code: 'forbidden', message: 'No.' });
    const view = render(<NotificationsPage />);
    await until(() => expect(screen.queryByText(/We couldn’t load your alerts/)).toBeTruthy());
    view.unmount();
    answer = () => Promise.reject(new TypeError('network'));
    render(<NotificationsPage />);
    await until(() => expect(screen.queryByText(/We couldn’t load your alerts/)).toBeTruthy());
  });

  it('a 400 or 422 on the page shows the error card', async () => {
    answer = () => json(400, { code: 'invalid_query', message: 'No.' });
    render(<NotificationsPage />);
    await until(() => expect(screen.queryByText(/We couldn’t load your alerts/)).toBeTruthy());
  });

  it('a 401 shows the signed-out state and sends nothing more', async () => {
    answer = () => json(401, { code: 'unauthenticated', message: 'Sign in.' });
    render(<NotificationsPage />);
    await until(() => expect(screen.queryByText(/signed out/i)).toBeTruthy());
    await settle();
    expect(calls).toHaveLength(1);
  });

  it('a body with no items array is a load error, never "No alerts"', async () => {
    answer = () => json(200, { as_of: '2026-11-23T10:42:00Z', page: 1, next_page: null, unread: 0 });
    render(<NotificationsPage />);
    await until(() => expect(screen.queryByText(/We couldn’t load your alerts/)).toBeTruthy());
    expect(screen.queryByText('No alerts')).toBeNull();
  });

  it('a body with items that are not an array, or with no unread number, is a load error', async () => {
    answer = () => json(200, { ...list, items: null });
    const view = render(<NotificationsPage />);
    await until(() => expect(screen.queryByText(/We couldn’t load your alerts/)).toBeTruthy());
    view.unmount();
    answer = () => json(200, { ...list, unread: undefined });
    render(<NotificationsPage />);
    await until(() => expect(screen.queryByText(/We couldn’t load your alerts/)).toBeTruthy());
  });
});
