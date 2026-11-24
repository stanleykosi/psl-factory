// @vitest-environment jsdom
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { useMemo, useSyncExternalStore } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ProjectJourneyPage } from '@/features/projects/ProjectJourney';
import { AppShell } from '@/shell/AppShell';

// @ts-expect-error plain ESM module without type declarations
import { projectTab } from '../mock/project-tabs.mjs';
// @ts-expect-error plain ESM module without type declarations
import { normaliseProjectPath, projects, uuidOf } from '../mock/projects.mjs';
import { bellFeed, isBellFeed, isRoleDashboard, roleDashboard } from './bell-feed';

// SCR-11 Registers and SCR-29 Actions on the live sectioned read, against the contract mock's handler.
const nav = vi.hoisted(() => ({ search: '', listeners: new Set<() => void>(), replaced: [] as string[] }));
vi.mock('next/navigation', () => ({
  usePathname: () => '/projects/P-0101/registers',
  useRouter: () => ({
    replace: (href: string) => {
      nav.replaced.push(href);
      nav.search = href.includes('?') ? href.slice(href.indexOf('?') + 1) : '';
      nav.listeners.forEach((l) => l());
    },
    push: vi.fn(),
    prefetch: vi.fn(),
  }),
  useSearchParams: () => {
    const search = useSyncExternalStore(
      (l) => {
        nav.listeners.add(l);
        return () => nav.listeners.delete(l);
      },
      () => nav.search,
      () => nav.search,
    );
    return useMemo(() => new URLSearchParams(search), [search]);
  },
}));

type Tab = 'registers' | 'actions';
type Body = { sections: { key: string; title: string; items: Record<string, unknown>[] }[] } & Record<string, unknown>;
const me = (persona: string) => JSON.parse(readFileSync(join(__dirname, `../mock/fixtures/me.${persona}.json`), 'utf8'));
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });

let persona = 'pm';
let respond: ((url: URL) => Response | Promise<Response> | undefined) | undefined;
let calls: URL[];

beforeEach(() => {
  persona = 'pm';
  respond = undefined;
  calls = [];
  nav.search = '';
  nav.replaced = [];
  vi.stubGlobal(
    'fetch',
    vi.fn(async (request: Request) => {
      if (isBellFeed(request)) return bellFeed();
      if (isRoleDashboard(request)) return roleDashboard();
      const url = new URL(request.url);
      if (url.pathname === '/api/v1/me') return json(200, me(persona));
      calls.push(url);
      const mockUrl = new URL(normaliseProjectPath(url.pathname) + url.search, url);
      const custom = respond?.(mockUrl);
      if (custom) return custom;
      const r = mockUrl.pathname.split('/').length > 5 ? projectTab({ url: mockUrl, persona, cookies: {} }) : projects({ operationId: 'E-PROJECT', url: mockUrl, persona });
      return json(r.status, r.body);
    }),
  );
});
afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

async function until(check: () => void, ms = 3000) {
  const end = Date.now() + ms;
  for (;;) {
    try {
      check();
      return;
    } catch (error) {
      if (Date.now() > end) throw error;
    }
    await act(async () => {
      await new Promise((r) => setTimeout(r, 5));
    });
  }
}

const tabCalls = () => calls.filter((u) => u.pathname.split('/').length > 5);
// a copy, so a test that edits a row never edits the fixture the next test reads
const served = (url: URL) => structuredClone(projectTab({ url, persona, cookies: {} }).body) as Body;

async function open(caseId: string, tab: Tab, search = '') {
  nav.search = search;
  const result = render(
    <AppShell>
      <ProjectJourneyPage caseId={caseId} tab={tab} />
    </AppShell>,
  );
  await until(() => expect(screen.queryByText('Loading…')).toBeNull());
  await until(() => expect(tabCalls().length).toBeGreaterThan(0));
  await until(() => expect(screen.queryByText('Loading…')).toBeNull());
  return result;
}

