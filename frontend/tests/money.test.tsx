// @vitest-environment jsdom
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { setImmediate as realImmediate } from 'node:timers';

import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ProjectJourneyPage } from '@/features/projects/ProjectJourney';
import { AppShell } from '@/shell/AppShell';

// @ts-expect-error plain ESM module without type declarations
import { moneyRoute } from '../mock/money.mjs';
// @ts-expect-error plain ESM module without type declarations
import { normaliseProjectPath, projects, uuidOf } from '../mock/projects.mjs';
import { destinationList } from './destinations';
import { bellFeed, isBellFeed, isRoleDashboard, roleDashboard } from './bell-feed';

// F-71 Money tab (SCR-12) on the live money read, against the contract mock's own handlers. Every money rule is a test
// here: Unknown is never 0 or blank, nothing is totalled, no paid word is made up, the drill-down shows only the figure's
// own sources, and a refused read names no stage or amount.
const nav = vi.hoisted(() => {
  const listeners = new Set<() => void>();
  let params = new URLSearchParams();
  const set = (search: string) => {
    params = new URLSearchParams(search);
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
    usePathname: () => '/projects/P-0101/money',
    useRouter: () => nav.router,
    useSearchParams: () => useSyncExternalStore(subscribe, nav.get),
  };
});

type Body = Record<string, unknown>;
const me = (persona: string) => JSON.parse(readFileSync(join(__dirname, `../mock/fixtures/me.${persona}.json`), 'utf8'));
const fixture = (path: string) => JSON.parse(readFileSync(join(__dirname, '../mock/fixtures', path), 'utf8')) as Body;
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
const STATUSES = ['200', '401', '403', '404'];

/** The mock's own answer for a request: the project from projects.mjs, money from money.mjs. */
function fromMock(raw: URL, who: string): Response {
  // the mock server names a project by its P-nnnn id for the money fixtures (normaliseProjectPath)
  const url = new URL(normaliseProjectPath(raw.pathname) + raw.search, raw);
  const parts = url.pathname.split('/');
  const cookies = { psl_mock_persona: who };
  if (parts[5] === 'money') return json(...(moneyRoute({ route: { operationId: 'E-PROJECT-TAB', statuses: STATUSES }, url, req: { headers: {} }, cookies }) as [number, Body]));
  const r = projects({ operationId: 'E-PROJECT', url, persona: who }) as { status: number; body: Body };
  return json(r.status, r.body);
}

let persona = 'finance_lead';
let destinations: string[] | undefined;
let respond: (url: URL) => Response | Promise<Response>;
let calls: URL[];

