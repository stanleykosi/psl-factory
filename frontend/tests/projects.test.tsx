// @vitest-environment jsdom
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { setImmediate as realImmediate } from 'node:timers';

import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ProjectsPage } from '@/features/projects/ProjectsPage';
import { AppShell } from '@/shell/AppShell';

// @ts-expect-error plain ESM module without type declarations
import { projects } from '../mock/projects.mjs';
import { destinationList } from './destinations';
import { bellFeed, isBellFeed, isRoleDashboard, roleDashboard } from './bell-feed';

// next/navigation: the search params live in a small store that router.replace updates, like the app router.
const nav = vi.hoisted(() => {
  const listeners = new Set<() => void>();
  let params = new URLSearchParams();
  const set = (search: string) => {
    params = new URLSearchParams(search);
    window.history.replaceState(null, '', `/projects${search}`);
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
    usePathname: () => '/projects',
    useRouter: () => nav.router,
    useSearchParams: () => useSyncExternalStore(subscribe, nav.get),
  };
});

type Item = { case_id: string; title: string; manager: string | null; lifecycle: string | null; phase: string | null; reviews: number | null; exceptions: number | null; sample: boolean };
type Body = { items: Item[]; next_cursor: string | null; as_of: string };
const AS_OF = '2026-11-23T09:00:00Z';
const row = (n: number, over: Partial<Item> = {}): Item => ({ case_id: `00000000-0000-4000-8000-${String(n).padStart(12, '0')}`, title: `Project ${n}`, manager: 'Ada Okafor', lifecycle: 'active', phase: 'Planning', reviews: 0, exceptions: 0, sample: true, ...over });
const me = (persona: string) => JSON.parse(readFileSync(join(__dirname, `../mock/fixtures/me.${persona}.json`), 'utf8'));
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
const fromMock = (url: URL, persona = 'finance_lead') => projects({ operationId: 'E-PROJECTS', url, persona }) as { status: number; body: Body };
const mockResponse = (url: URL, persona = 'finance_lead') => {
  const r = fromMock(url, persona);
  return json(r.status, r.body);
};

let persona = 'finance_lead';
let respond: (url: URL) => Response | Promise<Response>;
let calls: URL[];

beforeEach(() => {
  persona = 'finance_lead';
  calls = [];
  respond = (url) => mockResponse(url, persona);
  nav.router.replace.mockClear();
  nav.set('');
  vi.stubGlobal(
    'fetch',
    vi.fn(async (request: Request) => {
      if (isBellFeed(request)) return bellFeed();
      if (isRoleDashboard(request)) return roleDashboard();
      const url = new URL(request.url);
      if (url.pathname === '/api/v1/me') return json(200, me(persona));
      calls.push(url);
      return respond(url);
    }),
  );
});
afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
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

const rows = () => document.querySelectorAll('tbody tr');
const titles = () => [...rows()].map((r) => r.querySelector('a')!.textContent);
const lastCall = () => calls[calls.length - 1];
const query = (url: URL) => Object.fromEntries(url.searchParams);
const tabs = () => within(screen.getByRole('tablist', { name: 'Projects' })).getAllByRole('tab');
const moreButton = () => screen.queryByRole('button', { name: 'Show more' });

function renderPage(search = '') {
  nav.set(search);
  return render(
    <AppShell>
      <ProjectsPage />
    </AppShell>,
  );
}

async function open(search = '') {
  const result = renderPage(search);
  await until(() => expect(calls.length).toBeGreaterThan(0));
  await until(() => expect(screen.queryByText('Loading…')).toBeNull());
  return result;
}


const ACTIVE = 'http://x/api/v1/projects?status=active';
const textOfRow = (r: Element) => [...r.querySelectorAll('td')].map((td) => td.textContent);
const LAGOON = '/projects/00000000-0000-4000-8000-000000000101';

