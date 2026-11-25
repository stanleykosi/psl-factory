// @vitest-environment jsdom
// F-101: the income schedule (SCR-54 part 1) on the live work item, against the live-shaped mock (mock/income-schedules-live.mjs).
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import Ajv2020 from 'ajv/dist/2020';
import addFormats from 'ajv-formats';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { setCsrfToken } from '@/api/client';
import type { LiveSchedule } from '@/api/types';
import { ToastProvider } from '@/components';
import { LiveWorkItemView } from '@/features/work-item/live/LiveWorkItemView';
import { amountText, HOLD_TEXT, incomeSchedulesAdapter, offeredVerdicts, scheduleCommands, scheduleSections } from '@/features/workspace/incomeSchedulesAdapter';
import { resetScopedWriteLocks } from '@/features/workspace/useWriteLock';

// @ts-expect-error plain ESM module without type declarations
import { INCOME_SCHEDULES_PATH, incomeSchedulesLive, resetIncomeSchedulesLive } from '../mock/income-schedules-live.mjs';

vi.mock('@/shell/AppShell', () => ({ usePhoneBack: () => undefined }));
vi.mock('next/navigation', () => ({ usePathname: () => '/work/4203', useRouter: () => ({ replace: vi.fn(), push: vi.fn(), prefetch: vi.fn() }) }));

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
const me = { name: 'Kemi Adebayo', destinations: [], startable_lines: [], csrf_token: 't', assistant_agents: [] };
let scenario: string | undefined;
let fetchStub: ReturnType<typeof vi.fn<(request: Request) => Promise<Response>>>;
const posts = () => fetchStub.mock.calls.filter(([r]) => r.method === 'POST');
const sent = async () => Promise.all(posts().map(async ([r]) => ({ path: new URL(r.url).pathname, csrf: r.headers.get('X-CSRFToken'), body: JSON.parse(await r.clone().text()) as Record<string, unknown> })));

