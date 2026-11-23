// @vitest-environment jsdom
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { setImmediate as realImmediate } from 'node:timers';

import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { useMemo, useSyncExternalStore } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ListToolbar } from '@/components';
import { ProjectJourneyPage } from '@/features/projects/ProjectJourney';
import { AppShell } from '@/shell/AppShell';

// @ts-expect-error plain ESM module without type declarations
import { projectTab } from '../mock/project-tabs.mjs';
// @ts-expect-error plain ESM module without type declarations
import { normaliseProjectPath, projects, uuidOf } from '../mock/projects.mjs';
import { bellFeed, isBellFeed, isRoleDashboard, roleDashboard } from './bell-feed';

// The URL of the page: replace() rewrites it and the page re-renders, as the router does.
const nav = vi.hoisted(() => {
  const state = { search: '', listeners: new Set<() => void>(), replaced: [] as string[] };
  return state;
});
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

type Tab = 'milestones' | 'documents' | 'registers' | 'actions';
const me = (persona: string) => JSON.parse(readFileSync(join(__dirname, `../mock/fixtures/me.${persona}.json`), 'utf8'));
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });

let persona = 'pm';
let cookies: Record<string, string>;
let respond: ((url: URL) => Response | Promise<Response> | undefined) | undefined;
let calls: URL[];

beforeEach(() => {
  persona = 'pm';
  cookies = {};
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
      // the mock server names a project by its P-nnnn id for the tab fixtures (normaliseProjectPath); the request keeps the UUID
      const mockUrl = new URL(normaliseProjectPath(url.pathname) + url.search, url);
      const custom = respond?.(mockUrl);
      if (custom) return custom;
      const r = mockUrl.pathname.split('/').length > 5 ? projectTab({ url: mockUrl, persona, cookies }) : projects({ operationId: 'E-PROJECT', url: mockUrl, persona });
      return json(r.status, r.body);
    }),
  );
});
afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
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
const phone = () =>
  vi.stubGlobal('matchMedia', (q: string) => ({ matches: q.includes('max-width'), media: q, addEventListener: () => {}, removeEventListener: () => {} }));

