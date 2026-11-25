// @vitest-environment jsdom
// F-79 SCR-20 Payments and follow-up against the contract mock's live GET /payments (mock/invoices.mjs, 1.24.0 shape).
// The fetch stub stands in for the backend: nothing here proves a real ledger, a real total or a real overdue figure;
// it proves the page shows only what it is given, computes nothing and sends its queries to the server.
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { matchingSources } from './source-files';

import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { PaymentsView } from '@/features/finance/payments/PaymentsView';
import { coverageText, figureText, knownAmountText, linkOf, overdueText, overdueValues, owedValues, parseQuery, receivedValues } from '@/features/finance/payments/model';
import { AppShell } from '@/shell/AppShell';

// @ts-expect-error plain ESM module without type declarations
import { invoices } from '../mock/invoices.mjs';
import { bellFeed, isBellFeed, isRoleDashboard, roleDashboard } from './bell-feed';

const nav = vi.hoisted(() => ({ search: '', listeners: new Set<() => void>(), replaced: [] as string[] }));
vi.mock('next/navigation', async () => {
  const React = await import('react');
  return {
    usePathname: () => '/finance/payments',
    useSearchParams: () => {
      const search = React.useSyncExternalStore(
        (listener: () => void) => {
          nav.listeners.add(listener);
          return () => nav.listeners.delete(listener);
        },
        () => nav.search,
      );
      return React.useMemo(() => new URLSearchParams(search), [search]);
    },
    useRouter: () => ({
      replace: (href: string) => {
        nav.replaced.push(href);
        nav.search = href.split('?')[1] ?? '';
        nav.listeners.forEach((listener) => listener());
      },
      push: vi.fn(),
      prefetch: vi.fn(),
    }),
  };
});

type Call = { method: string; path: string; params: URLSearchParams };
type Item = Record<string, unknown>;
type Body = { items: Item[] } & Record<string, unknown>;
const fixtures = join(__dirname, '../mock/fixtures');
const read = (name: string) => JSON.parse(readFileSync(join(fixtures, name), 'utf8'));
const me = read('me.finance_lead.json');
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
const board = (): Body => read('finance/invoices.board.json');

let persona: string;
let cookies: Record<string, string>;
let calls: Call[];
let override: (call: Call) => Response | Promise<Response> | undefined;

beforeEach(() => {
  persona = 'finance_lead';
  cookies = {};
  calls = [];
  nav.search = '';
  nav.replaced = [];
  override = () => undefined;
  vi.stubGlobal(
    'fetch',
    vi.fn(async (request: Request) => {
      if (isBellFeed(request)) return bellFeed();
      if (isRoleDashboard(request)) return roleDashboard();
      const url = new URL(request.url);
      if (url.pathname === '/api/v1/me') return json(200, me);
      const call = { method: request.method, path: url.pathname, params: url.searchParams };
      calls.push(call);
      const own = override(call);
      if (own) return own;
      const r = invoices({ url, persona, cookies });
      return json(r.status, r.body);
    }),
  );
});
afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

const reads = () => calls.filter((c) => c.path === '/api/v1/payments');
/** Serves `body` for every payments read. */
const serve = (body: unknown) => {
  override = (call) => (call.path === '/api/v1/payments' ? json(200, body) : undefined);
};
const phone = () => vi.stubGlobal('matchMedia', (query: string) => ({ matches: true, media: query, addEventListener: vi.fn(), removeEventListener: vi.fn() }));

async function open(search = '') {
  nav.search = search;
  const view = render(
    <AppShell>
      <PaymentsView />
    </AppShell>,
  );
  await waitFor(() => expect(document.querySelector('.payments__toolbar, .payments__noaccess, .shell-errorcard, .psl-callout')).not.toBeNull());
  await waitFor(() => expect(screen.queryByText('Loading…')).toBeNull());
  return view;
}
const table = () => within(screen.getByRole('table', { name: 'Invoices' }));
const rowOf = (reference: string) => within(screen.getByText(reference).closest('tr, li') as HTMLElement);
const cells = (reference: string) => [...(screen.getByText(reference).closest('tr') as HTMLElement).querySelectorAll('td')].map((td) => td.textContent);
const strip = () => within(screen.getByRole('region', { name: 'Facts earned' }));
const cell = (label: string) => strip().getByText(label).closest('.payments__cell') as HTMLElement;
const cellValues = (label: string) => [...cell(label).querySelectorAll('.payments__cellvalue')].map((v) => v.textContent);
const withRow = (patch: Item, index = 0): Body => {
  const body = board();
  body.items[index] = { ...body.items[index], ...patch };
  return body;
};

