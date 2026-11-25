// @vitest-environment jsdom
// F-79 SCR-36 Month-end against the contract mock's live GET /month-end (mock/finance.mjs, 1.24.0 shape). The fetch stub
// stands in for the backend: it proves the page shows only what it is given, computes nothing and sends its reads to the live path.
import { join } from 'node:path';

import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

// @ts-expect-error plain ESM module without type declarations
import { monthEnd } from '../mock/finance.mjs';
import { asOfLine, cashView, compactAmount, countText, parsePeriod, periodNames, taskHref, taskTag } from '@/features/finance/month-end/model';
import { MonthEndView } from '@/features/finance/month-end/MonthEndView';
import { matchingSources } from './source-files';

vi.mock('next/navigation', () => ({
  usePathname: () => '/finance/month-end',
  useRouter: () => ({ replace: vi.fn(), push: vi.fn(), prefetch: vi.fn(), back: vi.fn() }),
}));

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });

type Call = { method: string; path: string; params: URLSearchParams };
let persona: string;
let cookies: Record<string, string>;
let calls: Call[];
let override: (call: Call) => Response | undefined;

beforeEach(() => {
  persona = 'finance_lead';
  cookies = {};
  calls = [];
  override = () => undefined;
  vi.stubGlobal(
    'fetch',
    vi.fn(async (request: Request) => {
      const url = new URL(request.url);
      const call = { method: request.method, path: url.pathname, params: url.searchParams };
      calls.push(call);
      const own = override(call);
      if (own) return own;
      const r = monthEnd({ url, persona, cookies });
      return json(r.status, r.body);
    }),
  );
});
afterEach(() => vi.unstubAllGlobals());

async function open(period = '2026-10') {
  const view = render(<MonthEndView period={period} />);
  await waitFor(() => expect(screen.queryByRole('status')).toBeNull());
  return view;
}

const strip = () =>
  Object.fromEntries(
    [...screen.getByRole('region', { name: 'Month-end counts' }).querySelectorAll('.monthend-cell')].map((c) => [c.querySelector('.monthend-cell__label')!.textContent, c.querySelector('.monthend-cell__value')!.textContent]),
  );
const rows = () => within(screen.getByRole('table')).getAllByRole('row').slice(1) as HTMLTableRowElement[];
const cashLines = () => [...document.querySelectorAll('.monthend-cash li')].map((li) => li.textContent);