describe('Milestones (SCR-38)', () => {
  it('P-0101: the four milestones in returned order, one read, facts kept separate, no totals', async () => {
    await open('P-0101', 'milestones');
    expect(calls.map((u) => u.pathname)).toEqual(['/api/v1/projects/P-0101', `/api/v1/projects/${uuidOf('P-0101')}/milestones`]);
    expect(tabCalls()[0].search).toBe('?limit=10');
    expect(screen.getByRole('heading', { level: 1 }).textContent).toBe('Lagoon Health · patient app');
    expect(screen.getByRole('tab', { name: /^Milestones/ }).getAttribute('aria-selected')).toBe('true');
    expect(document.querySelector('.ptabs__route')!.textContent).toBe('PM Tunde Bello · Route A');
    expect([...document.querySelectorAll('thead th')].map((th) => th.textContent)).toEqual(['MILESTONE', 'CONTRACT AMOUNT', 'COMPLETION', 'INVOICE', 'PAID']);
    expect(rowsOf()).toEqual([
      ['1 · Kick-off', '₦3,000,000.00', 'Done 27 Oct · proof', 'INV-0398 · Verified', 'Part paid · ₦500,000.00 owed'],
      ['2 · UAT sign-off', '₦4,250,000.00', 'Done 11 Nov · client UAT sign-off', 'INV-0412 · Waiting', '—'],
      ['3 · Go-live', '₦4,250,000.00', 'Not yet', '—', '—'],
      ['4 · Hypercare', 'Unknown', 'Not yet · amount set at go-live', '—', '—'],
    ]);
    expect(document.querySelector('.psl-unknown')!.textContent).toBe('Unknown');
    expect(screen.getByRole('link', { name: 'INV-0398' }).getAttribute('href')).toBe('/work/W-1713');
    expect(text()).toContain('Milestones and amounts come from the signed SOW.');
    expect(text()).toMatch(/As of 12 Nov 16:40/);
    expect(text()).not.toMatch(/₦0(\.00)?(?![\d,])/);
    expect(screen.queryByRole('link', { name: /complete/i })).toBeNull();
    expect(screen.queryByRole('button', { name: /complete/i })).toBeNull();
    expect(document.querySelector('form')).toBeNull();
  });

  it('makes no further request in 60 s (no polling)', async () => {
    await open('P-0101', 'milestones');
    const before = calls.length;
    vi.useFakeTimers();
    await act(async () => {
      vi.advanceTimersByTime(60_000);
    });
    vi.useRealTimers();
    expect(calls).toHaveLength(before);
  });

  it('changed: a CHANGES column links the change; the amount reads next to the change, never added; INVOICE and PAID stay', async () => {
    cookies = { psl_mock_milestones: 'changed' };
    await open('P-0101', 'milestones');
    expect([...document.querySelectorAll('thead th')].map((th) => th.textContent)).toEqual(['MILESTONE', 'CONTRACT AMOUNT', 'COMPLETION', 'INVOICE', 'PAID', 'CHANGES']);
    const golive = rowsOf()[2];
    expect(golive[1]).toBe('₦4,250,000.00 + the change · change amount Unknown');
    expect(golive[5]).toBe('CR-0031 · SMS reminders');
    expect(screen.getByRole('link', { name: 'CR-0031 · SMS reminders' }).getAttribute('href')).toBe('/work/W-1005');
    expect(rowsOf()[0][5]).toBe('—');
    expect(rowsOf()[0][3]).toBe('INV-0398 · Verified');
    expect(text()).not.toContain('SOW amendment');
  });

  it('phone: one card per milestone with the paid line and the CHANGED tag', async () => {
    phone();
    cookies = { psl_mock_milestones: 'changed' };
    await open('P-0101', 'milestones');
    expect(cardsOf()).toEqual([
      '1 · Kick-off₦3,000,000.00 · Done 27 Oct · proofINV-0398 · VerifiedPaid: Part paid · ₦500,000.00 owed',
      '2 · UAT sign-off₦4,250,000.00 · Done 11 Nov · client UAT sign-offINV-0412 · WaitingPaid: —',
      '3 · Go-live₦4,250,000.00 + the change · change amount Unknown · Not yet—Paid: —CHANGED · CR-0031',
      '4 · HypercareUnknown · Not yet · amount set at go-live—Paid: —',
    ]);
    expect(screen.getByRole('link', { name: 'CHANGED · CR-0031' }).getAttribute('href')).toBe('/work/W-1005');
  });

  it('P-0102: unknown stays Unknown, each paid status is its own word, a known change amount is not added', async () => {
    await open('P-0102', 'milestones');
    const rows = rowsOf();
    expect(rows[0]).toEqual(['1 · Discovery', 'Unknown', 'Done', '—', 'Unknown', '—']);
    expect(rows[1]).toEqual(['2 · Design (billed in USD)', 'USD 1,250,000.50', 'Not yet', '—', 'Paid', '—']);
    expect(rows[2][1]).toBe('₦9,500,000.00 + the change · change amount ₦750,000.00');
    expect(rows[2].slice(2)).toEqual(['Done 05 Nov · build sign-off', 'INV-0501 · Verified', '—', 'CR-0090 · Biometric login']);
    expect(rows[3]).toEqual(['4 · Pilot', '₦2,000,000.00 + the change · change amount Unknown', 'Done 08 Nov · proof', 'INV-0502 · Ready to continue', 'Part paid · Unknown owed', 'CR-0091 · Dark mode']);
    expect(rows[4][4]).toBe('Not paid · ₦3,000,000.00 owed');
    expect(rows[5][4]).toBe('Not due');
    expect(rows[6][4]).toBe('Tracked by Finance');
    // a not-yet milestone with an invoice still reads Not yet; the invoice is never read for paid
    expect(rows[4].slice(2, 4)).toEqual(['Not yet', 'INV-0503 · Action needed']);
    expect(text()).not.toContain('2,750,000');
    expect(text()).not.toContain('10,250,000');
    expect(text()).not.toMatch(/₦0(\.00)?(?![\d,])/);
  });

  it('an invoice without a state, or with one the contract does not list, reads Unknown, never a blank status', async () => {
    respond = (url) => {
      if (!url.pathname.endsWith('/milestones')) return undefined;
      const body = projectTab({ url, persona, cookies }).body;
      body.milestones[0].invoice = { reference: 'INV-0398' };
      body.milestones[1].invoice = { reference: 'INV-0412', state: 'surprise' };
      return json(200, body);
    };
    await open('P-0101', 'milestones');
    expect(rowsOf()[0][3]).toBe('INV-0398 · Unknown');
    expect(rowsOf()[1][3]).toBe('INV-0412 · Unknown');
  });

  it('P-0106 shows the empty sentence once and no table', async () => {
    await open('P-0106', 'milestones');
    expect(text()).toContain('No milestones on this project yet.');
    expect(text().split('No milestones on this project yet.')).toHaveLength(2);
    expect(document.querySelector('table')).toBeNull();
    expect(text()).not.toContain('As of');
  });
});

