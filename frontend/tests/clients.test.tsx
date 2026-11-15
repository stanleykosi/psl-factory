// @vitest-environment jsdom
import { execSync } from 'node:child_process';
import { readFileSync, readdirSync } from 'node:fs';
import { join } from 'node:path';

import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ClientDetailPage, ClientsList } from '@/features/clients';
import { AppShell } from '@/shell/AppShell';

// @ts-expect-error plain ESM module without type declarations
import { clients, resetClients } from '../mock/clients.mjs';
import { bellFeed, isBellFeed } from './bell-feed';

vi.mock('next/navigation', () => ({
  usePathname: () => '/clients',
  useRouter: () => ({ replace: vi.fn(), push: vi.fn(), prefetch: vi.fn() }),
}));

type Call = { method: string; path: string; search: string; body?: Record<string, unknown>; csrf: string | null };
type Reply = Response | Promise<Response>;
const me = JSON.parse(readFileSync(join(__dirname, '../mock/fixtures/me.finance_lead.json'), 'utf8'));
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
const OPERATIONS: Record<string, string> = { GET: 'E-CLIENT', PUT: 'E-CLIENT-CONTACT' };

let apiPersona: string;
let cookies: Record<string, string>;
let calls: Call[];
// Replaces the mock's answer for a request; returning undefined lets the mock answer.
let override: (call: Call) => Reply | undefined;

function fromMock(call: Call): Response {
  const url = new URL(call.path + call.search, 'http://x');
  const operationId = call.path === '/api/v1/clients' ? 'E-CLIENTS' : OPERATIONS[call.method];
  const r = clients({ operationId, url, raw: call.body ? JSON.stringify(call.body) : '', persona: apiPersona, cookies });
  return json(r.status, r.body);
}

beforeEach(() => {
  apiPersona = 'finance_lead';
  cookies = {};
  calls = [];
  override = () => undefined;
  resetClients();
  vi.stubGlobal(
    'fetch',
    vi.fn(async (request: Request) => {
      if (isBellFeed(request)) return bellFeed();
      const url = new URL(request.url);
      if (url.pathname === '/api/v1/me') return json(200, me);
      const text = request.method === 'GET' ? '' : await request.clone().text();
      const call: Call = { method: request.method, path: url.pathname, search: url.search, body: text ? JSON.parse(text) : undefined, csrf: request.headers.get('X-CSRFToken') };
      calls.push(call);
      return override(call) ?? fromMock(call);
    }),
  );
});
afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

const reads = () => calls.filter((c) => c.method === 'GET');
const puts = () => calls.filter((c) => c.method === 'PUT');

function renderList() {
  return render(
    <AppShell>
      <ClientsList />
    </AppShell>,
  );
}
async function openList() {
  renderList();
  await screen.findByRole('heading', { level: 1, name: 'Clients' });
  await waitFor(() => expect(screen.queryByText('Loading…')).toBeNull());
}
async function openDetail(id: string) {
  render(
    <AppShell>
      <ClientDetailPage clientId={id} />
    </AppShell>,
  );
  await screen.findByRole('heading', { level: 1 });
  await waitFor(() => expect(screen.queryByText('Loading…')).toBeNull());
}

const bodyRows = () => [...document.querySelectorAll('tbody tr')].map((r) => [...r.querySelectorAll('td')].map((td) => td.textContent));
const nameBox = () => screen.getByLabelText('Billing contact name') as HTMLInputElement;
const emailBox = () => screen.getByLabelText('Billing email') as HTMLInputElement;
const saveButton = () => screen.queryByRole('button', { name: /Save billing contact|Saving…/ }) as HTMLButtonElement | null;
function fill(name: string, email: string) {
  fireEvent.change(nameBox(), { target: { value: name } });
  fireEvent.change(emailBox(), { target: { value: email } });
}
const press = async () => {
  await act(async () => {
    fireEvent.click(saveButton()!);
  });
};