describe('list reads GET /projects, drawn as SCR-22', () => {
  it('finance_lead: one GET with status=active and no limit, the eyebrow, tabs without counts, five columns, rows in response order', async () => {
    await open();
    expect(calls).toHaveLength(1);
    expect(calls[0].pathname).toBe('/api/v1/projects');
    expect(calls[0].search).toBe('?status=active');
    expect(calls[0].searchParams.has('limit')).toBe(false);
    expect(document.querySelector('.projects__eyebrow')!.textContent).toBe('PROJECTS');
    expect(screen.getByRole('heading', { level: 1, name: 'Projects' })).toBeTruthy();
    expect(tabs().map((t) => [t.textContent, t.getAttribute('aria-selected')])).toEqual([
      ['Active', 'true'],
      ['Closed', 'false'],
      ['All I can see', 'false'],
    ]);
    expect(screen.getByRole('tabpanel', { name: 'Active' })).toBeTruthy();
    expect(screen.getAllByRole('columnheader').map((th) => th.textContent)).toEqual(['PROJECT', 'PM', 'WHERE IT IS', 'NEEDS A PERSON', 'STOPPED']);
    const expected = fromMock(new URL(ACTIVE)).body;
    expect(rows()).toHaveLength(20);
    expect(titles()).toEqual(expected.items.map((i) => i.title));
    const first = within(rows()[0] as HTMLElement).getByRole('link', { name: 'Lagoon Health · patient app' });
    expect(first.getAttribute('href')).toBe(LAGOON);
    expect(textOfRow(rows()[0])).toEqual(['Lagoon Health · patient app', 'Tunde Bello', 'Release · UAT with client', '2', '1']);
    expect([...rows()[0].querySelectorAll('td')].slice(3).map((td) => td.firstElementChild!.className)).toEqual(['projects__count', 'projects__count']);
    expect(document.querySelector('.psl-resultcount')!.textContent).toBe('20 shown, more available');
    expect(screen.getByText('You see projects your roles cover. Open one for its journey, documents, money and registers.')).toBeTruthy();
  });

  it('there is no NEXT MILESTONE column, no count badge, no "N PROJECTS" total and no rows-per-page choice', async () => {
    await open();
    expect(document.body.textContent).not.toContain('NEXT MILESTONE');
    expect(document.body.textContent).not.toMatch(/\d+ PROJECTS?\b/);
    expect(document.querySelector('.psl-badge')).toBeNull();
    expect(screen.queryByRole('radiogroup', { name: 'Rows per page' })).toBeNull();
    expect(document.body.textContent).not.toContain('Rows per page');
  });

  it('a null manager reads No manager, null counts read Unknown, and a real 0 reads 0', async () => {
    respond = () =>
      json(200, {
        items: [row(1, { reviews: 0, exceptions: 0 }), row(104, { title: 'Atlas Retail · POS refresh', manager: null, lifecycle: null, phase: null, reviews: null, exceptions: null })],
        next_cursor: null,
        as_of: AS_OF,
      });
    await open();
    expect(textOfRow(rows()[0])).toEqual(['Project 1', 'Ada Okafor', 'Planning', '0', '0']);
    expect(textOfRow(rows()[1])).toEqual(['Atlas Retail · POS refresh', 'No manager', 'Unknown', 'Unknown', 'Unknown']);
    expect(rows()[1].querySelectorAll('.psl-unknown')).toHaveLength(2);
    expect(rows()[0].querySelectorAll('.projects__zero')).toHaveLength(2);
    expect(document.body.textContent).not.toContain('undefined');
  });

  it('WHERE IT IS shows the phase, else the lifecycle, else Unknown', async () => {
    respond = () =>
      json(200, { items: [row(1, { phase: 'Release', lifecycle: 'active' }), row(2, { phase: null, lifecycle: 'closed' }), row(3, { phase: null, lifecycle: null })], next_cursor: null, as_of: AS_OF });
    await open();
    expect([...rows()].map((r) => textOfRow(r)[2])).toEqual(['Release', 'closed', 'Unknown']);
  });

  it('pm sees the four active SCR-22 board projects and Standalone fit-out, never P-0104', async () => {
    persona = 'pm';
    await open();
    expect(titles()).toEqual(['Lagoon Health · patient app', 'Harmattan Bank · mobile onboarding', 'Kora Logistics · fleet tracker', 'Ojo Foods · ordering app', 'Standalone fit-out']);
    expect(document.body.textContent).not.toContain('Delta Foods');
    expect(document.querySelector('.psl-resultcount')!.textContent).toBe('5 shown');
    expect(moreButton()).toBeNull();
  });

  it('Active sends status=active (and none in the address), Closed and All I can see send status=closed and status=all; arrow keys move between tabs', async () => {
    persona = 'pm';
    await open();
    expect(query(lastCall())).toEqual({ status: 'active' });
    expect(window.location.search).toBe('');
    fireEvent.click(tabs()[1]);
    await until(() => expect(titles()).toEqual(['Sabi Market · web store']));
    expect(query(lastCall())).toEqual({ status: 'closed' });
    expect(window.location.search).toBe('?status=closed');
    tabs()[1].focus();
    fireEvent.keyDown(tabs()[1], { key: 'ArrowRight' });
    await waitFor(() => expect(document.activeElement).toBe(tabs()[2]));
    fireEvent.click(tabs()[2]);
    await until(() => expect(rows()).toHaveLength(6));
    expect(query(lastCall())).toEqual({ status: 'all' });
    expect(window.location.search).toBe('?status=all');
    await waitFor(() => expect(document.activeElement).toBe(tabs()[2]));
    expect(tabs().map((t) => t.tabIndex)).toEqual([-1, -1, 0]);
    fireEvent.keyDown(tabs()[2], { key: 'Home' });
    await waitFor(() => expect(document.activeElement).toBe(tabs()[0]));
    fireEvent.click(tabs()[0]);
    await until(() => expect(rows()).toHaveLength(5));
    expect(window.location.search).toBe('');
  });

  it('Filter opens a panel that says filters come next; Escape closes it and returns focus', async () => {
    await open();
    const button = screen.getByRole('button', { name: 'Filter' });
    expect(button.getAttribute('aria-expanded')).toBe('false');
    fireEvent.click(button);
    const dialog = screen.getByRole('dialog', { name: 'Filter projects' });
    expect(dialog.textContent).toContain('Filters come next');
    expect(button.getAttribute('aria-expanded')).toBe('true');
    fireEvent.keyDown(dialog, { key: 'Escape' });
    expect(screen.queryByRole('dialog')).toBeNull();
    await waitFor(() => expect(document.activeElement).toBe(button));
    expect(calls).toHaveLength(1);
  });

  it('server order is kept: the page never sorts or filters', async () => {
    respond = () => json(200, { items: [row(9, { title: 'Zulu works' }), row(1, { title: 'Alpha works' })], next_cursor: null, as_of: AS_OF });
    await open();
    expect(titles()).toEqual(['Zulu works', 'Alpha works']);
  });
});