describe('model', () => {
  it('knownAmountText: only a two-decimal string is an amount; null and malformed are never 0', () => {
    expect(knownAmountText('3500000.00', 'NGN')).toBe('₦3,500,000.00');
    expect(knownAmountText('12000.00', 'USD')).toBe('USD 12,000.00');
    for (const bad of [null, undefined, '', 'abc', '12', '1.5', '1,000.00', '-']) expect(knownAmountText(bad as string, 'NGN')).toBeUndefined();
    expect(figureText(null, 'NGN', 'gross')).toBeUndefined();
    expect(figureText('0.00', 'NGN', 'gross')).toBe('₦0.00 gross');
  });

  it('overdueText: days past due, a dash for 0, Unknown for null', () => {
    expect(overdueText({ age_days: 9 })).toBe('9 days overdue');
    expect(overdueText({ age_days: 1 })).toBe('1 day overdue');
    expect(overdueText({ age_days: 0 })).toBe('—');
    expect(overdueText({ age_days: null })).toBe('Unknown');
  });

  it('no strip or amount helper returns 0 for a missing figure', () => {
    const total = { currency: 'NGN', basis: 'gross', owed: null, overdue: null, known_owed: null, unknown_owed_count: 0 };
    expect([...owedValues([total]), ...overdueValues([total]), ...owedValues([]), ...overdueValues([])].map((v) => v.text)).toEqual(['Unknown', 'Unknown', 'Unknown', 'Unknown']);
    const received = { month: '2026-11', scope: 'workspaces_in_results' as const, workspaces_read: 2, workspaces_unknown: 0, last_received_at: null, last_verified_at: null };
    expect(receivedValues({ ...received, totals: [] }).map((v) => v.text)).toEqual(['Unknown']);
    expect(receivedValues({ ...received, totals: [{ currency: 'NGN', basis: 'gross', amount: 'x' }] }).map((v) => v.text)).toEqual(['Unknown']);
  });

  it('coverageText only when some projects could not be read', () => {
    const received = { month: '2026-11', scope: 'workspaces_in_results' as const, workspaces_read: 2, workspaces_unknown: 1, last_received_at: null, last_verified_at: null, totals: [] };
    expect(coverageText(received)).toBe('Received this month covers 2 of 3 projects; 1 could not be read.');
    expect(coverageText({ ...received, workspaces_unknown: 0 })).toBeUndefined();
  });

  it('linkOf offers only a path on this site', () => {
    expect(linkOf('/finance/review/41')).toBe('/finance/review/41');
    for (const bad of [null, undefined, '', 'https://x.example', '//x.example', '/\\x.example', 'javascript:alert(1)', 'finance/review']) expect(linkOf(bad)).toBeUndefined();
  });

  it('parseQuery drops a status outside the five and keeps q to 100 characters', () => {
    expect(parseQuery(new URLSearchParams('q=kora&status=overdue'))).toEqual({ q: 'kora', status: 'overdue' });
    expect(parseQuery(new URLSearchParams('status=bogus')).status).toBeUndefined();
    expect(parseQuery(new URLSearchParams('status=part_paid')).status).toBeUndefined();
    expect(parseQuery(new URLSearchParams(`q=${'a'.repeat(120)}`)).q).toHaveLength(100);
  });
});

describe('the list reads the live path (AC 6)', () => {
  it('opens GET /api/v1/payments with no state, and never the v7 invoices route', async () => {
    await open();
    expect(reads().map((c) => c.params.toString())).toEqual(['']);
    expect(calls.some((c) => c.path.includes('/finance/invoices'))).toBe(false);
  });

  it('?q=kora&status=overdue sends q and state', async () => {
    await open('q=kora&status=overdue');
    expect(reads()[0].params.get('q')).toBe('kora');
    expect(reads()[0].params.get('state')).toBe('overdue');
    expect(reads()[0].params.has('status')).toBe(false);
    expect(screen.getByText('Overdue', { selector: '.psl-chip *, .psl-chip' })).toBeTruthy();
  });

  it('a status outside the five sends no state and shows no chip', async () => {
    await open('status=bogus');
    expect(reads()[0].params.has('state')).toBe(false);
    expect(document.querySelector('.psl-chip')).toBeNull();
  });

  it('the State filter offers the five contract values', async () => {
    await open();
    fireEvent.click(screen.getByRole('button', { name: 'Filter' }));
    expect(screen.getAllByRole('radio').map((r) => (r as HTMLInputElement).value)).toEqual(['', 'issued', 'part-paid', 'overdue', 'paid', 'unknown']);
  });

  it('applying a state changes the address and re-reads with state', async () => {
    await open();
    fireEvent.click(screen.getByRole('button', { name: 'Filter' }));
    fireEvent.click(screen.getByRole('radio', { name: 'Part-paid' }));
    fireEvent.click(screen.getByRole('button', { name: 'Show results' }));
    await waitFor(() => expect(reads().at(-1)!.params.get('state')).toBe('part-paid'));
    expect(nav.replaced.at(-1)).toBe('/finance/payments?status=part-paid');
  });
});

