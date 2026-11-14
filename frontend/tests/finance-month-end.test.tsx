// @vitest-environment jsdom
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

// @ts-expect-error plain ESM module without type declarations
import { contractBody } from '../mock/finance.mjs';
import {
  asOfLine,
  cashView,
  compactAmount,
  countText,
  doneText,
  parsePeriod,
  periodNames,
  taskEnd,
  taskTag,
} from '@/features/finance/month-end/model';
import { MonthEndView } from '@/features/finance/month-end/MonthEndView';
import type { MonthEnd, MonthEndTask } from '@/features/finance/month-end/proposal';

vi.mock('next/navigation', () => ({
  usePathname: () => '/finance/month-end',
  useRouter: () => ({ replace: vi.fn(), push: vi.fn(), prefetch: vi.fn(), back: vi.fn() }),
}));

const fixtures = join(__dirname, '../mock/fixtures');
const read = (name: string) => JSON.parse(readFileSync(join(fixtures, name), 'utf8')) as MonthEnd;
const board = () => read('E-MONTH-END.json');
const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });

let fetchStub: ReturnType<typeof vi.fn<(request: Request) => Promise<Response>>>;
const urls = () => fetchStub.mock.calls.map(([request]) => new URL(request.url));

beforeEach(() => {
  fetchStub = vi.fn<(request: Request) => Promise<Response>>();
  vi.stubGlobal('fetch', fetchStub);
});
afterEach(() => vi.unstubAllGlobals());

async function open(body: unknown, status = 200) {
  fetchStub.mockImplementation(async () => json(status, body));
  const view = render(<MonthEndView period="2026-10" />);
  await waitFor(() => expect(screen.queryByRole('status')).toBeNull());
  return view;
}

const strip = () =>
  within(screen.getByRole('region', { name: 'Facts earned' }))
    .getAllByText(/./, { selector: '.monthend-cell__value' })
    .map((el) => el.textContent);
const rows = () => within(screen.getByRole('table')).getAllByRole('row').slice(1) as HTMLTableRowElement[];
const amount = (value: string, currency = 'NGN') => ({ amount: value, currency, unknown: false });

describe('cashView: unknown is never 0', () => {
  it.each([
    ['4712500.00', 'NGN', '₦4.7M'],
    ['5000000.00', 'NGN', '₦5M'],
    ['4750000.00', 'NGN', '₦4.8M'],
    ['999950000.00', 'NGN', '₦1B'],
    ['999950.00', 'NGN', '₦1M'],
    ['-1250.00', 'NGN', '-₦1.3K'],
    ['1200.00', 'USD', 'USD 1.2K'],
    ['999.50', 'NGN', '₦999.50'],
    ['1000.00', 'NGN', '₦1K'],
  ])('%s %s reads %s', (value, currency, text) => {
    expect(compactAmount(amount(value, currency))).toBe(text);
  });

  it('known part plus Unknown, with the full value as the description', () => {
    expect(cashView(board())).toEqual({
      text: '₦4.7M + Unknown',
      description: 'Known so far ₦4,712,500.00; the rest is not known yet.',
      unknown: true,
    });
  });

  it('fully known reads the compact amount in a plain cell', () => {
    const body = { ...board(), cash_received_detail: { known: amount('4712500.00'), has_unknown: false } };
    expect(cashView(body)).toEqual({ text: '₦4.7M', description: '₦4,712,500.00', unknown: false });
  });

  it.each([
    ['no known part', { has_unknown: true }],
    ['no known part and nothing unknown', { has_unknown: false }],
    ['a malformed amount', { known: amount('4.7M'), has_unknown: true }],
    ['an empty amount', { known: amount(''), has_unknown: false }],
    ['known.unknown true with an amount', { known: { amount: '4712500.00', currency: 'NGN', unknown: true }, has_unknown: false }],
  ])('%s reads Unknown', (_, detail) => {
    expect(cashView({ ...board(), cash_received_detail: detail })).toEqual({ text: 'Unknown', description: 'Not known yet.', unknown: true });
  });

  it('without the proposal field, reads the v4 cash_received', () => {
    expect(cashView({ cash_received: { currency: 'NGN', unknown: true } }).text).toBe('Unknown');
    expect(cashView({ cash_received: { amount: '4712500.00', currency: 'NGN', unknown: true } }).text).toBe('Unknown');
    expect(cashView({ cash_received: amount('4712500.00') }).text).toBe('₦4.7M');
    expect(cashView({ cash_received: amount('7') }).text).toBe('Unknown');
  });
});

