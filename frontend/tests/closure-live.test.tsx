// @vitest-environment jsdom
// F-118: the closure page on the live work item against the live-shaped mock (mock/closure-live.mjs): what is read in each state, and the
// safety rules of the three writes (decide, replace the report, confirm milestone notifications): one request per press, no automatic
// retry, a lost answer locks, the result from the re-read, a stale decision leaves a lasting notice and the unsent note, no client rule
// about who may act, proofs from served lists, unknown stays Unknown. The two ids a decision needs are not served by any read (D-26,
// LD-2), so the adapter holds Close and Return; the write tests give them to the readback the way a served read would.
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { setCsrfToken } from '@/api/client';
import { ToastProvider } from '@/components';
import { closureAdapter } from '@/features/delivery-closure/closureAdapter';
import { LiveWorkItemView } from '@/features/work-item/live/LiveWorkItemView';
import { resetScopedWriteLocks } from '@/features/workspace/useWriteLock';

// @ts-expect-error plain ESM module without type declarations
import { CLOSURE_PATH, closureLive, resetClosureLive } from '../mock/closure-live.mjs';

vi.mock('@/shell/AppShell', () => ({ usePhoneBack: () => undefined }));
vi.mock('next/navigation', () => ({ usePathname: () => '/work/6204', useRouter: () => ({ replace: vi.fn(), push: vi.fn(), prefetch: vi.fn() }) }));

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
const me = { name: 'Tunde Bello', destinations: [], startable_lines: [], csrf_token: 't', assistant_agents: [] };
let scenario: string | undefined;
let fetchStub: ReturnType<typeof vi.fn<(request: Request) => Promise<Response>>>;
let gate: Promise<void> | null = null;
let sessionReads = 0;
const WRITE = /\/(reviews|closure-report|finance-confirmation)$/;
const writes = () => fetchStub.mock.calls.filter(([r]) => r.method === 'POST' && WRITE.test(new URL(r.url).pathname));
const sent = async () => Promise.all(writes().map(async ([r]) => ({ path: new URL(r.url).pathname, body: JSON.parse(await r.clone().text()) as Record<string, unknown> })));
/** A closure write straight to the mock, as another person's tab would make it. */
const elsewhere = (id: number, path: string, body: unknown) =>
  closureLive({ method: 'post', url: new URL(`http://mock/api/v1/work/${id}${path}`), scenario: undefined, csrfOk: true, persona: 'finance_lead', rawBytes: Buffer.from(JSON.stringify(body)) }) as [number, unknown];

const realRead = closureAdapter.read;
beforeEach(() => {
  resetScopedWriteLocks();
  resetClosureLive();
  scenario = undefined;
  gate = null;
  sessionReads = 0;
  setCsrfToken('t');
  fetchStub = vi.fn(async (request: Request) => {
    const url = new URL(request.url);
    if (url.pathname === '/api/v1/me') return json(200, me);
    if (url.pathname === '/api/v1/session') {
      sessionReads += 1;
      return json(200, { csrf_token: 't', signed_in: true, next_url: '/' });
    }
    const rawBytes = request.method === 'POST' ? Buffer.from(await request.clone().text()) : undefined;
    if (!CLOSURE_PATH.test(url.pathname)) return json(404, { code: 'not_found', message: 'This record is unavailable.' });
    if (gate && request.method === 'POST') await gate;
    const reply = closureLive({ method: request.method.toLowerCase(), url, scenario, csrfOk: request.headers.get('X-CSRFToken') === 't', persona: 'finance_lead', rawBytes }) as [number | 'drop', unknown];
    if (reply[0] === 'drop') throw new TypeError('network');
    return json(reply[0], reply[1]);
  });
  vi.stubGlobal('fetch', fetchStub);
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  closureAdapter.read = realRead;
});

