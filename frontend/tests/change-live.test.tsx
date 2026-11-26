// @vitest-environment jsdom
// F-112: the change request on the live work item against the live-shaped mock (mock/change-live.mjs): what is read, the assessment, the
// decisions and the authorisation, and each safety rule: one request per press, no automatic retry, a lost answer locks, the result from
// the re-read, no client rule about who may decide, proofs chosen from served lists, unknown stays unknown.
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { setCsrfToken } from '@/api/client';
import { ToastProvider } from '@/components';
import { LiveWorkItemView } from '@/features/work-item/live/LiveWorkItemView';
import { resetScopedWriteLocks } from '@/features/workspace/useWriteLock';

// @ts-expect-error plain ESM module without type declarations
import { CHANGE_PATH, changeLive, resetChangeLive } from '../mock/change-live.mjs';

vi.mock('@/shell/AppShell', () => ({ usePhoneBack: () => undefined }));
vi.mock('next/navigation', () => ({ usePathname: () => '/work/4901', useRouter: () => ({ replace: vi.fn(), push: vi.fn(), prefetch: vi.fn() }) }));

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
const me = { name: 'Tunde Bello', destinations: [], startable_lines: [], csrf_token: 't', assistant_agents: [] };
let scenario: string | undefined;
let fetchStub: ReturnType<typeof vi.fn<(request: Request) => Promise<Response>>>;
let gate: Promise<void> | null = null;
/** After this many reads of the change, the next read of it answers 503 (a failed re-read). */
let failChangeReadAfter: number | null = null;
let changeReads = 0;
const calls = () => fetchStub.mock.calls.map(([r]) => ({ method: r.method, path: new URL(r.url).pathname }));
const posts = () => fetchStub.mock.calls.filter(([r]) => r.method === 'POST');
const WRITES = /\/work\/\d+\/change$/;
const writes = () => posts().filter(([r]) => WRITES.test(new URL(r.url).pathname));
const sent = async () => Promise.all(writes().map(async ([r]) => ({ path: new URL(r.url).pathname, body: JSON.parse(await r.clone().text()) as Record<string, unknown> })));
const sessionReads = () => calls().filter((c) => c.path === '/api/v1/session').length;

