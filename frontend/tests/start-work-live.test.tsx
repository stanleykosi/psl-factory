// @vitest-environment jsdom
// F-86: Start work on the live API: the chooser, the project and source reads, the weekly start and its answers, the upload
// wrapper and the registry. The fetch stand-in is the mock itself (mock/start-live.mjs), so the shapes are the browser's.
import { act, fireEvent, render, renderHook, screen, waitFor, within } from '@testing-library/react';
import { readFileSync, readdirSync } from 'node:fs';
import { join } from 'node:path';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { setCsrfToken } from '@/api/client';
import { LineChooser } from '@/features/start-work/LineChooser';
import { StartWorkDrawer } from '@/features/start-work/StartWorkDrawer';
import { lineFormFor } from '@/features/start-work/lines';
import { localMidnight, weeklyReport } from '@/features/start-work/lines/weeklyReport';
import { mapProblems, useStart } from '@/features/start-work/useStart';
import { fetchProjects, fetchSources, useLines } from '@/features/start-work/useStartWork';
import type { WeeklyBody } from '@/features/start-work/types';
import { StartUpload } from '@/features/start-work/StartUpload';

// @ts-expect-error plain ESM module without type declarations
import { resetStartLive, startLive, startLiveLog } from '../mock/start-live.mjs';

const nav = vi.hoisted(() => ({ push: vi.fn() }));
vi.mock('next/navigation', () => ({
  usePathname: () => '/my-work',
  useRouter: () => ({ push: nav.push, replace: vi.fn(), prefetch: vi.fn() }),
}));

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
const TOKEN = 'mock-csrf-pm';
let scenario: string | undefined;
let override: ((request: Request, url: URL) => Response | undefined) | undefined;
let fetchStub: ReturnType<typeof vi.fn<(request: Request) => Promise<Response>>>;
const requests = () => fetchStub.mock.calls.map(([r]) => r);
const reads = (path: RegExp) => requests().filter((r) => path.test(new URL(r.url).pathname));
const bodies = async () => Promise.all(reads(/^\/api\/v1\/work$/).filter((r) => r.method === 'POST').map(async (r) => JSON.parse(await r.clone().text())));

beforeEach(() => {
  resetStartLive();
  scenario = undefined;
  override = undefined;
  nav.push.mockReset();
  setCsrfToken(TOKEN);
  fetchStub = vi.fn(async (request: Request) => {
    const url = new URL(request.url);
    const custom = override?.(request, url);
    if (custom) return custom;
    if (url.pathname === '/api/v1/session') return json(200, { csrf_token: 'fresh', signed_in: true, next_url: '/' });
    const raw = request.method === 'GET' ? '' : await request.clone().text();
    const [status, body] = startLive({ method: request.method.toLowerCase(), url, raw, scenario, csrfOk: request.headers.get('x-csrftoken') === TOKEN, persona: 'pm' });
    return json(status, body);
  });
  vi.stubGlobal('fetch', fetchStub);
});
afterEach(() => {
  vi.unstubAllGlobals();
  setCsrfToken(null);
});

const WEEK = { from: '2026-11-16', to: '2026-11-22' };
const PROJECT = { case_id: '00000000-0000-4000-8000-000000000001', title: 'Project 01', case_revision: 4, sample: false, django_url: '/', source_options_url: '/', workflow_intake_url: null };

