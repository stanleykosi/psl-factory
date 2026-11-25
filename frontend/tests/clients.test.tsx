// @vitest-environment jsdom
import { readFileSync, readdirSync } from 'node:fs';
import { join } from 'node:path';
import { matchingSources } from './source-files';

import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ClientDetailPage, ClientsList } from '@/features/clients';
import { AppShell } from '@/shell/AppShell';

// @ts-expect-error plain ESM module without type declarations
import { clients } from '../mock/clients.mjs';
import { bellFeed, isBellFeed, isRoleDashboard, roleDashboard } from './bell-feed';

const nav = vi.hoisted(() => ({ search: '' }));
vi.mock('next/navigation', () => ({
  usePathname: () => '/clients',
  useRouter: () => ({ replace: vi.fn(), push: vi.fn(), prefetch: vi.fn() }),
  useSearchParams: () => new URLSearchParams(nav.search),
}));

type Call = { method: string; path: string; search: string; csrf: string | null };
type Reply = Response | Promise<Response>;
const me = JSON.parse(readFileSync(join(__dirname, '../mock/fixtures/me.finance_lead.json'), 'utf8'));
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });

const ACME = 'a1b2c3d4'.repeat(8);
const HARMATTAN = 'b2c3d4e5'.repeat(8);
const LAGOON = 'c3d4e5f6'.repeat(8);
const SABI = 'd4e5f607'.repeat(8);
const TAMARIND = 'e5f60718'.repeat(8);
const id = (n: number) => `0b6f9e1a-3c44-4d0a-9d52-${String(n).padStart(12, '0')}`;

let apiPersona: string;
let cookies: Record<string, string>;
let calls: Call[];
// Replaces the mock's answer for a request; returning undefined lets the mock answer.
let override: (call: Call) => Reply | undefined;

function fromMock(call: Call): Response {
  const r = clients({ url: new URL(call.path + call.search, 'http://x'), persona: apiPersona, cookies });
  return json(r.status, r.body);
}

beforeEach(() => {
  apiPersona = 'finance_lead';
  cookies = {};
  calls = [];
  nav.search = '';
  override = () => undefined;
  vi.stubGlobal(
    'fetch',
    vi.fn(async (request: Request) => {
      if (isBellFeed(request)) return bellFeed();
      if (isRoleDashboard(request)) return roleDashboard();
      const url = new URL(request.url);
      if (url.pathname === '/api/v1/me') return json(200, me);
      const call: Call = { method: request.method, path: url.pathname, search: url.search, csrf: request.headers.get('X-CSRFToken') };
      calls.push(call);
      return override(call) ?? fromMock(call);
    }),
  );
});
afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

const reads = () => calls.filter((c) => c.path.startsWith('/api/v1/clients'));
const writes = () => calls.filter((c) => c.method !== 'GET');
const phoneOn = () => vi.stubGlobal('matchMedia', (query: string) => ({ matches: true, media: query, addEventListener: vi.fn(), removeEventListener: vi.fn() }));

async function openList() {
  render(
    <AppShell>
      <ClientsList />
    </AppShell>,
  );
  await screen.findByRole('heading', { level: 1, name: 'Clients' });
  await waitFor(() => expect(screen.queryByText('Loading…')).toBeNull());
}
async function openDetail(clientId: string) {
  render(
    <AppShell>
      <ClientDetailPage clientId={clientId} />
    </AppShell>,
  );
  await screen.findByRole('heading', { level: 1 });
  await waitFor(() => expect(screen.queryByText('Loading…')).toBeNull());
}

const bodyRows = () => [...document.querySelectorAll('tbody tr')].map((r) => [...r.querySelectorAll('td')].map((td) => td.textContent));
const hrefs = () => [...document.querySelectorAll<HTMLAnchorElement>('[data-client-link]')].map((a) => a.getAttribute('href') ?? '');
const panel = (name: string) => screen.getByRole('region', { name });

