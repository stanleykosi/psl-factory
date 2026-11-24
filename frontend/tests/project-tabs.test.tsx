// @vitest-environment jsdom
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { setImmediate as realImmediate } from 'node:timers';

import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/react';
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

describe('access and errors (all tabs)', () => {
  it('P-0103: the tab answers 403; the header and tab bar stay and no fixture text is shown', async () => {
    await open('P-0103', 'milestones');
    expect(screen.getByRole('heading', { level: 1 }).textContent).toBe('Kora Logistics · fleet tracker');
    expect(screen.getByRole('heading', { level: 2, name: 'No access to this tab' })).toBeTruthy();
    expect(text()).not.toMatch(/Kick-off|INV-|₦/);
    expect(screen.getByRole('tablist', { name: 'Project' })).toBeTruthy();
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

  it('documents lists the project\u2019s documents; no row links, as no tab row names its review (B-7)', async () => {
    await open('P-0101', 'documents');
    const rows = within(screen.getByRole('table', { name: 'Documents' })).getAllByRole('row').slice(1);
    expect(rows).toHaveLength(6);
    expect(within(rows[0]).queryByRole('link')).toBeNull();
    expect(rows[0].textContent).toContain('v2');
    expect(rows[0].textContent).toContain('Awaiting PMO Lead review');
    expect(rows[0].textContent).toContain('TEST TEMPLATE');
    expect(within(rows[1]).queryByRole('link')).toBeNull();
    expect(rows[1].textContent).toContain('Costing COST-0140');
    expect(rows[2].textContent).toContain('Weekly sync minutes');
    expect(tabCalls().map((u) => u.pathname)).toEqual([`/api/v1/projects/${uuidOf('P-0101')}/documents`]);
  });

  it('a document row links to review only when its own api_url is this project\u2019s document-review path', async () => {
    const id = uuidOf('P-0101');
    const urls = [`/api/v1/projects/${id}/document-reviews/2901`, `/api/v1/projects/${uuidOf('P-0102')}/document-reviews/2901`, `//evil.example/api/v1/projects/${id}/document-reviews/2901`, `/api/v1/projects/${id}/documents/2901`, null];
    respond = (url) => {
      if (!url.pathname.endsWith('/documents')) return undefined;
      const body = projectTab({ url, persona, cookies }).body as { documents: Record<string, unknown>[] };
      return json(200, { ...body, documents: body.documents.slice(0, urls.length).map((row, i) => ({ ...row, api_url: urls[i] })) });
    };
    await open('P-0101', 'documents');
    const rows = within(screen.getByRole('table', { name: 'Documents' })).getAllByRole('row').slice(1);
    expect(within(rows[0]).getByRole('link', { name: 'Statement of work' }).getAttribute('href')).toBe(`/projects/${id}/documents/2901`);
    for (const row of rows.slice(1)) expect(within(row).queryByRole('link')).toBeNull();
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