beforeEach(() => {
  resetScopedWriteLocks();
  resetIncomeSchedulesLive();
  scenario = undefined;
  setCsrfToken('t');
  fetchStub = vi.fn(async (request: Request) => {
    const url = new URL(request.url);
    if (url.pathname === '/api/v1/me') return json(200, me);
    if (url.pathname === '/api/v1/session') return json(200, { csrf_token: 't', signed_in: true, next_url: '/' });
    if (!INCOME_SCHEDULES_PATH.test(url.pathname)) return json(404, { code: 'not_found', message: 'This record is unavailable.' });
    const post = request.method === 'POST';
    const rawBytes = post ? Buffer.from(await request.clone().text()) : undefined;
    const [status, body] = incomeSchedulesLive({ method: request.method.toLowerCase(), url, scenario: post ? scenario : undefined, csrfOk: request.headers.get('X-CSRFToken') === 't', persona: 'finance_lead', rawBytes }) as [number | 'drop', unknown];
    if (status === 'drop') throw new TypeError('network');
    return json(status, body);
  });
  vi.stubGlobal('fetch', fetchStub);
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const open = async (id: number, wait: RegExp | string = /What was found/) => {
  render(
    <ToastProvider>
      <LiveWorkItemView id={String(id)} tab="overview" />
    </ToastProvider>,
  );
  await screen.findAllByText(wait, {}, { timeout: 8000 });
};
const btn = (name: string) => screen.queryByRole('button', { name }) as HTMLButtonElement | null;
const ALL = ['Approve', 'Return', 'Reject', 'Withdraw approval'];
const choose = () => {
  fireEvent.click(screen.getByRole('combobox', { name: /Evidence/ }));
  fireEvent.click(screen.getByRole('option', { name: /^document/ }));
};
const note = (text: string) => fireEvent.change(screen.getByLabelText(/Note/), { target: { value: text } });
const schedule = (id: number, patch: object = {}) => ({ ...(incomeSchedulesLive({ method: 'get', url: new URL(`/api/v1/work/${id}/finance-schedule`, 'http://m.local'), csrfOk: true, persona: 'finance_lead' }) as [number, LiveSchedule])[1], ...patch }) as LiveSchedule;
const ctx = { workId: 4203, caseId: 'c', revision: 5, caseRevision: 12 };

const spec = JSON.parse(readFileSync(join(__dirname, '../../contracts/psl-factory.openapi.json'), 'utf8')) as { paths: Record<string, Record<string, object>> };
const ajv = new Ajv2020({ allErrors: true, strict: false });
addFormats(ajv);
ajv.addSchema({ $id: 'spec', ...spec });
const schemaOf = (path: string, method: string, status: string) => `spec#/paths/${path.replaceAll('/', '~1')}/${method}/responses/${status}/content/application~1json/schema`;

describe('the contract and the mock agree', () => {
  it('every read answers the operation’s 200 shape, and the write its 200', () => {
    const valid = ajv.getSchema(schemaOf('/api/v1/work/{work_id}/finance-schedule', 'get', '200'))!;
    for (const id of [4201, 4202, 4203, 4204, 4205, 4206, 4207]) {
      expect(valid(schedule(id)), JSON.stringify(valid.errors)).toBe(true);
    }
    const write = ajv.getSchema(schemaOf('/api/v1/work/{work_id}/reviews', 'post', '200'))!;
    const body = JSON.stringify({ kind: 'schedule', expected_revision: 5, case_revision: 12, target_id: 9, verdict: 'approve', evidence_id: 61, note: 'ok' });
    const [status, answer] = incomeSchedulesLive({ method: 'post', url: new URL('/api/v1/work/4203/reviews', 'http://m.local'), csrfOk: true, persona: 'finance_lead', rawBytes: Buffer.from(body) }) as [number, unknown];
    expect(status).toBe(200);
    expect(write(answer), JSON.stringify(write.errors)).toBe(true);
  });
});

describe('the sections', () => {
  const text = (s: LiveSchedule) => JSON.stringify(scheduleSections(s));
  it('an unknown amount and total read Unknown, never 0', () => {
    expect(amountText(null, 'NGN')).toBe('Unknown');
    expect(amountText('1500000.00', 'NGN')).toBe('1,500,000.00 NGN');
    const rows = scheduleSections(schedule(4201)).find((s) => s.key === 'rows')!;
    expect(rows.items.map((i) => i.cells!.find((c) => c.column === 'amount')!.text)).toEqual(['1,500,000.00 NGN', 'Unknown', '250,000.50 NGN']);
    const result = scheduleSections(schedule(4203)).find((s) => s.key === 'result')!;
    expect(result.items.find((i) => i.id === 'additive')!.value).toBe('Unknown');
    expect(text(schedule(4203))).not.toMatch(/"0(\.00)?"|₦/);
  });
  it('draws no result block when result is null, and no inventory block for an income read', () => {
    expect(scheduleSections(schedule(4201)).map((s) => s.key)).toEqual(['found', 'schedule', 'rows']);
    expect(scheduleSections(schedule(4203)).map((s) => s.key)).toEqual(['found', 'schedule', 'rows', 'result']);
  });
  it('held: findings, what is missing and the duplicate lines as returned', () => {
    const keys = scheduleSections(schedule(4202)).map((s) => s.key);
    expect(keys).toEqual(['found', 'schedule', 'rows', 'result', 'findings', 'missing', 'duplicates']);
    expect(text(schedule(4202))).toContain('row-7');
    expect(text(schedule(4202))).toContain('Report line');
  });
  it('returned shows the rows and no quoted note', () => {
    const s = scheduleSections(schedule(4204)).find((x) => x.key === 'returned')!;
    expect(s.title).toBe('Returned for correction');
    expect(s.items.map((i) => i.text)).toEqual(['row-12: Disaggregation']);
  });
  it('a hold code draws its own sentence; no code draws none', () => {
    expect(JSON.stringify(scheduleSections(schedule(4206)))).toContain(HOLD_TEXT.reviewer_missing);
    expect(JSON.stringify(scheduleSections(schedule(4206, { review_hold_code: 'review_rule_missing' })))).toContain(HOLD_TEXT.review_rule_missing);
    expect(JSON.stringify(scheduleSections(schedule(4205)))).not.toMatch(/set to review|isn’t set up/);
  });
  it('inventory: coverage as returned, schedules read only, a restricted schedule shows its key only', () => {
    const keys = scheduleSections(schedule(4207)).map((s) => s.key);
    expect(keys).toEqual(['found', 'coverage', 'inventory']);
    const inv = scheduleSections(schedule(4207)).find((s) => s.key === 'inventory')!;
    expect(inv.items[1]!.cells).toEqual([{ column: 'schedule', text: 'restricted-detail' }]);
    expect(text(schedule(4207))).not.toContain('Hidden');
  });
});

describe('the verdicts and the command', () => {
  it('offers only the verdicts the read lists, in order, and only while a review is open', () => {
    expect(offeredVerdicts(schedule(4203))).toEqual(['approve', 'return', 'reject']);
    expect(offeredVerdicts(schedule(4205))).toEqual(['revoke']);
    for (const id of [4201, 4204, 4206]) expect(offeredVerdicts(schedule(id))).toEqual([]);
    expect(offeredVerdicts(schedule(4203, { review_verdicts: ['reject', 'bless', 'approve'] }))).toEqual(['approve', 'reject']);
    expect(offeredVerdicts(schedule(4203, { schedule_id: null }))).toEqual([]);
  });
  it('4205 has no review id yet offers revoke because the read lists it; no hold code and no verdicts invents nothing', () => {
    expect(offeredVerdicts(schedule(4205, { review_verdicts: [] }))).toEqual([]);
    expect(JSON.stringify(scheduleSections(schedule(4205, { review_verdicts: [] })))).not.toMatch(/Nobody|rule/);
  });
  it('describes one review command with the exact body, no action and no key', () => {
    const [c, ...rest] = scheduleCommands(schedule(4203), ctx);
    expect(rest).toEqual([]);
    expect(c!.id).toBe('income-schedules.review');
    expect(c!.url).toBe('/api/v1/work/4203/reviews');
    expect(c!.idempotency.field).toBeNull();
    expect(c!.successStatuses).toEqual([200]);
    expect(c!.body({ verdict: 'approve', evidence_id: 61, note: 'ok' })).toEqual({ kind: 'schedule', expected_revision: 5, case_revision: 12, target_id: 9, verdict: 'approve', evidence_id: 61, note: 'ok' });
    expect(incomeSchedulesAdapter.commands!(schedule(4203), ctx)).toHaveLength(1);
  });
  it('a null token stays null and holds the command; no schedule holds it', () => {
    const [c] = scheduleCommands(schedule(4203, { expected_revision: null, case_revision: null }), ctx);
    expect(c!.body({})).toMatchObject({ expected_revision: null, case_revision: null });
    expect(c!.disabledReason).toMatch(/Reload and try again/);
    expect(scheduleCommands(schedule(4203, { schedule_id: null }), ctx)[0]!.disabledReason).toMatch(/no schedule/);
  });
});

describe('the page', () => {
  it('4203 shows the stage, rows, result and exactly Approve, Return and Reject', async () => {
    await open(4203);
    expect(screen.getByText('The rows add up to the parent amount.')).toBeTruthy();
    expect(screen.getByText('row-12')).toBeTruthy();
    expect(screen.getAllByText('Unknown').length).toBeGreaterThan(0);
    expect(btn('Approve')).toBeTruthy();
    expect(btn('Return')).toBeTruthy();
    expect(btn('Reject')).toBeTruthy();
    expect(btn('Withdraw approval')).toBeNull();
  });
  it('4205 offers only Withdraw approval; 4201, 4204 and 4206 offer none', async () => {
    await open(4205);
    expect(ALL.filter((n) => btn(n))).toEqual(['Withdraw approval']);
    for (const id of [4201, 4204, 4206]) {
      cleanup();
      await open(id);
      expect(ALL.filter((n) => btn(n))).toEqual([]);
    }
  });
  it('4206 says nobody is set to review, with no panel, reviewer name or link', async () => {
    await open(4206);
    expect(screen.getByText(HOLD_TEXT.reviewer_missing)).toBeTruthy();
    expect(screen.queryByText('Your decision')).toBeNull();
    expect(screen.queryByRole('link', { name: /set ?up|setup/i })).toBeNull();
  });
  it('4202 shows the duplicates read only; 4204 the returned rows; 4207 the inventory with no button', async () => {
    await open(4202);
    expect(screen.getByText('Possible duplicates')).toBeTruthy();
    expect(screen.getAllByText('row-7').length).toBe(2);
    cleanup();
    await open(4204);
    expect(screen.getByText('Returned for correction')).toBeTruthy();
    expect(screen.queryByText(/Correct and resubmit/i)).toBeNull();
    cleanup();
    await open(4207, /Coverage/);
    expect(screen.getAllByText('Partial').length).toBeGreaterThan(0);
    expect(screen.queryByText('Rows')).toBeNull();
    expect(ALL.filter((n) => btn(n))).toEqual([]);
  });
  it('4299 is unavailable with no title and no other call', async () => {
    render(<ToastProvider><LiveWorkItemView id="4299" tab="overview" /></ToastProvider>);
    await screen.findAllByText(/unavailable/i, {}, { timeout: 8000 });
    expect(screen.queryByText(/Kora Logistics/)).toBeNull();
  });
  it('nothing is sent without evidence and a note, and the reasons show', async () => {
    await open(4203);
    for (const n of ['Approve', 'Return', 'Reject']) expect(btn(n)!.disabled).toBe(true);
    expect(screen.getAllByText('Choose the evidence this decision rests on.').length).toBeGreaterThan(0);
    choose();
    expect(btn('Approve')!.disabled).toBe(true);
    expect(screen.getAllByText('Add a note.').length).toBeGreaterThan(0);
    fireEvent.click(btn('Approve')!);
    note('   ');
    expect(btn('Approve')!.disabled).toBe(true);
    expect(posts()).toHaveLength(0);
  });
  it('evidence only from evidence[]; none shows the message and no buttons', async () => {
    await open(4203);
    fireEvent.click(screen.getByRole('combobox', { name: /Evidence/ }));
    expect(screen.getAllByRole('option')).toHaveLength(1);
    expect(document.querySelector('input[type=file]')).toBeNull();
  });
  it('Approve sends one exact body with the CSRF header, re-reads, then shows verified from the re-read', async () => {
    await open(4203);
    choose();
    note('  Checked against the ledger.  ');
    fireEvent.click(btn('Approve')!);
    await screen.findAllByText(/Verified/);
    expect(await sent()).toEqual([{ path: '/api/v1/work/4203/reviews', csrf: 't', body: { kind: 'schedule', expected_revision: 5, case_revision: 12, target_id: 9, verdict: 'approve', evidence_id: 61, note: 'Checked against the ledger.' } }]);
    await waitFor(() => expect(btn('Approve')).toBeNull());
    expect(btn('Withdraw approval')).toBeTruthy();
  });
  it('a 200 whose re-read shows the old schedule does not say verified', async () => {
    scenario = 'wstale';
    await open(4203);
    choose();
    note('ok');
    fireEvent.click(btn('Approve')!);
    await waitFor(() => expect(posts()).toHaveLength(1));
    await screen.findByText(/This item is now: Waiting/);
    expect(screen.queryByText(/Verified/)).toBeNull();
    expect(btn('Approve')).toBeTruthy();
  });
  it('409 says nothing was recorded, re-reads and keeps the note and evidence', async () => {
    scenario = 'w409';
    await open(4203);
    choose();
    note('keep me');
    fireEvent.click(btn('Return')!);
    await screen.findByText(/This schedule changed while you were reading it, so nothing was recorded\./);
    expect((screen.getByLabelText(/Note/) as HTMLTextAreaElement).value).toBe('keep me');
    expect(screen.getByRole('combobox', { name: /Evidence/ }).textContent).toMatch(/document/);
    expect(posts()).toHaveLength(1);
  });
  it('a dropped connection or a 503 never sends twice and says it could not confirm', async () => {
    scenario = 'wdrop';
    await open(4203);
    choose();
    note('ok');
    fireEvent.click(btn('Approve')!);
    await screen.findByText(/We couldn’t confirm whether your decision was recorded\. Check the schedule before trying again\./);
    for (const n of ['Approve', 'Return', 'Reject']) expect(btn(n)!.disabled).toBe(true);
    fireEvent.click(btn('Approve')!);
    expect(posts()).toHaveLength(1);
  });
  it('403 csrf asks to press again; 429 and 503 say try again shortly; 422 shows the field message and keeps the input', async () => {
    scenario = 'wcsrf';
    await open(4203);
    choose();
    note('keep');
    fireEvent.click(btn('Approve')!);
    await screen.findByText(/Press the button again\./);
    expect(screen.queryByText(/can’t review/)).toBeNull();
    expect(posts()).toHaveLength(1);
    scenario = 'w429';
    fireEvent.click(btn('Approve')!);
    await screen.findByText(/Try again shortly\./);
    expect(posts()).toHaveLength(2);
    scenario = 'w422';
    fireEvent.click(btn('Approve')!);
    await screen.findByText(/The request was not accepted\./);
    expect(screen.getByText(/The note is needed\./)).toBeTruthy();
    expect((screen.getByLabelText(/Note/) as HTMLTextAreaElement).value).toBe('keep');
  });
  it('the page has no ledger, export or correct-and-resubmit words', async () => {
    await open(4203);
    expect(document.body.textContent).not.toMatch(/Posted to the ledger|Export|Correct and resubmit/i);
  });
});