describe('period, heading, as-of, counts and tags', () => {
  it('accepts exactly one YYYY-MM month', () => {
    expect(parsePeriod('2026-10')).toBe('2026-10');
    for (const bad of [undefined, '', '2026-13', '2026-00', 'Oct', '2026-1', ['2026-10', '2026-11'], ['2026-10']]) {
      expect(parsePeriod(bad), String(bad)).toBeUndefined();
    }
  });

  it('names the month from the returned period', () => {
    expect(periodNames('2026-10')).toEqual({ long: 'October 2026', short: 'Oct' });
    expect(periodNames('2027-01')).toEqual({ long: 'January 2027', short: 'Jan' });
    expect(periodNames('Q4')).toBeUndefined();
  });

  it('as-of line from coverage and as_of, either alone, or none', () => {
    expect(asOfLine({ coverage: 'FROM RECORDS YOU CAN SEE', as_of: '2026-11-14T09:42:00Z' })).toBe('FROM RECORDS YOU CAN SEE · UPDATED 10:42');
    expect(asOfLine({ as_of: '2026-11-14T09:42:00Z' })).toBe('UPDATED 10:42');
    expect(asOfLine({ coverage: 'FROM RECORDS YOU CAN SEE' })).toBe('FROM RECORDS YOU CAN SEE');
    expect(asOfLine({})).toBeUndefined();
  });

  it('counts are taken as returned; missing reads Unknown', () => {
    expect(doneText({ done: 5, total: 4 })).toBe('5 of 4');
    expect(doneText({ done: 5 })).toBe('Unknown');
    expect(doneText(undefined)).toBe('Unknown');
    expect(countText(0)).toBe('0');
    expect(countText(undefined)).toBe('Unknown');
  });

  it('tag text and colour from the backend, else from the state', () => {
    const task = (extra: Partial<MonthEndTask>): MonthEndTask => ({ line: 'L', where: 'W', state: 'waiting', ...extra });
    expect(taskTag(task({}))).toEqual({ text: 'WAITING', className: 'psl-tag psl-tag--waiting' });
    expect(taskTag(task({ state: 'action_needed' })).text).toBe('ACTION NEEDED');
    const tones = { neutral: 'neutral', person: 'person', stopped: 'person', agent: 'agent', uncertain: 'waiting', restricted: 'waiting', verified: 'done' } as const;
    for (const [tone, cls] of Object.entries(tones)) {
      expect(taskTag(task({ tone: tone as MonthEndTask['tone'], status_label: 'X' }))).toEqual({ text: 'X', className: `psl-tag psl-tag--${cls}` });
    }
  });

  it('restricted rows never link; other rows link only with a work_id', () => {
    const base: MonthEndTask = { line: 'Payroll', where: 'W', state: 'waiting' };
    expect(taskEnd({ ...base, restricted: true, restricted_label: 'HR only', work_id: 'W-9' })).toEqual({ kind: 'restricted', text: 'HR only' });
    expect(taskEnd({ ...base, restricted: true })).toEqual({ kind: 'restricted', text: 'Restricted' });
    expect(taskEnd({ ...base, work_id: 'W 1' })).toEqual({ kind: 'link', href: '/work/W%201' });
    expect(taskEnd(base)).toEqual({ kind: 'none' });
  });
});