/** What a served read would add: the closure document version and decision proof, and the Finance proofs the person may attach. */
const served = () => {
  closureAdapter.read = async (ref, ctx) => ({ ...(await realRead(ref, ctx)), decision: { version_id: 9601, evidence_id: 9602 }, financeEvidence: [{ id: 9701, label: 'Receipt review' }] });
};
const open = async (id: number, wait: RegExp | string = 'Before closure') => {
  render(
    <ToastProvider>
      <LiveWorkItemView id={String(id)} tab="overview" />
    </ToastProvider>,
  );
  await screen.findAllByText(wait);
};
const button = (name: string | RegExp) => screen.getByRole('button', { name }) as HTMLButtonElement;
const type = (label: string | RegExp, value: string) => fireEvent.change(screen.getByLabelText(label), { target: { value } });
const choose = (label: string | RegExp, option: RegExp) => {
  fireEvent.click(screen.getByRole('combobox', { name: label }));
  fireEvent.click(screen.getByRole('option', { name: option }));
};
const DECIDE_NOTE = /^Note \(needed to return\)/;
const FINANCE_NOTE = 'Note';
const quiet = () => new Promise((r) => setTimeout(r, 30));

describe('reading', () => {
  it('6201 (not yet): the tag, the next line from the first held check, eight rows with their words, no Finance block and no Tola', async () => {
    await open(6201);
    expect(screen.getAllByText('Closure · Not yet').length).toBeGreaterThan(0);
    expect(screen.getByText('Next: No retrospective saved')).toBeTruthy();
    for (const t of ['Current project scope', 'Go-live acceptance', 'Release stability', 'Project archive', 'Support handover', 'Retrospective', 'Finance notification coverage', 'PM closure report']) expect(screen.getAllByText(new RegExp(t)).length).toBeGreaterThan(0);
    expect(screen.getAllByText('Not yet').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Unknown').length).toBeGreaterThan(0);
    expect(screen.queryByText('Finance confirmation: milestone notifications')).toBeNull();
    expect(screen.queryByRole('button', { name: /Close the project|Return|Confirm/ })).toBeNull();
    expect(document.body.textContent).not.toMatch(/Tola|read-only|Support contract|debts? (are |is )?confirmed/i);
    expect(screen.getByRole('link', { name: 'Write the retrospective' }).getAttribute('href')).toBe('/projects/00000000-0000-4000-8000-000000006201/retrospective?dossier=7001');
  });
  it('6201: the Finance read answered 403, so the block is absent with no message, and the rest of the page loaded', async () => {
    await open(6201);
    expect(document.body.textContent).not.toMatch(/Finance confirmation: milestone|couldn’t load the Finance|can’t do this|no access/i);
  });
  it('6202 (ready): says Ready to prepare and asks no Finance read, because the finance check is current', async () => {
    await open(6202);
    expect(screen.getAllByText('Closure · Ready to prepare').length).toBeGreaterThan(0);
    expect(fetchStub.mock.calls.some(([r]) => /finance-confirmation$/.test(new URL(r.url).pathname))).toBe(false);
  });
  it('6203 (awaiting): says the Head of PMO decides, draws no decision control, and gives the finding as the reason nothing can be confirmed', async () => {
    await open(6203);
    expect(screen.getAllByText('Closure · Awaiting Head of PMO').length).toBeGreaterThan(0);
    expect(screen.getByText('Next: The Head of PMO decides on closure.')).toBeTruthy();
    expect(screen.queryByRole('button', { name: /Close the project|Return with a note/ })).toBeNull();
    expect(screen.getAllByText('Receipt missing for milestone 3').length).toBeGreaterThan(0);
    expect(button('Confirm milestone notifications').disabled).toBe(true);
  });
  it('6204 (decide): Close and Return are drawn from the task\'s verdicts but held with their reason, because no read serves the two ids', async () => {
    await open(6204);
    expect(screen.getAllByText('Closure · Waiting for your decision').length).toBeGreaterThan(0);
    expect(button('Close the project').disabled).toBe(true);
    expect(button('Return with a note').disabled).toBe(true);
    expect(screen.getAllByText('The closure report isn’t ready to decide yet').length).toBeGreaterThan(0);
    fireEvent.click(button('Close the project'));
    await quiet();
    expect(writes()).toHaveLength(0);
    expect(screen.getByText('Closing the project doesn’t erase debt.')).toBeTruthy();
    expect(document.body.textContent).not.toMatch(/debts? (are |is )?confirmed/i);
  });
  it('6204: the Finance block lists the milestones and says milestone notifications; with no proof served the form says so and stays held', async () => {
    await open(6204);
    expect(screen.getByText('Finance confirmation: milestone notifications')).toBeTruthy();
    expect(screen.getByText('Milestone 31')).toBeTruthy();
    expect(screen.getByText('Receipt 72')).toBeTruthy();
    fireEvent.click(screen.getByRole('checkbox', { name: 'These are all the milestone notifications' }));
    type(FINANCE_NOTE, 'Checked each one');
    expect(screen.getAllByText('No Finance evidence available to attach').length).toBeGreaterThan(0);
    expect(button('Confirm milestone notifications').disabled).toBe(true);
    expect(writes()).toHaveLength(0);
  });
  it('6205 (returned): who, when and why from the history row, and the replace form', async () => {
    await open(6205);
    expect(screen.getAllByText('Closure · Returned').length).toBeGreaterThan(0);
    expect(screen.getByText('Ada Okafor returned closure on 24 Nov: “Add the client’s sign-off on the hypercare summary to the report.”')).toBeTruthy();
    expect(screen.getByRole('region', { name: 'Replace the report' })).toBeTruthy();
    expect(screen.queryByRole('button', { name: /Close the project/ })).toBeNull();
  });
  it('6206 (closed): the amount, "Amount not recorded", the date, the limited note and Verified; nothing about read-only or a support contract', async () => {
    await open(6206);
    expect(screen.getAllByText('Closed').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Verified').length).toBeGreaterThan(0);
    expect(screen.getByText('Still open after closure')).toBeTruthy();
    expect(screen.getByText('INV-0533')).toBeTruthy();
    expect(screen.getByText('₦1,250,000.00')).toBeTruthy();
    expect(screen.getByText('Amount not recorded')).toBeTruthy();
    expect(screen.getByText('As of 20 Nov 2026 · List is limited; more may exist.')).toBeTruthy();
    expect(document.body.textContent).not.toMatch(/read-only|Support contract|moves to Closed|Tola|debts? (are |is )?confirmed/i);
    expect(screen.queryByRole('button', { name: /Close the project|Return|Replace|Confirm/ })).toBeNull();
  });
  it('6207 says no open invoices with the date; 6208 (debt not visible) draws no heading and no placeholder', async () => {
    await open(6207);
    expect(screen.getByText('No open invoices recorded as of 20 Nov 2026.')).toBeTruthy();
    cleanup();
    await open(6208, 'Closed');
    expect(screen.queryByText('Still open after closure')).toBeNull();
    expect(screen.queryByText(/No open invoices|Amount not recorded/)).toBeNull();
  });
  it('6209 reads "This record is unavailable."', async () => {
    render(<ToastProvider><LiveWorkItemView id="6209" tab="overview" /></ToastProvider>);
    expect((await screen.findAllByText('This record is unavailable.')).length).toBeGreaterThan(0);
  });
  it('a failed Finance read says so without hiding the page; a 403 on it says nothing', async () => {
    scenario = undefined;
    const original = fetchStub.getMockImplementation()!;
    fetchStub.mockImplementation(async (r) => (/finance-confirmation$/.test(new URL(r.url).pathname) ? json(503, { code: 'unavailable', message: 'x' }) : original(r)));
    await open(6204);
    expect(screen.getByText('We couldn’t load the Finance confirmation.')).toBeTruthy();
    expect(screen.getAllByText('Closure · Waiting for your decision').length).toBeGreaterThan(0);
  });
});

describe('close or return', () => {
  it('Close sends one request with the exact body and no claim, and "Closed" comes from the re-read', async () => {
    served();
    await open(6204);
    expect(button('Close the project').disabled).toBe(false);
    expect(button('Return with a note').disabled).toBe(true);
    expect(screen.getAllByText('Add a note to return the closure.').length).toBeGreaterThan(0);
    fireEvent.click(button('Close the project'));
    await screen.findAllByText(/^Closed 26 Nov 2026$/);
    expect(await sent()).toEqual([{ path: '/api/v1/work/6204/reviews', body: { kind: 'closure', expected_revision: 8, case_revision: 41, version_id: 9601, evidence_id: 9602, verdict: 'approve', note: '' } }]);
    expect(fetchStub.mock.calls.some(([r]) => /\/tasks\//.test(new URL(r.url).pathname))).toBe(false);
    expect(screen.queryByRole('button', { name: /Close the project|Return with a note/ })).toBeNull();
  });
  it('Return sends the note exactly as typed, then the page is returned from the re-read, with the note from history', async () => {
    served();
    await open(6204);
    type(DECIDE_NOTE, '  Add the sign-off.  ');
    fireEvent.click(button('Return with a note'));
    await screen.findAllByText('Closure · Returned');
    expect((await sent())[0].body).toMatchObject({ verdict: 'return', note: '  Add the sign-off.  ' });
    expect(screen.getByText(/Tunde Bello returned closure on 26 Nov: “\s+Add the sign-off\.\s+”/)).toBeTruthy();
  });
  it('a double click sends one request, and both buttons are off while it runs', async () => {
    served();
    let release: () => void = () => undefined;
    gate = new Promise((resolve) => (release = resolve));
    await open(6204);
    const b = button('Close the project');
    fireEvent.click(b);
    fireEvent.click(b);
    await waitFor(() => expect(writes()).toHaveLength(1));
    expect(screen.getAllByRole('button', { name: /Working|Return with a note/ }).every((x) => (x as HTMLButtonElement).disabled)).toBe(true);
    release();
    await screen.findAllByText(/^Closed 26 Nov 2026$/);
    expect(writes()).toHaveLength(1);
  });
  it('409: the page re-reads, says "This changed. Review the latest report.", keeps the typed note and sends nothing more', async () => {
    served();
    await open(6204);
    type(DECIDE_NOTE, 'My note');
    scenario = 'w409';
    fireEvent.click(button('Return with a note'));
    await screen.findByText('This changed. Review the latest report.');
    expect((screen.getByLabelText(DECIDE_NOTE) as HTMLTextAreaElement).value).toBe('My note');
    await quiet();
    expect(writes()).toHaveLength(1);
  });
  it('the two-reviewer sequence: the other person closes first, so the late press gets 409 and sees a lasting notice, the unsent note and no decide buttons', async () => {
    served();
    await open(6204);
    type(DECIDE_NOTE, 'Return it please');
    expect(elsewhere(6204, '/reviews', { kind: 'closure', expected_revision: 8, case_revision: 41, version_id: 9601, evidence_id: 9602, verdict: 'approve', note: '' })[0]).toBe(200);
    fireEvent.click(button('Return with a note'));
    await screen.findByText('This changed. Review the latest report.');
    await waitFor(() => expect(screen.queryByRole('button', { name: /Close the project|Return with a note/ })).toBeNull());
    expect((screen.getByLabelText('Your unsent note') as HTMLTextAreaElement).value).toBe('Return it please');
    expect(screen.getAllByText(/^Closed 26 Nov 2026$/).length).toBeGreaterThan(0);
    await quiet();
    expect(screen.getByText('This changed. Review the latest report.')).toBeTruthy();
    expect(writes()).toHaveLength(1);
  });
  it('403 csrf refreshes the session once and says to press again; no second write happens by itself', async () => {
    served();
    await open(6204);
    scenario = 'w403csrf';
    fireEvent.click(button('Close the project'));
    await screen.findByText('Press the button again.');
    await quiet();
    expect(writes()).toHaveLength(1);
    expect(sessionReads).toBe(1);
  });
  it('403 says "You can’t decide this closure." and never the server\'s reason', async () => {
    served();
    await open(6204);
    scenario = 'w403';
    fireEvent.click(button('Close the project'));
    await screen.findByText('You can’t decide this closure.');
    expect(document.body.textContent).not.toMatch(/Only the Head of PMO can do this/);
    expect(writes()).toHaveLength(1);
  });
  it('422 shows the server\'s message and the first field message; 429 and 503 say try again shortly; each is one request and the note stays', async () => {
    served();
    await open(6204);
    type(DECIDE_NOTE, 'Keep me');
    scenario = 'w422';
    fireEvent.click(button('Close the project'));
    await screen.findByText(/The request was not accepted\./);
    expect(screen.getByText(/A note is needed\./)).toBeTruthy();
    scenario = 'w429';
    fireEvent.click(button('Close the project'));
    await screen.findByText('Try again shortly.');
    scenario = 'w503';
    fireEvent.click(button('Close the project'));
    await waitFor(() => expect(writes()).toHaveLength(3));
    expect((screen.getByLabelText(DECIDE_NOTE) as HTMLTextAreaElement).value).toBe('Keep me');
  });
  it('a lost answer says so, locks both buttons and never sends again on its own', async () => {
    served();
    await open(6204);
    scenario = 'wdrop0';
    fireEvent.click(button('Close the project'));
    await screen.findByText('We couldn’t confirm that this happened. Check the page before trying again.');
    expect(button('Close the project').disabled).toBe(true);
    expect(button('Return with a note').disabled).toBe(true);
    fireEvent.click(button('Close the project'));
    await quiet();
    expect(writes()).toHaveLength(1);
  });
  it('a lost answer for a write that did run is told from the re-read, not from the press', async () => {
    served();
    await open(6204);
    scenario = 'wdrop';
    fireEvent.click(button('Close the project'));
    await screen.findAllByText(/^Closed 26 Nov 2026$/);
    expect(screen.getByText('We couldn’t confirm that this happened. Check the page before trying again.')).toBeTruthy();
    expect(writes()).toHaveLength(1);
  });
});

describe('replace the report', () => {
  const fillReport = (report = 'The corrected report') => {
    type('Report', report);
    type('Where it comes from', 'PM archive');
    type('Why it is replaced', 'The sign-off was missing');
  };
  it('the button stays off until the three fields are filled, and 16 001 characters are refused before any request', async () => {
    await open(6205);
    expect(button('Replace the report').disabled).toBe(true);
    fillReport('x'.repeat(16001));
    expect(button('Replace the report').disabled).toBe(true);
    expect(screen.getAllByText('Keep the report to 16,000 characters.').length).toBeGreaterThan(0);
    fireEvent.click(button('Replace the report'));
    await quiet();
    expect(writes()).toHaveLength(0);
  });
  it('sends one request with the report evidence from the check, then the page leaves the returned state from the re-read', async () => {
    await open(6205);
    fillReport('x'.repeat(16000));
    fireEvent.click(button('Replace the report'));
    await screen.findAllByText('Closure · Awaiting Head of PMO');
    expect(await sent()).toEqual([{ path: '/api/v1/work/6205/closure-report', body: { expected_revision: 8, case_revision: 41, previous_evidence_id: 107, report_text: 'x'.repeat(16000), source_reference: 'PM archive', reason: 'The sign-off was missing' } }]);
    expect(screen.queryByRole('region', { name: 'Replace the report' })).toBeNull();
  });
  it('a double click sends one request; 413 says the report is too long and keeps the text; 409 keeps it too', async () => {
    await open(6205);
    fillReport();
    scenario = 'w413';
    fireEvent.click(button('Replace the report'));
    await screen.findByText('The report is too long.');
    scenario = 'w409';
    fireEvent.click(button('Replace the report'));
    await screen.findByText('This changed. Review the latest report.');
    expect((screen.getByLabelText('Report') as HTMLTextAreaElement).value).toBe('The corrected report');
    scenario = undefined;
    const b = button('Replace the report');
    fireEvent.click(b);
    fireEvent.click(b);
    await screen.findAllByText('Closure · Awaiting Head of PMO');
    expect(writes()).toHaveLength(3);
  });
  it('a lost answer locks the form', async () => {
    await open(6205);
    fillReport();
    scenario = 'wdrop0';
    fireEvent.click(button('Replace the report'));
    await screen.findByText('We couldn’t confirm that this happened. Check the page before trying again.');
    expect(button('Replace the report').disabled).toBe(true);
    await quiet();
    expect(writes()).toHaveLength(1);
  });
});

describe('confirm milestone notifications', () => {
  const ready = () => {
    fireEvent.click(screen.getByRole('checkbox', { name: 'These are all the milestone notifications' }));
    choose('Finance proof', /Receipt review/);
    type(FINANCE_NOTE, ' Checked each ');
  };
  it('stays off until the box is ticked, a served proof is chosen and a note is typed', async () => {
    served();
    await open(6204);
    const b = () => button('Confirm milestone notifications');
    expect(b().disabled).toBe(true);
    fireEvent.click(screen.getByRole('checkbox', { name: 'These are all the milestone notifications' }));
    expect(b().disabled).toBe(true);
    choose('Finance proof', /Receipt review/);
    expect(b().disabled).toBe(true);
    type(FINANCE_NOTE, 'x');
    expect(b().disabled).toBe(false);
  });
  it('sends the Finance read\'s revision, every listed milestone and the proof once; the row becomes Confirmed from the re-read', async () => {
    served();
    await open(6204);
    ready();
    fireEvent.click(button('Confirm milestone notifications'));
    await waitFor(() => expect(screen.getAllByText('Confirmed').length).toBeGreaterThan(0));
    expect(await sent()).toEqual([{ path: '/api/v1/projects/00000000-0000-4000-8000-000000006204/delivery/7004/finance-confirmation', body: { revision: 41, milestone_ids: [31, 32], inventory_complete: true, evidence_id: 9701, note: 'Checked each' } }]);
    expect(screen.queryByRole('button', { name: 'Confirm milestone notifications' })).toBeNull();
    expect(document.body.textContent).not.toMatch(/debts? (are |is )?confirmed/i);
  });
  it('409 says the confirmation changed, keeps the typed note and sends nothing more; a lost answer locks it', async () => {
    served();
    await open(6204);
    ready();
    scenario = 'w409';
    fireEvent.click(button('Confirm milestone notifications'));
    await screen.findByText('Finance confirmation changed. Review it again.');
    expect((screen.getByLabelText(FINANCE_NOTE) as HTMLTextAreaElement).value).toBe(' Checked each ');
    scenario = 'wdrop0';
    fireEvent.click(button('Confirm milestone notifications'));
    await screen.findByText('We couldn’t confirm that this happened. Check the page before trying again.');
    expect(button('Confirm milestone notifications').disabled).toBe(true);
    await quiet();
    expect(writes()).toHaveLength(2);
  });
  it('a double click sends one request', async () => {
    served();
    await open(6204);
    ready();
    const b = button('Confirm milestone notifications');
    fireEvent.click(b);
    fireEvent.click(b);
    await waitFor(() => expect(screen.getAllByText('Confirmed').length).toBeGreaterThan(0));
    expect(writes()).toHaveLength(1);
  });
});