describe('rows (AC 7, 11, 12)', () => {
  it('draws the rows in returned order with billed, received and owed carrying currency and basis', async () => {
    await open();
    expect(screen.getByRole('heading', { level: 1, name: 'Payments and follow-up' })).toBeTruthy();
    expect(table().getAllByRole('columnheader').map((h) => h.textContent)).toEqual(['INVOICE', 'WORK', 'BILLED', 'RECEIVED', 'STILL OWED', 'STATE', 'OVERDUE BY', '']);
    expect(table().getAllByRole('row').slice(1).map((r) => r.querySelector('.psl-mono')!.textContent)).toEqual(['INV-0398', 'INV-0391', 'INV-0388', 'INV-0402']);
    expect(cells('INV-0398').slice(1, 7)).toEqual(['Lagoon Health · Phase 1', '₦3,000,000.00 gross', '₦2,500,000.00 gross', '₦500,000.00 gross', 'Part paid', '9 days overdue']);
    expect(cells('INV-0388').slice(1, 7)).toEqual(['Kora Foods · Phase 1', '₦2,400,000.00 gross', '₦2,400,000.00 gross', '₦0.00 gross', 'Paid', '—']);
  });

  it('a null owed or paid reads Unknown, never 0, with its reason as helper text', async () => {
    await open();
    const row = cells('INV-0402');
    expect(row.slice(1, 7)).toEqual(['Kora Foods', '₦3,100,000.00 gross', 'Unknown amount not known', 'Unknown amount not known', 'UnknownThe payment record is incomplete.', 'Unknown']);
    expect(row.join(' ')).not.toMatch(/₦0(\.00)?\b/);
  });

  it('face null is Unknown; a blank customer and contract read Unknown', async () => {
    const body = withRow({ face: null, customer: '', contract: '' }, 2);
    serve(body);
    await open();
    expect(cells('INV-0388').slice(1, 3)).toEqual(['Unknown', 'Unknown amount not known']);
  });

  it('status tones follow the status; voided and unknown are neutral', async () => {
    const body = withRow({ status: 'voided', label: 'Voided' }, 3);
    serve(body);
    await open();
    expect(rowOf('INV-0398').getByText('Part paid').className).toContain('psl-tag--waiting');
    expect(rowOf('INV-0391').getByText('Overdue').className).toContain('psl-tag--person');
    expect(rowOf('INV-0388').getByText('Paid').className).toContain('psl-tag--done');
    expect(rowOf('INV-0402').getByText('Voided').className).toContain('psl-tag--neutral');
  });

  it('a record link follows records_url only when it is a path', async () => {
    serve(withRow({ records_url: 'https://elsewhere.example/x' }, 1));
    await open();
    expect(screen.getByText('INV-0398').closest('a')!.getAttribute('href')).toBe('/projects/00000000-0000-4000-8000-000000000101');
    expect(screen.getByText('INV-0391').closest('a')).toBeNull();
  });

  it('the phone draws cards with the same figures and 44px-class actions', async () => {
    phone();
    await open();
    const card = rowOf('INV-0398');
    expect(card.getByText('₦500,000.00 gross')).toBeTruthy();
    expect(card.getByRole('link', { name: 'Open the reminder' })).toBeTruthy();
    expect(card.getByText(/9 days overdue/)).toBeTruthy();
  });
});