describe('model', () => {
  it.each([
    ['4712500.00', 'NGN', '₦4.7M'],
    ['5000000.00', 'NGN', '₦5M'],
    ['999950000.00', 'NGN', '₦1B'],
    ['-1250.00', 'NGN', '-₦1.3K'],
    ['1200.00', 'USD', 'USD 1.2K'],
    ['999.50', 'NGN', '₦999.50'],
    ['999.50', 'USD', 'USD 999.50'],
  ])('compactAmount %s %s reads %s', (amount, currency, text) => {
    expect(compactAmount({ amount, currency })).toBe(text);
  });

  it('parsePeriod and periodNames', () => {
    expect(parsePeriod('2026-10')).toBe('2026-10');
    for (const bad of [undefined, '', '2026-13', '2026-00', '26-10', ['2026-10', '2026-11'], '2026-10 ', '0999-10']) expect(parsePeriod(bad as string)).toBeUndefined();
    expect(periodNames('2026-10')).toEqual({ long: 'October 2026', short: 'Oct' });
    expect(periodNames('2026-13')).toBeUndefined();
  });

  it('countText never turns a missing count into 0', () => {
    expect(countText(undefined)).toBe('Unknown');
    expect(countText(-1)).toBe('Unknown');
    expect(countText(1.5)).toBe('Unknown');
    expect(countText(0)).toBe('0');
  });

  it('asOfLine is the Lagos clock, or nothing', () => {
    expect(asOfLine('2026-11-12T09:42:00Z')).toBe('UPDATED 10:42');
    expect(asOfLine(undefined)).toBeUndefined();
    expect(asOfLine('nonsense')).toBeUndefined();
  });

  it('taskHref links only a path on this site', () => {
    expect(taskHref('/projects/abc')).toBe('/projects/abc');
    for (const bad of ['https://x.example', '//x.example', '/\\x.example', 'javascript:alert(1)', 'projects/abc', '']) expect(taskHref(bad)).toBeUndefined();
  });

  it('taskTag reads the returned label in the tone of the state; stopped reuses the stopped tone', () => {
    expect(taskTag({ state: 'done', label: 'Verified' })).toEqual({ text: 'Verified', tone: 'done' });
    expect(taskTag({ state: 'waiting', label: 'W' }).tone).toBe('waiting');
    expect(taskTag({ state: 'in_progress', label: 'P' }).tone).toBe('agent');
    expect(taskTag({ state: 'stopped', label: 'S' }).tone).toBe('person');
  });

  const ws = (caseId: string, unavailable: boolean) => ({ workspace: { case_id: caseId, title: 'T', revision: 1, sample: false }, cash_unavailable: unavailable }) as never;
  const row = (workspaceId: string | null, workspace: string | null, amount: string, currency = 'NGN', basis = 'gross') => ({ workspace_id: workspaceId, workspace, currency, basis, amount, sample: false });

  it('cashView: no path returns 0 for a missing, unavailable or malformed amount', () => {
    const outcomes = [
      cashView({ cash: [], workspaces: [], more_cash_groups: false }),
      cashView({ cash: [row('a', 'A', 'abc')], workspaces: [], more_cash_groups: false }),
      cashView({ cash: [row('a', 'A', '12')], workspaces: [], more_cash_groups: false }),
      cashView({ cash: [row('a', 'A', '500.00')], workspaces: [ws('a', true)], more_cash_groups: false }),
      cashView({ cash: [], workspaces: [ws('a', true)], more_cash_groups: false }),
    ];
    const texts = outcomes.flatMap((o) => [o.cell, ...o.lines.map((l) => l.text)]);
    expect(texts.join(' ')).not.toMatch(/(^|\s)(₦|USD )?0(\.00)?($|\s)/);
    expect(outcomes[0].cell).toBe('Unknown');
    expect(outcomes[3]).toMatchObject({ cell: 'By project', lines: [{ text: 'Unknown', unknown: true }] });
    expect(outcomes[4].lines).toEqual([{ key: 'u0', workspace: 'T', text: 'Unknown', unknown: true }]);
  });

  it('cashView: one amount stands alone; a confirmed 0.00 is shown as a zero', () => {
    expect(cashView({ cash: [row('a', 'A', '4700000.00')], workspaces: [], more_cash_groups: false })).toMatchObject({ cell: '₦4.7M', lines: [] });
    expect(cashView({ cash: [row('a', 'A', '0.00')], workspaces: [], more_cash_groups: false }).cell).toBe('₦0.00');
  });

  it('cashView: two currencies are two lines and never a combined figure', () => {
    const view = cashView({ cash: [row('a', 'A', '4700000.00'), row('b', 'B', '12000.00', 'USD', 'net')], workspaces: [], more_cash_groups: false });
    expect(view.cell).toBe('By project');
    expect(view.lines.map((l) => `${l.workspace} ${l.text} ${l.basis}`)).toEqual(['A ₦4.7M gross', 'B USD 12K net']);
  });
});

describe('the live path (AC 1)', () => {
  it('reads GET /api/v1/month-end?month=2026-10 once, and never the v7 route', async () => {
    await open();
    expect(calls.map((c) => `${c.method} ${c.path}?${c.params}`)).toEqual(['GET /api/v1/month-end?month=2026-10']);
  });

  it('the page route sends no request for an invalid period (parsePeriod gates it)', () => {
    expect(parsePeriod('2026-13')).toBeUndefined();
    expect(calls).toHaveLength(0);
  });
});