describe('search', () => {
  it('sends one q=lagoon request 200 ms after the last keystroke; clearing drops q', async () => {
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout', 'setInterval', 'clearInterval', 'Date'] });
    await open();
    const box = screen.getByRole('searchbox', { name: 'Search' });
    expect(box.getAttribute('placeholder')).toBe('Search projects or clients');
    for (const text of ['l', 'la', 'lag', 'lagoon']) {
      fireEvent.change(box, { target: { value: text } });
      await act(() => vi.advanceTimersByTimeAsync(100));
    }
    expect(calls).toHaveLength(1);
    await act(() => vi.advanceTimersByTimeAsync(99));
    expect(calls).toHaveLength(1);
    await act(() => vi.advanceTimersByTimeAsync(1));
    await until(() => expect(calls).toHaveLength(2));
    expect(calls[1].search).toBe('?status=active&q=lagoon');
    expect(window.location.search).toBe('?q=lagoon');
    await until(() => expect(titles()).toEqual(['Lagoon Health · patient app']));
    expect(document.querySelector('.psl-resultcount')!.textContent).toBe('1 shown');

    fireEvent.change(box, { target: { value: '' } });
    await act(() => vi.advanceTimersByTimeAsync(300));
    await until(() => expect(calls).toHaveLength(3));
    expect(calls[2].searchParams.has('q')).toBe(false);
    expect(window.location.search).toBe('');
    expect(calls.every((c) => c.searchParams.get('q') !== '')).toBe(true);
  });

  it('trims the search, and a pasted 200 characters are cut to 120 in the box and in the request', async () => {
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout', 'setInterval', 'clearInterval', 'Date'] });
    await open();
    const box = screen.getByRole('searchbox', { name: 'Search' }) as HTMLInputElement;
    fireEvent.change(box, { target: { value: 'z'.repeat(200) } });
    expect(box.value).toHaveLength(120);
    await act(() => vi.advanceTimersByTimeAsync(300));
    await until(() => expect(calls).toHaveLength(2));
    expect(lastCall().searchParams.get('q')).toBe('z'.repeat(120));
    fireEvent.change(box, { target: { value: '  harmattan  ' } });
    await act(() => vi.advanceTimersByTimeAsync(300));
    await until(() => expect(calls).toHaveLength(3));
    expect(lastCall().searchParams.get('q')).toBe('harmattan');
  });

  it('no match shows No projects match; Show all projects restores the full list', async () => {
    await open('?q=zzz');
    expect(query(calls[0])).toEqual({ status: 'active', q: 'zzz' });
    expect(screen.getByRole('heading', { name: 'No projects match' })).toBeTruthy();
    expect(moreButton()).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: 'Show all projects' }));
    await until(() => expect(rows()).toHaveLength(20));
    expect(lastCall().searchParams.has('q')).toBe(false);
    expect((screen.getByRole('searchbox') as HTMLInputElement).value).toBe('');
  });

  it('zero projects without a search shows the empty state', async () => {
    respond = () => json(200, { items: [], next_cursor: null, as_of: AS_OF });
    await open();
    expect(screen.getByRole('heading', { name: 'No projects you can see yet.' })).toBeTruthy();
    expect(screen.getByText('You see projects your roles cover.')).toBeTruthy();
    expect(screen.queryByRole('table')).toBeNull();
  });
});