describe('the strip (AC 7, 8, 9)', () => {
  it('shows known part plus Unknown with the count when the owed total is incomplete', async () => {
    await open();
    expect(cellValues('OWED TO PSL')).toEqual(['₦7,300,000.00 gross + Unknown1 invoice has no known balance']);
    expect(cellValues('OVERDUE')).toEqual(['₦6,800,000.00 gross']);
    expect(cellValues('RECEIVED THIS MONTH')).toEqual(['₦1,500,000.00 gross']);
    expect(cell('RECEIVED THIS MONTH').textContent).toContain('(November 2026)');
    expect(cellValues('DATA DATE')).toEqual(['12 Nov']);
  });

  it('a complete owed total shows that value alone', async () => {
    cookies.psl_mock_invoices = 'known';
    await open();
    expect(cellValues('OWED TO PSL')).toEqual(['₦7,300,000.00 gross']);
    expect(screen.queryByText(/no known balance/)).toBeNull();
  });

  it('owed and known_owed both null read Unknown; empty received totals read Unknown, never 0', async () => {
    cookies.psl_mock_invoices = 'unknown';
    await open();
    expect(cellValues('OWED TO PSL')).toEqual(['Unknown']);
    expect(cellValues('OVERDUE')).toEqual(['Unknown']);
    expect(cellValues('RECEIVED THIS MONTH')).toEqual(['Unknown']);
    expect(strip().getByText('OWED TO PSL').closest('.payments__cell')!.className).not.toContain('payments__cell--owed');
  });

  it('two currencies show two values and no sum', async () => {
    cookies.psl_mock_invoices = 'currencies';
    await open();
    expect(cellValues('OWED TO PSL')).toEqual(['₦7,300,000.00 gross + Unknown1 invoice has no known balance', 'USD 12,000.00 gross']);
    expect(cellValues('RECEIVED THIS MONTH')).toEqual(['₦1,500,000.00 gross', 'USD 3,000.00 net']);
  });

  it('the coverage line shows only when some projects could not be read', async () => {
    await open();
    expect(screen.getByText('Received this month covers 2 of 3 projects; 1 could not be read.')).toBeTruthy();
  });

  it('no coverage line when none is unknown', async () => {
    cookies.psl_mock_invoices = 'known';
    await open();
    expect(screen.queryByText(/could not be read/)).toBeNull();
  });
});

describe('the partial-result notice (AC 10)', () => {
  it('limited shows the notice; not limited does not', async () => {
    cookies.psl_mock_invoices = 'limited';
    const view = await open();
    expect(screen.getByText('Partial result. The totals cover the rows returned, not every invoice. Use Show more for the rest.')).toBeTruthy();
    view.unmount();
    cookies.psl_mock_invoices = 'board';
    await open();
    expect(screen.queryByText(/Partial result/)).toBeNull();
  });
});

describe('action links follow the API (AC 11)', () => {
  it('a returned link is a plain anchor; a null one is disabled with the reason and no anchor', async () => {
    await open();
    const first = rowOf('INV-0398');
    expect(first.getByRole('link', { name: 'Open the reminder' }).getAttribute('href')).toBe('/work/new?invoice=398');
    expect(first.getByRole('link', { name: 'Review the payment' }).getAttribute('href')).toBe('/finance/review/41');
    const record = first.getByText('Record a payment');
    expect(record.closest('a')).toBeNull();
    expect(record.getAttribute('aria-disabled')).toBe('true');
    expect(first.getByText('Not available to you for this invoice').id).toBe(record.getAttribute('aria-describedby'));
    expect(rowOf('INV-0391').getByRole('link', { name: 'Record a payment' }).getAttribute('href')).toBe('/finance/record/34');
  });

  it('has_reminder_draft adds Draft ready beside the reminder link only', async () => {
    await open();
    expect(rowOf('INV-0391').getByText('Draft ready')).toBeTruthy();
    expect(rowOf('INV-0398').queryByText('Draft ready')).toBeNull();
  });

  it('all three links null: three disabled actions, none a link', async () => {
    cookies.psl_mock_invoices = 'links';
    await open();
    const row = rowOf('INV-0398');
    expect(row.queryByRole('link', { name: /reminder|Record|Review/ })).toBeNull();
    expect(row.getAllByText(/Open the reminder|Record a payment|Review the payment/).every((el) => el.getAttribute('aria-disabled') === 'true')).toBe(true);
  });

  it('opens no payment form and sends nothing but reads', async () => {
    await open();
    fireEvent.click(screen.getAllByRole('link', { name: 'Record a payment' })[0]);
    expect(screen.queryByRole('dialog')).toBeNull();
    expect(calls.every((c) => c.method === 'GET')).toBe(true);
  });
});

describe('Show more (AC 6)', () => {
  it('requests the returned cursor and appends the rows, keeping page 1 totals', async () => {
    cookies.psl_mock_invoices = 'paged';
    await open();
    expect(table().getAllByRole('row').slice(1)).toHaveLength(2);
    fireEvent.click(screen.getByRole('button', { name: 'Show more' }));
    await waitFor(() => expect(table().getAllByRole('row').slice(1)).toHaveLength(4));
    expect(reads().map((c) => c.params.get('cursor'))).toEqual([null, 'c2']);
    expect(cellValues('OWED TO PSL')[0]).toContain('₦7,300,000.00 gross');
    expect(screen.queryByRole('button', { name: 'Show more' })).toBeNull();
  });

  it('a failed Show more keeps the rows and offers retry', async () => {
    cookies.psl_mock_invoices = 'paged';
    await open();
    let fail = true;
    override = (call) => (call.params.get('cursor') && fail ? json(500, { code: 'server_error', message: 'x' }) : undefined);
    fireEvent.click(screen.getByRole('button', { name: 'Show more' }));
    await screen.findByRole('alert');
    expect(table().getAllByRole('row').slice(1)).toHaveLength(2);
    fail = false;
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
    await waitFor(() => expect(table().getAllByRole('row').slice(1)).toHaveLength(4));
  });

  it('no Show more without a cursor', async () => {
    await open();
    expect(screen.queryByRole('button', { name: 'Show more' })).toBeNull();
  });
});

