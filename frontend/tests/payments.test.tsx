// @vitest-environment jsdom
// F-41 SCR-20 Payments and follow-up against the contract mock's E-INVOICES (mock/invoices.mjs, PROPOSAL G-SCR20-1 to -6).
// The fetch stub stands in for the backend: nothing here proves a real ledger, a real total or a real overdue figure;
// it proves the page shows only what it is given, computes nothing and sends its queries to the server.
import { execSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { PaymentsView } from '@/features/finance/payments/PaymentsView';
import { AppShell } from '@/shell/AppShell';

// @ts-expect-error plain ESM module without type declarations
import { contractBody, invoices } from '../mock/invoices.mjs';
import { bellFeed, isBellFeed } from './bell-feed';

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
type Body = Record<string, unknown> & { items: Record<string, unknown>[] };
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
  vi.stubEnv('NEXT_PUBLIC_SHOW_SAMPLE_LABEL', '1');
  vi.stubGlobal(
    'fetch',
    vi.fn(async (request: Request) => {
      if (isBellFeed(request)) return bellFeed();
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
  vi.unstubAllEnvs();
});

const reads = () => calls.filter((c) => c.path === '/api/v1/finance/invoices');
/** Serves `body` for every invoices read. */
const serve = (body: unknown) => {
  override = (call) => (call.path === '/api/v1/finance/invoices' ? json(200, body) : undefined);
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
const cellValue = (label: string) => cell(label).querySelector('.payments__cellvalue')!.textContent;

describe('rows from data (AC 1, 2, 7, 10)', () => {
  it('draws the four board rows in returned order with every column as sent, the count from total and the as-of line', async () => {
    await open('status=issued');
    expect(screen.getByRole('heading', { level: 1, name: 'Payments and follow-up' })).toBeTruthy();
    expect(table().getAllByRole('columnheader').map((h) => h.textContent)).toEqual(['INVOICE', 'WORK', 'INVOICED', 'RECEIVED', 'STILL OWED', 'STATE', 'OVERDUE BY']);
    const refs = table().getAllByRole('row').slice(1).map((r) => r.querySelector('.psl-mono')!.textContent);
    expect(refs).toEqual(['INV-0398', 'INV-0391', 'INV-0402', 'INV-0388']);
    expect(cells('INV-0398').slice(1)).toEqual(['Lagoon Health · M1', '₦3,000,000.00', '₦2,500,000.00', '₦500,000.00', 'PART PAID', '9 days']);
    expect(cells('INV-0391').slice(1)).toEqual(['Harmattan Bank · M1', '₦6,800,000.00', '₦0.00', '₦6,800,000.00', 'OVERDUE', '21 days']);
    expect(cells('INV-0402').slice(1)).toEqual(['Kora Logistics · M1', '₦4,100,000.00', 'Unknown amount not known', 'Unknown amount not known', 'BANK DATA MISSING', '6 days']);
    expect(cells('INV-0388').slice(1)).toEqual(['Sabi Market · final', '₦2,200,000.00', '₦2,200,000.00', '₦0.00', 'PAID', '—']);
    expect(document.querySelector('.psl-resultcount')!.textContent).toBe('4 INVOICES');
    expect(screen.getByText('Updated 12 Nov 10:00')).toBeTruthy();
    // the state's tone is the backend's: PART PAID amber, OVERDUE red, PAID green
    expect(rowOf('INV-0398').getByText('PART PAID').className).toContain('psl-tag--waiting');
    expect(rowOf('INV-0391').getByText('OVERDUE').className).toContain('psl-tag--person');
    expect(rowOf('INV-0388').getByText('PAID').className).toContain('psl-tag--done');
    // sample rows carry the shared label
    expect(rowOf('INV-0398').getByText('SAMPLE DATA')).toBeTruthy();
    expect(screen.queryByText(/7\.3M|₦7\.3/)).toBeNull();
  });

  it('no board value is written in src (AC 1, 12)', () => {
    const root = join(__dirname, '..');
    // the files this feature adds or changes in src (older comments elsewhere in src quote board names)
    const files = 'src/features/finance/payments src/app/finance/payments src/features/workspace/proposals.ts src/features/workspace/Sections.tsx src/features/workspace/Workspace.tsx';
    const grep = (pattern: string) => execSync(`grep -rn "${pattern}" ${files} || true`, { cwd: root, encoding: 'utf8' }).trim();
    expect(grep('Harmattan\\|Lagoon Health\\|INV-0391\\|PART PAID\\|BANK DATA MISSING\\|7,300,000\\|7300000')).toBe('');
    expect(grep('7 days\\|second reminder')).toBe('');
  });

  it('an amount is the decimal string as sent: "500000.10" reads ₦500,000.10, never rounded (AC 2)', async () => {
    const body = board();
    (body.items[0].owed as { amount: string }).amount = '500000.10';
    (body.items[0].received as { amount: string }).amount = '2499999.90';
    serve(body);
    await open();
    expect(cells('INV-0398').slice(3, 5)).toEqual(['₦2,499,999.90', '₦500,000.10']);
  });

  it('the same amounts on the phone cards, at 390 (AC 2, 6, 22)', async () => {
    phone();
    const body = board();
    (body.items[0].owed as { amount: string }).amount = '500000.10';
    serve(body);
    await open();
    expect(screen.getByRole('heading', { level: 1, name: 'Payments' })).toBeTruthy();
    const cards = within(screen.getByRole('list', { name: 'Invoices' })).getAllByRole('listitem');
    // every returned row is a card, PAID included
    expect(cards).toHaveLength(4);
    expect(cards[0].textContent).toContain('Lagoon Health · M1');
    expect(cards[0].textContent).toContain('Still owed ₦500,000.10');
    expect(cards[0].textContent).toContain('INV-0398 · overdue 9 days');
    // the backend says INV-0388 is not overdue: the card adds no overdue words of its own
    expect(cards[3].textContent).toContain('INV-0388');
    expect(cards[3].textContent).not.toContain('overdue');
    expect(cards[3].textContent).toContain('PAID');
    expect(screen.queryByRole('table')).toBeNull();
  });

  it('a copy with sample: false draws no SAMPLE DATA label on that row (AC 10)', async () => {
    const body = board();
    body.items[1].sample = false;
    serve(body);
    await open();
    expect(rowOf('INV-0391').queryByText('SAMPLE DATA')).toBeNull();
    expect(rowOf('INV-0398').getByText('SAMPLE DATA')).toBeTruthy();
  });
});

describe('Unknown is never 0 (AC 3)', () => {
  it('the unknown variant reads Unknown in every unknown amount, overdue cell and strip cell; no ₦0.00, blank or dash stands in', async () => {
    cookies.psl_mock_invoices = 'unknown';
    await open();
    for (const reference of ['INV-0398', 'INV-0391', 'INV-0402', 'INV-0388']) {
      const row = cells(reference);
      expect(row[3]).toBe('Unknown amount not known');
      expect(row[4]).toBe('Unknown amount not known');
      expect(row[6]).toBe('Unknown');
      expect(row.every((text) => text !== '' && text !== '—')).toBe(true);
    }
    const unknown = rowOf('INV-0391').getAllByText('Unknown')[0];
    expect(unknown.className).toContain('psl-unknown');
    for (const label of ['OWED TO PSL', 'OVERDUE', 'RECEIVED THIS MONTH', 'BANK DATA TO']) expect(cellValue(label)).toBe('Unknown');
    expect(document.body.textContent).not.toContain('₦0.00');
  });
});

describe('the page computes nothing (AC 4, 5, 6, 7)', () => {
  it('board strip: OWED with "+ Unknown", OVERDUE, RECEIVED THIS MONTH, BANK DATA TO and the coverage sentence', async () => {
    await open();
    expect(cellValue('OWED TO PSL')).toBe('₦7,300,000.00 + Unknown');
    expect(cellValue('OVERDUE')).toBe('₦6,800,000.00');
    expect(cellValue('RECEIVED THIS MONTH')).toBe('₦4,700,000.00');
    expect(cellValue('BANK DATA TO')).toBe('10 Nov');
    expect(cell('RECEIVED THIS MONTH').textContent).toContain('(November 2026)');
    expect(screen.getByText('"Unknown" means the October bank statement hasn\'t been imported for that account, so the factory won\'t assume nothing was paid.')).toBeTruthy();
  });

  it('has_unknown false removes "+ Unknown"; changing owed.known changes only the OWED cell', async () => {
    const body = board() as Body & { totals_detail: { owed: { known: { amount: string }; has_unknown: boolean } } };
    body.totals_detail.owed.has_unknown = false;
    body.totals_detail.owed.known.amount = '123.45';
    serve(body);
    await open();
    expect(cellValue('OWED TO PSL')).toBe('₦123.45');
    expect(cellValue('OVERDUE')).toBe('₦6,800,000.00');
    expect(cellValue('RECEIVED THIS MONTH')).toBe('₦4,700,000.00');
    expect(cells('INV-0391')[4]).toBe('₦6,800,000.00');
  });

  it("changing INV-0398's received leaves its STILL OWED and the strip unchanged; a changed due date leaves OVERDUE BY unchanged", async () => {
    const body = board();
    (body.items[0].received as { amount: string }).amount = '1.00';
    (body.items[0].due as { date: string }).date = '2020-01-01';
    serve(body);
    await open();
    expect(cells('INV-0398').slice(3)).toEqual(['₦1.00', '₦500,000.00', 'PART PAID', '9 days']);
    expect(cellValue('OWED TO PSL')).toBe('₦7,300,000.00 + Unknown');
  });

  it('without total no count is drawn (rows are never counted)', async () => {
    const body = board();
    delete body.total;
    serve(body);
    await open();
    expect(document.querySelector('.psl-resultcount')!.textContent).toBe('');
    expect(screen.queryByText(/INVOICES/)).toBeNull();
    expect(screen.getByText('Updated 12 Nov 10:00')).toBeTruthy();
  });

  it('a PAID row whose amounts say otherwise still reads PAID; a row without status reads Unknown (no state inferred)', async () => {
    const body = board();
    (body.items[3].owed as { amount: string }).amount = '900.00';
    delete body.items[0].status;
    serve(body);
    await open();
    expect(cells('INV-0388')[5]).toBe('PAID');
    expect(cells('INV-0398')[5]).toBe('Unknown');
  });

  it('overdue: no overdue field and overdue {unknown: true} both read Unknown; {unknown: false} with no days reads —', async () => {
    const body = board();
    delete body.items[0].overdue;
    body.items[1].overdue = { unknown: true, days: 21 };
    serve(body);
    await open();
    expect(cells('INV-0398')[6]).toBe('Unknown');
    expect(cells('INV-0391')[6]).toBe('Unknown');
    expect(cells('INV-0388')[6]).toBe('—');
  });

  it('the contract variant: OWED from totals.owed (Unknown), the other cells Unknown, no coverage sentence, WORK from the project title', async () => {
    cookies.psl_mock_invoices = 'contract';
    await open();
    for (const label of ['OWED TO PSL', 'OVERDUE', 'RECEIVED THIS MONTH', 'BANK DATA TO']) expect(cellValue(label)).toBe('Unknown');
    expect(screen.queryByText(/statement hasn't been imported/)).toBeNull();
    expect(cells('INV-0398')[1]).toBe('Lagoon Health · Lagoon Health · patient app');
    expect(cells('INV-0398')[6]).toBe('Unknown');
    // without agent_note, no note and nothing standing in for it
    expect(screen.queryByRole('complementary', { name: 'Chidi · Finance agent' })).toBeNull();
    expect(screen.queryByRole('link', { name: 'Open the reminder draft' })).toBeNull();
  });

  it('a known typed totals.owed is drawn in full when no totals_detail is sent', async () => {
    serve({ ...contractBody(board()), totals: { owed: { amount: '42.00', currency: 'NGN', unknown: false } } });
    await open();
    expect(cellValue('OWED TO PSL')).toBe('₦42.00');
  });

  it('the payments feature has no payment record, receipt, allocation or short-payment control, and no wording that clears a debt (AC 7)', async () => {
    await open();
    expect(screen.queryByRole('button', { name: /record a payment/i })).toBeNull();
    expect(screen.queryByRole('link', { name: /record a payment|short/i })).toBeNull();
    expect(document.querySelectorAll('main input:not([type=search])')).toHaveLength(0);
    const root = join(__dirname, '..');
    const out = execSync('grep -rniE "written off|write off|settled|cleared|balance" src/features/finance/payments || true', { cwd: root, encoding: 'utf8' });
    expect(out.trim()).toBe('');
    const sums = execSync('grep -rnE "parseFloat|\\.reduce\\(|compactAmount|Date\\.now|new Date\\(" src/features/finance/payments || true', { cwd: root, encoding: 'utf8' });
    expect(sums.trim()).toBe('');
  });
});

describe("Chidi's note (AC 9)", () => {
  it('draws the three lines as agent text, the marked line bold, and links to the reminder', async () => {
    await open();
    const note = within(screen.getByRole('complementary', { name: 'Chidi · Finance agent' }));
    expect(note.getByText('Harmattan Bank is 21 days overdue. I drafted a reminder from the invoice and the SOW payment terms.')).toBeTruthy();
    expect(note.getByText('You send it.').tagName).toBe('STRONG');
    expect(note.getByText("I can't send messages to clients or change what is owed.").tagName).toBe('P');
    expect(note.getByRole('link', { name: 'Open the reminder draft' }).getAttribute('href')).toBe('/work/W-3801');
  });

  it('without work_id no link is drawn; without strong_lines nothing is bold', async () => {
    const body = board() as Body & { agent_note: Record<string, unknown> };
    delete body.agent_note.work_id;
    delete body.agent_note.strong_lines;
    serve(body);
    await open();
    const note = within(screen.getByRole('complementary', { name: 'Chidi · Finance agent' }));
    expect(note.queryByRole('link')).toBeNull();
    expect(note.getByText('You send it.').tagName).toBe('P');
  });
});

describe('search, filter and paging go to the server (AC 8)', () => {
  it('typing "Harm" sends one read with q=Harm after the pause, and none for one character', async () => {
    await open();
    expect(reads()).toHaveLength(1);
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const box = screen.getByRole('searchbox', { name: 'Search' });
    fireEvent.change(box, { target: { value: 'H' } });
    await act(() => vi.advanceTimersByTimeAsync(500));
    expect(reads()).toHaveLength(1);
    fireEvent.change(box, { target: { value: 'Harm' } });
    await act(() => vi.advanceTimersByTimeAsync(500));
    vi.useRealTimers();
    await waitFor(() => expect(reads()).toHaveLength(2));
    expect(reads()[1].params.get('q')).toBe('Harm');
    expect(reads()[1].params.get('limit')).toBe('10');
    expect(nav.replaced.at(-1)).toBe('/finance/payments?q=Harm');
    await waitFor(() => expect(screen.getAllByRole('row')).toHaveLength(2));
  });

  it('Enter follows the same rule (TECH-1-3): one character sends nothing; two send q', async () => {
    await open();
    const box = screen.getByRole('searchbox', { name: 'Search' });
    fireEvent.change(box, { target: { value: 'H' } });
    fireEvent.submit(box.closest('form')!);
    await new Promise((resolve) => setTimeout(resolve, 400));
    expect(reads()).toHaveLength(1);
    fireEvent.change(box, { target: { value: 'Ha' } });
    fireEvent.submit(box.closest('form')!);
    await waitFor(() => expect(reads()).toHaveLength(2));
    expect(reads()[1].params.get('q')).toBe('Ha');
  });

  it('rows are never filtered by the browser: a reply whose rows do not match q is shown whole', async () => {
    serve(board());
    await open('q=zzz');
    expect(reads()[0].params.get('q')).toBe('zzz');
    expect(table().getAllByRole('row')).toHaveLength(5);
  });

  it('Issued from the filter panel sends status=issued and writes it into the address; the chip × and Clear all clear it and re-read', async () => {
    await open();
    fireEvent.click(screen.getByRole('button', { name: 'Filter' }));
    const panel = within(screen.getByRole('dialog', { name: 'Filter' }));
    expect(panel.getAllByRole('radio').map((r) => r.closest('label')!.textContent)).toEqual(['Any state', 'Issued', 'Overdue', 'Part paid', 'Paid']);
    fireEvent.click(panel.getByRole('radio', { name: 'Issued' }));
    fireEvent.click(panel.getByRole('button', { name: 'Show results' }));
    await waitFor(() => expect(reads()).toHaveLength(2));
    expect(reads()[1].params.get('status')).toBe('issued');
    expect(nav.replaced.at(-1)).toBe('/finance/payments?status=issued');
    await screen.findByRole('button', { name: 'Remove State filter' });
    const chip = screen.getByRole('button', { name: 'Remove State filter' }).closest('.psl-chip')!;
    expect(chip.textContent).toBe('StateIssued×');
    fireEvent.click(screen.getByRole('button', { name: 'Remove State filter' }));
    await waitFor(() => expect(reads()).toHaveLength(3));
    expect(reads()[2].params.has('status')).toBe(false);
    expect(nav.replaced.at(-1)).toBe('/finance/payments');

    nav.replaced = [];
    act(() => {
      nav.search = 'status=overdue';
      nav.listeners.forEach((l) => l());
    });
    await waitFor(() => expect(reads()).toHaveLength(4));
    expect(reads()[3].params.get('status')).toBe('overdue');
    fireEvent.click(await screen.findByRole('button', { name: 'Clear all' }));
    await waitFor(() => expect(reads()).toHaveLength(5));
    expect(reads()[4].params.has('status')).toBe(false);
  });

  it('a reload of /finance/payments?status=issued sends the same query', async () => {
    await open('status=issued');
    expect(reads()).toHaveLength(1);
    expect(reads()[0].params.get('status')).toBe('issued');
    expect(screen.getByRole('button', { name: 'Remove State filter' })).toBeTruthy();
  });

  it('paged: a short page with a next_cursor is topped up by cursor until the window of 10 is full or the rows run out', async () => {
    cookies.psl_mock_invoices = 'paged';
    await open();
    await waitFor(() => expect(table().getAllByRole('row')).toHaveLength(5));
    expect(reads()[1].params.get('cursor')).toBe('o2');
    expect(reads()[1].params.get('limit')).toBe('10');
    expect(reads()).toHaveLength(2);
    expect(screen.queryByRole('button', { name: 'Show more' })).toBeNull();
    expect(screen.getByText('All 4 showing')).toBeTruthy();
    // the count stays the backend's total, not the rows shown
    expect(document.querySelector('.psl-resultcount')!.textContent).toBe('4 INVOICES');
  });

  it('a failed Show more keeps the rows and offers Try again', async () => {
    cookies.psl_mock_invoices = 'paged';
    override = (call) => (call.params.has('cursor') ? json(500, { code: 'server_error', message: 'x' }) : undefined);
    await open();
    await screen.findByText(/We couldn’t load more/);
    expect(table().getAllByRole('row')).toHaveLength(3);
    override = () => undefined;
    fireEvent.click(screen.getByRole('button', { name: /^Show (more|\d+ more)$/ }));
    await waitFor(() => expect(table().getAllByRole('row')).toHaveLength(5));
  });
});

describe('empty, error and access (AC 11, 21)', () => {
  it('empty: "No invoices to show yet." and the strip invents no figure', async () => {
    cookies.psl_mock_invoices = 'empty';
    await open();
    expect(screen.getByText('No invoices to show yet.')).toBeTruthy();
    for (const label of ['OWED TO PSL', 'OVERDUE', 'RECEIVED THIS MONTH', 'BANK DATA TO']) expect(cellValue(label)).toBe('Unknown');
    expect(document.body.textContent).not.toContain('₦');
    expect(document.querySelector('.psl-resultcount')!.textContent).toBe('0 INVOICES');
  });

  it('a search with no rows shows "No invoices match" and Clear filters re-reads with no query', async () => {
    await open('q=nobody');
    expect(screen.getByRole('heading', { name: 'No invoices match' })).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Clear filters' }));
    await waitFor(() => expect(reads()).toHaveLength(2));
    expect([...reads()[1].params.keys()]).toEqual(['limit']);
  });

  it('error: the problem card, and Try again sends one new read', async () => {
    cookies.psl_mock_invoices = 'error';
    await open();
    const card = screen.getByRole('alert');
    expect(card.textContent).toContain('We couldn’t load the payments. Nothing was changed.');
    expect(reads()).toHaveLength(1);
    cookies.psl_mock_invoices = 'board';
    fireEvent.click(within(card).getByRole('button', { name: 'Try again' }));
    await waitFor(() => expect(reads()).toHaveLength(2));
    await screen.findByText('INV-0391');
  });

  it('a body without items or as_of is an unexpected response, not an empty list', async () => {
    serve({ items: [] });
    await open();
    expect(screen.getByRole('alert').textContent).toContain('We couldn’t load the payments.');
    expect(screen.queryByText('No invoices to show yet.')).toBeNull();
  });

  it('401: signed out with next=/finance/payments', async () => {
    cookies.psl_mock_scenario = '401';
    override = (call) => (call.path === '/api/v1/finance/invoices' ? json(401, { code: 'not_signed_in', message: 'Sign in to continue.' }) : undefined);
    await open();
    expect(screen.getByRole('link', { name: 'Sign in' }).getAttribute('href')).toContain(`next=${encodeURIComponent('/finance/payments')}`);
  });

  for (const status of [403, 404]) {
    it(`${status}: the not-open view with no client, invoice, amount or count, and no further call`, async () => {
      override = (call) => (call.path === '/api/v1/finance/invoices' ? json(status, { code: 'x', message: 'Hidden from you: Harmattan Bank' }) : undefined);
      await open();
      expect(screen.getByRole('heading', { level: 1, name: 'You can’t open this page' })).toBeTruthy();
      const text = document.body.textContent!;
      for (const s of ['Harmattan', 'INV-', '₦', 'INVOICES', 'Unknown']) expect(text).not.toContain(s);
      expect(reads()).toHaveLength(1);
    });
  }

  for (const who of ['pm', 'none']) {
    it(`persona ${who} gets the not-open view with no further call`, async () => {
      persona = who;
      await open();
      expect(screen.getByRole('heading', { level: 1, name: 'You can’t open this page' })).toBeTruthy();
      expect(reads()).toHaveLength(1);
      expect(calls.every((c) => c.method === 'GET')).toBe(true);
    });
  }

  it('the payments page never reads /me itself and sends no write', async () => {
    await open();
    expect(calls.some((c) => c.path === '/api/v1/me')).toBe(false);
    expect(calls.every((c) => c.method === 'GET')).toBe(true);
    const root = join(__dirname, '..');
    const out = execSync('grep -rn "useMe\\|/api/v1/me" src/features/finance/payments src/features/workspace/proposals.ts || true', { cwd: root, encoding: 'utf8' });
    expect(out.trim()).toBe('');
  });
});