describe('paging with next_cursor', () => {
  it('shows "N shown, more available"; Show more sends the cursor, appends, and focuses the first new row', async () => {
    await open();
    expect(rows()).toHaveLength(20);
    expect(document.querySelector('.psl-resultcount')!.textContent).toBe('20 shown, more available');
    fireEvent.click(moreButton()!);
    await until(() => expect(rows()).toHaveLength(23));
    expect(query(lastCall())).toEqual({ status: 'active', cursor: 'o20' });
    expect(moreButton()).toBeNull();
    const all = [...fromMock(new URL(ACTIVE)).body.items, ...fromMock(new URL(`${ACTIVE}&cursor=o20`)).body.items];
    expect(titles()).toEqual(all.map((i) => i.title));
    expect(document.querySelector('.psl-resultcount')!.textContent).toBe('23 shown');
    await waitFor(() => expect(document.activeElement?.textContent).toBe(all[20].title));
  });

  it('a new tab or search loads page 1 again; the cursor never reaches the address', async () => {
    await open();
    fireEvent.click(moreButton()!);
    await until(() => expect(rows()).toHaveLength(23));
    expect(window.location.search).toBe('');
    fireEvent.click(tabs()[2]);
    await until(() => expect(rows()).toHaveLength(20));
    expect(query(lastCall())).toEqual({ status: 'all' });
    expect(window.location.search).toBe('?status=all');
  });

  it('an old ?limit= is ignored: no limit is sent', async () => {
    await open('?limit=50');
    expect(query(calls[0])).toEqual({ status: 'active' });
    expect(rows()).toHaveLength(20);
  });

  it('a failed Show more keeps the loaded rows and shows the inline problem; Retry recovers', async () => {
    await open();
    respond = () => json(503, { code: 'unavailable', message: 'Down.' });
    fireEvent.click(moreButton()!);
    await until(() => expect(screen.getByText(/We couldn’t load more/)).toBeTruthy());
    expect(rows()).toHaveLength(20);
    respond = (url) => mockResponse(url);
    fireEvent.click(screen.getByRole('button', { name: 'Retry' }));
    await until(() => expect(rows()).toHaveLength(23));
  });
});

