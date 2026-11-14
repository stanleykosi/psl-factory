// @vitest-environment jsdom
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { setImmediate as realImmediate } from 'node:timers';

import { act, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { nextMilestoneText, type NextMilestone } from '@/features/projects/model';
import { ProjectsPage } from '@/features/projects/ProjectsPage';
import { AppShell } from '@/shell/AppShell';

// @ts-expect-error plain ESM module without type declarations
import { projects } from '../mock/projects.mjs';

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

type Item = { case_id: string; title: string; pm: string; stage: string; sample: boolean; next_milestone?: NextMilestone; needs_person?: number; stopped?: number };
type Body = { items: Item[]; next_cursor?: string; as_of: string; counts?: Record<string, number>; total?: number };
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
const radios = () => within(screen.getByRole('radiogroup', { name: 'Rows per page' })).getAllByRole('radio');

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
  await until(() => expect(screen.queryByRole('status')).toBeNull());
  return result;
}

const ACTIVE_20 = 'http://x/api/v1/projects?limit=20';
const cellsOf = (i: Item) => [i.title, i.pm, i.stage, nextMilestoneText(i.next_milestone) ?? '—', String(i.needs_person ?? '—'), String(i.stopped ?? '—')];

describe('list reads E-PROJECTS (JR-08 open project), drawn as SCR-22', () => {
  it('finance_lead: one GET for the Active tab, the eyebrow, tabs with counts, six columns, rows in response order', async () => {
    await open();
    expect(calls).toHaveLength(1);
    expect(calls[0].pathname).toBe('/api/v1/projects');
    expect(calls[0].search).toBe('?limit=20');
    expect(document.querySelector('.projects__eyebrow')!.textContent).toBe('PROJECTS');
    expect(screen.getByRole('heading', { level: 1, name: 'Projects' })).toBeTruthy();
    expect(tabs().map((t) => [t.textContent, t.getAttribute('aria-selected')])).toEqual([
      ['Active22', 'true'],
      ['Closed2', 'false'],
      ['All I can see24', 'false'],
    ]);
    expect(screen.getByRole('tabpanel').getAttribute('aria-labelledby')).toBe(tabs()[0].id);
    expect(screen.getAllByRole('columnheader').map((th) => th.textContent)).toEqual([
      'PROJECT',
      'PM',
      'WHERE IT IS',
      'NEXT MILESTONE',
      'NEEDS A PERSON',
      'STOPPED',
    ]);
    const expected = fromMock(new URL(ACTIVE_20)).body.items;
    expect(rows()).toHaveLength(20);
    expect([...rows()].map((r) => [...r.querySelectorAll('td')].map((td) => td.textContent))).toEqual(expected.map(cellsOf));
    expect([...rows()[0].querySelectorAll('td')].slice(4).map((td) => td.firstElementChild!.className)).toEqual(['projects__count', 'projects__count']);
    const first = within(rows()[0] as HTMLElement).getByRole('link', { name: 'Lagoon Health · patient app' });
    expect(first.getAttribute('href')).toBe('/projects/P-0101');
    expect(document.querySelector('.psl-resultcount')!.textContent).toBe('22 PROJECTS');
    expect(screen.getByRole('button', { name: 'Show more' })).toBeTruthy();
    expect(screen.getByText('You see projects your roles cover. Open one for its journey, documents, money and registers.')).toBeTruthy();
  });

  it('pm sees the four active SCR-22 board projects, never P-0104', async () => {
    persona = 'pm';
    await open();
    expect(titles()).toEqual(['Lagoon Health · patient app', 'Harmattan Bank · mobile onboarding', 'Kora Logistics · fleet tracker', 'Ojo Foods · ordering app']);
    expect(document.body.textContent).not.toContain('Delta Foods');
    expect(screen.getByText('All 4 showing')).toBeTruthy();
    expect(document.querySelector('.psl-resultcount')!.textContent).toBe('4 PROJECTS');
  });

  it('Active sends no status, Closed and All I can see send status=closed and status=all, write ?status=, and arrow keys move between tabs', async () => {
    persona = 'pm';
    await open();
    fireEvent.click(tabs()[1]);
    await until(() => expect(titles()).toEqual(['Sabi Market · web store']));
    expect(query(lastCall())).toEqual({ limit: '20', status: 'closed' });
    expect(window.location.search).toBe('?status=closed');
    expect([...rows()[0].querySelectorAll('td')].map((td) => td.textContent)).toEqual(['Sabi Market · web store', 'Kemi Adebayo', 'Closed 09 Nov', '—', '0', '0']);
    expect(document.querySelector('.psl-resultcount')!.textContent).toBe('1 PROJECTS');
    tabs()[1].focus();
    fireEvent.keyDown(tabs()[1], { key: 'ArrowRight' });
    await until(() => expect(rows()).toHaveLength(5));
    expect(query(lastCall())).toEqual({ limit: '20', status: 'all' });
    expect(window.location.search).toBe('?status=all');
    expect(document.activeElement).toBe(tabs()[2]);
    expect(tabs().map((t) => t.tabIndex)).toEqual([-1, -1, 0]);
    fireEvent.keyDown(tabs()[2], { key: 'Home' });
    await until(() => expect(rows()).toHaveLength(4));
    expect(window.location.search).toBe('');
  });

  it('Filter opens a panel that says filters come next; Escape closes it and returns focus', async () => {
    await open();
    const button = screen.getByRole('button', { name: 'Filter' });
    expect(button.getAttribute('aria-haspopup')).toBe('dialog');
    fireEvent.click(button);
    const dialog = screen.getByRole('dialog', { name: 'Filter projects' });
    expect(dialog.textContent).toContain('Filters come next');
    expect(button.getAttribute('aria-expanded')).toBe('true');
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(screen.queryByRole('dialog')).toBeNull();
    expect(document.activeElement).toBe(button);
    expect(calls).toHaveLength(1);
  });

  it('server order is kept: the page never sorts or filters', async () => {
    const items: Item[] = [
      { case_id: 'P-9', title: 'Zulu works', pm: 'Kunle Ade', stage: 'Closed', sample: true },
      { case_id: 'P-1', title: 'Alpha works', pm: 'Ada Okafor', stage: 'Planning', sample: true },
    ];
    respond = () => json(200, { items, as_of: '2026-11-14T09:00:00Z' });
    await open();
    expect(titles()).toEqual(['Zulu works', 'Alpha works']);
  });
});