describe('tasks and counts (AC 2, 3)', () => {
  it('shows the returned rows in order with title, workspace, label and time, and the counts with Stopped and no total', async () => {
    await open();
    expect(screen.getByRole('heading', { level: 1 }).textContent).toContain('October 2026');
    expect(screen.getByText('UPDATED 10:42')).toBeTruthy();
    expect(strip()).toMatchObject({ DONE: '2', WAITING: '1', 'IN PROGRESS': '3', STOPPED: '1' });
    expect(screen.queryByText(/ of \d/)).toBeNull();
    expect(within(screen.getByRole('table')).getAllByRole('columnheader').map((h) => h.textContent)).toEqual(['TASK', 'STATE', 'UPDATED']);
    expect(rows().map((r) => r.cells[0].textContent)).toEqual([
      'Receivables snapshotLagoon Health patient app',
      'Bank statementsHarmattan Bank mobile onboarding',
      'Management accountsLagoon Health patient app',
      'Income detail and schedulesKora Foods portal',
    ]);
    expect(rows().map((r) => r.cells[1].textContent)).toEqual(['Waiting for review', 'Waiting for the Access Bank statement', 'Agent preparing', 'Verified']);
    expect(rows()[0].cells[2].textContent).toBe('12 Nov 09:10');
    expect(within(rows()[3]).getByText('Verified').className).toContain('psl-tag--done');
  });

  it('a title links to a returned path; the link is a plain anchor', async () => {
    await open();
    expect(screen.getAllByText('Receivables snapshot')[0].closest('a')!.getAttribute('href')).toBe('/projects/00000000-0000-4000-8000-000000000101');
  });

  it('Show more requests next_page, appends the rows and keeps page 1 counts; the control then goes', async () => {
    await open();
    fireEvent.click(screen.getByRole('button', { name: 'Show more' }));
    await waitFor(() => expect(rows()).toHaveLength(6));
    expect(calls.map((c) => c.params.get('page'))).toEqual([null, '2']);
    expect(strip()).toMatchObject({ DONE: '2', STOPPED: '1' });
    expect(within(rows()[4]).getByText('Stopped: register not reviewed').className).toContain('psl-tag--person');
    // a url that is not a path is not linked
    expect(within(rows()[5]).getByText('Payroll summary').closest('a')).toBeNull();
    expect(screen.queryByRole('button', { name: 'Show more' })).toBeNull();
  });

  it('a failed Show more keeps the rows and offers a retry', async () => {
    await open();
    override = (call) => (call.params.has('page') ? json(500, { code: 'server_error', message: 'x' }) : undefined);
    fireEvent.click(screen.getByRole('button', { name: 'Show more' }));
    await screen.findByRole('alert');
    expect(rows()).toHaveLength(4);
    override = () => undefined;
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
    await waitFor(() => expect(rows()).toHaveLength(6));
  });

  it('no Show more without a next page', async () => {
    cookies.psl_mock_month_end = 'one-page';
    await open();
    expect(screen.queryByRole('button', { name: 'Show more' })).toBeNull();
  });
});