describe('access and failures', () => {
  it('without the projects destination: not open, and no projects request', async () => {
    persona = 'pm';
    const pm = me('pm');
    vi.mocked(fetch).mockImplementation(async (request) => {
      if (isBellFeed(request as Request)) return bellFeed();
      if (isRoleDashboard(request as Request)) return roleDashboard();
      const url = new URL((request as Request).url);
      if (url.pathname === '/api/v1/me') return json(200, { ...pm, destinations: destinationList(['my_work', 'assistant']) });
      calls.push(url);
      return respond(url);
    });
    renderPage();
    await until(() => expect(screen.getByText('This section isn’t open to your role.')).toBeTruthy());
    expect(screen.getByRole('link', { name: 'Go to My work' })).toBeTruthy();
    await act(async () => {
      await new Promise((r) => realImmediate(r));
    });
    expect(calls).toHaveLength(0);
  });

  it('persona none (no destinations at all): the frame says no sections are open, and no projects request', async () => {
    persona = 'none';
    renderPage();
    await until(() => expect(screen.getByText('No sections are open to your role yet.')).toBeTruthy());
    await act(async () => {
      await new Promise((r) => realImmediate(r));
    });
    expect(calls).toHaveLength(0);
  });

  it('401 shows the signed-out callout with next=/projects', async () => {
    respond = () => json(401, { code: 'not_signed_in', message: 'Sign in to continue.' });
    await open();
    await until(() => expect(screen.getByText('You’re signed out.')).toBeTruthy());
    expect(screen.getByRole('link', { name: 'Sign in' }).getAttribute('href')).toBe('/accounts/login/?next=%2Fprojects');
  });

  it('403 shows not open with the first destination', async () => {
    respond = () => json(403, { code: 'forbidden', message: 'Your role does not allow this.' });
    await open();
    expect(screen.getByText('This section isn’t open to your role.')).toBeTruthy();
    expect(screen.getByRole('link', { name: 'Go to My work' }).getAttribute('href')).toBe('/my-work');
    expect(document.body.textContent).not.toContain('Your role does not allow this.');
  });

  it.each([
    ['500', () => json(500, { code: 'server_down', message: 'x' }), 'server_down'],
    ['400', () => json(400, { code: 'bad_request', message: 'x' }), 'bad_request'],
    ['422 invalid_filter', () => json(422, { code: 'invalid_filter', message: 'x' }), 'invalid_filter'],
    ['network', () => Promise.reject(new TypeError('Failed to fetch')), 'network_error'],
    ['malformed 200 (the /me body)', () => json(200, me('finance_lead')), 'unexpected_response'],
  ])('%s shows the error card; Try again re-reads and recovers', async (_, failure, code) => {
    respond = failure as () => Response;
    await open();
    const card = screen.getByRole('alert');
    expect(card.textContent).toContain('ERROR · COULDN’T LOAD');
    expect(card.textContent).toContain('We couldn’t load your projects. Your work is safe; nothing was changed.');
    expect(card.textContent).toContain(`Reference ${code} for support.`);
    respond = (url) => mockResponse(url);
    fireEvent.click(within(card).getByRole('button', { name: 'Try again' }));
    await until(() => expect(rows()).toHaveLength(20));
    expect(query(lastCall())).toEqual({ status: 'active' });
  });

  it('loading shows status with no old rows; a late response for an earlier q is ignored', async () => {
    await open();
    const pending: Record<string, () => void> = {};
    respond = (url) => new Promise<Response>((resolve) => (pending[url.searchParams.get('q') ?? ''] = () => resolve(mockResponse(url))));
    const box = screen.getByRole('searchbox', { name: 'Search' });
    fireEvent.change(box, { target: { value: 'lagoon' } });
    await act(() => new Promise((r) => setTimeout(r, 260)));
    await until(() => expect(pending.lagoon).toBeTruthy());
    expect(screen.getByText('Loading…')).toBeTruthy();
    expect(rows()).toHaveLength(0);
    fireEvent.change(box, { target: { value: 'harmattan' } });
    await act(() => new Promise((r) => setTimeout(r, 260)));
    await until(() => expect(pending.harmattan).toBeTruthy());
    await act(async () => pending.harmattan());
    await until(() => expect(titles()).toEqual(['Harmattan Bank · mobile onboarding']));
    await act(async () => pending.lagoon());
    await act(async () => {
      await new Promise((r) => realImmediate(r));
    });
    expect(titles()).toEqual(['Harmattan Bank · mobile onboarding']);
  });
});