describe('Clients list (SCR-35)', () => {
  it('shows the six clients in the returned order from the data only', async () => {
    await openList();
    expect(reads()).toHaveLength(1);
    expect(reads()[0]).toMatchObject({ path: '/api/v1/clients', search: '' });
    expect(screen.getAllByRole('columnheader').map((th) => th.textContent)).toEqual(['CLIENT', 'PROJECTS', 'OWED', 'BILLING CONTACT', 'STATE']);
    expect(bodyRows()).toEqual([
      ['Lagoon Health', '1', 'Unknown amount not known', 'Missing · invoices can’t start', 'Billing contact missing'],
      ['Harmattan Bank', '1', '₦4,250,000.00', 'Set', 'Set'],
      ['Kora Logistics', '1', '₦0.00', 'Set', 'Set'],
      ['Ojo Foods', '1', 'Unknown amount not known', 'Missing · invoices can’t start', 'Billing contact missing'],
      ['Sabi Market', '1', '₦1,200,000.00', 'Set', 'Set'],
      ['Tamarind Loans', '0', 'Not given', 'Set', 'Set'],
    ]);
    const links = [...document.querySelectorAll<HTMLAnchorElement>('[data-client-link]')].map((a) => a.getAttribute('href'));
    expect(links).toEqual(['CL-3501', 'CL-3502', 'CL-3503', 'CL-3504', 'CL-3505', 'CL-3506'].map((id) => `/clients/${id}`));
    expect(screen.getByText('6 clients as of 14 Nov 2026 10:00 WAT · 2 missing billing contact')).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Show more' })).toBeNull();
    expect(screen.queryByRole('button', { name: /Filter/ })).toBeNull();
    const text = document.body.textContent ?? '';
    for (const word of ['@', 'active', 'closed', 'Prospect', 'READY', 'NEEDS DETAILS', 'PROSPECT']) expect(text).not.toContain(word);
  });

  it('phone: one link card per client with a readable name', async () => {
    vi.stubGlobal('matchMedia', (query: string) => ({ matches: true, media: query, addEventListener: vi.fn(), removeEventListener: vi.fn() }));
    await openList();
    expect(document.querySelector('table')).toBeNull();
    const link = screen.getByRole('link', { name: 'Lagoon Health' });
    expect(link.getAttribute('href')).toBe('/clients/CL-3501');
    const card = link.closest('li')!;
    expect(card.textContent).toContain('Owed: Unknown');
    expect(card.textContent).toContain('Billing contact missing');
    expect(document.querySelectorAll('ul li a[data-client-link]')).toHaveLength(6);
  });

  it('pages by next_cursor: one request per press, rows appended, the line and button follow the cursor', async () => {
    cookies = { psl_mock_clients: 'many' };
    // The page sends no limit; this backend answers pages of 10.
    override = (call) => {
      if (call.path !== '/api/v1/clients') return undefined;
      const search = new URLSearchParams(call.search);
      search.set('limit', '10');
      return fromMock({ ...call, search: `?${search}` });
    };
    await openList();
    expect(document.querySelectorAll('tbody tr')).toHaveLength(10);
    expect(screen.getByText(/^10 clients loaded as of /)).toBeTruthy();
    expect(screen.queryByText(/missing billing contact/)).toBeNull();
    const more = screen.getByRole('button', { name: 'Show more' });
    await act(async () => {
      fireEvent.click(more);
      fireEvent.click(more);
    });
    await waitFor(() => expect(document.querySelectorAll('tbody tr')).toHaveLength(20));
    expect(calls.filter((c) => c.search.includes('cursor='))).toHaveLength(1);
    expect(reads()[1].search).toBe('?cursor=o10');
    fireEvent.click(screen.getByRole('button', { name: 'Show more' }));
    await waitFor(() => expect(document.querySelectorAll('tbody tr')).toHaveLength(25));
    expect(reads()[2].search).toBe('?cursor=o20');
    expect(screen.queryByRole('button', { name: 'Show more' })).toBeNull();
    expect(screen.getByText(/^25 clients as of .* · \d+ missing billing contact$/)).toBeTruthy();
    const names = [...document.querySelectorAll('[data-client-link]')].map((a) => a.textContent);
    expect(new Set(names).size).toBe(25);
  });

  it('a failed second page keeps the loaded rows and offers Try again', async () => {
    cookies = { psl_mock_clients: 'many' };
    let fail = true;
    override = (call) => {
      if (call.path !== '/api/v1/clients') return undefined;
      const search = new URLSearchParams(call.search);
      if (search.has('cursor') && fail) return json(500, { code: 'server_error', message: 'Something went wrong.' });
      search.set('limit', '10');
      return fromMock({ ...call, search: `?${search}` });
    };
    await openList();
    fireEvent.click(screen.getByRole('button', { name: 'Show more' }));
    const alert = await screen.findByRole('alert');
    expect(document.querySelectorAll('tbody tr')).toHaveLength(10);
    fail = false;
    fireEvent.click(within(alert).getByRole('button', { name: 'Try again' }));
    await waitFor(() => expect(document.querySelectorAll('tbody tr')).toHaveLength(20));
    expect(screen.queryByRole('alert')).toBeNull();
  });

  it('empty list says so, with no count of missing contacts', async () => {
    cookies = { psl_mock_clients: 'empty' };
    await openList();
    expect(screen.getByText('No clients to show yet.')).toBeTruthy();
    expect(document.querySelector('table')).toBeNull();
  });

  it('5xx shows the error card; Try again only reads', async () => {
    let fail = true;
    override = () => (fail ? json(500, { code: 'server_error', message: 'Boom.' }) : undefined);
    renderList();
    const alert = await screen.findByRole('alert');
    expect(alert.textContent).toContain('We couldn’t load the clients. Your work is safe; nothing was changed.');
    fail = false;
    fireEvent.click(within(alert).getByRole('button', { name: 'Try again' }));
    await screen.findByText('Lagoon Health');
    expect(calls.every((c) => c.method === 'GET')).toBe(true);
    expect(calls).toHaveLength(2);
  });

  it('401 shows the signed-out callout with next=/clients', async () => {
    override = () => json(401, { code: 'not_signed_in', message: 'Sign in to continue.' });
    renderList();
    const link = await screen.findByRole('link', { name: 'Sign in' });
    expect(link.getAttribute('href')).toContain('next=%2Fclients');
  });

  it('403 (persona none) and 404 show the no-access page and name nothing', async () => {
    apiPersona = 'none';
    renderList();
    expect(await screen.findByRole('heading', { level: 1, name: 'You can’t open the clients' })).toBeTruthy();
    expect(document.body.textContent).not.toContain('Lagoon');
  });
});