beforeEach(() => {
  resetScopedWriteLocks();
  resetChangeLive();
  scenario = undefined;
  gate = null;
  failChangeReadAfter = null;
  changeReads = 0;
  setCsrfToken('t');
  fetchStub = vi.fn(async (request: Request) => {
    const url = new URL(request.url);
    if (url.pathname === '/api/v1/me') return json(200, me);
    if (url.pathname === '/api/v1/session') return json(200, { csrf_token: 't', signed_in: true, next_url: '/' });
    const rawBytes = request.method === 'POST' ? Buffer.from(await request.clone().text()) : undefined;
    const args = { method: request.method.toLowerCase(), url, scenario, csrfOk: request.headers.get('X-CSRFToken') === 't', persona: 'finance_lead', rawBytes };
    if (!CHANGE_PATH.test(url.pathname)) return json(404, { code: 'not_found', message: 'This record is unavailable.' });
    if (gate && request.method === 'POST') await gate;
    if (request.method === 'GET' && WRITES.test(url.pathname)) {
      changeReads += 1;
      if (failChangeReadAfter !== null && changeReads > failChangeReadAfter) return json(503, { code: 'unavailable', message: 'A dependency is unavailable.' });
    }
    const reply = changeLive(args) as [number | 'drop', unknown];
    if (reply[0] === 'drop') throw new TypeError('network');
    return json(reply[0], reply[1]);
  });
  vi.stubGlobal('fetch', fetchStub);
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const open = async (id: number, wait: RegExp | string = 'Impact assessments') => {
  render(
    <ToastProvider>
      <LiveWorkItemView id={String(id)} tab="overview" />
    </ToastProvider>,
  );
  await screen.findAllByText(wait);
};
const button = (name: string | RegExp) => screen.getByRole('button', { name }) as HTMLButtonElement;
const choose = (label: string | RegExp, option: RegExp) => {
  fireEvent.click(screen.getByRole('combobox', { name: label }));
  fireEvent.click(screen.getByRole('option', { name: option }));
};
const press = (name: string | RegExp) => fireEvent.click(button(name));
const type = (label: string | RegExp, value: string) => fireEvent.change(screen.getByLabelText(label), { target: { value } });
const quiet = () => new Promise((r) => setTimeout(r, 30));

const fillAssessment = (opts: { effort?: string; answers?: [RegExp, RegExp, RegExp, RegExp] } = {}) => {
  type('Assessment', 'Uses the existing SMS provider.');
  if (opts.effort !== undefined) type(/^Effort in person-days/, opts.effort);
  const [cost, timeline, client, production] = opts.answers ?? [/^No$/, /^No$/, /^Yes$/, /^Not known$/];
  choose('Changes the cost', cost);
  choose('Changes the timeline', timeline);
  choose('The client will see it', client);
  choose('Affects production', production);
  choose('Proof', /security assessment/);
};
const rowOf = (name: string) => screen.getByText(name, { selector: 'td, [role="cell"]' }).closest('tr') as HTMLElement;

describe('reading', () => {
  it('4901 opens with reads only: the category, the track with step 1 current, four impact rows and one Record an assessment', async () => {
    await open(4901);
    expect(calls().filter((c) => c.method !== 'GET')).toEqual([]);
    expect(screen.getByText('Being assessed · 3 of 4')).toBeTruthy();
    expect(screen.getAllByText('Normal').length).toBeGreaterThan(0);
    expect(screen.getByText('Reference').nextSibling?.textContent).toBe('CR-0031');
    expect(screen.getByText('1 · Authorization')).toBeTruthy();
    for (const team of ['Engineering', 'QA', 'Infra', 'Security']) expect(rowOf(team)).toBeTruthy();
    expect(within(rowOf('Security')).getByText('Not given yet')).toBeTruthy();
    expect(within(rowOf('Security')).getByText('Missing')).toBeTruthy();
    expect(within(rowOf('Infra')).getByText('Not recorded')).toBeTruthy();
    expect(screen.getAllByRole('button', { name: 'Record an assessment' })).toHaveLength(1);
    expect(screen.queryByRole('button', { name: /Approve|Return|Reject|authorisation/i })).toBeNull();
  });
  it('4912 (nothing recorded): four Missing rows, and every team can be assessed', async () => {
    await open(4912);
    expect(screen.getAllByText('Missing')).toHaveLength(4);
    expect(screen.getAllByText('Not given yet')).toHaveLength(4);
    expect(screen.getAllByRole('button', { name: 'Record an assessment' })).toHaveLength(4);
  });
  it('4905 (read only for the caller): rows and deciders draw, no write control and no "you can’t" banner', async () => {
    await open(4905);
    expect(screen.getByText('Deciders')).toBeTruthy();
    expect(screen.queryByRole('button', { name: /Record|Approve|Return|Reject/ })).toBeNull();
    expect(document.body.textContent).not.toMatch(/can’t|cannot|not allowed|only the/i);
  });
  it('the deciders are exactly the roles the read returns: 4902 five, 4911 two, 4901 three; never "all five"', async () => {
    for (const [id, roles] of [[4902, ['Product', 'Engineering', 'Client', 'Engineering Lead', 'Security Manager']], [4911, ['Product', 'Engineering']], [4901, ['Product', 'Client', 'Engineering Lead']]] as const) {
      cleanup();
      await open(id);
      const table = screen.getByRole('table', { name: /Deciders/ });
      expect(within(table).getAllByRole('row').slice(1).map((r) => r.querySelector('td, [role="cell"]')?.textContent)).toEqual(roles);
      expect(document.body.textContent).not.toMatch(/all five|five deciders/i);
    }
  });
  it('4910 (a stage outside the eight codes): no step is lit and the raw stage is shown', async () => {
    await open(4910);
    expect(screen.getByText('review_pending')).toBeTruthy();
    expect(document.querySelectorAll('.ws-word--status-now, .ws-word--status-done').length).toBe(0);
    // the reference is left out when no listed change has this version
    expect(screen.queryByText('Reference')).toBeNull();
  });
  it('4903 (a rejection): REJECTED, the finding, "You can log a new change later." and no authorise or decide control', async () => {
    await open(4903);
    expect(screen.getAllByText('Rejected').length).toBeGreaterThan(0);
    expect(screen.getByText('The client did not approve this change.')).toBeTruthy();
    expect(screen.getByText('You can log a new change later.')).toBeTruthy();
    expect(screen.queryByRole('button', { name: /Record|Approve|Return|Reject/ })).toBeNull();
  });
  it('4906 (authorised): "Authorised" and the record number, no authorise control, no person or time', async () => {
    await open(4906);
    expect(screen.getAllByText('Authorised').length).toBeGreaterThan(0);
    expect(screen.getByText('Recorded (#7001)')).toBeTruthy();
    expect(screen.queryByRole('button', { name: /authorisation/i })).toBeNull();
    expect(document.body.textContent).not.toMatch(/Authorised by|Authorised on/);
  });
  it('4907 (at the notice step): step 2 is current and nothing can be sent for steps 2 to 5', async () => {
    await open(4907);
    expect(screen.getByText('2 · Notice')).toBeTruthy();
    expect(screen.queryByRole('button', { name: /notice|execution|go-live|signature|close|retry|cancel|restart/i })).toBeNull();
  });
  it('4999 reads "This record is unavailable."', async () => {
    render(<ToastProvider><LiveWorkItemView id="4999" tab="overview" /></ToastProvider>);
    expect((await screen.findAllByText('This record is unavailable.')).length).toBeGreaterThan(0);
  });
  it('the page never says deployment is authorised and draws no agent card, recorder or person names', async () => {
    await open(4902);
    expect(document.body.textContent).not.toMatch(/deployment|Tola|Recorded by|Femi|Authorised by|milestone scope/i);
  });
});

describe('recording an assessment', () => {
  it('sends one request with every contract key, unknown as null, the effort as typed, and the row shows recorded only after the re-read', async () => {
    await open(4901);
    press('Record an assessment');
    expect(button('Record assessment').disabled).toBe(true);
    fillAssessment({ effort: ' 0.5 ' });
    expect(button('Record assessment').disabled).toBe(false);
    press('Record assessment');
    await waitFor(() => expect(within(rowOf('Security')).getByText('Recorded')).toBeTruthy());
    expect(await sent()).toEqual([
      {
        path: '/api/v1/work/4901/change',
        body: {
          action: 'assess',
          expected_revision: 6,
          case_revision: 41,
          change_version_id: 1,
          contributor: 'Security',
          cost_impact: false,
          timeline_impact: false,
          client_facing: true,
          production_impact: null,
          scope_items: null,
          outputs: null,
          effort_person_days: '0.5',
          evidence: 7901,
          note: 'Uses the existing SMS provider.',
          proof_upload: null,
        },
      },
    ]);
    expect(screen.queryByRole('button', { name: 'Record an assessment' })).toBeNull();
    expect(screen.getByText('0.5')).toBeTruthy();
  });
  it('a blank effort is null and reads "Not recorded", never 0', async () => {
    await open(4901);
    press('Record an assessment');
    fillAssessment();
    press('Record assessment');
    await waitFor(() => expect(within(rowOf('Security')).getByText('Recorded')).toBeTruthy());
    expect((await sent())[0].body.effort_person_days).toBeNull();
    expect(within(rowOf('Security')).getByText('Not recorded')).toBeTruthy();
    expect(within(rowOf('Security')).queryByText(/^0\b/)).toBeNull();
  });
  it('scope items and the five output notes go as lists and an object with the blanks null', async () => {
    await open(4901);
    press('Record an assessment');
    fillAssessment();
    type(/^Scope items, one per line/, 'Reminder texts\n\n  Opt-out link  ');
    type(/^Risk note/, 'Provider outage');
    press('Record assessment');
    await waitFor(() => expect(writes()).toHaveLength(1));
    expect((await sent())[0].body).toMatchObject({ scope_items: ['Reminder texts', 'Opt-out link'], outputs: { discipline: null, timeline: null, cost_resource: null, risk: 'Provider outage', dependency: null } });
  });
  it('no answer is chosen ahead: until every question is answered the button is off with its reason', async () => {
    await open(4901);
    press('Record an assessment');
    type('Assessment', 'x');
    choose('Proof', /security assessment/);
    expect(button('Record assessment').disabled).toBe(true);
    expect(screen.getAllByText(/Answer each question/).length).toBeGreaterThan(0);
    press('Record assessment');
    await quiet();
    expect(writes()).toHaveLength(0);
  });
  it('4908 (no proof recorded): the form says so, the button is off and nothing is sent', async () => {
    await open(4908);
    press('Record an assessment');
    expect(screen.getAllByText('No proof file is recorded for this case yet').length).toBeGreaterThan(0);
    expect(screen.queryByRole('combobox', { name: 'Proof' })).toBeNull();
    expect(button('Record assessment').disabled).toBe(true);
    press('Record assessment');
    await quiet();
    expect(writes()).toHaveLength(0);
  });
  it('after a 201 the next write uses a freshly read pair, never the old one', async () => {
    await open(4912);
    const assess = async (team: string, n: number) => {
      fireEvent.click(within(screen.getByRole('region', { name: `${team} assessment` })).getByRole('button', { name: 'Record an assessment' }));
      fillAssessment();
      press('Record assessment');
      await waitFor(() => expect(writes()).toHaveLength(n));
    };
    await assess('Engineering', 1);
    await waitFor(() => expect(screen.getAllByRole('button', { name: 'Record an assessment' })).toHaveLength(3));
    await assess('QA', 2);
    const bodies = (await sent()).map((x) => x.body);
    expect(bodies.map((b) => [b.contributor, b.expected_revision, b.case_revision])).toEqual([['Engineering', 6, 41], ['QA', 7, 42]]);
  });
  it('a team the read does not list is never sent: the body builder refuses it', async () => {
    const { assessHeld, emptyOutputs } = await import('@/features/change-request/changeModel');
    const change = (await import('./change-fixture')).start(4901);
    const choice = { team: 'QA' as const, note: 'n', effort: '', cost: 'no' as const, timeline: 'no' as const, clientFacing: 'no' as const, production: 'no' as const, scope: '', outputs: emptyOutputs(), evidence: '7901' };
    expect(assessHeld(change, choice)).toMatch(/isn’t open to you/);
    expect(assessHeld(change, { ...choice, team: 'Security' })).toBeNull();
    expect(assessHeld(change, { ...choice, team: 'Security', evidence: '9999' })).toBe('Choose the proof for this assessment.');
  });
});

const decisionOf = (role: string) => screen.getByRole('group', { name: `${role} decision` });
const approve = (role: string) => within(decisionOf(role)).getByRole('button', { name: `Approve for ${role}` }) as HTMLButtonElement;
const prepare = (role: string, note = 'The client agreed by email.') => {
  fireEvent.change(within(decisionOf(role)).getByLabelText(`${role} note`), { target: { value: note } });
  fireEvent.click(within(decisionOf(role)).getByRole('combobox', { name: `${role} proof` }));
  fireEvent.click(screen.getByRole('option', { name: /meeting minutes/ }));
};
const DECIDE = (role: string, verdict: string, note = 'The client agreed by email.') => ({ action: 'decide', expected_revision: 6, case_revision: 41, change_version_id: 2, role, verdict, evidence: 7902, note });

describe('recording a decision', () => {
  it('4902: each row offers only the verdicts the read lists; no row without verdicts has a control', async () => {
    await open(4902);
    const names = (role: string) => within(screen.getByRole('group', { name: `${role} decision` })).getAllByRole('button').map((b) => b.textContent);
    expect(names('Client')).toEqual(['Approve', 'Return', 'Reject']);
    expect(names('Engineering Lead')).toEqual(['Approve']);
    for (const role of ['Product', 'Engineering', 'Security Manager']) expect(screen.queryByRole('group', { name: `${role} decision` })).toBeNull();
  });
  it('approve needs a note and a listed proof: with an empty note the button is off with its reason and nothing is sent', async () => {
    await open(4902);
    expect(approve('Client').disabled).toBe(true);
    expect(screen.getAllByText('Add a note for this decision.').length).toBeGreaterThan(0);
    fireEvent.click(approve('Client'));
    fireEvent.change(within(decisionOf('Client')).getByLabelText('Client note'), { target: { value: '   ' } });
    expect(approve('Client').disabled).toBe(true);
    await quiet();
    expect(writes()).toHaveLength(0);
    fireEvent.change(within(decisionOf('Client')).getByLabelText('Client note'), { target: { value: 'x' } });
    expect(approve('Client').disabled).toBe(true);
    expect(screen.getAllByText('Choose the proof for this decision.').length).toBeGreaterThan(0);
  });
  it('approve sends once with role, verdict, evidence from the list and the note; the row reads Approved only after the re-read', async () => {
    await open(4902);
    prepare('Client');
    fireEvent.click(approve('Client'));
    await waitFor(() => expect(screen.queryByRole('group', { name: 'Client decision' })).toBeNull());
    expect(await sent()).toEqual([{ path: '/api/v1/work/4902/change', body: DECIDE('Client', 'approve') }]);
    expect(within(screen.getByRole('table', { name: /Deciders/ })).getAllByText('Approved')).toHaveLength(3);
    expect(screen.queryByText('Recorded.')).toBeNull();
  });
  it('return asks for confirmation: Cancel sends nothing, the confirm sends one request with the note', async () => {
    await open(4902);
    prepare('Client', 'Not this phase.');
    press('Return for Client');
    expect(screen.getByRole('alertdialog', { name: 'Return for Client' })).toBeTruthy();
    expect(within(screen.getByRole('alertdialog')).getByText('Not this phase.')).toBeTruthy();
    fireEvent.click(within(screen.getByRole('alertdialog')).getByRole('button', { name: 'Cancel' }));
    await quiet();
    expect(writes()).toHaveLength(0);
    expect(screen.queryByRole('alertdialog')).toBeNull();
    press('Return for Client');
    fireEvent.click(within(screen.getByRole('alertdialog')).getByRole('button', { name: 'Return' }));
    await waitFor(() => expect(writes()).toHaveLength(1));
    expect((await sent())[0].body).toMatchObject({ action: 'decide', role: 'Client', verdict: 'return', note: 'Not this phase.', evidence: 7902 });
  });
  it('reject confirms the same way; the page then shows Rejected and "You can log a new change later."', async () => {
    await open(4902);
    prepare('Client', 'Not this phase; revisit after go-live.');
    press('Reject for Client');
    fireEvent.click(within(screen.getByRole('alertdialog')).getByRole('button', { name: 'Reject' }));
    await screen.findByText('You can log a new change later.');
    expect(writes()).toHaveLength(1);
    expect(screen.getAllByText('Rejected').length).toBeGreaterThan(0);
    expect(screen.queryByRole('button', { name: /authorisation/i })).toBeNull();
  });
  it('4908 (no proof recorded): the decision is held with the words and nothing is sent', async () => {
    await open(4908);
    expect(screen.getAllByText('No proof file is recorded for this case yet').length).toBeGreaterThan(0);
    fireEvent.change(within(decisionOf('Product')).getByLabelText('Product note'), { target: { value: 'ok' } });
    expect(approve('Product').disabled).toBe(true);
    fireEvent.click(approve('Product'));
    await quiet();
    expect(writes()).toHaveLength(0);
  });
  it('a verdict the row does not list, and a proof the read does not list, are never sent (the model refuses them)', async () => {
    const { decideHeld } = await import('@/features/change-request/changeModel');
    const { start } = await import('./change-fixture');
    const c = start(4902);
    expect(decideHeld(c, { role: 'Engineering Lead', verdict: 'reject', note: 'n', evidence: '7902' })).toMatch(/isn’t open to you/);
    expect(decideHeld(c, { role: 'Product', verdict: 'approve', note: 'n', evidence: '7902' })).toMatch(/isn’t open to you/);
    expect(decideHeld(c, { role: 'Client', verdict: 'approve', note: 'n', evidence: '1' })).toBe('Choose the proof for this decision.');
    expect(decideHeld(c, { role: 'Client', verdict: 'approve', note: 'n', evidence: '7902' })).toBeNull();
  });
  it('4909 (a stale decision): the 409 says so, the unsent note stays, no decide button is drawn and nothing is sent again', async () => {
    await open(4909);
    prepare('Product', 'Approved after the call.');
    fireEvent.click(approve('Product'));
    await screen.findByText(/This changed while you were working/);
    await waitFor(() => expect(screen.queryByRole('button', { name: /Approve for Product/ })).toBeNull());
    expect(screen.getByText('Approved after the call.')).toBeTruthy();
    expect(screen.getByText(/Your note was not sent/)).toBeTruthy();
    await quiet();
    expect(writes()).toHaveLength(1);
  });
});

describe('recording the authorisation', () => {
  it('4904: the choices are the read’s, a confirm step says what it commits, and one request goes with the chosen commercial item', async () => {
    await open(4904);
    expect(screen.getByText('Approved · to authorise')).toBeTruthy();
    fireEvent.click(screen.getByRole('combobox', { name: /Linked commercial item/ }));
    expect(screen.getAllByRole('option').map((o) => o.textContent)).toEqual(['Commercial item #11', 'Commercial item #12']);
    fireEvent.click(screen.getByRole('option', { name: 'Commercial item #12' }));
    press('Record authorisation');
    expect(within(screen.getByRole('alertdialog')).getByText('This commits the change. It cannot be undone here.')).toBeTruthy();
    expect(within(screen.getByRole('alertdialog')).getByText('Linked commercial item: #12.')).toBeTruthy();
    expect(writes()).toHaveLength(0);
    fireEvent.click(within(screen.getByRole('alertdialog')).getByRole('button', { name: 'Cancel' }));
    await quiet();
    expect(writes()).toHaveLength(0);
    press('Record authorisation');
    fireEvent.click(within(screen.getByRole('alertdialog')).getByRole('button', { name: 'Record authorisation' }));
    await waitFor(() => expect(screen.queryByRole('button', { name: 'Record authorisation' })).toBeNull());
    expect(await sent()).toEqual([{ path: '/api/v1/work/4904/change', body: { action: 'authorize', expected_revision: 6, case_revision: 41, change_version_id: 4, commercial: 12 } }]);
    expect(screen.getAllByText('Authorised').length).toBeGreaterThan(0);
    expect(screen.getByText('Recorded (#7104)')).toBeTruthy();
    expect(document.body.textContent).not.toMatch(/Authorised by|Authorised on/);
  });
  it('with no choice made the commercial item is null and the confirm step says none is linked', async () => {
    await open(4904);
    press('Record authorisation');
    expect(within(screen.getByRole('alertdialog')).getByText('No commercial item is linked.')).toBeTruthy();
    fireEvent.click(within(screen.getByRole('alertdialog')).getByRole('button', { name: 'Record authorisation' }));
    await waitFor(() => expect(writes()).toHaveLength(1));
    expect((await sent())[0].body.commercial).toBeNull();
  });
  it('a commercial item the read does not list is never sent', async () => {
    const { authorizeInputs, authorizeOffered } = await import('@/features/change-request/changeModel');
    const { start } = await import('./change-fixture');
    const c = start(4904);
    expect(authorizeInputs(c, '99')).toEqual({ commercial: null });
    expect(authorizeInputs(c, '11')).toEqual({ commercial: 11 });
    expect(authorizeOffered({ ...c, can_authorize: false })).toBe(false);
    expect(authorizeOffered({ ...c, authorization_id: 5 })).toBe(false);
    expect(authorizeInputs({ ...c, authorization_choices: [] }, '11')).toEqual({ commercial: null });
  });
});

describe('the write safety rules', () => {
  const decideNow = async () => {
    await open(4902);
    prepare('Client');
  };
  it('a double click in one tick sends one request', async () => {
    await decideNow();
    const b = approve('Client');
    fireEvent.click(b);
    fireEvent.click(b);
    await waitFor(() => expect(screen.queryByRole('group', { name: 'Client decision' })).toBeNull());
    expect(writes()).toHaveLength(1);
  });
  it('a press while one runs sends nothing, and every control is off with the write running', async () => {
    let release: () => void = () => undefined;
    gate = new Promise((resolve) => (release = resolve));
    await decideNow();
    fireEvent.click(approve('Client'));
    await waitFor(() => expect(writes()).toHaveLength(1));
    for (const b of within(decisionOf('Client')).getAllByRole('button') as HTMLButtonElement[]) expect(b.disabled).toBe(true);
    fireEvent.click(within(decisionOf('Client')).getAllByRole('button')[0]);
    release();
    await waitFor(() => expect(screen.queryByRole('group', { name: 'Client decision' })).toBeNull());
    expect(writes()).toHaveLength(1);
  });
  it('csrf_failed: "Press the button again.", the session is read once, no second write', async () => {
    await decideNow();
    const before = sessionReads();
    scenario = 'w403csrf';
    fireEvent.click(approve('Client'));
    await screen.findByText('Press the button again.');
    await quiet();
    expect(writes()).toHaveLength(1);
    expect(sessionReads() - before).toBe(1);
    expect((within(decisionOf('Client')).getByLabelText('Client note') as HTMLTextAreaElement).value).toBe('The client agreed by email.');
  });
  it('a lost answer before the write ran locks every change control with the words; it is never sent again', async () => {
    await decideNow();
    scenario = 'wdrop0';
    fireEvent.click(approve('Client'));
    await screen.findByText('We couldn’t confirm that this happened. Check the page before trying again.');
    expect(approve('Client').disabled).toBe(true);
    expect((within(decisionOf('Client')).getByRole('button', { name: 'Return for Client' }) as HTMLButtonElement).disabled).toBe(true);
    expect(screen.getAllByText('Check the page before trying again.').length).toBeGreaterThan(0);
    fireEvent.click(approve('Client'));
    await quiet();
    expect(writes()).toHaveLength(1);
    expect(within(screen.getByRole('table', { name: /Deciders/ })).queryAllByText('Approved')).toHaveLength(2);
  });
  it('a lost answer after the write ran: approved is shown only because the re-read shows it; no second write', async () => {
    await decideNow();
    scenario = 'wdrop';
    fireEvent.click(approve('Client'));
    await waitFor(() => expect(within(screen.getByRole('table', { name: /Deciders/ })).getAllByText('Approved')).toHaveLength(3));
    await quiet();
    expect(writes()).toHaveLength(1);
  });
  it('403: "You can’t do this." with the server’s words; whoever may decide is the server’s rule', async () => {
    await decideNow();
    scenario = 'w403';
    fireEvent.click(approve('Client'));
    await screen.findByText(/You can’t do this\./);
    expect(screen.getByText(/Only the assigned people can record this\./)).toBeTruthy();
    expect(writes()).toHaveLength(1);
  });
  it('422, 429 and 503 show the words and send nothing again', async () => {
    for (const [name, words] of [['w422', /The request was not accepted\. A note is needed\./], ['w429', /Try again shortly\./], ['w503', /Try again shortly\./]] as const) {
      cleanup();
      resetScopedWriteLocks();
      resetChangeLive();
      fetchStub.mockClear();
      scenario = undefined;
      await decideNow();
      scenario = name;
      fireEvent.click(approve('Client'));
      expect((await screen.findAllByText(words)).length).toBeGreaterThan(0);
      await quiet();
      expect(writes()).toHaveLength(1);
    }
  });
  it('a 409 keeps the typed note, says the change was updated and sends nothing by itself', async () => {
    await decideNow();
    scenario = 'w409';
    fireEvent.click(approve('Client'));
    await screen.findByText(/This changed while you were working/);
    expect((within(decisionOf('Client')).getByLabelText('Client note') as HTMLTextAreaElement).value).toBe('The client agreed by email.');
    await quiet();
    expect(writes()).toHaveLength(1);
  });
  it('a re-read that fails after the 201 leaves the controls off with the words and Try again; nothing is sent again, and a good read frees them', async () => {
    await decideNow();
    failChangeReadAfter = 1;
    fireEvent.click(approve('Client'));
    await screen.findByText(/We couldn’t load this part of the page/);
    expect(writes()).toHaveLength(1);
    expect(approve('Client').disabled).toBe(true);
    expect(screen.getAllByText('Reading the change again before the next entry.').length).toBeGreaterThan(0);
    fireEvent.click(approve('Client'));
    await quiet();
    expect(writes()).toHaveLength(1);
    failChangeReadAfter = null;
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
    await waitFor(() => expect(screen.queryByRole('group', { name: 'Client decision' })).toBeNull());
    expect(writes()).toHaveLength(1);
    expect(within(screen.getByRole('table', { name: /Deciders/ })).getAllByText('Approved')).toHaveLength(3);
  });
});