beforeEach(() => {
  persona = 'finance_lead';
  destinations = undefined;
  calls = [];
  respond = (url) => fromMock(url, persona);
  nav.router.replace.mockClear();
  nav.set('');
  vi.stubGlobal(
    'fetch',
    vi.fn(async (request: Request) => {
      if (isBellFeed(request)) return bellFeed();
      if (isRoleDashboard(request)) return roleDashboard();
      const url = new URL(request.url);
      if (url.pathname === '/api/v1/me') return json(200, { ...me(persona), ...(destinations ? { destinations: destinationList(destinations) } : {}) });
      calls.push(url);
      return respond(url);
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

const settle = () => until(() => expect(document.querySelector('.psl-loading')).toBeNull());

async function open(caseId = 'P-0101', search = '') {
  nav.set(search);
  render(
    <AppShell>
      <ProjectJourneyPage caseId={caseId} tab="money" />
    </AppShell>,
  );
  await until(() => expect(calls.length).toBeGreaterThan(0));
  await settle();
}

const phone = () => vi.stubGlobal('matchMedia', (q: string) => ({ matches: q.includes('max-width'), media: q, addEventListener: () => {}, removeEventListener: () => {} }));
const panel = () => screen.getByRole('tabpanel', { name: 'Money' });
const bodyRows = () => [...panel().querySelectorAll('tbody tr')] as HTMLTableRowElement[];
const cells = () => bodyRows().map((tr) => [...tr.cells].map((td) => td.textContent));
const cell = (row: number, col: number) => bodyRows()[row].cells[col];
const paths = () => calls.map((u) => u.pathname);
const aside = () => screen.getByRole('complementary');
// A zero or a missing number: "₦0", a lone "0.00" (not the end of "₦3,000,000.00") or NaN.
const ZERO = /₦0(?![\d,.])|₦0\.00|(?<![\d,])0\.00|NaN/;

const MONEY = `/api/v1/projects/${uuidOf('P-0101')}/money`;
const moneyBody = () => fixture('projects/money/P-0101.json') as { items: Record<string, unknown>[] } & Body;
const asMoney = (body: unknown) => (url: URL) => (url.pathname.endsWith('/money') ? json(200, body) : fromMock(url, persona));
const text = () => panel().textContent ?? '';

describe('rows from the live money read (P-0101, as SCR-12 draws it)', () => {
  it('five items in the order sent, the number only where a stage has one, one read, as of', async () => {
    await open();
    expect(paths()).toEqual(['/api/v1/projects/P-0101', MONEY]);
    expect(calls[1].search).toBe('');
    expect(screen.getByRole('heading', { level: 1 }).textContent).toBe('Lagoon Health · patient app');
    expect(within(panel()).getAllByRole('columnheader').map((th) => [th.textContent, th.getAttribute('scope')])).toEqual([
      ['STAGE', 'col'],
      ['AMOUNT', 'col'],
      ['INVOICE', 'col'],
      ['PAID', 'col'],
    ]);
    expect(within(panel()).getByRole('table', { name: 'Billing by contract stage' })).toBeTruthy();
    expect(cells()).toEqual([
      ['1 · Kick-off', 'NGN 3,000,000.00', 'INV-0398 · DeliveredINV-0399 · Issued', 'Paid NGN 2,000,000.00 · Owed NGN 500,000.00Paid NGN 250,000.00 · Owed NGN 250,000.00'],
      ['2 · UAT sign-off', 'NGN 4,250,000.00', 'INV-0412 · Delivered', 'Paid Unknown · Owed Unknown'],
      ['3 · Go-live', 'UnknownThe reviewed stage terms do not state an amount.', 'INV-0419 · Awaiting Finance decision', 'Paid Unknown · Owed Unknown'],
      ['Hypercare', 'NGN 500,000.00', '—No invoice', '—No payment'],
      ['INV-0420 outside any stage', 'USD 1,000.00', 'INV-0420 · Draft', 'Paid Unknown · Owed USD 1,000.00'],
    ]);
    expect(panel().querySelector('.money__asof')!.textContent).toBe('As of 12 Nov 16:40');
    expect(screen.getByText('Every figure links to the record it came from. Unknown amounts are shown as Unknown, never as 0.')).toBeTruthy();
  });

  it('the order is the order sent, not alphabetical and not by position', async () => {
    const body = moneyBody();
    body.items = [body.items[4], body.items[2], body.items[0]].map((i, n) => ({ ...i, key: `z${3 - n}` }));
    respond = asMoney(body);
    await open();
    expect(cells().map((c) => c[0])).toEqual(['INV-0420 outside any stage', '3 · Go-live', '1 · Kick-off']);
  });

  it('finance_lead and pm see the same rows; the page hides the retired Finance link', async () => {
    await open();
    const lead = cells();
    expect(panel().querySelector('a[href*="finance"]')).toBeNull();
    document.body.innerHTML = '';
    persona = 'pm';
    calls = [];
    await open();
    expect(cells()).toEqual(lead);
  });

  it('no total, no computation: five rows, no footer, none of the sums the numbers would give', async () => {
    await open();
    expect(bodyRows()).toHaveLength(5);
    expect(panel().querySelector('tfoot')).toBeNull();
    expect(text()).not.toMatch(/total|subtotal|balance|outstanding|%/i);
    for (const sum of ['7,250,000', '7,750,000', '2,750,000', '3,000,000.00 +']) expect(text()).not.toContain(sum);
  });

  it('a stage with two invoices lists both, each with its own status, paid and owed', async () => {
    await open();
    const [invoices, paid] = [cell(0, 2), cell(0, 3)].map((c) => [...c.querySelectorAll('.money__block')].map((b) => b.textContent));
    expect(invoices).toEqual(['INV-0398 · Delivered', 'INV-0399 · Issued']);
    expect(paid).toEqual(['Paid NGN 2,000,000.00 · Owed NGN 500,000.00', 'Paid NGN 250,000.00 · Owed NGN 250,000.00']);
  });
});

describe('Unknown is not zero', () => {
  it('a null amount is the amber Unknown with its reason, not a link and never 0', async () => {
    await open();
    expect(cell(2, 1).querySelector('.psl-unknown')!.textContent).toBe('Unknown');
    expect(cell(2, 1).querySelector('.money__note')!.textContent).toBe('The reviewed stage terms do not state an amount.');
    expect(cell(2, 1).querySelector('a')).toBeNull();
    expect(text()).not.toMatch(ZERO);
    expect(cell(0, 1).querySelector('.money__note')).toBeNull();
  });

  it('a null paid or owed reads Unknown for that figure; no paid word is composed; Delivered is not paid', async () => {
    await open();
    expect(cell(1, 3).querySelectorAll('.psl-unknown')).toHaveLength(2);
    expect(cell(4, 3).querySelectorAll('.psl-unknown')).toHaveLength(1);
    expect(cell(1, 2).textContent).toBe('INV-0412 · Delivered');
    expect(text()).not.toMatch(/part[ -]paid|not paid|fully paid|\bpaid in full|unpaid|settled/i);
  });

  it('changing only the amount to equal the paid figure changes no paid text', async () => {
    const before = (await open(), cells().map((c) => c[3]));
    document.body.innerHTML = '';
    const body = moneyBody();
    const stage = body.items[1] as { invoices: { paid: string | null }[] };
    stage.invoices[0].paid = '4250000.00';
    respond = asMoney(body);
    calls = [];
    await open();
    expect(cells().map((c) => c[3])[0]).toBe(before[0]);
    expect(cell(1, 3).textContent).toBe('Paid NGN 4,250,000.00 · Owed Unknown');
    expect(text()).not.toMatch(/\bpaid in full|fully paid|settled/i);
  });
});

describe('limited and empty', () => {
  it('limited: true shows the warning above the table, limited: false none', async () => {
    await open();
    expect(screen.queryByText('Some figures may be incomplete.')).toBeNull();
    document.body.innerHTML = '';
    calls = [];
    await open('P-0102');
    expect(within(panel()).getByText('Some figures may be incomplete.').closest('.psl-callout')).toBeTruthy();
  });

  it('P-0106 has no items: "No contract stages yet", no table, no aside', async () => {
    await open('P-0106');
    expect(within(panel()).getByRole('heading', { level: 2, name: 'No contract stages yet' })).toBeTruthy();
    expect(within(panel()).getByText('Stages appear here once the SOW is signed.')).toBeTruthy();
    expect(panel().querySelector('table')).toBeNull();
    expect(screen.queryByRole('complementary')).toBeNull();
  });
});

describe('drill-down (?figure=<key>)', () => {
  it('nothing chosen: the aside asks for a choice and makes no figure read', async () => {
    await open();
    expect(within(aside()).getByText('Choose an amount to see where it comes from.')).toBeTruthy();
    expect(paths()).toEqual(['/api/v1/projects/P-0101', MONEY]);
    const links = [...panel().querySelectorAll('tbody a')].map((a) => a.getAttribute('href'));
    expect(links).toEqual(['/projects/P-0101/money?figure=kickoff', '/projects/P-0101/money?figure=uat', '/projects/P-0101/money?figure=hypercare', '/projects/P-0101/money?figure=invoice-420']);
  });

  it('?figure=kickoff reads that key once and lists its sources in order, the reference after the label, no links', async () => {
    await open('P-0101', '?figure=kickoff');
    const read = calls.filter((u) => u.search.includes('figure'));
    expect(read.map((u) => [u.pathname, u.searchParams.get('figure')])).toEqual([[MONEY, 'kickoff']]);
    expect(within(aside()).getByText('Kick-off')).toBeTruthy();
    const items = [...aside().querySelectorAll('ol > li')].map((li) => li.textContent);
    expect(items).toHaveLength(2);
    expect(items[0]).toMatch(/^Statement of work SOW-0198 v2 · Signed SOW · 30 Sep/);
    expect(items[1]).toMatch(/^Kick-off minutes · Meeting · 27 Oct/);
    expect(aside().querySelector('.money__ref')!.textContent).toBe('SOW-0198 v2');
    expect(aside().querySelectorAll('.money__ref')).toHaveLength(1);
    expect(aside().querySelector('a')).toBeNull();
    expect(cell(0, 1).querySelector('a')!.getAttribute('aria-current')).toBe('true');
  });

  it('an item with no sources says so; the head is its label', async () => {
    await open('P-0101', '?figure=uat');
    await until(() => expect(aside().textContent).toContain('No source recorded'));
    expect(within(aside()).getByText('UAT sign-off')).toBeTruthy();
  });

  it('an unknown key says it is not available and leaves the table', async () => {
    await open('P-0101', '?figure=nope');
    await until(() => expect(aside().textContent).toContain('That figure isn’t available.'));
    expect(bodyRows()).toHaveLength(5);
  });

  it('the key is encoded in the request', async () => {
    await open('P-0101', '?figure=a%20b%2Fc');
    expect(calls.find((u) => u.search.includes('figure'))!.searchParams.get('figure')).toBe('a b/c');
  });

  it('pressing an amount announces the figure', async () => {
    await open();
    fireEvent.click(cell(0, 1).querySelector('a')!);
    expect(nav.router.replace).not.toHaveBeenCalled();
    nav.set('?figure=kickoff');
    await until(() => expect(document.querySelector('[aria-live="polite"].cmp-sr')!.textContent).toBe('Showing where Kick-off comes from'));
  });

  it('a failed figure read shows Try again, which re-reads only the figure', async () => {
    respond = (url) => (url.searchParams.has('figure') ? json(500, { code: 'server_error', message: 'Boom' }) : fromMock(url, persona));
    await open('P-0101', '?figure=kickoff');
    await until(() => expect(within(aside()).getByRole('button', { name: 'Try again' })).toBeTruthy());
    expect(bodyRows()).toHaveLength(5);
    respond = (url) => fromMock(url, persona);
    const before = paths().length;
    fireEvent.click(within(aside()).getByRole('button', { name: 'Try again' }));
    await until(() => expect(aside().querySelector('ol')).toBeTruthy());
    expect(calls.slice(before).map((u) => u.search)).toEqual(['?figure=kickoff']);
  });

  it('a refused figure read says so and shows nothing from the server', async () => {
    respond = (url) => (url.searchParams.has('figure') ? json(403, { code: 'forbidden', message: 'SECRET detail' }) : fromMock(url, persona));
    await open('P-0101', '?figure=kickoff');
    await until(() => expect(aside().textContent).toContain('You can’t see where this figure comes from.'));
    expect(document.body.textContent).not.toContain('SECRET');
  });
});

describe('phone (390): cards and the bottom sheet', () => {
  beforeEach(phone);

  it('five cards in order with the number only on stages, one line per invoice, no table and no aside', async () => {
    await open();
    const cards = [...panel().querySelectorAll('.money__card')];
    expect(cards.map((c) => c.querySelector('.money__stage')!.textContent)).toEqual(['1 · Kick-off', '2 · UAT sign-off', '3 · Go-live', 'Hypercare', 'INV-0420 outside any stage']);
    expect(cards.map((c) => [...c.querySelectorAll('.money__block')].map((l) => l.textContent))[0]).toEqual([
      'INV-0398 · Delivered',
      'INV-0399 · Issued',
      'Paid NGN 2,000,000.00 · Owed NGN 500,000.00',
      'Paid NGN 250,000.00 · Owed NGN 250,000.00',
    ]);
    expect(cards[2].querySelector('.psl-unknown')!.textContent).toBe('Unknown');
    expect(cards[2].querySelector('.money__note')!.textContent).toBe('The reviewed stage terms do not state an amount.');
    expect(screen.getByText('Tap an amount to see where it comes from').tagName).toBe('P');
    expect(panel().querySelector('table')).toBeNull();
    expect(screen.queryByRole('complementary')).toBeNull();
    expect(screen.queryByRole('dialog')).toBeNull();
    expect(panel().querySelector('.money__asof')!.textContent).toBe('As of 12 Nov 16:40');
  });

  it('?figure=kickoff opens the sheet with the label and sources; Esc closes it, drops figure and refocuses the amount', async () => {
    await open('P-0101', '?figure=kickoff');
    const sheet = screen.getByRole('dialog', { name: 'Kick-off' });
    await until(() => expect(sheet.querySelectorAll('ol > li')).toHaveLength(2));
    fireEvent.keyDown(sheet, { key: 'Escape' });
    expect(nav.router.replace).toHaveBeenCalledWith('/projects/P-0101/money', { scroll: false });
    await until(() => expect(screen.queryByRole('dialog')).toBeNull());
    const amount = panel().querySelectorAll('.money__card')[0].querySelector('a')!;
    expect(amount.textContent).toBe('NGN 3,000,000.00');
    await waitFor(() => expect(document.activeElement).toBe(amount));
  });

  it('the close button closes the sheet too', async () => {
    await open('P-0101', '?figure=kickoff');
    fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Close' }));
    await until(() => expect(screen.queryByRole('dialog')).toBeNull());
    expect(nav.router.replace).toHaveBeenCalledWith('/projects/P-0101/money', { scroll: false });
  });

  it('an unknown key in the sheet says it is not available', async () => {
    await open('P-0101', '?figure=nope');
    await until(() => expect(screen.getByRole('dialog').textContent).toContain('That figure isn’t available.'));
  });
});

describe('errors and access', () => {
  it.each([
    ['a 500', () => json(500, { code: 'server_error', message: 'Boom' })],
    ['a network failure', () => Promise.reject(new TypeError('offline'))],
    ['a body without items', () => json(200, { limited: false, as_of: '2026-11-12T15:40:00Z', finance_url: '/f' })],
    ['a malformed item', () => json(200, { ...moneyBody(), items: [moneyBody().items[0], { key: 'x', label: 'Broken', amount: 4250000 }] })],
  ] as const)('money read failure (%s): the error card and Try again, nothing partial, one new read', async (_, answer) => {
    respond = (url) => (url.pathname.endsWith('/money') ? answer() : fromMock(url, persona));
    await open();
    await until(() => expect(screen.getByRole('alert').textContent).toContain('We couldn’t load this project’s money. Your work is safe; nothing was changed.'));
    expect(panel().querySelector('table')).toBeNull();
    expect(document.body.textContent).not.toContain('Kick-off');
    expect(document.body.textContent).not.toContain('Boom');
    respond = (url) => fromMock(url, persona);
    const before = paths().length;
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
    await until(() => expect(bodyRows()).toHaveLength(5));
    expect(paths().slice(before)).toEqual([MONEY]);
  });

  it.each([
    ['P-0107', 403],
    ['P-0108', 404],
  ])('%s answers %i on money: only the no-access line, no stage, amount or server message', async (id, status) => {
    await open(id);
    expect(within(panel()).getByText('You can’t see this project’s money.')).toBeTruthy();
    expect(panel().querySelector('table')).toBeNull();
    expect(document.body.textContent).not.toMatch(/NGN|Kick-off|We could not find|Your role does not allow/);
    expect(status).toBeGreaterThan(400);
  });

  it('a 401 on the money read signs in back to the money tab', async () => {
    respond = (url) => (url.pathname.endsWith('/money') ? json(401, { code: 'not_signed_in', message: 'Sign in to continue.' }) : fromMock(url, persona));
    await open();
    expect(screen.getByRole('link', { name: 'Sign in' }).getAttribute('href')).toBe('/sign-in?next=%2Fprojects%2FP-0101%2Fmoney');
  });

  it('pm on P-0104 and anyone on P-0099: the project read is refused; no money read', async () => {
    persona = 'pm';
    await open('P-0104');
    expect(screen.getByText('You can’t open this project')).toBeTruthy();
    expect(paths()).toEqual(['/api/v1/projects/P-0104']);
    document.body.innerHTML = '';
    persona = 'finance_lead';
    calls = [];
    await open('P-0099');
    expect(paths()).toEqual(['/api/v1/projects/P-0099']);
    expect(document.body.textContent).not.toContain('NGN');
  });

  it('only GET requests leave the tab, even after pressing an amount', async () => {
    const methods: string[] = [];
    const base = globalThis.fetch;
    vi.stubGlobal('fetch', vi.fn(async (request: Request) => {
      methods.push(request.method);
      return base(request);
    }));
    await open('P-0101', '?figure=kickoff');
    fireEvent.click(cell(0, 1).querySelector('a')!);
    expect(methods.length).toBeGreaterThan(2);
    expect(new Set(methods)).toEqual(new Set(['GET']));
    expect(panel().querySelector('form, button[type="submit"]')).toBeNull();
  });

  it('a late answer for an earlier read is ignored', async () => {
    let release: (r: Response) => void = () => {};
    const first = new Promise<Response>((r) => (release = r));
    let n = 0;
    respond = (url) => (url.pathname.endsWith('/money') && n++ === 0 ? first : fromMock(url, persona));
    nav.set('');
    const view = render(
      <AppShell>
        <ProjectJourneyPage caseId="P-0101" tab="money" />
      </AppShell>,
    );
    await until(() => expect(n).toBe(1));
    view.unmount();
    release(json(200, { ...moneyBody(), items: [] }));
    await act(async () => {
      await new Promise((r) => realImmediate(r));
    });
    expect(n).toBe(1);
  });
});