describe('chooser', () => {
  async function chooser(items?: unknown[]) {
    if (items) override = (_r, url) => (url.pathname === '/api/v1/lines' ? json(200, { items, as_of: '2026-11-23T09:00:00Z' }) : undefined);
    render(<StartWorkDrawer onClose={vi.fn()} />);
    return within(await screen.findByRole('dialog')).findByText('Weekly client report');
  }

  it('lists live lines by title and description, with no group heading and no "Next:" (AC1)', async () => {
    await chooser();
    const dialog = screen.getByRole('dialog');
    expect(within(dialog).getByText('Friday report for a client')).toBeTruthy();
    expect(dialog.textContent).not.toMatch(/Next:|stations/);
    expect(within(dialog).queryAllByRole('heading', { level: 3 })).toHaveLength(0);
    expect(requests().filter((r) => new URL(r.url).pathname === '/api/v1/lines')).toHaveLength(1);
  });

  it('shows a line it cannot start, or has no form for, as unavailable with a link, and no invoice line when the server sends none (AC2)', async () => {
    await chooser([
      ...startLive({ method: 'get', url: new URL('http://m/api/v1/lines'), persona: 'pm' })[1].items,
    ]);
    const dialog = screen.getByRole('dialog');
    expect(within(dialog).queryByText('Invoice')).toBeNull();
    const links = within(dialog).getAllByRole('link', { name: 'Open in the full form' });
    // finance-payroll (can submit, no registered form), pmo-leadership-report (can submit; its schema has array and object leaves, F-92)
    expect(links.map((a) => a.getAttribute('href'))).toEqual(['/lines/finance-payroll/', '/lines/pmo-leadership-report/']);
    // the weekly report, the received RFP, which owns its submit (F-88), the five engine lines (F-92) the fixed asset schedule (F-102) and the invoice (F-94)
    expect(within(dialog).getAllByRole('radio').map((r) => r.getAttribute('value'))).toEqual(['pmo-weekly-report/v1', 'pmo-minutes/v1', 'received-bid', 'pmo-issues/v1', 'pmo-escalation/v1', 'pmo-emergency/v1', 'pmo-change/v1', 'finance-ppe/v1', 'pmo-finance/v1']);
    expect((within(dialog).getByRole('button', { name: 'Next' }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(within(dialog).getAllByRole('radio')[0]);
    expect((within(dialog).getByRole('button', { name: 'Next' }) as HTMLButtonElement).disabled).toBe(false);
  });

  it('says so for an empty list; a line `/lines` does not list is never added (F-88)', async () => {
    render(<LineChooser state={{ status: 'ready', data: { items: [], as_of: '' } }} onRetry={vi.fn()} onNext={vi.fn()} onClose={vi.fn()} pathname="/" />);
    expect(screen.getByText('There are no lines you can start right now.')).toBeTruthy();
  });

  it('opens the project step for the weekly report, with no default line (AC15)', async () => {
    await chooser();
    fireEvent.click(screen.getAllByRole('radio')[0]);
    fireEvent.click(screen.getByRole('button', { name: 'Next' }));
    expect(await screen.findByRole('dialog', { name: 'Weekly client report' })).toBeTruthy();
    expect(screen.getByRole('combobox', { name: 'Project' })).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Start report' })).toBeTruthy();
    expect(screen.getByText('Week')).toBeTruthy();
    expect(screen.getByText('Reference')).toBeTruthy();
    expect(screen.queryByText(/Evidence file|up to 8/i)).toBeNull();
  });

  it('presses Start report with nothing filled: no POST /work, each missing field listed (AC4)', async () => {
    await chooser();
    fireEvent.click(screen.getAllByRole('radio')[0]);
    fireEvent.click(screen.getByRole('button', { name: 'Next' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Start report' }));
    const summary = await screen.findByRole('alert');
    expect(summary.textContent).toContain('3 things to fix');
    for (const text of ['Project is required.', 'Week is required.', 'Reference is required.']) expect(within(summary).getByText(text)).toBeTruthy();
    expect(await bodies()).toEqual([]);
  });

  it('a prefill for a line with no live form says "You can\'t start this here." (AC14)', async () => {
    render(<StartWorkDrawer onClose={vi.fn()} prefill={{ line_key: 'weekly_report', intake: {} }} />);
    expect(await screen.findByText('You can’t start this here.')).toBeTruthy();
    expect(fetchStub).toHaveBeenCalled();
  });

  it('a prefill for the live weekly line opens its form directly', async () => {
    render(<StartWorkDrawer onClose={vi.fn()} prefill={{ line_key: 'pmo-weekly-report/v1', intake: {} }} />);
    expect(await screen.findByRole('button', { name: 'Start report' })).toBeTruthy();
  });

  it('a start from the assistant draft path hands the work id to onStarted as a string and does not navigate (TECH-1-2)', async () => {
    const onStarted = vi.fn();
    render(<StartWorkDrawer onClose={vi.fn()} onStarted={onStarted} prefill={{ line_key: 'pmo-weekly-report/v1', intake: {} }} />);
    const dialog = await screen.findByRole('dialog', { name: 'Weekly client report' });
    fireEvent.click(within(dialog).getByRole('combobox', { name: 'Project' }));
    fireEvent.click(await screen.findByRole('option', { name: 'Project 01' }));
    const week = dialog.querySelector('[data-field="week"]') as HTMLElement;
    fireEvent.change(within(week).getByLabelText('From'), { target: { value: '16 Nov 2026' } });
    fireEvent.blur(within(week).getByLabelText('From'));
    fireEvent.change(within(week).getByLabelText('To'), { target: { value: '22 Nov 2026' } });
    fireEvent.blur(within(week).getByLabelText('To'));
    fireEvent.change(within(dialog).getByLabelText('Reference'), { target: { value: 'Week 47' } });
    fireEvent.click(within(dialog).getByRole('button', { name: 'Start report' }));
    await waitFor(() => expect(onStarted).toHaveBeenCalledWith('4102'));
    expect(nav.push).not.toHaveBeenCalled();
    const [sent] = await bodies();
    expect(sent.intake.inputs.start_at).toMatch(/^2026-11-16T00:00:00[+-]\d\d:\d\d$/);
    expect(sent.intake.inputs.end_at).toMatch(/^2026-11-23T00:00:00[+-]\d\d:\d\d$/);
  });

  it('a 401 on the lines read shows the signed-out state with the sign-in return', async () => {
    scenario = '401';
    render(<StartWorkDrawer onClose={vi.fn()} />);
    expect((await screen.findByRole('link', { name: /sign in/i })).getAttribute('href')).toContain('/sign-in?next=');
  });

  it('useLines reads again on every opening', async () => {
    const { result, unmount } = renderHook(() => useLines());
    await waitFor(() => expect(result.current.state.status).toBe('ready'));
    unmount();
    renderHook(() => useLines());
    await waitFor(() => expect(requests().filter((r) => new URL(r.url).pathname === '/api/v1/lines')).toHaveLength(2));
  });
});

describe('reads', () => {
  it('fetchProjects sends line, q only when not empty (trimmed, at most 120) and page only when asked (AC3)', async () => {
    const first = await fetchProjects('pmo-weekly-report/v1', '  ', undefined);
    expect(first.items).toHaveLength(25);
    expect(first.next_page).toBe(2);
    const second = await fetchProjects('pmo-weekly-report/v1', '', 2);
    expect(second.items).toHaveLength(3);
    expect(second.next_page).toBeNull();
    await fetchProjects('pmo-weekly-report/v1', `  ${'x'.repeat(130)}  `);
    const found = await fetchProjects('pmo-weekly-report/v1', ' sample ');
    expect(found.items.map((p) => p.title)).toEqual(['Sample project']);
    expect(found.items[0].sample).toBe(true);
    const urls = requests().map((r) => new URL(r.url));
    expect(urls[0].search).toBe('?line=pmo-weekly-report%2Fv1');
    expect(urls[1].searchParams.get('page')).toBe('2');
    expect(urls[1].searchParams.has('q')).toBe(false);
    expect(urls[2].searchParams.get('q')).toBe('x'.repeat(120));
    expect(urls[3].searchParams.get('q')).toBe('sample');
  });

  it('fetchSources sends line, field, parent_id and before only when set, and returns next_before and the revision (AC13)', async () => {
    const id = PROJECT.case_id;
    const plain = await fetchSources(id, 'pmo-weekly-report/v1');
    expect(plain.items.map((i) => i.id)).toEqual([11, 12, 13]);
    expect(plain.nextBefore).toBeNull();
    expect(plain.caseRevision).toBe(4);
    await fetchSources(id, 'pmo-weekly-report/v1', { field: 'meeting', parentId: 5, before: 12 });
    const [a, b] = requests().map((r) => new URL(r.url));
    expect(a.pathname).toBe(`/api/v1/projects/${id}/intake-sources`);
    expect([...a.searchParams.keys()]).toEqual(['line']);
    expect(Object.fromEntries(b.searchParams)).toEqual({ line: 'pmo-weekly-report/v1', field: 'meeting', parent_id: '5', before: '12' });
  });
});

/** The offset the browser would report (minutes west of UTC, as `getTimezoneOffset` gives it), for the calls inside `fn`. */
function offsetMinutes<T>(minutes: number[], fn: () => T): T {
  const spy = vi.spyOn(Date.prototype, 'getTimezoneOffset');
  for (const m of minutes) spy.mockReturnValueOnce(m);
  spy.mockReturnValue(minutes[minutes.length - 1]);
  try {
    return fn();
  } finally {
    spy.mockRestore();
  }
}

describe('the period carries an explicit offset (QA-1-1)', () => {
  it('local midnight with the zone offset, including half-hour zones, zero and a daylight change', () => {
    expect(offsetMinutes([-60], () => localMidnight('2026-11-16'))).toBe('2026-11-16T00:00:00+01:00');
    expect(offsetMinutes([0], () => localMidnight('2026-11-16'))).toBe('2026-11-16T00:00:00+00:00');
    expect(offsetMinutes([-330], () => localMidnight('2026-11-16'))).toBe('2026-11-16T00:00:00+05:30');
    expect(offsetMinutes([210], () => localMidnight('2026-11-16'))).toBe('2026-11-16T00:00:00-03:30');
    // each midnight reads its own offset (the clocks went back that night in New York)
    expect(offsetMinutes([240], () => localMidnight('2026-11-01'))).toBe('2026-11-01T00:00:00-04:00');
    expect(offsetMinutes([300], () => localMidnight('2026-11-01', 1))).toBe('2026-11-02T00:00:00-05:00');
    // the day after rolls over the month and the year
    expect(offsetMinutes([0], () => localMidnight('2026-12-31', 1))).toBe('2027-01-01T00:00:00+00:00');
  });

  it('is the browser\'s own local midnight', () => {
    const at = new Date(localMidnight('2026-11-16'));
    expect([at.getHours(), at.getMinutes(), at.getDate()]).toEqual([0, 0, 16]);
  });

  it('the body ends the period at the midnight after the last day, so that day is included', () => {
    const body = offsetMinutes([-60], () => weeklyReport.buildBody({ week: WEEK, reference: 'r' }, { caseId: PROJECT.case_id, caseRevision: 4, idempotencyKey: 'k' }) as WeeklyBody);
    expect(body.intake).toEqual({ inputs: { template_id: null, content_id: null, start_at: '2026-11-16T00:00:00+01:00', end_at: '2026-11-23T00:00:00+01:00' } });
  });

  const post = (inputs: Record<string, unknown>) =>
    startLive({
      method: 'post',
      url: new URL('http://m/api/v1/work'),
      raw: JSON.stringify({ line: 'pmo-weekly-report/v1', case_id: PROJECT.case_id, case_revision: 4, idempotency_key: `k-${Math.random()}`, intake: { inputs: { template_id: null, content_id: null, ...inputs } }, reference: 'r' }),
      csrfOk: true,
      persona: 'pm',
    }) as [number, { code?: string; message?: string }];

  it('the mock refuses date-only and offset-less values as the server does, so the old body would have failed', () => {
    for (const bad of [{ start_at: '2026-11-16', end_at: '2026-11-22' }, { start_at: '2026-11-16T00:00:00', end_at: '2026-11-23T00:00:00' }, { start_at: '2026-11-16T00:00:00+01:00', end_at: '2026-11-22' }]) {
      const [status, body] = post(bad);
      expect(status).toBe(422);
      expect(body.code).toBe('action_unavailable');
      expect(body.message).toMatch(/requires an explicit timezone offset$/);
    }
    expect(post({ start_at: '2026-11-16', end_at: '2026-11-22' })[1].message).toBe('Period start requires an explicit timezone offset');
    expect(post({ start_at: '2026-11-16T00:00:00+01:00', end_at: '2026-11-22' })[1].message).toBe('Period end requires an explicit timezone offset');
  });

  it('the mock also keeps the server\'s window rules: positive, at most eight days, already ended', () => {
    expect(post({ start_at: '2026-11-16T00:00:00+01:00', end_at: '2026-11-16T00:00:00+01:00' })[0]).toBe(422);
    expect(post({ start_at: '2026-11-01T00:00:00+01:00', end_at: '2026-11-10T00:00:00+01:00' })[0]).toBe(422);
    expect(post({ start_at: '2026-11-22T00:00:00+01:00', end_at: '2026-11-30T00:00:00+01:00' })[1].message).toMatch(/must have ended/);
    expect(post({ start_at: '2026-11-16T00:00:00+01:00', end_at: '2026-11-23T00:00:00+01:00' })[0]).toBe(200);
  });
});

describe('the weekly body', () => {
  it('is exactly the schema branch, with null template and content and no background (AC5)', () => {
    const body = weeklyReport.buildBody({ week: WEEK, reference: ' Week 47 ' }, { caseId: PROJECT.case_id, caseRevision: 4, idempotencyKey: 'k-1' });
    expect(body).toEqual({
      line: 'pmo-weekly-report/v1',
      case_id: PROJECT.case_id,
      case_revision: 4,
      idempotency_key: 'k-1',
      intake: { inputs: { template_id: null, content_id: null, start_at: localMidnight('2026-11-16'), end_at: localMidnight('2026-11-22', 1) } },
      reference: 'Week 47',
    });
    expect(Object.keys(body).sort()).toEqual(['case_id', 'case_revision', 'idempotency_key', 'intake', 'line', 'reference']);
  });

  it('lists what is missing in the order drawn', () => {
    expect(weeklyReport.missing({}).map((m) => m.name)).toEqual(['week', 'reference']);
    expect(weeklyReport.missing({ week: { from: '2026-11-16', to: '' }, reference: '   ' }).map((m) => m.name)).toEqual(['week', 'reference']);
    expect(weeklyReport.missing({ week: WEEK, reference: 'x' })).toEqual([]);
  });
});

describe('server field names (AC8)', () => {
  const cases: [string, string | undefined][] = [
    ['case_id', 'project'],
    ['case_revision', 'project'],
    ['line', 'general'],
    ['idempotency_key', 'general'],
    ['reference', 'reference'],
    ['intake.inputs.start_at', 'week'],
    ['intake.inputs.end_at', 'week'],
    ['intake.inputs', 'week'],
    ['start_at', 'week'],
    ['end_at', 'week'],
    ['template_id', 'general'],
    ['content_id', 'general'],
    ['background', undefined],
    ['something_else', undefined],
  ];
  for (const [name, control] of cases) {
    it(`${name} -> ${control ?? 'its own box'}`, () => {
      const mapped = mapProblems(weeklyReport, [{ name, message: 'M' }]);
      if (control === undefined) expect(mapped.unmatched).toEqual([{ name, message: 'M' }]);
      else if (control === 'general') expect(mapped.general).toEqual(['M']);
      else expect(mapped.errors).toEqual({ [control]: 'M' });
    });
  }
  it('keeps every problem, none dropped', () => {
    const mapped = mapProblems(weeklyReport, [{ name: 'reference', message: 'A' }, { name: 'x', message: 'B' }, { name: 'line', message: 'C' }, { name: 'start_at', message: 'D' }]);
    expect(mapped).toEqual({ errors: { reference: 'A', week: 'D' }, unmatched: [{ name: 'x', message: 'B' }], general: ['C'] });
  });
});

describe('the start', () => {
  const started = vi.fn();
  const conflict = vi.fn();
  async function ready() {
    const hook = renderHook(() => useStart(weeklyReport, started, conflict));
    act(() => {
      hook.result.current.chooseProject(PROJECT);
      hook.result.current.setValue('week', WEEK);
      hook.result.current.setValue('reference', 'Week 47');
    });
    return hook;
  }
  beforeEach(() => {
    started.mockReset();
    conflict.mockReset();
  });

  it('sends one body with the CSRF header and hands the work id on as a string (AC5)', async () => {
    const { result } = await ready();
    await act(() => result.current.submit());
    const [post] = reads(/^\/api\/v1\/work$/);
    expect(post.headers.get('x-csrftoken')).toBe(TOKEN);
    expect(await bodies()).toHaveLength(1);
    expect(started).toHaveBeenCalledWith('4102');
  });

  it('a double press sends one request (AC6)', async () => {
    const { result } = await ready();
    await act(async () => {
      void result.current.submit();
      void result.current.submit();
    });
    expect(await bodies()).toHaveLength(1);
    expect(startLiveLog().started).toHaveLength(1);
  });

  it('after a 503, "Check again" resends the same body with the same key and starts one work item (AC6, AC11)', async () => {
    scenario = 'start_uncertain';
    const { result } = await ready();
    await act(() => result.current.submit());
    expect(result.current.uncertain).toBe(true);
    expect(result.current.notice).toEqual({ kind: 'uncertain' });
    expect(started).not.toHaveBeenCalled();
    await act(() => result.current.submit());
    const [first, second] = await bodies();
    expect(second).toEqual(first);
    expect(started).toHaveBeenCalledWith('4102');
    expect(startLiveLog().started).toHaveLength(1);
  });

  it('a network failure is uncertain and does not start a second work item (AC11)', async () => {
    override = (request) => {
      if (request.method === 'POST') throw new TypeError('network');
      return undefined;
    };
    const { result } = await ready();
    await act(() => result.current.submit());
    expect(result.current.uncertain).toBe(true);
    expect(startLiveLog().started).toHaveLength(0);
  });

  it('a 2xx with no work id is uncertain', async () => {
    override = (request) => (request.method === 'POST' ? json(200, { state: 'processing' }) : undefined);
    const { result } = await ready();
    await act(() => result.current.submit());
    expect(result.current.uncertain).toBe(true);
    expect(started).not.toHaveBeenCalled();
  });

  it('a 409 keeps every value, reads the revision again, and the next press carries a new key and the new revision (AC7)', async () => {
    scenario = 'start_stale';
    const { result } = await ready();
    await act(() => result.current.submit());
    expect(result.current.notice).toMatchObject({ kind: 'stale' });
    expect(conflict).toHaveBeenCalled();
    expect(result.current.values).toEqual({ week: WEEK, reference: 'Week 47' });
    expect(result.current.project?.case_revision).toBe(5);
    expect(reads(/^\/api\/v1\/work$/).filter((r) => r.method === 'POST')).toHaveLength(1);
    const projectReads = reads(/lines\/projects$/);
    expect(new URL(projectReads[0].url).searchParams.get('q')).toBe('Project 01');
    await act(() => result.current.submit());
    const [first, second] = await bodies();
    expect(second.idempotency_key).not.toBe(first.idempotency_key);
    expect(first.case_revision).toBe(4);
    expect(second.case_revision).toBe(5);
    expect(started).toHaveBeenCalledWith('4102');
  });

  it('a 422 puts each message under its control and an unknown name in its own box (AC8)', async () => {
    override = (request) =>
      request.method === 'POST'
        ? json(422, { code: 'invalid', message: 'No.', fields: [{ name: 'reference', message: 'Too long.' }, { name: 'intake.inputs.end_at', message: 'End is before start.' }, { name: 'zzz', message: 'Odd.' }, { name: 'line', message: 'Wrong line.' }] })
        : undefined;
    const { result } = await ready();
    await act(() => result.current.submit());
    expect(result.current.errors).toEqual({ reference: 'Too long.', week: 'End is before start.' });
    expect(result.current.notice).toEqual({ kind: 'invalid', unmatched: [{ name: 'zzz', message: 'Odd.' }], general: ['Wrong line.'] });
    expect(result.current.values.reference).toBe('Week 47');
  });

  it('a 422 with no fields shows its message as the general text', async () => {
    override = (request) => (request.method === 'POST' ? json(422, { code: 'invalid', message: 'The week is too long.' }) : undefined);
    const { result } = await ready();
    await act(() => result.current.submit());
    expect(result.current.notice).toEqual({ kind: 'invalid', unmatched: [], general: ['The week is too long.'] });
  });

  it('401 is the signed-out state (AC9)', async () => {
    scenario = '401';
    const { result } = await ready();
    await act(() => result.current.submit());
    expect(result.current.signedOut).toBe(true);
  });

  it('a 403 csrf_failed refreshes the session once and does not say "can\'t start" (AC9)', async () => {
    scenario = 'csrf_failed';
    const { result } = await ready();
    await act(() => result.current.submit());
    expect(result.current.notice).toEqual({ kind: 'problem', message: 'Refresh your session and try again.' });
    expect(reads(/^\/api\/v1\/session$/)).toHaveLength(1);
    expect(result.current.values.reference).toBe('Week 47');
  });

  it('any other 403 says the role does not let them start it', async () => {
    scenario = 'start_denied';
    const { result } = await ready();
    await act(() => result.current.submit());
    expect(result.current.notice).toEqual({ kind: 'problem', message: 'Your role doesn’t let you start this line. Your role does not allow this.' });
  });

  it('a 404 says exactly "This record is unavailable." and gives no hint a hand-edited case exists (AC9, AC10)', async () => {
    scenario = 'start_missing';
    const { result } = await ready();
    await act(() => result.current.submit());
    expect(result.current.notice).toEqual({ kind: 'problem', message: 'This record is unavailable.' });
    // another project can still be chosen and started
    scenario = undefined;
    act(() => result.current.chooseProject({ ...PROJECT, case_id: '00000000-0000-4000-8000-000000000002', title: 'Project 02', case_revision: 7 }));
    await act(() => result.current.submit());
    expect(started).toHaveBeenCalledWith('4102');
  });

  it('a case that is not in the list (hand-edited) is a 404 from the server', async () => {
    const { result } = await ready();
    act(() => result.current.chooseProject({ ...PROJECT, case_id: '11111111-1111-4111-8111-111111111111' }));
    await act(() => result.current.submit());
    expect(result.current.notice).toEqual({ kind: 'problem', message: 'This record is unavailable.' });
  });

  it('429 is "Try again shortly." with a new key; 413 and 415 show the server message', async () => {
    const { result } = await ready();
    scenario = '429';
    // a numeric scenario answers every route, including the read the form makes; the start itself is what is checked
    await act(() => result.current.submit());
    expect(result.current.notice).toEqual({ kind: 'problem', message: 'Try again shortly.' });
    scenario = '413';
    await act(() => result.current.submit());
    expect(result.current.notice).toEqual({ kind: 'problem', message: 'The request is too large.' });
    scenario = '415';
    await act(() => result.current.submit());
    expect(result.current.notice).toEqual({ kind: 'problem', message: 'The request type is not accepted.' });
    const keys = (await bodies()).map((b) => b.idempotency_key);
    expect(keys[1]).not.toBe(keys[0]);
  });

  it('changing the project clears what is bound to the old case (none for the weekly line)', async () => {
    const { result } = await ready();
    act(() => result.current.chooseProject({ ...PROJECT, case_id: '00000000-0000-4000-8000-000000000002' }));
    expect(result.current.values).toEqual({ week: WEEK, reference: 'Week 47' });
  });
});

describe('StartUpload (AC12)', () => {
  it('is closed until a project is chosen and says why', () => {
    render(<StartUpload caseId={null} value={null} onChange={vi.fn()} />);
    expect(screen.getByText('Choose a project first.')).toBeTruthy();
    expect(fetchStub).not.toHaveBeenCalled();
  });

  it('uploads to the chosen case only and returns the upload id', async () => {
    override = (request, url) =>
      request.method === 'POST' && /\/cases\/[^/]+\/files$/.test(url.pathname)
        ? json(200, { upload_id: 8001, name: 'a.pdf', size: 3, sha256: 'a'.repeat(64), download_url: '/x' })
        : undefined;
    const onChange = vi.fn();
    const { container } = render(<StartUpload caseId={PROJECT.case_id} value={null} onChange={onChange} />);
    const input = container.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(input, { target: { files: [new File(['abc'], 'a.pdf', { type: 'application/pdf' })] } });
    await waitFor(() => expect(onChange).toHaveBeenCalled());
    expect(onChange.mock.calls[0][0]).toBe(8001);
    expect(new URL(requests()[0].url).pathname).toBe(`/api/v1/cases/${PROJECT.case_id}/files`);
  });

  it('starts empty again when the project changes', () => {
    const file = { upload_id: 8001, name: 'a.pdf', size: 3, sha256: 'x', download_url: '/x' } as never;
    const view = render(<StartUpload caseId="c1" value={file} onChange={vi.fn()} />);
    expect(screen.getByText('a.pdf')).toBeTruthy();
    view.rerender(<StartUpload caseId="c2" value={null} onChange={vi.fn()} />);
    expect(screen.queryByText('a.pdf')).toBeNull();
  });
});

describe('the registry and the source (AC15, AC16)', () => {
  const dir = join(__dirname, '../src/features/start-work');
  const files = (d: string): string[] => readdirSync(d, { withFileTypes: true }).flatMap((e) => (e.isDirectory() ? files(join(d, e.name)) : [join(d, e.name)]));
  const text = (f: string) => readFileSync(f, 'utf8');

  it('knows the weekly line and the five engine lines, and gives nothing for any other key', () => {
    expect(lineFormFor('pmo-weekly-report/v1')?.startLabel).toBe('Start report');
    expect(lineFormFor('pmo-weekly-report/v1')?.drawerTitle).toBe('Weekly client report');
    for (const key of ['pmo-issues/v1', 'pmo-escalation/v1', 'pmo-minutes/v1', 'pmo-emergency/v1', 'pmo-change/v1']) expect(lineFormFor(key)?.key).toBe(key);
    expect(lineFormFor('pmo-leadership-report/v1')).toBeUndefined();
    expect(lineFormFor('')).toBeUndefined();
  });

  it('no default_line path, no per-line import in the chooser, no invented week rule, one multipart upload helper', () => {
    const all = files(dir).filter((f) => /\.(tsx?|css)$/.test(f));
    expect(all.filter((f) => /default_line/.test(text(f)))).toEqual([]);
    expect(text(join(dir, 'LineChooser.tsx'))).not.toMatch(/from '\.\/lines\/|weeklyReport/);
    expect(all.filter((f) => /8 days|up to 8/.test(text(f)))).toEqual([]);
    // F-92: the one FormData is the minutes start; the upload helper stays F-85's
    expect(all.filter((f) => /FormData/.test(text(f))).map((f) => f.replace(`${dir}/`, ''))).toEqual(['engine/minutes.ts']);
    expect(all.filter((f) => /uploadCaseFile/.test(text(f))).filter((f) => /\/(engine|lines)\//.test(f))).toEqual([]);
    expect(text(join(dir, 'StartUpload.tsx'))).toMatch(/EvidencePicker/);
    expect(text(join(dir, 'lines/weeklyReport.tsx'))).not.toMatch(/StartUpload|StartProof/);
  });
});