describe('cash (AC 4)', () => {
  it('one amount stands alone in the strip, with no list', async () => {
    await open();
    expect(strip()['CASH RECEIVED']).toBe('₦4.7M');
    expect(cashLines()).toEqual([]);
  });

  it('a cash_unavailable workspace reads By project with that line Unknown', async () => {
    cookies.psl_mock_month_end = 'cash-unavailable';
    await open();
    expect(strip()['CASH RECEIVED']).toBe('By project');
    expect(cashLines()).toEqual(['Lagoon Health patient app₦4.7Mgross', 'Harmattan Bank mobile onboardingUnknown']);
    expect(document.body.textContent).not.toContain('900');
  });

  it('two currencies show two lines and no combined figure', async () => {
    cookies.psl_mock_month_end = 'two-currency';
    await open();
    expect(strip()['CASH RECEIVED']).toBe('By project');
    expect(cashLines()).toEqual(['Lagoon Health patient app₦4.7Mgross', 'Harmattan Bank mobile onboardingUSD 12Kgross']);
  });

  it('more_cash_groups adds the neutral line', async () => {
    cookies.psl_mock_month_end = 'more-cash';
    await open();
    expect(screen.getByText('More projects are not shown here')).toBeTruthy();
    expect(strip()['CASH RECEIVED']).toBe('By project');
  });

  it('a row with no workspace name reads Project not named', async () => {
    cookies.psl_mock_month_end = 'unnamed';
    await open();
    expect(cashLines()).toEqual(['Lagoon Health patient app₦4.7Mgross', 'Project not named₦250Kgross']);
  });

  it('a confirmed 0.00 row shows a zero', async () => {
    cookies.psl_mock_month_end = 'zero';
    await open();
    expect(strip()['CASH RECEIVED']).toBe('₦0.00');
  });
});

describe('what has no source is absent (AC 5, 15)', () => {
  it('shows no agent note, next action, detail line, restricted text or N of M', async () => {
    await open();
    expect(screen.queryByRole('complementary')).toBeNull();
    expect(screen.queryByRole('link', { name: /Open$|next/i })).toBeNull();
    expect(screen.queryByText(/restricted|HR only/i)).toBeNull();
    expect(screen.queryByText(/ of \d/)).toBeNull();
    expect(document.querySelector('.monthend-bar, .monthend-note, .monthend-aside')).toBeNull();
  });

  it('the feature code sends no write and calls no v7 or per-project route', () => {
    const files = [join(__dirname, '../src/features/finance/month-end'), join(__dirname, '../src/app/finance/month-end')];
    expect(matchingSources(files, /api\.POST|liveApi\.POST|\.POST\(|receipts|\/receivables|finance\/month-end'|can_capture|\.reduce\(|parseFloat/)).toEqual([]);
  });
});

describe('empty, access and failure (AC 13)', () => {
  it('no work shows the empty card and the counts', async () => {
    cookies.psl_mock_month_end = 'empty';
    await open();
    expect(screen.getByText('Nothing to close this month')).toBeTruthy();
    expect(strip()).toMatchObject({ DONE: '0', WAITING: '0', 'IN PROGRESS': '0', STOPPED: '0' });
  });

  it('a persona without finance gets the no-access card with no task data', async () => {
    persona = 'pm';
    await open();
    expect(screen.getByText('NO ACCESS')).toBeTruthy();
    expect(screen.queryByText('Receivables snapshot')).toBeNull();
  });

  it('401 shows the signed-out state', async () => {
    override = () => json(401, { code: 'not_signed_in', message: 'Sign in to continue.' });
    await open();
    expect(screen.getByRole('link', { name: 'Sign in' }).getAttribute('href')).toContain(encodeURIComponent('/finance/month-end?period=2026-10'));
  });

  it('the error variant shows the error card and Try again re-reads', async () => {
    cookies.psl_mock_month_end = 'error';
    await open();
    expect(screen.getByText(/couldn’t load the month-end checklist/)).toBeTruthy();
    cookies.psl_mock_month_end = '';
    fireEvent.click(screen.getByRole('button', { name: /Try again/ }));
    await screen.findAllByText('Receivables snapshot');
    expect(calls).toHaveLength(2);
  });

  it.each(['work', 'counts', 'cash'])('a 200 missing %s shows the error card', async (field) => {
    const r = monthEnd({ url: new URL('http://x/api/v1/month-end?month=2026-10'), persona, cookies });
    const body = { ...r.body } as Record<string, unknown>;
    delete body[field];
    override = () => json(200, body);
    await open();
    expect(screen.getByText(/couldn’t load the month-end checklist/)).toBeTruthy();
  });
});