describe('Registers (SCR-11)', () => {
  it('Issues by default: tabs with counts, search without Filter, rows, footer; one read with register=issues', async () => {
    await open('P-0101', 'registers');
    expect(tabCalls()).toHaveLength(1);
    expect(tabCalls()[0].search).toBe('?limit=10&register=issues');
    const tabs = within(screen.getByRole('tablist', { name: 'Register' })).getAllByRole('tab');
    expect(tabs.map((t) => t.textContent)).toEqual(['Issues 3', 'Changes 2', 'Emergencies 0', 'RFPs 1']);
    expect(tabs.map((t) => t.getAttribute('href'))).toEqual(['/projects/P-0101/registers', '/projects/P-0101/registers?register=changes', '/projects/P-0101/registers?register=emergencies', '/projects/P-0101/registers?register=rfps']);
    expect(tabs[0].getAttribute('aria-selected')).toBe('true');
    expect(document.querySelector('.psl-resultcount')!.textContent).toBe('3 ISSUES');
    expect(screen.queryByRole('button', { name: /filter/i })).toBeNull();
    expect(screen.getByRole('searchbox', { name: 'Search' }).getAttribute('placeholder')).toBe('Search issues by title or reference');
    expect([...document.querySelectorAll('thead th')].map((th) => th.textContent)).toEqual(['ISSUE', 'WHAT', 'SEVERITY', 'OWNER', 'STATE', 'AGE']);
    expect(rowsOf()).toEqual([
      ['ISS-0233', 'Login fails on older Android phones', '■■■High', 'PM · Tunde Bello', 'Fix in testing', '2d'],
      ['ISS-0229', 'Report totals round differently', '■■□Medium', 'Engineering (recorded by PM)', 'Waiting on Engineering', '4d'],
      ['ISS-0221', 'Slow search on patient list', '■□□Low', 'PM · Tunde Bello', 'Closed by QA and PM', 'Unknown'],
    ]);
    expect(text()).toContain('Severity is set by the PM. Closing an issue needs QA and the PM; there is no separate approval.');
    // only a row with a work_id opens its work item
    expect(screen.getByRole('link', { name: 'Login fails on older Android phones' }).getAttribute('href')).toBe('/work/W-2411');
    expect(screen.queryByRole('link', { name: 'Report totals round differently' })).toBeNull();
  });

  it('an unknown ?register= reads as Issues; ?register=changes requests changes and selects it', async () => {
    await open('P-0101', 'registers', 'register=x');
    expect(tabCalls()[0].searchParams.get('register')).toBe('issues');
    cleanup();
    calls = [];
    await open('P-0101', 'registers', 'register=changes');
    expect(tabCalls()[0].searchParams.get('register')).toBe('changes');
    expect(screen.getByRole('tab', { name: /^Changes/ }).getAttribute('aria-selected')).toBe('true');
    expect(rowsOf().map((r) => r[0])).toEqual(['CR-0031', 'CR-0027']);
    expect(document.querySelector('.psl-resultcount')!.textContent).toBe('2 CHANGES');
  });

  it('arrow keys, Home and End move along the register tabs', async () => {
    await open('P-0101', 'registers');
    const tabs = within(screen.getByRole('tablist', { name: 'Register' })).getAllByRole('tab');
    tabs[0].focus();
    fireEvent.keyDown(tabs[0], { key: 'ArrowRight' });
    await waitFor(() => expect(document.activeElement).toBe(tabs[1]));
    fireEvent.keyDown(tabs[1], { key: 'End' });
    await waitFor(() => expect(document.activeElement).toBe(tabs[3]));
    fireEvent.keyDown(tabs[3], { key: 'Home' });
    await waitFor(() => expect(document.activeElement).toBe(tabs[0]));
  });

  it('search writes ?q= after the pause, requests q, and clearing removes it', async () => {
    await open('P-0101', 'registers');
    const box = screen.getByRole('searchbox', { name: 'Search' });
    fireEvent.change(box, { target: { value: 'android' } });
    await until(() => expect(nav.replaced).toEqual(['/projects/P-0101/registers?q=android']));
    await until(() => expect(tabCalls().at(-1)!.searchParams.get('q')).toBe('android'));
    await until(() => expect(rowsOf().map((r) => r[0])).toEqual(['ISS-0233']));
    expect(tabCalls().at(-1)!.searchParams.has('cursor')).toBe(false);
    fireEvent.change(box, { target: { value: '' } });
    await until(() => expect(nav.replaced.at(-1)).toBe('/projects/P-0101/registers'));
    await until(() => expect(tabCalls().at(-1)!.searchParams.has('q')).toBe(false));
  });

  it('empty register and no-match sentences; Clear search clears q', async () => {
    await open('P-0101', 'registers', 'register=emergencies');
    expect(text()).toContain('No emergencies on this project yet.');
    cleanup();
    await open('P-0101', 'registers', 'q=zzz');
    expect(text()).toContain('No issues match “zzz”.');
    fireEvent.click(document.querySelector<HTMLElement>('.psl-empty button')!);
    expect(nav.replaced.at(-1)).toBe('/projects/P-0101/registers');
  });

  it('P-0102 pages by cursor: 10 rows, Show more appends the next, focus is kept, no cursor in the URL', async () => {
    vi.stubEnv('NEXT_PUBLIC_SHOW_SAMPLE_LABEL', '1');
    await open('P-0102', 'registers');
    expect(rowsOf()).toHaveLength(10);
    expect(text()).toContain('10 showing');
    expect(rowsOf()[1][1]).toContain('SAMPLE DATA');
    expect(rowsOf()[3][3]).toBe('No owner');
    expect(rowsOf()[4][4]).toBe('—');
    expect(rowsOf()[5][5]).toBe('Unknown');
    const more = screen.getByRole('button', { name: 'Show more' });
    more.focus();
    fireEvent.click(more);
    await until(() => expect(rowsOf()).toHaveLength(20));
    expect(tabCalls().at(-1)!.searchParams.get('cursor')).toBe('o10');
    fireEvent.click(screen.getByRole('button', { name: 'Show more' }));
    await until(() => expect(rowsOf()).toHaveLength(25));
    const second = tabCalls().at(-1)!;
    expect(second.searchParams.get('cursor')).toBe('o20');
    expect(second.searchParams.get('register')).toBe('issues');
    expect(screen.queryByRole('button', { name: 'Show more' })).toBeNull();
    await waitFor(() => expect(document.activeElement).not.toBe(document.body));
    expect(nav.replaced).toEqual([]);
  });

  it('phone: register tabs as a strip and one card per row', async () => {
    phone();
    await open('P-0101', 'registers');
    expect(screen.getByRole('tablist', { name: 'Register' }).className).toContain('psl-tabs--strip');
    expect(screen.getByRole('searchbox', { name: 'Search' }).getAttribute('placeholder')).toBe('Search issues');
    expect(cardsOf()[0]).toBe('ISS-0233■■■HighLogin fails on older Android phonesFix in testing · PM · Tunde Bello');
    expect(cardsOf()).toHaveLength(3);
  });
});