describe('Clients list (SCR-35, live)', () => {
  it('shows groups first, then ungrouped projects, in the returned order, with no owed column', async () => {
    await openList();
    expect(reads()).toHaveLength(1);
    expect(reads()[0]).toMatchObject({ method: 'GET', path: '/api/v1/clients', search: '' });
    expect(screen.getAllByRole('columnheader').map((th) => th.textContent)).toEqual(['CLIENT', 'PROJECTS', 'BILLING CONTACT', 'STATE']);
    expect(bodyRows()).toEqual([
      ['Acme Logistics', '3', '1 project needs a billing contact', 'Billing contact missing'],
      ['Harmattan Bank', '27', '9 projects need a billing contact', 'Billing contact missing'],
      ['Lagoon Health', '1', '1 project needs a billing contact', 'Billing contact missing'],
      ['Sabi Market', '2', 'None needed', 'None needed'],
      ['Tamarind Loans', '1', 'None needed', 'None needed'],
      ['Kora FoodsKitchen display screens', '1', 'Missing · invoices can’t start', 'Billing contact missing'],
      ['Office move', '1', 'Unknown', 'Unknown'],
      ['Delta PrintPrint portal', '1', 'Set', 'Set'],
    ]);
    expect(hrefs()).toEqual([ACME, HARMATTAN, LAGOON, SABI, TAMARIND, id(101), id(102), id(103)].map((key) => `/clients/${key}`));
    const text = document.body.textContent ?? '';
    expect(text).toMatch(/^.*8 clients loaded as of \d+ \w+, \d\d:\d\d · 12 missing billing contact/s);
    for (const word of ['Owed', 'OWED', 'Invoiced', 'Received', 'blocked']) expect(text).not.toContain(word);
    expect(screen.queryByRole('button', { name: 'Show more' })).toBeNull();
    expect(writes()).toEqual([]);
  });

  it('a project with unknown billing never reads Set or Missing', async () => {
    await openList();
    const row = screen.getByRole('link', { name: 'Office move' }).closest('tr')!;
    expect(row.textContent).toContain('Unknown');
    expect(row.textContent).not.toMatch(/Set|issing/);
  });

  it('phone: one link card per row with the billing words and no owed line', async () => {
    phoneOn();
    await openList();
    expect(document.querySelector('table')).toBeNull();
    const card = screen.getByRole('link', { name: 'Acme Logistics' }).closest('li')!;
    expect(card.textContent).toContain('1 project needs a billing contact');
    expect(card.textContent).not.toContain('Owed');
    expect(document.querySelectorAll('ul li a[data-client-link]')).toHaveLength(8);
    expect(screen.getByRole('link', { name: 'Office move' }).closest('li')!.textContent).toContain('Unknown');
  });

  it('sends q and a known billing value from the address, and ignores a bad billing value', async () => {
    nav.search = '?q=%20kora%20&billing=needed';
    await openList();
    expect(reads()[0].search).toBe('?q=kora&billing=needed');
    expect(hrefs()).toEqual([`/clients/${id(101)}`]);
  });

  it('?billing=bogus is not sent and the list loads', async () => {
    nav.search = '?billing=bogus';
    await openList();
    expect(reads()[0].search).toBe('');
    expect(hrefs()).toHaveLength(8);
  });

  it('Show more asks for the next group page, then the next project page, and never repeats a row', async () => {
    cookies = { psl_mock_clients: 'many' };
    await openList();
    expect(reads().map((c) => c.search)).toEqual(['']);
    expect(screen.getByText(/^50 clients loaded as of/)).toBeTruthy();
    // Rows per page 50: the 50 loaded rows show; Show more then needs the next group page, then the next project page.
    fireEvent.click(screen.getByRole('radio', { name: '50' }));
    await waitFor(() => expect(document.querySelectorAll('tbody tr')).toHaveLength(50));
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'Show more' }));
    });
    await waitFor(() => expect(document.querySelectorAll('tbody tr')).toHaveLength(60));
    expect(reads().map((c) => c.search)).toEqual(['', '?clients_page=2', '?page=2']);
    const all = hrefs();
    expect(new Set(all).size).toBe(60);
    expect(all[0]).toMatch(/^\/clients\/[a-f0-9]{64}$/);
    expect(all.slice(0, 30).every((h) => /[a-f0-9]{64}$/.test(h))).toBe(true);
    expect(all.slice(30).every((h) => h.includes('0b6f9e1a'))).toBe(true);
    expect(screen.queryByRole('button', { name: 'Show more' })).toBeNull();
  });

  it('a failed next page keeps the rows and offers to try again', async () => {
    cookies = { psl_mock_clients: 'many' };
    let fail = true;
    override = (call) => (fail && call.search.includes('clients_page=2') ? json(503, { code: 'unavailable', message: 'Try later.' }) : undefined);
    await openList();
    fireEvent.click(screen.getByRole('radio', { name: '50' }));
    await waitFor(() => expect(document.querySelectorAll('tbody tr')).toHaveLength(50));
    fireEvent.click(screen.getByRole('button', { name: 'Show more' }));
    await screen.findByText('We couldn’t load more. Choose Show more to try again.');
    expect(document.querySelectorAll('tbody tr')).toHaveLength(50);
    fail = false;
    fireEvent.click(screen.getByRole('button', { name: 'Show more' }));
    await waitFor(() => expect(document.querySelectorAll('tbody tr')).toHaveLength(60));
  });

  it('empty says so', async () => {
    cookies = { psl_mock_clients: 'empty' };
    await openList();
    expect(screen.getByText('No clients to show yet.')).toBeTruthy();
    expect(document.querySelector('table')).toBeNull();
  });

  it('a 503 shows the error card; Try again only reads', async () => {
    let fail = true;
    override = () => (fail ? json(503, { code: 'unavailable', message: 'Boom.' }) : undefined);
    render(
      <AppShell>
        <ClientsList />
      </AppShell>,
    );
    const alert = await screen.findByRole('alert');
    expect(alert.textContent).toContain('We couldn’t load the clients. Your work is safe; nothing was changed.');
    fail = false;
    fireEvent.click(within(alert).getByRole('button', { name: 'Try again' }));
    await screen.findByText('Acme Logistics');
    expect(calls.every((c) => c.method === 'GET')).toBe(true);
  });

  it('a 400 shows the error card', async () => {
    override = () => json(400, { code: 'bad_request', message: 'No.' });
    render(
      <AppShell>
        <ClientsList />
      </AppShell>,
    );
    expect((await screen.findByRole('alert')).textContent).toContain('We couldn’t load the clients');
  });

  it('a 200 without the lists is an unexpected reply', async () => {
    override = () => json(200, { projects: [] });
    render(
      <AppShell>
        <ClientsList />
      </AppShell>,
    );
    expect((await screen.findByRole('alert')).textContent).toContain('We couldn’t load the clients');
  });

  it('401 shows the signed-out callout with next=/clients', async () => {
    override = () => json(401, { code: 'not_signed_in', message: 'Sign in to continue.' });
    render(
      <AppShell>
        <ClientsList />
      </AppShell>,
    );
    const link = await screen.findByRole('link', { name: 'Sign in' });
    expect(link.getAttribute('href')).toContain('next=%2Fclients');
  });

  it('403 shows the no-access page and names nothing', async () => {
    apiPersona = 'none';
    render(
      <AppShell>
        <ClientsList />
      </AppShell>,
    );
    expect(await screen.findByRole('heading', { level: 1, name: 'You can’t open the clients' })).toBeTruthy();
    expect(document.body.textContent).not.toContain('Acme');
  });
});