const text = () => document.body.textContent ?? '';
const rowsOf = () => [...document.querySelectorAll('tbody tr')].map((tr) => [...tr.children].map((c) => c.textContent));
const cardsOf = () => [...document.querySelectorAll('.ptabs__card')].map((c) => c.textContent);
const phone = () => vi.stubGlobal('matchMedia', (q: string) => ({ matches: q.includes('max-width'), media: q, addEventListener: () => {}, removeEventListener: () => {} }));
const registerTabs = () => within(screen.getByRole('tablist', { name: 'Register' })).getAllByRole('tab');
// What following a register link does: the address changes and the page re-renders (the link itself is next/link).
const toRegister = (search: string) =>
  act(() => {
    nav.search = search;
    nav.listeners.forEach((l) => l());
  });
const noAccess = () => screen.getByRole('heading', { level: 2, name: 'No access to this tab' });

describe('Registers (SCR-11)', () => {
  it('P-0101: one live read with no limit, register, cursor or filters; the drawn registers with the server totals', async () => {
    await open('P-0101', 'registers');
    expect(tabCalls()).toHaveLength(1);
    expect(tabCalls()[0].pathname).toBe(`/api/v1/projects/${uuidOf('P-0101')}/registers`);
    expect(tabCalls()[0].search).toBe('');
    expect(registerTabs().map((t) => t.textContent)).toEqual(['Issues 3', 'Changes 2', 'Emergencies 0', 'RFPs 1']);
    expect(registerTabs().map((t) => t.getAttribute('href'))).toEqual(['/projects/P-0101/registers', '/projects/P-0101/registers?register=changes', '/projects/P-0101/registers?register=emergencies', '/projects/P-0101/registers?register=rfps']);
    expect(document.querySelector('.psl-resultcount')!.textContent).toBe('3 ISSUES');
    expect(screen.queryByRole('button', { name: /filter/i })).toBeNull();
    expect(screen.getByRole('searchbox', { name: 'Search' }).getAttribute('placeholder')).toBe('Search issues by title or reference');
  });

  it('Issues rows: reference, issue title, severity as sent (Critical is its own tag), owner, age and state; no row is a link', async () => {
    await open('P-0101', 'registers');
    expect([...document.querySelectorAll('thead th')].map((th) => th.textContent)).toEqual(['ISSUE', 'WHAT', 'SEVERITY', 'OWNER', 'AGE', 'STATE']);
    expect(rowsOf()).toEqual([
      ['ISS-0233', 'Login fails on older Android phones', '■■■High', 'Tunde Bello', '2d', 'Fix in testing'],
      ['ISS-0229', 'Report totals round differently', 'Critical', 'Engineering', '4d', 'Waiting on Engineering'],
      ['ISS-0221', 'Slow search on patient list', '■□□Low', 'Owner needed', '—', 'Closed by QA and PM'],
    ]);
    expect(document.querySelector('.ptabs__noowner')!.textContent).toBe('Owner needed');
    expect(document.querySelector('tbody')!.querySelector('a')).toBeNull();
    expect(text()).toMatch(/As of 12 Nov 16:40/);
    expect(text()).toContain('Severity is set by the PM. Closing an issue needs QA and the PM; there is no separate approval.');
    expect(text()).not.toMatch(/recorded by PM|ISS-0240|Awaiting decision/);
  });

  it('age_days 0 reads 0d and a null age reads a dash, never 0d', async () => {
    respond = (url) => {
      if (!url.pathname.endsWith('/registers')) return undefined;
      const body = served(url);
      body.sections[0].items[0].age_days = 0;
      return json(200, body);
    };
    await open('P-0101', 'registers');
    expect(rowsOf().map((r) => r[4])).toEqual(['0d', '4d', '—']);
  });

  it('Changes, Emergencies and RFPs: one set of columns, a dash where live has no value, no owner role text', async () => {
    await open('P-0101', 'registers', 'register=changes');
    expect(registerTabs()[1].getAttribute('aria-selected')).toBe('true');
    expect(rowsOf()).toEqual([
      ['CHG-0031', 'Reminders', '—', '—', '—', 'Version 2'],
      ['CHG-0027', 'Visit list export', '—', '—', '—', 'Version 1'],
    ]);
    expect(document.querySelector('.psl-resultcount')!.textContent).toBe('2 CHANGES');
    cleanup();
    await open('P-0101', 'registers', 'register=rfps');
    expect(rowsOf()).toEqual([['RFP-0044', '—', '—', '—', '—', 'Bid request recorded']]);
    expect(text()).not.toMatch(/Owner needed|recorded by PM|outside/i);
    cleanup();
    await open('P-0101', 'registers', 'register=emergencies');
    expect(text()).toContain('No emergencies on this project yet.');
    expect(screen.getByRole('searchbox', { name: 'Search' }).getAttribute('placeholder')).toBe('Search emergencies by title or reference');
  });

  it('sections are matched by key: a renamed title still draws RFPs; an unknown key is not drawn', async () => {
    respond = (url) => {
      if (!url.pathname.endsWith('/registers')) return undefined;
      const body = served(url);
      body.sections = body.sections.filter((s) => s.key !== 'issues').map((s) => (s.key === 'rfp' ? { ...s, title: 'Renamed bids' } : s.key === 'changes' ? { ...s, key: 'mystery' } : s));
      return json(200, body);
    };
    await open('P-0101', 'registers');
    expect(registerTabs().map((t) => t.textContent)).toEqual(['Emergencies 0', 'RFPs 1']);
    expect(registerTabs()[0].getAttribute('aria-selected')).toBe('true');
  });

  it('a person with no issue.read sees the other registers; ?register=issues falls back to the first; none shows no access', async () => {
    persona = 'pmo_lead';
    await open('P-0101', 'registers', 'register=issues');
    expect(registerTabs().map((t) => t.textContent)).toEqual(['Changes 2', 'Emergencies 0', 'RFPs 1']);
    expect(registerTabs()[0].getAttribute('aria-selected')).toBe('true');
    expect(rowsOf()[0][0]).toBe('CHG-0031');
    cleanup();
    respond = (url) => (url.pathname.endsWith('/registers') ? json(200, { ...served(url), sections: [] }) : undefined);
    await open('P-0101', 'registers');
    expect(noAccess()).toBeTruthy();
    expect(screen.queryByRole('tablist', { name: 'Register' })).toBeNull();
  });

  it('arrow keys, Home and End move along the register tabs', async () => {
    await open('P-0101', 'registers');
    const tabs = registerTabs();
    tabs[0].focus();
    fireEvent.keyDown(tabs[0], { key: 'ArrowRight' });
    await waitFor(() => expect(document.activeElement).toBe(tabs[1]));
    fireEvent.keyDown(tabs[1], { key: 'End' });
    await waitFor(() => expect(document.activeElement).toBe(tabs[3]));
    fireEvent.keyDown(tabs[3], { key: 'Home' });
    await waitFor(() => expect(document.activeElement).toBe(tabs[0]));
  });

  it('P-0102 pages: 25 of 30 shown with the badge at 30, Show more asks page 2, appends 5 and goes; Changes is not doubled', async () => {
    await open('P-0102', 'registers');
    expect(rowsOf()).toHaveLength(25);
    expect(registerTabs()[0].textContent).toBe('Issues 30');
    expect(document.querySelector('.psl-resultcount')!.textContent).toBe('30 ISSUES');
    const more = screen.getByRole('button', { name: 'Show more' });
    more.focus();
    fireEvent.click(more);
    await until(() => expect(rowsOf()).toHaveLength(30));
    expect(tabCalls().at(-1)!.search).toBe('?page=2');
    expect(screen.queryByRole('button', { name: 'Show more' })).toBeNull();
    expect(registerTabs()[0].textContent).toBe('Issues 30');
    await waitFor(() => expect(document.activeElement).not.toBe(document.body));
    expect(registerTabs()[1].getAttribute('href')).toBe('/projects/P-0102/registers?register=changes');
    toRegister('register=changes');
    await until(() => expect(rowsOf()).toHaveLength(1));
    expect(rowsOf()).toEqual([['CHG-0090', 'Biometric login', '—', '—', '—', 'Version 1']]);
    expect(tabCalls()).toHaveLength(2);
  });

  it('the Show more button follows the selected register: Changes has none while Issues has more', async () => {
    await open('P-0102', 'registers', 'register=changes');
    expect(screen.queryByRole('button', { name: 'Show more' })).toBeNull();
  });

  it('a failed Show more keeps every row and says so; Retry loads page 2', async () => {
    let fail = true;
    respond = (url) => (fail && url.searchParams.get('page') === '2' ? json(503, { code: 'unavailable', message: 'x' }) : undefined);
    await open('P-0102', 'registers');
    fireEvent.click(screen.getByRole('button', { name: 'Show more' }));
    await until(() => expect(screen.getByRole('alert').textContent).toBe('We couldn’t load more. Your rows are safe; try again.'));
    expect(rowsOf()).toHaveLength(25);
    fail = false;
    fireEvent.click(screen.getByRole('button', { name: 'Retry' }));
    await until(() => expect(rowsOf()).toHaveLength(30));
    expect(screen.queryByRole('alert')).toBeNull();
  });

  it('a search is one read; switching register does not read again; changing the search reads from page 1 with the server counts', async () => {
    await open('P-0102', 'registers', 'q=biometric');
    expect(tabCalls()).toHaveLength(1);
    expect(tabCalls()[0].search).toBe('?q=biometric');
    expect(registerTabs().map((t) => t.textContent)).toEqual(['Issues 6', 'Changes 1', 'Emergencies 0', 'RFPs 0']);
    expect(registerTabs()[1].getAttribute('href')).toBe('/projects/P-0102/registers?register=changes&q=biometric');
    toRegister('register=changes&q=biometric');
    await until(() => expect(registerTabs()[1].getAttribute('aria-selected')).toBe('true'));
    expect(tabCalls()).toHaveLength(1);
    fireEvent.change(screen.getByRole('searchbox', { name: 'Search' }), { target: { value: 'android' } });
    await until(() => expect(nav.replaced.at(-1)).toBe('/projects/P-0102/registers?register=changes&q=android'));
    await until(() => expect(tabCalls()).toHaveLength(2));
    expect(tabCalls()[1].search).toBe('?q=android');
  });

  it('empty-search and empty-register sentences; Clear search clears q', async () => {
    await open('P-0101', 'registers', 'q=zzz');
    expect(text()).toContain('No issues match “zzz”.');
    fireEvent.click(document.querySelector<HTMLElement>('.psl-empty button')!);
    expect(nav.replaced.at(-1)).toBe('/projects/P-0101/registers');
    cleanup();
    await open('P-0106', 'registers');
    expect(text()).toContain('No issues on this project yet.');
    expect(registerTabs().map((t) => t.textContent)).toEqual(['Issues 0', 'Changes 0', 'Emergencies 0', 'RFPs 0']);
  });

  it('phone: a strip of registers and one card per row; a part that reads a dash is left out', async () => {
    phone();
    await open('P-0101', 'registers');
    expect(screen.getByRole('tablist', { name: 'Register' }).className).toContain('psl-tabs--strip');
    expect(screen.getByRole('searchbox', { name: 'Search' }).getAttribute('placeholder')).toBe('Search issues');
    expect(cardsOf()).toEqual([
      'ISS-0233■■■HighLogin fails on older Android phonesFix in testing · Tunde Bello · 2d',
      'ISS-0229CriticalReport totals round differentlyWaiting on Engineering · Engineering · 4d',
      'ISS-0221■□□LowSlow search on patient listClosed by QA and PM · Owner needed',
    ]);
  });
});