describe('a body without the PROPOSAL fields', () => {
  it('still draws every board element: tabs without counts, Filter, six columns with dashes, and N shown', async () => {
    respond = () =>
      json(200, {
        items: [
          { case_id: 'P-1', title: 'Alpha works', pm: 'Ada Okafor', stage: 'Planning', sample: true },
          { case_id: 'P-2', title: 'Beta works', pm: 'Kunle Ade', stage: 'Go-live', sample: true },
        ],
        as_of: '2026-11-14T09:00:00Z',
      });
    await open();
    expect(tabs().map((t) => t.textContent)).toEqual(['Active', 'Closed', 'All I can see']);
    expect(screen.getByRole('button', { name: 'Filter' })).toBeTruthy();
    expect(document.querySelectorAll('th')).toHaveLength(6);
    expect([...rows()].map((r) => [...r.querySelectorAll('td')].map((td) => td.textContent))).toEqual([
      ['Alpha works', 'Ada Okafor', 'Planning', '—', '—', '—'],
      ['Beta works', 'Kunle Ade', 'Go-live', '—', '—', '—'],
    ]);
    expect(document.body.textContent).not.toContain('undefined');
    expect(document.querySelector('.psl-resultcount')!.textContent).toBe('2 shown');
  });
});

describe('PROPOSAL fields in another shape (TECH-2-1)', () => {
  it('degrade to dashes and N shown instead of throwing; a search without total does not show the tab count', async () => {
    respond = () =>
      json(200, {
        items: [
          { case_id: 'P-1', title: 'Alpha works', pm: 'Ada Okafor', stage: 'Planning', sample: true, next_milestone: 'Plan approved', needs_person: '2', stopped: -1 },
          { case_id: 'P-2', title: 'Beta works', pm: 'Kunle Ade', stage: 'Go-live', sample: true, next_milestone: { name: 'Go-live', due: { unknown: true } }, needs_person: 1, stopped: 0 },
        ],
        as_of: '2026-11-14T09:00:00Z',
        counts: { active: 'many', closed: 3 },
        total: '2',
      });
    await open('?q=works');
    expect([...rows()].map((r) => [...r.querySelectorAll('td')].map((td) => td.textContent))).toEqual([
      ['Alpha works', 'Ada Okafor', 'Planning', '—', '—', '—'],
      ['Beta works', 'Kunle Ade', 'Go-live', 'Go-live · due not known', '1', '0'],
    ]);
    expect(tabs().map((t) => t.textContent)).toEqual(['Active', 'Closed3', 'All I can see']);
    expect(document.querySelector('.psl-resultcount')!.textContent).toBe('2 shown');
  });
});