describe('MonthEndView', () => {
  it('reads E-MONTH-END once for the period and shows the board in order', async () => {
    await open(board());
    expect(urls().map((u) => u.pathname + u.search)).toEqual(['/api/v1/finance/month-end?period=2026-10']);
    expect(screen.getByText('FINANCE / MONTH-END')).toBeTruthy();
    expect(screen.getByRole('heading', { level: 1 }).textContent).toContain('Month-end · October 2026');
    expect(screen.getByText('FROM RECORDS YOU CAN SEE · UPDATED 10:42')).toBeTruthy();
    expect(strip()).toEqual(['2 of 7', '3', '2', '₦4.7M + Unknown']);
    const cash = screen.getByText('₦4.7M + Unknown');
    expect(document.getElementById(cash.getAttribute('aria-describedby')!)!.textContent).toBe(
      'Known so far ₦4,712,500.00; the rest is not known yet.',
    );
    expect(rows().map((row) => Array.from(row.cells).map((cell) => cell.textContent))).toEqual([
      ['Bank statementsAccess Bank statement missing', '2 of 3 accounts imported', 'WAITING', 'Open'],
      ['Management accountsAccounting preparation and reviewed reports', 'In review · Finance reviewer', 'NEEDS FINANCE DECISION', 'Open'],
      ['Income detail and schedulesIncome detail and schedule inventory', 'Verified 05 Nov', 'DONE', 'Open'],
      ['Fixed asset scheduleAsset schedule and reviewed accounting note', 'Waiting for register review', 'WAITING', 'Open'],
      ['Cash forecastReviewed cash forecast and actual follow-up', 'Published 06 Nov', 'DONE', 'Open'],
      ['Business-unit totalsReviewed BU exception and event aggregates', 'Waiting for payroll matching', 'WAITING', 'Open'],
      ['PayrollRestricted payroll and BU staff-cost receipt', 'Restricted · HR\'s work', 'WAITING ON HR', 'HR only'],
    ]);
    expect(within(rows()[1]).getByText('NEEDS FINANCE DECISION').className).toBe('psl-tag psl-tag--person');
    expect(within(rows()[2]).getByText('DONE').className).toBe('psl-tag psl-tag--done');
    expect(within(rows()[6]).getByText('WAITING ON HR').className).toBe('psl-tag psl-tag--waiting');
    expect(within(rows()[6]).queryByRole('link')).toBeNull();
    expect(rows().slice(0, 6).map((row) => within(row).getByRole('link').getAttribute('href'))).toEqual(
      ['W-1601', 'W-1602', 'W-1603', 'W-1604', 'W-1605', 'W-1606'].map((id) => `/work/${id}`),
    );
    expect(
      rows()
        .slice(0, 6)
        .map((row) => document.getElementById(within(row).getByRole('link').getAttribute('aria-describedby')!)!.textContent),
    ).toEqual(['Bank statements', 'Management accounts', 'Income detail and schedules', 'Fixed asset schedule', 'Cash forecast', 'Business-unit totals']);
    const note = screen.getByText(/One Access Bank statement isn't imported/);
    expect(note.textContent).toBe(
      "Chidi · Finance agentOne Access Bank statement isn't imported, so October's cash received for that account is Unknown, not 0. Import it to complete the month.",
    );
    const avatar = note.parentElement!.querySelector('img')!;
    expect([avatar.getAttribute('src'), avatar.getAttribute('alt')]).toEqual(['/agents/chidi.png', '']);
    const actions = screen.getAllByRole('link', { name: 'Import the missing statement' });
    expect(actions.map((a) => a.getAttribute('href'))).toEqual(['/work/W-1601', '/work/W-1601']);
    expect(screen.getAllByText('← Finance')[0].getAttribute('href')).toBe('/my-work');
  });

  it('a restricted task with a work_id has no link, and /work/W-9 appears nowhere', async () => {
    const body = board();
    body.tasks = [{ line: 'Payroll', where: 'Restricted', state: 'waiting', restricted: true, restricted_label: 'HR only', work_id: 'W-9' }];
    const { container } = await open(body);
    expect(within(rows()[0]).queryByRole('link')).toBeNull();
    expect(within(rows()[0]).getByText('HR only')).toBeTruthy();
    expect(container.querySelector('a[href*="W-9"]')).toBeNull();
    expect(container.innerHTML).not.toContain('/work/W-9');
  });

  it('a restricted task without a label shows Restricted; a task with no work_id has an empty last cell', async () => {
    const body = board();
    body.tasks = [
      { line: 'Payroll', where: 'Restricted', state: 'waiting', restricted: true },
      { line: 'Ledger', where: 'Somewhere', state: 'processing' },
    ];
    await open(body);
    expect(rows()[0].cells[3].textContent).toBe('Restricted');
    expect(rows()[1].cells[3].textContent).toBe('');
    expect(rows()[1].cells[3].children).toHaveLength(0);
  });

  it('counts are shown as returned, never counted from the tasks', async () => {
    await open({ ...board(), summary: { done: 5, waiting: 0, in_progress: 9, total: 4 } });
    expect(strip().slice(0, 3)).toEqual(['5 of 4', '0', '9']);
  });

  it('no summary reads Unknown in the strip and on the phone line', async () => {
    const { summary: _summary, ...body } = board();
    void _summary;
    const { container } = await open(body);
    expect(strip().slice(0, 3)).toEqual(['Unknown', 'Unknown', 'Unknown']);
    expect(container.querySelector('.monthend-summary')!.textContent).toBe('Unknown done · Unknown waiting');
  });

  it('a pure v4 body: no as-of, Unknown counts and cash, line and state words, links only with work_id, no note or action', async () => {
    const { container } = await open(contractBody(board()));
    expect(container.querySelector('.monthend-asof')).toBeNull();
    expect(strip()).toEqual(['Unknown', 'Unknown', 'Unknown', 'Unknown']);
    expect(rows().map((row) => [row.cells[0].textContent, row.cells[2].textContent])).toEqual([
      ['Bank statements', 'WAITING'],
      ['Management accounts', 'ACTION NEEDED'],
      ['Income detail and schedules', 'VERIFIED'],
      ['Fixed asset schedule', 'WAITING'],
      ['Cash forecast', 'VERIFIED'],
      ['Business-unit totals', 'WAITING'],
      ['Payroll', 'WAITING'],
    ]);
    expect(rows().filter((row) => within(row).queryByRole('link'))).toHaveLength(6);
    expect(rows()[6].cells[3].textContent).toBe('');
    expect(container.querySelector('.monthend-note')).toBeNull();
    expect(screen.queryByRole('link', { name: 'Import the missing statement' })).toBeNull();
    expect(container.querySelector('.monthend-bar')).toBeNull();
  });

  it('empty: strip as returned and the empty line, no table, cards, note or action', async () => {
    const { container } = await open(read('finance/month-end.empty.json'));
    expect(strip()).toEqual(['0 of 0', '0', '0', 'Unknown']);
    expect(screen.getByText('No month-end tasks you can see for October 2026.')).toBeTruthy();
    expect(screen.queryByRole('table')).toBeNull();
    expect(container.querySelector('.monthend-cards, .monthend-note, .monthend-bar, .monthend-aside')).toBeNull();
  });

  it('403 and 404 render the same no-access view with nothing about the checklist', async () => {
    const forbidden = await open({ code: 'forbidden', message: 'Month-end is for Finance.' }, 403);
    const html403 = forbidden.container.innerHTML;
    expect(screen.getByRole('heading', { level: 1 }).textContent).toBe('You can’t open this month-end checklist');
    expect(screen.getByRole('link', { name: 'Back to my queue' }).getAttribute('href')).toBe('/my-work');
    expect(forbidden.container.textContent).not.toMatch(/₦|Bank statements|Payroll|[0-9]/);
    forbidden.unmount();
    const missing = await open({ code: 'not_found', message: 'We could not find that record.' }, 404);
    expect(missing.container.innerHTML).toBe(html403);
  });

  it('401 shows the signed-out state with next = this page', async () => {
    await open({ code: 'not_signed_in', message: 'Sign in to continue.' }, 401);
    expect(screen.getByText('You’re signed out.')).toBeTruthy();
    expect(screen.getByRole('link', { name: 'Sign in' }).getAttribute('href')).toBe(
      `/accounts/login/?next=${encodeURIComponent('/finance/month-end?period=2026-10')}`,
    );
  });

  it('500 shows the error card; Try again re-reads and shows the board', async () => {
    await open({ code: 'server_error', message: 'Boom.' }, 500);
    const alert = screen.getByRole('alert');
    expect(alert.textContent).toContain('We couldn’t load the month-end checklist. Your work is safe; nothing was changed.');
    expect(alert.textContent).toContain('Reference server_error for support.');
    fetchStub.mockImplementation(async () => json(200, board()));
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
    await screen.findByRole('table');
    expect(fetchStub).toHaveBeenCalledTimes(2);
  });

  it('a network failure shows the error card with the network reference', async () => {
    fetchStub.mockImplementation(async () => {
      throw new TypeError('fetch failed');
    });
    render(<MonthEndView period="2026-10" />);
    const alert = await screen.findByRole('alert');
    expect(alert.textContent).toContain('Reference network_error for support.');
  });

  it('an answer to a superseded read is ignored', async () => {
    const pending: ((r: Response) => void)[] = [];
    fetchStub.mockImplementation(() => new Promise<Response>((resolve) => pending.push(resolve)));
    const { rerender } = render(<MonthEndView period="2026-10" />);
    await waitFor(() => expect(pending).toHaveLength(1));
    rerender(<MonthEndView period="2026-11" />);
    await waitFor(() => expect(pending).toHaveLength(2));
    expect(urls().map((u) => u.searchParams.get('period'))).toEqual(['2026-10', '2026-11']);
    await act(async () => pending[1](json(200, { ...board(), period: '2026-11', summary: { done: 1, waiting: 1, in_progress: 1, total: 1 } })));
    await screen.findByRole('table');
    await act(async () => pending[0](json(200, board())));
    expect(strip().slice(0, 3)).toEqual(['1 of 1', '1', '1']);
    expect(screen.getByRole('heading', { level: 1 }).textContent).toContain('November 2026');
  });
});