describe('Actions (SCR-29)', () => {
  it('P-0101: the header from the server counts, nine rows, owners, due dates, state tags and the From line', async () => {
    await open('P-0101', 'actions');
    expect(tabCalls()[0].search).toBe('');
    expect(document.querySelector('.psl-resultcount')!.textContent).toBe('9 ACTIONS · 2 OVERDUE · 1 WITHOUT OWNER');
    expect([...document.querySelectorAll('thead th')].map((th) => th.textContent)).toEqual(['ACTION', 'OWNER', 'DUE', 'STATE']);
    const rows = rowsOf();
    expect(rows).toHaveLength(9);
    expect(rows[0]).toEqual(['Send test accounts for UATFrom Weekly sync · 10 Nov', 'Lagoon Health', '13 Nov', 'OPEN']);
    expect(rows[2]).toEqual(['Assess the SMS reminders changeFrom Weekly sync · 10 Nov', 'Owner needed', 'Unknown', 'OPEN']);
    expect(rows[4].slice(1)).toEqual(['Lagoon Health', '06 Nov', 'IN PROGRESS']);
    expect(rows[5]).toEqual(['Book go-live call', 'Tunde Bello', '20 Nov', 'OPEN']);
    expect(rows[6].slice(1)).toEqual(['Lagoon Health', '01 Nov', 'COMPLETED']);
    expect(rows[8].slice(1)).toEqual(['Engineering', '18 Nov', 'PAUSED']);
    expect(text()).not.toMatch(/OVERDUE(?! ·)/);
    expect(document.querySelector('tbody')!.querySelector('a')).toBeNull();
    expect(text()).toContain('Actions come from confirmed minutes.');
    expect(text()).toMatch(/As of 12 Nov 16:40/);
  });

  it('state tones come from the state code: completed is done, an unknown code is neutral', async () => {
    respond = (url) => {
      if (!url.pathname.endsWith('/actions')) return undefined;
      const body = served(url);
      body.sections[0].items[0].state_code = 'surprise';
      return json(200, body);
    };
    await open('P-0101', 'actions');
    const tags = [...document.querySelectorAll('tbody .psl-tag')];
    expect(tags[0].className).toContain('psl-tag--neutral');
    expect(tags[1].className).toContain('psl-tag--waiting');
    expect(tags[6].className).toContain('psl-tag--done');
  });

  it('a null counts draws no header; a null owner and a null due read Owner needed and Unknown, never 0', async () => {
    respond = (url) => {
      if (!url.pathname.endsWith('/actions')) return undefined;
      const body = served(url) as Body & { sections: { counts: unknown }[] };
      body.sections[0].counts = null;
      body.sections[0].items[3].detail = null;
      return json(200, body);
    };
    await open('P-0101', 'actions');
    expect(document.querySelector('.psl-resultcount')!.textContent).toBe('');
    expect(rowsOf()[3].slice(1, 3)).toEqual(['Owner needed', '04 Nov']);
    expect(text()).not.toMatch(/\b0 ACTIONS/);
  });

  it('with a search the header is the matching total, from the server', async () => {
    await open('P-0101', 'actions', 'q=uat');
    expect(tabCalls()[0].search).toBe('?q=uat');
    expect(document.querySelector('.psl-resultcount')!.textContent).toBe('3 actions match “uat”');
    expect(rowsOf()).toHaveLength(3);
  });

  it('P-0102: no meeting reads as no From line, a null due as Unknown', async () => {
    await open('P-0102', 'actions');
    expect(rowsOf()[0]).toEqual(['Collect the bank sign-off', 'Amina Yusuf', 'Unknown', 'OPEN']);
    expect(document.querySelector('.psl-resultcount')!.textContent).toBe('4 ACTIONS · 1 OVERDUE · 1 WITHOUT OWNER');
  });

  it('phone cards: title with its state tag, the From line, then owner and due', async () => {
    phone();
    await open('P-0101', 'actions');
    expect(cardsOf()[0]).toBe('Send test accounts for UATOPENFrom Weekly sync · 10 NovLagoon Health · due 13 Nov');
    expect(cardsOf()[5]).toBe('Book go-live callOPENTunde Bello · due 20 Nov');
  });

  it('P-0106: the section is there and empty: the sentence and a known 0 header', async () => {
    await open('P-0106', 'actions');
    expect(text()).toContain('No actions on this project yet.');
    expect(document.querySelector('.psl-resultcount')!.textContent).toBe('0 ACTIONS · 0 OVERDUE · 0 WITHOUT OWNER');
  });

  it('a response without the meetings section shows no access', async () => {
    respond = (url) => (url.pathname.endsWith('/actions') ? json(200, { ...served(url), sections: [] }) : undefined);
    await open('P-0101', 'actions');
    expect(noAccess()).toBeTruthy();
  });
});