describe('search', () => {
  it('sends one q=lagoon&limit=20 request 300 ms after the last keystroke; clearing drops q', async () => {
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout', 'setInterval', 'clearInterval', 'Date'] });
    await open();
    const box = screen.getByRole('searchbox', { name: 'Search' });
    expect(box.getAttribute('placeholder')).toBe('Search projects or clients');
    for (const text of ['l', 'la', 'lag', 'lagoon']) {
      fireEvent.change(box, { target: { value: text } });
      await act(() => vi.advanceTimersByTimeAsync(100));
    }
    expect(calls).toHaveLength(1);
    await act(() => vi.advanceTimersByTimeAsync(199));
    expect(calls).toHaveLength(1);
    await act(() => vi.advanceTimersByTimeAsync(1));
    await until(() => expect(calls).toHaveLength(2));
    expect(calls[1].search).toBe('?limit=20&q=lagoon');
    expect(window.location.search).toBe('?q=lagoon');
    await until(() => expect(titles()).toEqual(['Lagoon Health · patient app']));
    expect(document.querySelector('.psl-resultcount')!.textContent).toBe('1 PROJECTS');
    expect(tabs()[0].textContent).toBe('Active22');

    fireEvent.change(box, { target: { value: '' } });
    await act(() => vi.advanceTimersByTimeAsync(300));
    await until(() => expect(calls).toHaveLength(3));
    expect(calls[2].searchParams.has('q')).toBe(false);
    expect(window.location.search).toBe('');
    expect(calls.every((c) => c.searchParams.get('q') !== '')).toBe(true);
  });

  it('no match shows No projects match; Clear search restores the full list', async () => {
    await open('?q=zzz');
    expect(query(calls[0])).toEqual({ limit: '20', q: 'zzz' });
    expect(screen.getByRole('heading', { name: 'No projects match' })).toBeTruthy();
    expect(document.querySelector('.psl-showmore')).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: 'Clear search' }));
    await until(() => expect(rows()).toHaveLength(20));
    expect(lastCall().searchParams.has('q')).toBe(false);
    expect((screen.getByRole('searchbox') as HTMLInputElement).value).toBe('');
  });

  it('zero projects without a search shows the empty state', async () => {
    respond = () => json(200, { items: [], as_of: '2026-11-14T09:00:00Z' });
    await open();
    expect(screen.getByRole('heading', { name: 'No projects you can see yet.' })).toBeTruthy();
    expect(screen.getByText('You see projects your roles cover.')).toBeTruthy();
    expect(screen.queryByRole('table')).toBeNull();
  });
});

describe('paging (D-PAGING r2)', () => {
  it('Show more sends cursor=o20&limit=20 and appends the rest, then All N showing with no button', async () => {
    await open();
    fireEvent.click(screen.getByRole('button', { name: 'Show more' }));
    await until(() => expect(screen.queryByRole('button', { name: 'Show more' })).toBeNull());
    expect(query(lastCall())).toEqual({ limit: '20', cursor: 'o20' });
    const all = fromMock(new URL('http://x/api/v1/projects?limit=50')).body.items;
    expect(titles()).toEqual(all.map((i) => i.title));
    expect(screen.getByText(`All ${all.length} showing`)).toBeTruthy();
    expect(document.querySelector('.psl-resultcount')!.textContent).toBe(`${all.length} PROJECTS`);
    expect(document.activeElement?.textContent).toBe(all[20].title);
  });

  it('Rows per page 10 sends limit=10 without a cursor and writes ?limit=10; a reload keeps it', async () => {
    await open();
    expect(radios().map((r) => [r.textContent, r.getAttribute('aria-checked')])).toEqual([
      ['10', 'false'],
      ['20', 'true'],
      ['50', 'false'],
    ]);
    fireEvent.click(radios()[0]);
    await until(() => expect(rows()).toHaveLength(10));
    expect(query(lastCall())).toEqual({ limit: '10' });
    expect(window.location.search).toBe('?limit=10');
  });

  it('?limit=10 loads 10; ?limit=7 falls back to 20', async () => {
    const first = await open('?limit=10');
    expect(query(calls[0])).toEqual({ limit: '10' });
    expect(rows()).toHaveLength(10);
    first.unmount();
    calls = [];
    await open('?limit=7');
    expect(query(calls[0])).toEqual({ limit: '20' });
  });

  it('arrow keys move the radiogroup selection with a roving tabindex', async () => {
    await open();
    radios()[1].focus();
    fireEvent.keyDown(radios()[1], { key: 'ArrowRight' });
    await until(() => expect(rows()).toHaveLength(22));
    expect(radios()[2].getAttribute('aria-checked')).toBe('true');
    expect(document.activeElement).toBe(radios()[2]);
    expect(radios().map((r) => r.tabIndex)).toEqual([-1, -1, 0]);
    expect(query(lastCall())).toEqual({ limit: '50' });
    fireEvent.keyDown(radios()[2], { key: 'ArrowRight' });
    await until(() => expect(query(lastCall())).toEqual({ limit: '10' }));
    fireEvent.keyDown(radios()[0], { key: 'ArrowLeft' });
    await until(() => expect(query(lastCall())).toEqual({ limit: '50' }));
  });

  it('a failed Show more keeps the loaded rows and shows the inline problem; Try again recovers', async () => {
    await open();
    respond = () => json(503, { code: 'unavailable', message: 'Down.' });
    fireEvent.click(screen.getByRole('button', { name: 'Show more' }));
    await until(() => expect(screen.getByText('We couldn’t load more. Nothing was changed.')).toBeTruthy());
    expect(document.querySelector('.psl-callout--problem')).toBeTruthy();
    expect(rows()).toHaveLength(20);
    respond = (url) => mockResponse(url);
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
    await until(() => expect(rows().length).toBeGreaterThan(20));
    expect(document.querySelector('.psl-callout--problem')).toBeNull();
  });
});