describe('what has no source is absent (AC 5)', () => {
  it('shows no BANK DATA TO, row count, filter count, note panel or last-received time', async () => {
    await open();
    expect(screen.queryByText('BANK DATA TO')).toBeNull();
    expect(document.querySelector('.psl-resultcount')?.textContent ?? '').not.toMatch(/INVOICES?/);
    expect(document.querySelector('.psl-countbadge')).toBeNull();
    expect(screen.queryByRole('complementary')).toBeNull();
    expect(screen.queryByText(/SAMPLE DATA/)).toBeNull();
    expect(document.body.textContent).not.toMatch(/10 Nov|14:00/);
  });

  it('the feature code reads no board value, sums nothing and calls no write or v7 route (AC 15)', () => {
    const files = [join(__dirname, '../src/features/finance/payments'), join(__dirname, '../src/app/finance/payments')];
    expect(matchingSources(files, /Harmattan|Lagoon Health|INV-0391|7,300,000|7300000/)).toEqual([]);
    expect(matchingSources(files, /parseFloat|\.reduce\(|Number\(.*(owed|paid|face)|Date\.now|new Date\(/)).toEqual([]);
    expect(matchingSources(files, /api\.POST|liveApi\.POST|\.POST\(|receipts|\/receivables|\/payments\/\$\{|finance\/invoices|api\/v1\/work\b|useMe|\/api\/v1\/me/)).toEqual([]);
  });
});

describe('empty, search and failure (AC 13)', () => {
  it('no invoices and no filter: the plain empty state', async () => {
    cookies.psl_mock_invoices = 'empty';
    await open();
    expect(screen.getByText('No invoices to show yet.')).toBeTruthy();
  });

  it('a filter with no rows: the search-and-filters message with Clear filters', async () => {
    cookies.psl_mock_invoices = 'empty';
    await open('status=paid');
    expect(screen.getByText('Nothing matches your search and filters.')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Clear filters' }));
    expect(nav.replaced.at(-1)).toBe('/finance/payments');
  });

  it('typing sends q after the pause', async () => {
    await open();
    vi.useFakeTimers({ shouldAdvanceTime: true });
    fireEvent.change(screen.getByRole('searchbox', { name: 'Search' }), { target: { value: 'Kora' } });
    await act(() => vi.advanceTimersByTimeAsync(500));
    expect(nav.replaced.at(-1)).toBe('/finance/payments?q=Kora');
  });

  it('a persona without finance gets the no-access card and no invoice data', async () => {
    persona = 'pm';
    await open();
    expect(screen.getByText('NO ACCESS')).toBeTruthy();
    expect(screen.queryByText('INV-0398')).toBeNull();
  });

  it('401 shows the signed-out state with the way back', async () => {
    override = (call) => (call.path === '/api/v1/payments' ? json(401, { code: 'not_signed_in', message: 'Sign in to continue.' }) : undefined);
    await open();
    expect(screen.getByRole('link', { name: 'Sign in' }).getAttribute('href')).toContain(`next=${encodeURIComponent('/finance/payments')}`);
    expect(screen.queryByText('INV-0398')).toBeNull();
  });

  it('the error variant shows the error card and Try again re-reads', async () => {
    cookies.psl_mock_invoices = 'error';
    await open();
    expect(screen.getByText(/couldn’t load the payments/)).toBeTruthy();
    cookies.psl_mock_invoices = 'board';
    fireEvent.click(screen.getByRole('button', { name: /Try again/ }));
    await screen.findByText('INV-0398');
    expect(reads()).toHaveLength(2);
  });

  it.each(['items', 'received_this_month', 'totals'])('a 200 missing %s shows the error card', async (field) => {
    const body = board();
    delete body[field];
    serve(body);
    await open();
    expect(screen.getByText(/couldn’t load the payments/)).toBeTruthy();
    expect(screen.queryByText('INV-0398')).toBeNull();
  });
});