describe('Actions (SCR-29)', () => {
  it('P-0101: the header counts, nine rows, owners, due dates, state tags and the footer', async () => {
    await open('P-0101', 'actions');
    expect(tabCalls()[0].search).toBe('?limit=10');
    expect(document.querySelector('.psl-resultcount')!.textContent).toBe('9 ACTIONS · 3 OVERDUE · 1 WITHOUT OWNER');
    expect(screen.getByRole('searchbox', { name: 'Search' }).getAttribute('placeholder')).toBe('Search actions');
    expect(screen.queryByRole('button', { name: /filter/i })).toBeNull();
    const rows = rowsOf();
    expect(rows).toHaveLength(9);
    expect(rows[0]).toEqual(['Send test accounts for UATFrom Weekly sync · 10 Nov', 'Client · Lagoon Health', '13 Nov', 'OPEN']);
    expect(rows[1].slice(1)).toEqual(['Engineering (recorded by PM)', '15 Nov', 'OPEN']);
    expect(rows[2].slice(1)).toEqual(['No owner', 'Unknown', 'OPEN']);
    expect(rows[3].slice(1)).toEqual(['Tunde Bello', '04 Nov', 'OVERDUE']);
    expect(rows[6].slice(1)).toEqual(['Client · Lagoon Health', '01 Nov', 'DONE']);
    expect(text()).toContain('Actions come from confirmed minutes.');
    expect(text()).not.toContain('recorded with your name');
    expect(screen.getByRole('link', { name: 'Assess the SMS reminders change' }).getAttribute('href')).toBe('/work/W-1006');
    expect(screen.queryByRole('link', { name: 'Send test accounts for UAT' })).toBeNull();
  });

  it('P-0102: no meeting and no due date read as nothing and Unknown', async () => {
    await open('P-0102', 'actions');
    expect(rowsOf()[0]).toEqual(['Collect the bank sign-off', 'Amina Yusuf', 'Unknown', 'OPEN']);
  });

  it('phone cards: title with its state tag, then owner and due', async () => {
    phone();
    await open('P-0101', 'actions');
    expect(cardsOf()[0]).toBe('Send test accounts for UATOPENClient · Lagoon Health · due 13 Nov');
    expect(cardsOf()[2]).toBe('Assess the SMS reminders changeOPENNo owner · due Unknown');
  });

  it('P-0106: the empty sentence and no count text', async () => {
    await open('P-0106', 'actions');
    expect(text()).toContain('No actions on this project yet.');
    expect(document.querySelector('.psl-resultcount')!.textContent).toBe('');
  });
});

