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

type Tab = 'documents' | 'registers' | 'actions';
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

describe('access and errors (all tabs)', () => {
  it('P-0103: the tab answers 403; the header and tab bar stay and no fixture text is shown', async () => {
    await open('P-0103', 'documents');
    expect(screen.getByRole('heading', { level: 1 }).textContent).toBe('Kora Logistics · fleet tracker');
    expect(screen.getByRole('heading', { level: 2, name: 'No access to this tab' })).toBeTruthy();
    expect(text()).not.toMatch(/Statement of work|INV-|₦/);
    expect(screen.getByRole('tablist', { name: 'Project' })).toBeTruthy();
  });

  it('P-0099: F-07 no-access page and no tab request', async () => {
    nav.search = '';
    render(
      <AppShell>
        <ProjectJourneyPage caseId="P-0099" tab="documents" />
      </AppShell>,
    );
    await until(() => expect(screen.getByRole('heading', { name: /can.t open this project/ })).toBeTruthy());
    expect(tabCalls()).toHaveLength(0);
  });

  it('a 500 and a network failure show the error card; Retry sends exactly one new request', async () => {
    let fail: 'server' | 'network' | undefined = 'server';
    respond = (url) => {
      if (!url.pathname.endsWith('/actions') || !fail) return undefined;
      if (fail === 'network') throw new TypeError('Failed to fetch');
      return json(500, { code: 'server_error', message: 'x' });
    };
    await open('P-0101', 'actions');
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
    await until(() => expect(rowsOf()).toHaveLength(9));
    expect(tabCalls()).toHaveLength(3);
  });

  it('every role gets the same columns for the same fixture', async () => {
    await open('P-0101', 'actions');
    const pm = rowsOf();
    cleanup();
    persona = 'finance_lead';
    await open('P-0101', 'actions');
    expect(rowsOf()).toEqual(pm);
  });

  it('documents lists the project\u2019s documents on the live sectioned read; only the review path links (B-7)', async () => {
    await open('P-0101', 'documents');
    const rows = within(screen.getByRole('table', { name: 'Documents' })).getAllByRole('row').slice(1);
    expect(rows).toHaveLength(6);
    expect(within(rows[0]).getByRole('link', { name: 'Statement of work' }).getAttribute('href')).toBe(`/projects/${uuidOf('P-0101')}/documents/2901`);
    expect(rows[0].textContent).toContain('Version 2');
    expect(rows[0].textContent).toContain('Awaiting PMO Lead review');
    expect(rows[0].textContent).toContain('16 Nov 2026');
    expect(within(rows[1]).queryByRole('link')).toBeNull();
    expect(rows[1].textContent).toContain('Costing COST-0140');
    expect(rows[2].textContent).toContain('Weekly sync minutes');
    expect(text()).not.toContain('couldn\u2019t load');
    expect(tabCalls().map((u) => u.pathname)).toEqual([`/api/v1/projects/${uuidOf('P-0101')}/documents`]);
  });

  it('a document row links to review only when its own api_url is this project\u2019s document-review path', async () => {
    const id = uuidOf('P-0101');
    const urls = [`/api/v1/projects/${id}/document-reviews/2901`, `/api/v1/projects/${uuidOf('P-0102')}/document-reviews/2901`, `//evil.example/api/v1/projects/${id}/document-reviews/2901`, `/api/v1/projects/${id}/documents/2901`, null];
    respond = (url) => {
      if (!url.pathname.endsWith('/documents')) return undefined;
      const body = structuredClone(projectTab({ url, persona, cookies }).body) as { sections: { items: Record<string, unknown>[] }[] };
      body.sections[0].items = body.sections[0].items.slice(0, urls.length).map((row, i) => ({ ...row, api_url: urls[i] }));
      return json(200, body);
    };
    await open('P-0101', 'documents');
    const rows = within(screen.getByRole('table', { name: 'Documents' })).getAllByRole('row').slice(1);
    expect(within(rows[0]).getByRole('link', { name: 'Statement of work' }).getAttribute('href')).toBe(`/projects/${id}/documents/2901`);
    for (const row of rows.slice(1)) expect(within(row).queryByRole('link')).toBeNull();
  });

  it('a body that is not the documents sections is a load failure', async () => {
    respond = (url) => (url.pathname.endsWith('/documents') ? json(200, { case_id: uuidOf('P-0101'), tab: 'documents', documents: [] }) : undefined);
    await open('P-0101', 'documents');
    expect(text()).toContain('We couldn\u2019t load this tab');
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