describe('Client group page', () => {
  it('shows the label, its projects with billing tags and links, the pointer line and no form', async () => {
    await openDetail(ACME);
    expect(reads()[0]).toMatchObject({ path: `/api/v1/clients/groups/${ACME}` });
    expect(screen.getByRole('heading', { level: 1 }).textContent).toBe('Acme Logistics');
    const projects = panel('Projects');
    expect(within(projects).getByRole('link', { name: 'Warehouse portal' }).getAttribute('href')).toBe(`/projects/${id(1)}`);
    const row = (title: string) => within(projects).getByRole('link', { name: title }).closest('.clients__project')!.textContent;
    expect(row('Warehouse portal')).toContain('Billing contact missing');
    expect(row('Fleet tracking')).toContain('Set');
    expect(row('Depot cabling')).toContain('Unknown');
    expect(row('Depot cabling')).not.toMatch(/Set|issing/);
    expect(within(projects).getAllByRole('link', { name: /^Billing contacts/ }).map((a) => a.getAttribute('href'))).toEqual([1, 2, 3].map((n) => `/clients/${id(n)}`));
    expect(screen.getByText('Billing contacts are recorded for each project. Open a project’s billing contacts from the list.')).toBeTruthy();
    expect(document.querySelector('form, input')).toBeNull();
    expect(writes()).toEqual([]);
    for (const word of ['Invoiced', 'Received', 'blocked']) expect(document.body.textContent).not.toContain(word);
  });

  it('owed: a known amount and an unknown one stay on their own currency lines, never summed', async () => {
    await openDetail(ACME);
    const owed = panel('Owed');
    const lines = [...owed.querySelectorAll('li')].map((li) => li.textContent);
    expect(lines).toEqual(['Owed · NGN₦1,250,000.00' + '1 project with an amount not knownsample basis', 'Owed · USDNot known' + '2 projects with an amount not knownsample basis']);
    expect(owed.textContent).toContain('As of 23 Nov 2026 · 3 projects you can see');
    expect(owed.textContent).not.toContain('May be incomplete');
    expect(owed.textContent).not.toMatch(/\b0\.00\b|USD 0/);
  });

  it('owed: limited coverage, empty totals, no debt, and a lone unknown amount', async () => {
    await openDetail(HARMATTAN);
    expect(panel('Owed').textContent).toContain('₦480,000.00');
    expect(panel('Owed').textContent).toContain('May be incomplete: only part of this group is in your view or could be read.');
  });
  it('owed: empty totals does not claim zero', async () => {
    await openDetail(LAGOON);
    expect(panel('Owed').textContent).toContain('Nothing owed is recorded for the projects you can see.');
    expect(panel('Owed').textContent).toContain('As of 23 Nov 2026 · 1 project you can see');
  });
  it('owed: debt null says it is not available', async () => {
    await openDetail(SABI);
    expect(panel('Owed').textContent).toBe('OwedOwed amount is not available for this group.');
  });
  it('owed: a null amount reads Not known, with the count', async () => {
    await openDetail(TAMARIND);
    expect(panel('Owed').textContent).toContain('Not known');
    expect(panel('Owed').textContent).toContain('1 project with an amount not known');
    expect(panel('Owed').textContent).not.toMatch(/₦|0\.00/);
  });

  it('Show more loads the next page of projects once and adds no repeats', async () => {
    await openDetail(HARMATTAN);
    expect(within(panel('Projects')).getAllByRole('link', { name: /^Branch rollout/ })).toHaveLength(25);
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'Show more' }));
    });
    await waitFor(() => expect(within(panel('Projects')).getAllByRole('link', { name: /^Branch rollout/ })).toHaveLength(27));
    expect(reads().map((c) => c.search)).toEqual(['', '?page=2']);
    expect(screen.queryByRole('button', { name: 'Show more' })).toBeNull();
  });

  it('sends a group key URL-encoded once', async () => {
    await openDetail('a/b%c');
    expect(reads()[0].path).toBe('/api/v1/clients/groups/a%2Fb%25c');
  });

  it('403 and 404 show the no-access page and name nothing', async () => {
    apiPersona = 'none';
    await openDetail(ACME);
    expect(screen.getByRole('heading', { level: 1 }).textContent).toBe('You can’t open this client');
    expect(document.body.textContent).not.toContain('Acme');
  });
  it('a stale key is no access', async () => {
    await openDetail('f'.repeat(64));
    expect(screen.getByRole('heading', { level: 1 }).textContent).toBe('You can’t open this client');
  });

  it('401 shows the signed-out callout with a return path to this page', async () => {
    override = () => json(401, { code: 'not_signed_in', message: 'Sign in.' });
    render(
      <AppShell>
        <ClientDetailPage clientId={ACME} />
      </AppShell>,
    );
    const link = await screen.findByRole('link', { name: 'Sign in' });
    expect(decodeURIComponent(link.getAttribute('href') ?? '')).toContain(`/clients/${ACME}`);
  });

  it('a 503 shows the error card; Try again reads again', async () => {
    let fail = true;
    override = () => (fail ? json(503, { code: 'unavailable', message: 'x' }) : undefined);
    render(
      <AppShell>
        <ClientDetailPage clientId={ACME} />
      </AppShell>,
    );
    const alert = await screen.findByRole('alert');
    expect(alert.textContent).toContain('We couldn’t load this client. Your work is safe; nothing was changed.');
    fail = false;
    fireEvent.click(within(alert).getByRole('button', { name: 'Try again' }));
    await screen.findByRole('heading', { level: 1, name: 'Acme Logistics' });
    expect(calls.every((c) => c.method === 'GET')).toBe(true);
  });
});