describe('access and errors (all tabs)', () => {
  it('P-0103: the tab answers 403; the header and tab bar stay and no fixture text is shown', async () => {
    await open('P-0103', 'milestones');
    expect(screen.getByRole('heading', { level: 1 }).textContent).toBe('Kora Logistics · fleet tracker');
    expect(screen.getByRole('heading', { level: 2, name: 'No access to this tab' })).toBeTruthy();
    expect(text()).not.toMatch(/Kick-off|INV-|₦/);
    expect(screen.getByRole('tablist', { name: 'Project' })).toBeTruthy();
  });

  it('a 404 on the tab shows the same state', async () => {
    respond = (url) => (url.pathname.endsWith('/actions') ? json(404, { code: 'not_found', message: 'x' }) : undefined);
    await open('P-0101', 'actions');
    expect(screen.getByRole('heading', { level: 2, name: 'No access to this tab' })).toBeTruthy();
    expect(text()).not.toContain('Send test accounts');
  });

  it('a 403 after a successful page (search) removes the earlier rows', async () => {
    await open('P-0101', 'actions');
    expect(rowsOf()).toHaveLength(9);
    respond = (url) => (url.searchParams.has('q') ? json(403, { code: 'forbidden', message: 'x' }) : undefined);
    fireEvent.change(screen.getByRole('searchbox', { name: 'Search' }), { target: { value: 'sms' } });
    await until(() => expect(screen.getByRole('heading', { level: 2, name: 'No access to this tab' })).toBeTruthy());
    expect(text()).not.toMatch(/Send test accounts|Weekly sync/);
  });

  it('P-0099: F-07 no-access page and no tab request', async () => {
    nav.search = '';
    render(
      <AppShell>
        <ProjectJourneyPage caseId="P-0099" tab="milestones" />
      </AppShell>,
    );
    await until(() => expect(screen.getByRole('heading', { name: /can.t open this project/ })).toBeTruthy());
    expect(tabCalls()).toHaveLength(0);
  });

  it('a 401 on the tab signs in back to the tab with its query', async () => {
    respond = (url) => (url.pathname.endsWith('/registers') ? json(401, { code: 'not_signed_in', message: 'x' }) : undefined);
    await open('P-0101', 'registers', 'register=changes&q=sms');
    expect(screen.getByRole('link', { name: 'Sign in' }).getAttribute('href')).toBe('/sign-in?next=%2Fprojects%2FP-0101%2Fregisters%3Fregister%3Dchanges%26q%3Dsms');
  });

  it('a 500 and a network failure show the error card; Retry sends exactly one new request', async () => {
    let fail: 'server' | 'network' | undefined = 'server';
    respond = (url) => {
      if (!url.pathname.endsWith('/milestones') || !fail) return undefined;
      if (fail === 'network') throw new TypeError('Failed to fetch');
      return json(500, { code: 'server_error', message: 'x' });
    };
    await open('P-0101', 'milestones');
    expect(screen.getByText('We couldn’t load this tab. Your work is safe; nothing was changed.')).toBeTruthy();
    expect(tabCalls()).toHaveLength(1);
    fail = 'network';
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
    await until(() => expect(tabCalls()).toHaveLength(2));
    await until(() => expect(screen.getByText('We couldn’t load this tab. Your work is safe; nothing was changed.')).toBeTruthy());
    await act(async () => {
      await new Promise((r) => realImmediate(r));
    });
    expect(tabCalls()).toHaveLength(2);
    fail = undefined;
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
    await until(() => expect(rowsOf()).toHaveLength(4));
    expect(tabCalls()).toHaveLength(3);
  });

  it('every role gets the same columns for the same fixture', async () => {
    await open('P-0101', 'milestones');
    const pm = rowsOf();
    cleanup();
    persona = 'finance_lead';
    await open('P-0101', 'milestones');
    expect(rowsOf()).toEqual(pm);
  });

  it('documents lists the project\u2019s documents; only a row with a work_id opens its review', async () => {
    await open('P-0101', 'documents');
    const rows = within(screen.getByRole('table', { name: 'Documents' })).getAllByRole('row').slice(1);
    expect(rows).toHaveLength(6);
    const link = within(rows[0]).getByRole('link', { name: 'Statement of work' });
    expect(link.getAttribute('href')).toBe(`/projects/${uuidOf('P-0101')}/documents/D-2901?v=2`);
    expect(rows[0].textContent).toContain('v2');
    expect(rows[0].textContent).toContain('Awaiting PMO Lead review');
    expect(rows[0].textContent).toContain('TEST TEMPLATE');
    expect(within(rows[1]).queryByRole('link')).toBeNull();
    expect(rows[1].textContent).toContain('Costing COST-0140');
    expect(rows[2].textContent).toContain('Weekly sync minutes');
    expect(tabCalls().map((u) => u.pathname)).toEqual([`/api/v1/projects/${uuidOf('P-0101')}/documents`]);
  });

  it('documents of a project with none says so', async () => {
    await open('P-0106', 'documents');
    expect(screen.getByRole('heading', { level: 2, name: 'No documents on this project yet.' })).toBeTruthy();
  });
});

describe('ListToolbar without a Filter handler', () => {
  it('draws no Filter button; with one, the button is there', () => {
    const search = { label: 'Search', placeholder: 'Search', value: '', onChange: () => {} };
    const { rerender } = render(<ListToolbar search={search} resultText="" />);
    expect(screen.queryByRole('button', { name: /filter/i })).toBeNull();
    rerender(<ListToolbar search={search} filterCount={0} filterOpen={false} onFilterToggle={() => {}} resultText="" />);
    expect(screen.getByRole('button', { name: /filter/i })).toBeTruthy();
  });
});