describe('phone and sample label', () => {
  it('below 720px each project is one card link: title, where it is · PM, then what needs a person; no PM part without a manager', async () => {
    vi.stubGlobal('matchMedia', (q: string) => ({ matches: true, media: q, addEventListener: () => {}, removeEventListener: () => {} }));
    respond = () =>
      json(200, {
        items: [row(101, { title: 'Lagoon Health · patient app', manager: 'Tunde Bello', phase: 'Release · UAT with client', reviews: 2, exceptions: 1 }), row(104, { title: 'Atlas Retail · POS refresh', manager: null, phase: null, lifecycle: null, reviews: null, exceptions: null }), row(5)],
        next_cursor: null,
        as_of: AS_OF,
      });
    await open();
    expect(screen.queryByRole('table')).toBeNull();
    const cards = document.querySelectorAll('.projects__cards a');
    expect(cards).toHaveLength(3);
    expect(cards[0].getAttribute('href')).toBe(LAGOON);
    expect(cards[0].textContent).toBe('Lagoon Health · patient appRelease · UAT with client · PM Tunde Bello2 need a person · 1 stopped');
    expect(cards[0].querySelector('.projects__attention')!.textContent).toBe('2 need a person · 1 stopped');
    expect(cards[1].textContent).toBe('Atlas Retail · POS refreshUnknown');
    expect(cards[2].querySelector('.projects__attention')).toBeNull();
    expect(screen.getByRole('searchbox').getAttribute('placeholder')).toBe('Search projects');
    expect(screen.getByRole('button', { name: 'Filter' }).textContent).toBe('');
  });

  it('no SAMPLE DATA by default; with the switch on, exactly one per sample row and none for sample: false', async () => {
    respond = () => json(200, { items: [row(1), row(2, { sample: false })], next_cursor: null, as_of: AS_OF });
    const first = await open();
    expect(document.querySelector('.psl-sample')).toBeNull();
    first.unmount();
    vi.stubEnv('NEXT_PUBLIC_SHOW_SAMPLE_LABEL', '1');
    await open();
    expect([...rows()].map((r) => r.querySelectorAll('.psl-sample').length)).toEqual([1, 0]);
    expect(rows()[0].querySelector('.psl-sample')!.textContent).toBe('SAMPLE DATA');
  });
});