describe('Client detail (SCR-35 detail)', () => {
  it('CL-3501: banner from blocked[], empty inputs, the project link, money with owed Unknown', async () => {
    await openDetail('CL-3501');
    expect(screen.getByRole('heading', { level: 1 }).textContent).toBe('Lagoon Health Ltd');
    expect(screen.getByText("No billing contact, so invoices for this client can't start. Add one here.")).toBeTruthy();
    expect(nameBox().value).toBe('');
    expect(emailBox().value).toBe('');
    expect(screen.getByText('Needed before any invoice can start')).toBeTruthy();
    expect(screen.getByRole('link', { name: 'Patient app' }).getAttribute('href')).toBe('/projects/P-0101');
    const money = screen.getByRole('region', { name: 'Money' });
    expect(within(money).getAllByRole('term').map((t) => t.textContent)).toEqual(['Invoiced', 'Received', 'Owed']);
    expect(within(money).getAllByRole('definition').map((d) => d.textContent)).toEqual(['₦6,000,000.00', '₦3,000,000.00', 'Unknown amount not known']);
    expect(screen.getByRole('link', { name: 'Clients' }).getAttribute('href')).toBe('/clients');
    const text = document.body.textContent ?? '';
    for (const word of ['Tax ID', 'Billing address', 'Legal name', 'Contacts', 'Tunde Bello', 'milestones']) expect(text).not.toContain(word);
  });

  it('CL-3509 (only required fields): no banner, no money, "No projects yet.", no placeholders', async () => {
    await openDetail('CL-3509');
    expect(screen.getByText('No projects yet.')).toBeTruthy();
    expect(screen.queryByRole('region', { name: 'Money' })).toBeNull();
    expect(document.querySelector('.psl-callout')).toBeNull();
    expect(screen.queryByText('Unknown')).toBeNull();
  });

  it('CL-3503 (can_change false): values read-only, no form or button, the explanation', async () => {
    await openDetail('CL-3503');
    expect(document.querySelector('form')).toBeNull();
    expect(saveButton()).toBeNull();
    expect(screen.getByText('Emeka Obi')).toBeTruthy();
    expect(screen.getByText('accounts@koralogistics.example')).toBeTruthy();
    expect(screen.getByText('You can’t change this client’s details.')).toBeTruthy();
    expect(screen.getByText('₦0.00')).toBeTruthy();
  });

  it('CL-3507: the sample client reads Unknown for every amount, never 0', async () => {
    await openDetail('CL-3507');
    const money = screen.getByRole('region', { name: 'Money' });
    expect(within(money).getAllByRole('definition').map((d) => d.textContent)).toEqual(['Unknown amount not known', 'Unknown amount not known', 'Unknown amount not known']);
  });

  it('a blank input sends nothing and shows its message beside it with focus on the first; one press sends exactly one PUT, then one reload shows the stored values', async () => {
    await openDetail('CL-3501');
    expect(saveButton()!.disabled).toBe(false);
    expect(nameBox().className).toContain('clients__needed');
    expect(emailBox().className).toContain('clients__needed');
    await press();
    expect(puts()).toHaveLength(0);
    expect(screen.getByText('Enter the billing contact name.')).toBeTruthy();
    expect(screen.getByText('Enter the billing email.')).toBeTruthy();
    expect(document.activeElement).toBe(nameBox());
    fill('Ada Okoye', '   ');
    await press();
    expect(puts()).toHaveLength(0);
    expect(screen.queryByText('Enter the billing contact name.')).toBeNull();
    expect(screen.getByText('Enter the billing email.')).toBeTruthy();
    expect(document.activeElement).toBe(emailBox());
    fill('Ada Okoye', 'ada@lagoon.example');
    expect(saveButton()!.disabled).toBe(false);
    const button = saveButton()!;
    await act(async () => {
      fireEvent.click(button);
      fireEvent.click(button);
    });
    await screen.findByText('Billing contact saved.');
    expect(puts()).toHaveLength(1);
    expect(puts()[0]).toMatchObject({ path: '/api/v1/clients/CL-3501/billing-contact', csrf: me.csrf_token });
    expect(puts()[0].body).toEqual({ expected_revision: 3, name: 'Ada Okoye', email: 'ada@lagoon.example' });
    expect(reads()).toHaveLength(2);
    expect(nameBox().value).toBe('Ada Okoye');
    expect(emailBox().value).toBe('ada@lagoon.example');
    expect(document.querySelector('.psl-callout--problem, .psl-callout--warning')).toBeNull();
    expect(screen.getByRole('status').textContent).toBe('Billing contact saved.');
    expect(saveButton()!.textContent).toBe('Save billing contact');
  });

  it('a 200 whose reload fails keeps the entries, says so, turns the form off, and Try again only reads', async () => {
    await openDetail('CL-3501');
    let failReads = true;
    override = (call) => (call.method === 'GET' && failReads ? json(502, { code: 'bad_gateway', message: 'x' }) : undefined);
    fill('Ada Okoye', 'ada@lagoon.example');
    await press();
    await screen.findByText('Saved. We couldn’t refresh the page; reload to see the latest.');
    {
      const box = screen.getByText('Saved. We couldn’t refresh the page; reload to see the latest.').closest('[role="alert"]') as HTMLElement;
      expect(box).toBeTruthy();
      expect(document.activeElement).toBe(box);
    }
    expect(saveButton()).toBeNull();
    expect(nameBox().value).toBe('Ada Okoye');
    failReads = false;
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
    await waitFor(() => expect(saveButton()).toBeTruthy());
    expect(puts()).toHaveLength(1);
    expect(nameBox().value).toBe('Ada Okoye');
  });

  it('409 (CL-3508): reloads once, keeps what was typed, shows the newer saved values, resends nothing; the next press carries the new revision', async () => {
    await openDetail('CL-3508');
    expect(nameBox().value).toBe('Tolu Bank');
    fill('Tolu B.', 'tolu.b@miletwelve.example');
    await press();
    await screen.findByText('This client changed while you were editing. Check the details and save again.');
    {
      const box = screen.getByText('This client changed while you were editing. Check the details and save again.').closest('[role="alert"]') as HTMLElement;
      expect(box).toBeTruthy();
      expect(document.activeElement).toBe(box);
    }
    expect(puts()).toHaveLength(1);
    expect(reads()).toHaveLength(2);
    expect(nameBox().value).toBe('Tolu B.');
    expect(screen.getByText('Current: Ngozi Eze · ngozi@miletwelve.example')).toBeTruthy();
    expect(saveButton()!.disabled).toBe(false);
    await press();
    await screen.findByText('Billing contact saved.');
    expect(puts()).toHaveLength(2);
    expect(puts()[1].body).toEqual({ expected_revision: 3, name: 'Tolu B.', email: 'tolu.b@miletwelve.example' });
    expect(screen.queryByText(/^Current:/)).toBeNull();
  });

  it('409 when nothing was typed: the newer values replace the fields', async () => {
    await openDetail('CL-3508');
    await press();
    await screen.findByText('This client changed while you were editing. Check the details and save again.');
    expect(nameBox().value).toBe('Ngozi Eze');
    expect(screen.queryByText(/^Current:/)).toBeNull();
  });

  it('422 puts each message beside its input, keeps the entries, moves focus to the first invalid input, and does not reload', async () => {
    await openDetail('CL-3501');
    fill('Ada', 'nope');
    override = (call) =>
      call.method === 'PUT'
        ? json(422, { code: 'invalid', message: 'Check the fields.', fields: [{ name: 'email', message: 'Enter a valid email address.' }, { name: 'name', message: 'That name is too short.' }, { name: 'phone', message: 'Phone is not used.' }] })
        : undefined;
    await press();
    const alert = await screen.findByRole('alert');
    expect(alert.textContent).toContain('Check the highlighted details.');
    expect(alert.textContent).toContain('Phone is not used.');
    for (const [input, message] of [
      [emailBox(), 'Enter a valid email address.'],
      [nameBox(), 'That name is too short.'],
    ] as const) {
      expect(input.getAttribute('aria-invalid')).toBe('true');
      const described = input.getAttribute('aria-describedby')!.split(' ').map((id) => document.getElementById(id)!.textContent);
      expect(described).toContain(message);
    }
    expect(document.activeElement).toBe(nameBox());
    expect(nameBox().value).toBe('Ada');
    expect(emailBox().value).toBe('nope');
    expect(reads()).toHaveLength(1);
    expect(puts()).toHaveLength(1);
  });

  it('422 without fields shows the response message in the summary', async () => {
    await openDetail('CL-3501');
    fill('Ada', 'ada@lagoon.example');
    override = (call) => (call.method === 'PUT' ? json(422, { code: 'invalid', message: 'We could not read that request.' }) : undefined);
    await press();
    expect((await screen.findByRole('alert')).textContent).toBe('We could not read that request.');
  });

  it('403 reloads once; the reloaded can_change decides, and the server message shows', async () => {
    await openDetail('CL-3501');
    fill('Ada', 'ada@lagoon.example');
    override = (call) => {
      if (call.method === 'PUT') return json(403, { code: 'forbidden', message: 'Your role changed.' });
      if (call.method === 'GET' && reads().length > 1) return json(200, { ...JSON.parse(JSON.stringify({ client_id: 'CL-3501', name: 'Lagoon Health Ltd', revision: 3, billing_contact: { set: false }, projects: [], can_change: false })) });
      return undefined;
    };
    await press();
    await screen.findByText('Your role changed.');
    {
      const box = screen.getByText('Your role changed.').closest('[role="alert"]') as HTMLElement;
      expect(box).toBeTruthy();
      expect(document.activeElement).toBe(box);
    }
    expect(reads()).toHaveLength(2);
    expect(puts()).toHaveLength(1);
    expect(document.querySelector('form')).toBeNull();
    expect(screen.getByText('You can’t change this client’s details.')).toBeTruthy();
  });

  it('401 on save shows the signed-out callout', async () => {
    await openDetail('CL-3501');
    fill('Ada', 'ada@lagoon.example');
    override = (call) => (call.method === 'PUT' ? json(401, { code: 'not_signed_in', message: 'Sign in.' }) : undefined);
    await press();
    const link = await screen.findByRole('link', { name: 'Sign in' });
    expect(link.getAttribute('href')).toContain('next=%2Fclients%2FCL-3501');
  });

  it('404 on save shows the no-access page without the name', async () => {
    await openDetail('CL-3501');
    fill('Ada', 'ada@lagoon.example');
    override = (call) => (call.method === 'PUT' ? json(404, { code: 'not_found', message: 'Gone.' }) : undefined);
    await press();
    await screen.findByRole('heading', { level: 1, name: 'You can’t open this client' });
    expect(document.body.textContent).not.toContain('Lagoon');
  });

  for (const [label, failure] of [
    ['a network error', () => Promise.reject(new TypeError('Failed to fetch'))],
    ['a 502', () => json(502, { code: 'bad_gateway', message: 'x' })],
  ] as const) {
    it(`${label} on save: "couldn’t confirm", one reload, no second PUT`, async () => {
      await openDetail('CL-3501');
      fill('Ada', 'ada@lagoon.example');
      override = (call) => (call.method === 'PUT' ? (failure() as Reply) : undefined);
      await press();
      await screen.findByText('We couldn’t confirm the change was saved.');
      {
        const box = screen.getByText('We couldn’t confirm the change was saved.').closest('[role="alert"]') as HTMLElement;
        expect(box).toBeTruthy();
        expect(document.activeElement).toBe(box);
      }
      expect(puts()).toHaveLength(1);
      expect(reads()).toHaveLength(2);
      expect(nameBox().value).toBe('Ada');
      expect(saveButton()).toBeTruthy();
    });
  }

  it('an unclear failure whose reload also fails turns the form off; Try again only reads', async () => {
    await openDetail('CL-3501');
    fill('Ada', 'ada@lagoon.example');
    let failReads = true;
    override = (call) => {
      if (call.method === 'PUT') return json(500, { code: 'server_error', message: 'x' });
      return failReads && reads().length > 1 ? json(500, { code: 'server_error', message: 'x' }) : undefined;
    };
    await press();
    await screen.findByText('We couldn’t confirm the change was saved.');
    expect(saveButton()).toBeNull();
    failReads = false;
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
    await waitFor(() => expect(saveButton()).toBeTruthy());
    expect(puts()).toHaveLength(1);
  });

  it('CL-3599 (404) and persona none (403) show the no-access page: no id, name or title anywhere', async () => {
    await openDetail('CL-3599');
    expect(screen.getByRole('heading', { level: 1 }).textContent).toBe('You can’t open this client');
    expect(document.body.textContent).not.toContain('CL-3599');
    expect(document.title).not.toContain('CL-3599');
  });

  it('403 on load shows the same no-access page', async () => {
    apiPersona = 'none';
    await openDetail('CL-3501');
    expect(screen.getByRole('heading', { level: 1 }).textContent).toBe('You can’t open this client');
    expect(document.body.textContent).not.toContain('Lagoon');
  });

  it('a 5xx on load shows the error card; Try again reads again', async () => {
    let fail = true;
    override = () => (fail ? json(500, { code: 'server_error', message: 'x' }) : undefined);
    render(
      <AppShell>
        <ClientDetailPage clientId="CL-3501" />
      </AppShell>,
    );
    const alert = await screen.findByRole('alert');
    expect(alert.textContent).toContain('We couldn’t load this client. Your work is safe; nothing was changed.');
    fail = false;
    fireEvent.click(within(alert).getByRole('button', { name: 'Try again' }));
    await screen.findByRole('heading', { level: 1, name: 'Lagoon Health Ltd' });
    expect(calls.every((c) => c.method === 'GET')).toBe(true);
  });
});