describe('access and errors', () => {
  it('P-0103 (403), a 404 and a 403 after a search show the same state with no row text', async () => {
    await open('P-0103', 'registers');
    expect(noAccess()).toBeTruthy();
    cleanup();
    respond = (url) => (url.pathname.endsWith('/actions') ? json(404, { code: 'not_found', message: 'x' }) : undefined);
    await open('P-0101', 'actions');
    expect(noAccess()).toBeTruthy();
    expect(text()).not.toContain('Send test accounts');
    cleanup();
    respond = undefined;
    await open('P-0101', 'actions');
    expect(rowsOf()).toHaveLength(9);
    respond = (url) => (url.searchParams.has('q') ? json(403, { code: 'forbidden', message: 'x' }) : undefined);
    fireEvent.change(screen.getByRole('searchbox', { name: 'Search' }), { target: { value: 'sms' } });
    await until(() => expect(noAccess()).toBeTruthy());
    expect(text()).not.toMatch(/Send test accounts|Weekly sync/);
  });

  it('a 401 signs in back to the tab with its query', async () => {
    respond = (url) => (url.pathname.endsWith('/registers') ? json(401, { code: 'not_signed_in', message: 'x' }) : undefined);
    await open('P-0101', 'registers', 'register=changes&q=sms');
    expect(screen.getByRole('link', { name: 'Sign in' }).getAttribute('href')).toBe('/sign-in?next=%2Fprojects%2FP-0101%2Fregisters%3Fregister%3Dchanges%26q%3Dsms');
  });

  it('a 422, a 503 and a malformed 200 show the error card; Try again sends one new request', async () => {
    for (const bad of [() => json(422, { code: 'invalid_filter', message: 'x' }), () => json(503, { code: 'unavailable', message: 'x' }), () => json(200, { case_id: 'c', tab: 'actions', as_of: 'x', sections: [] }), () => json(200, { case_id: 'c', tab: 'registers', as_of: 'x', sections: [{ key: 'issues', title: 'Issues', items: [] }] })]) {
      let fail = true;
      respond = (url) => (fail && url.pathname.endsWith('/registers') ? bad() : undefined);
      await open('P-0101', 'registers');
      expect(screen.getByText('We couldn’t load this tab. Your work is safe; nothing was changed.')).toBeTruthy();
      const before = tabCalls().length;
      fail = false;
      fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
      await until(() => expect(rowsOf()).toHaveLength(3));
      expect(tabCalls()).toHaveLength(before + 1);
      cleanup();
      calls = [];
    }
  });

  it('makes no further request in 60 s (no polling)', async () => {
    await open('P-0101', 'registers');
    const before = calls.length;
    vi.useFakeTimers();
    await act(async () => {
      vi.advanceTimersByTime(60_000);
    });
    vi.useRealTimers();
    expect(calls).toHaveLength(before);
  });
});