describe('Client workspace page', () => {
  it('shows billing and project contacts read only, the sample label, a held add control and the money link', async () => {
    await openDetail(id(2));
    expect(reads()[0]).toMatchObject({ path: `/api/v1/clients/${id(2)}` });
    expect(screen.getByRole('heading', { level: 1 }).textContent).toBe('Fleet tracking');
    const billing = panel('Billing contact');
    expect(billing.textContent).toContain('Ada Okoye');
    expect(billing.textContent).toContain('ada@example.org');
    expect(billing.textContent).toContain('Accounts');
    expect(billing.textContent).toContain('Acme Logistics');
    expect(billing.textContent).toContain('version 2');
    expect(panel('Project contacts').textContent).toContain('Ife Balogun');
    expect(document.querySelector('form, input')).toBeNull();
    const add = within(billing).getByRole('button', { name: 'Add billing contact' }) as HTMLButtonElement;
    expect(add.disabled).toBe(true);
    expect(add.getAttribute('aria-describedby')).toBeTruthy();
    expect(document.getElementById(add.getAttribute('aria-describedby')!)!.textContent).toContain('not available yet');
    expect(within(panel('Projects')).getByRole('link', { name: 'Money for this project' }).getAttribute('href')).toBe(`/projects/${id(2)}/money`);
    expect(writes()).toEqual([]);
  });

  it('a sample workspace carries the sample label when the build shows it; one with no billing contact reads Not set', async () => {
    vi.stubEnv('NEXT_PUBLIC_SHOW_SAMPLE_LABEL', '1');
    await openDetail(id(1));
    expect(screen.getByRole('heading', { level: 1 }).closest('.clients__titlerow')!.textContent).toMatch(/sample data/i);
    expect(panel('Billing contact').textContent).toContain('Not set');
    expect(screen.queryByText('Show history')).toBeNull();
  });

  it('Show history lists versions newest first and pages with Show more', async () => {
    await openDetail(id(103));
    fireEvent.click(screen.getByRole('button', { name: 'Show history' }));
    const list = await screen.findByRole('list', { name: 'Billing contact history, newest first' });
    expect(reads().at(-1)).toMatchObject({ path: `/api/v1/clients/${id(103)}/contacts/history`, search: '?purpose=billing&customer=Delta%20Print' });
    expect(within(list).getAllByText(/^version \d+$/).map((n) => n.textContent)).toHaveLength(25);
    expect(within(list).getAllByText(/^version \d+$/)[0].textContent).toBe('version 28');
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'Show more' }));
    });
    await waitFor(() => expect(within(list).getAllByText(/^version \d+$/)).toHaveLength(28));
    expect(within(list).getAllByText(/^version \d+$/).at(-1)!.textContent).toBe('version 1');
    expect(reads().at(-1)!.search).toContain('page=2');
  });

  it('a failed history shows a retry and leaves the page', async () => {
    let fail = true;
    override = (call) => (fail && call.path.endsWith('/history') ? json(503, { code: 'unavailable', message: 'x' }) : undefined);
    await openDetail(id(103));
    fireEvent.click(screen.getByRole('button', { name: 'Show history' }));
    const alert = await screen.findByText(/We couldn’t load the history/);
    expect(screen.getByRole('heading', { level: 1 }).textContent).toBe('Print portal');
    expect(panel('Billing contact').textContent).toContain('Chi Eze');
    fail = false;
    fireEvent.click(within(alert.closest('p')!).getByRole('button', { name: 'Try again' }));
    await screen.findByRole('list', { name: 'Billing contact history, newest first' });
  });

  it('403 and 404 show the no-access page and name nothing', async () => {
    apiPersona = 'none';
    await openDetail(id(2));
    expect(screen.getByRole('heading', { level: 1 }).textContent).toBe('You can’t open this client');
    expect(document.body.textContent).not.toMatch(/Fleet|Ada Okoye/);
  });
  it('a case id from another tenant is no access', async () => {
    await openDetail(id(9999));
    expect(screen.getByRole('heading', { level: 1 }).textContent).toBe('You can’t open this client');
  });
});