describe('access and failures', () => {
  it('without the projects destination: not open, and no E-PROJECTS request', async () => {
    persona = 'pm';
    const pm = me('pm');
    vi.mocked(fetch).mockImplementation(async (request) => {
      const url = new URL((request as Request).url);
      if (url.pathname === '/api/v1/me') return json(200, { ...pm, destinations: ['my_work', 'assistant'] });
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

  it('persona none (no destinations at all): the frame says no sections are open, and no E-PROJECTS request', async () => {
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
    ['404', () => json(404, { code: 'invalid_query', message: 'x' }), 'invalid_query'],
    ['network', () => Promise.reject(new TypeError('Failed to fetch')), 'network_error'],
    ['malformed 200 (the E-ME body)', () => json(200, me('finance_lead')), 'unexpected_response'],
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
    expect(query(lastCall())).toEqual({ limit: '20' });
  });

  it('loading shows status with no old rows; a late response for an earlier q is ignored', async () => {
    await open();
    const pending: Record<string, () => void> = {};
    respond = (url) =>
      new Promise<Response>((resolve) => (pending[url.searchParams.get('q') ?? ''] = () => resolve(mockResponse(url))));
    const box = screen.getByRole('searchbox', { name: 'Search' });
    fireEvent.change(box, { target: { value: 'lagoon' } });
    fireEvent.submit(box.closest('form')!);
    await until(() => expect(pending.lagoon).toBeTruthy());
    expect(screen.getByRole('status')).toBeTruthy();
    expect(rows()).toHaveLength(0);
    fireEvent.change(box, { target: { value: 'harmattan' } });
    fireEvent.submit(box.closest('form')!);
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
  it('below 720px each project is one card link: title, where it is · PM, then what needs a person', async () => {
    vi.stubGlobal('matchMedia', (q: string) => ({ matches: true, media: q, addEventListener: () => {}, removeEventListener: () => {} }));
    await open();
    expect(screen.queryByRole('table')).toBeNull();
    const cards = document.querySelectorAll('.projects__cards a');
    expect(cards).toHaveLength(20);
    expect(cards[0].getAttribute('href')).toBe('/projects/P-0101');
    expect(cards[0].textContent).toBe('Lagoon Health · patient appRelease · UAT with client · PM Tunde Bello2 need a person · 1 stopped');
    expect(cards[0].querySelector('.projects__attention')!.textContent).toBe('2 need a person · 1 stopped');
    expect(screen.getByRole('searchbox').getAttribute('placeholder')).toBe('Search projects');
    expect(screen.getByRole('button', { name: 'Filter' }).textContent).toBe('');
    expect(document.querySelector('.psl-seg--phone')).toBeTruthy();
  });

  it('no SAMPLE DATA by default; with the switch on, exactly one per sample row and none for sample: false', async () => {
    respond = () =>
      json(200, {
        items: [
          { case_id: 'P-1', title: 'Alpha works', pm: 'Ada Okafor', stage: 'Planning', sample: true },
          { case_id: 'P-2', title: 'Beta works', pm: 'Kunle Ade', stage: 'Go-live', sample: false },
        ],
        as_of: '2026-11-14T09:00:00Z',
      });
    const first = await open();
    expect(document.querySelector('.psl-sample')).toBeNull();
    first.unmount();
    vi.stubEnv('NEXT_PUBLIC_SHOW_SAMPLE_LABEL', '1');
    await open();
    expect([...rows()].map((r) => r.querySelectorAll('.psl-sample').length)).toEqual([1, 0]);
    expect(rows()[0].querySelector('.psl-sample')!.textContent).toBe('SAMPLE DATA');
  });
});