describe('source rules for features/clients', () => {
  const dir = join(__dirname, '../src/features/clients');
  const files = readdirSync(dir).map((name) => [name, readFileSync(join(dir, name), 'utf8')] as const);
  const all = (pattern: RegExp) => files.flatMap(([name, text]) => text.split('\n').flatMap((line, i) => (pattern.test(line) ? [`${name}:${i + 1}: ${line.trim()}`] : [])));

  it('makes no permission decision from /me and defaults no amount to 0', () => {
    expect(all(/useMe|\.roles|destinations/)).toEqual([]);
    expect(all(/0\.00/)).toEqual([]);
  });
  it('names invoices only in copy, and makes no call beyond the three operations', () => {
    const invoice = all(/invoice/i).filter((line) => !/(Needed before any invoice|invoices can’t start|Invoiced|invoiced|\* |\/\/|label: )/.test(line));
    expect(invoice).toEqual([]);
    expect(all(/api\.(GET|PUT|POST|PATCH|DELETE)\(/).map((line) => line.replace(/^.*?(api\.\w+\('[^']+').*$/, '$1')).sort()).toEqual([
      "api.GET('/api/v1/clients'",
      "api.GET('/api/v1/clients/{client_id}'",
      "api.PUT('/api/v1/clients/{client_id}/billing-contact'",
    ]);
  });
  it('uses tokens only in clients.css', () => {
    expect(readFileSync(join(dir, 'clients.css'), 'utf8').match(/#[0-9a-fA-F]{3,8}\b|rgba?\(|hsl\(/g)).toBeNull();
  });
  it('hard-codes none of the sample client names in the clients code (other features already carry theirs)', () => {
    const found = execSync(`grep -rln "Lagoon\\|Harmattan\\|Kora\\|Ojo\\|Sabi\\|Tamarind" ${join(__dirname, '../src/features/clients')} ${join(__dirname, '../src/app/clients')} || true`).toString().trim();
    expect(found).toBe('');
  });
});