describe('source rules for features/clients', () => {
  const dir = join(__dirname, '../src/features/clients');
  const files = readdirSync(dir).map((name) => [name, readFileSync(join(dir, name), 'utf8')] as const);
  const all = (pattern: RegExp) => files.flatMap(([name, text]) => text.split('\n').flatMap((line, i) => (pattern.test(line) ? [`${name}:${i + 1}: ${line.trim()}`] : [])));

  it('makes no permission decision from /me and defaults no amount to 0', () => {
    expect(all(/\buseMe\b|\.roles|destinations/)).toEqual([]);
    expect(all(/0\.00/)).toEqual([]);
  });
  it('only reads: four live GETs, no write, and nothing calls the retired billing-contact PUT', () => {
    expect(all(/\.(PUT|POST|PATCH|DELETE)\(/)).toEqual([]);
    expect(all(/billing-contact/)).toEqual([]);
    expect(all(/liveApi\.GET\(/).map((line) => line.replace(/^.*?liveApi\.GET\('([^']+)'.*$/, '$1')).sort()).toEqual([
      '/api/v1/clients',
      '/api/v1/clients/groups/{group}',
      '/api/v1/clients/{case_id}',
      '/api/v1/clients/{case_id}/contacts/history',
    ]);
  });
  it('uses tokens only in clients.css', () => {
    expect(readFileSync(join(dir, 'clients.css'), 'utf8').match(/#[0-9a-fA-F]{3,8}\b|rgba?\(|hsl\(/g)).toBeNull();
  });
  it('hard-codes none of the sample client names in the clients code', () => {
    const found = matchingSources([join(__dirname, '../src/features/clients'), join(__dirname, '../src/app/clients')], /Lagoon|Harmattan|Kora|Ojo|Sabi|Tamarind|Acme/);
    expect(found).toEqual([]);
  });
});
