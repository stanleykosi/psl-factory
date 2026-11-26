// @vitest-environment jsdom
// F-114: go-live acceptance on the live work item against the live-shaped mock (mock/go-live.mjs): what is read, the proof upload, the
// sign-off write and each safety rule: one request per press, no automatic retry, a lost answer locks, the result from the re-read, no
// client rule about who may sign, proofs chosen from served lists, unknown stays Unknown.
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { setCsrfToken } from '@/api/client';
import { ToastProvider } from '@/components';
import { LiveWorkItemView } from '@/features/work-item/live/LiveWorkItemView';
import { resetScopedWriteLocks } from '@/features/workspace/useWriteLock';

// @ts-expect-error plain ESM module without type declarations
import { GO_LIVE_PATH, goLiveLive, resetGoLiveLive } from '../mock/go-live.mjs';
// @ts-expect-error plain ESM module without type declarations
import { CASE_FILES_PATH } from '../mock/work-live.mjs';

vi.mock('@/shell/AppShell', () => ({ usePhoneBack: () => undefined }));
vi.mock('next/navigation', () => ({ usePathname: () => '/work/4411', useRouter: () => ({ replace: vi.fn(), push: vi.fn(), prefetch: vi.fn() }) }));

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
const me = { name: 'Tunde Bello', destinations: [], startable_lines: [], csrf_token: 't', assistant_agents: [] };
let scenario: string | undefined;
let fetchStub: ReturnType<typeof vi.fn<(request: Request) => Promise<Response>>>;
let gate: Promise<void> | null = null;
let uploads = 0;
const calls = () => fetchStub.mock.calls.map(([r]) => ({ method: r.method, path: new URL(r.url).pathname }));
const posts = (path?: RegExp) => fetchStub.mock.calls.filter(([r]) => r.method === 'POST' && (!path || path.test(new URL(r.url).pathname)));
const WRITES = /\/work\/\d+\/go-live-(signoff|signoff\/proofs|replies|replies\/successor)$/;
const writes = (path: RegExp = WRITES) => posts(path);
const sent = async (path: RegExp = WRITES) => Promise.all(writes(path).map(async ([r]) => ({ path: new URL(r.url).pathname, body: JSON.parse(await r.clone().text()) as Record<string, unknown> })));
const sessionReads = () => calls().filter((c) => c.path === '/api/v1/session').length;

beforeEach(() => {
  resetScopedWriteLocks();
  resetGoLiveLive();
  scenario = undefined;
  gate = null;
  uploads = 0;
  setCsrfToken('t');
  fetchStub = vi.fn(async (request: Request) => {
    const url = new URL(request.url);
    if (url.pathname === '/api/v1/me') return json(200, me);
    if (url.pathname === '/api/v1/session') return json(200, { csrf_token: 't', signed_in: true, next_url: '/' });
    // the case file upload is multipart: its bytes are not read here
    if (CASE_FILES_PATH.test(url.pathname)) {
      uploads += 1;
      return json(200, { upload_id: 8000 + uploads, name: 'signed.pdf', size: 16, sha256: 'a'.repeat(64), download_url: '/x' });
    }
    const rawBytes = request.method === 'POST' ? Buffer.from(await request.clone().text()) : undefined;
    const args = { method: request.method.toLowerCase(), url, scenario, csrfOk: request.headers.get('X-CSRFToken') === 't', persona: 'finance_lead', rawBytes };
    if (!GO_LIVE_PATH.test(url.pathname)) return json(404, { code: 'not_found', message: 'This record is unavailable.' });
    if (gate && request.method === 'POST') await gate;
    const reply = goLiveLive(args) as [number | 'drop', unknown];
    if (reply[0] === 'drop') throw new TypeError('network');
    return json(reply[0], reply[1]);
  });
  vi.stubGlobal('fetch', fetchStub);
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const open = async (id: number, wait: RegExp | string = /Delivery recorded|hasn’t been sent|Only the appointed PM/) => {
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
const SIGNER = { 'source system': 'DocuSign', 'source reference': 'ENV-1', 'decision id': 'D-9', 'decision version': '2', 'signer reference': 'S-1' };
const fillSigner = (role: 'PM' | 'Client', skip?: string) => {
  for (const [name, value] of Object.entries(SIGNER)) if (name !== skip) type(`${role} ${name}`, value);
  type(`${role} signed at`, '2026-11-25T11:00');
};
const pdf = () => new File(['%PDF-1.4 signed'], 'signed.pdf', { type: 'application/pdf' });
const fileInput = (n: number) => document.querySelectorAll('input[type="file"]')[n] as HTMLInputElement;
const upload = async (n: number, file = pdf()) => {
  const before = uploads;
  fireEvent.change(fileInput(n), { target: { files: [file] } });
  await waitFor(() => expect(uploads).toBe(before + 1));
  await waitFor(() => expect(screen.getAllByText('signed.pdf').length).toBeGreaterThan(0));
};
const ready = async () => {
  fillSigner('PM');
  fillSigner('Client');
  choose(/PM signature record/, /#61/);
  choose(/Client signature record/, /#62/);
  type(/^Note/, 'Both signed copies checked');
};
const SIGNOFF_BODY = {
  expected_revision: 6,
  case_revision: 41,
  version_id: 11,
  receipt_id: 51,
  pm_signature_id: 61,
  client_signature_id: 62,
  mode: 'fresh_signatures',
  prior_acceptance_id: null,
  note: 'Both signed copies checked',
};
const signer = { source_system: 'DocuSign', source_reference: 'ENV-1', decision_id: 'D-9', decision_version: '2', signer_reference: 'S-1', signed_at: new Date('2026-11-25T11:00').toISOString() };

describe('reading', () => {
  it('4411 opens with reads only: the sent block, a PM and a Client block with six fields each, and the button off with its reason', async () => {
    await open(4411);
    expect(calls().filter((c) => c.method !== 'GET')).toEqual([]);
    expect(screen.getByText(/Delivery recorded 25 Nov/)).toBeTruthy();
    expect(screen.getByText('Sent to the client')).toBeTruthy();
    for (const role of ['PM', 'Client']) {
      for (const name of Object.keys(SIGNER)) expect((screen.getByLabelText(`${role} ${name}`) as HTMLInputElement).value).toBe('');
      expect(screen.getByLabelText(`${role} signed at`)).toBeTruthy();
    }
    expect(button('Record signatures').disabled).toBe(true);
    expect(screen.getAllByText(/Needs reconciliation: add the source system, reference, decision id and version from the signed record\./).length).toBeGreaterThan(0);
    expect(calls().some((c) => c.path.endsWith('/decline'))).toBe(false);
    expect(screen.queryByRole('combobox', { name: 'How to record' })).toBeNull();
  });
  it('4420 (nothing delivered): says so and draws no form', async () => {
    await open(4420);
    expect(screen.getByText('The go-live document hasn’t been sent to the client yet.')).toBeTruthy();
    expect(screen.queryByRole('button', { name: /Record signatures|Add signed copy/ })).toBeNull();
    expect(screen.queryByText('Sent to the client')).toBeNull();
  });
  it('4415 (not the appointed PM): no form, the words, and the replies and the unlock list still draw', async () => {
    await open(4415);
    expect(screen.getByText('Only the appointed PM records the signatures.')).toBeTruthy();
    expect(screen.queryByRole('button', { name: /Record signatures/ })).toBeNull();
    expect(screen.getAllByText(/Add the bureau outage contact/).length).toBeGreaterThan(0);
    expect(screen.getByText('What this unlocks')).toBeTruthy();
  });
  it('4412 (accepted): the banner and the unlock rows come from the reads; nothing about hypercare, archive or marking the milestone', async () => {
    await open(4412, /Go-live accepted/);
    expect(screen.getByText('Accepted (#7001)')).toBeTruthy();
    expect(screen.getByText('Go-live · Not recorded yet')).toBeTruthy();
    expect(screen.queryByRole('button', { name: /Record signatures/ })).toBeNull();
    expect(document.body.textContent).not.toMatch(/Mark milestone|Hypercare|Archive and handover|RUNNING|STARTED/);
  });
  it('4416 (an earlier acceptance): no accepted banner, the earlier one named, and the binding option offered; 4411 has none', async () => {
    await open(4416, /An earlier acceptance is on file \(#6990\)/);
    expect(screen.queryByText(/Go-live accepted/)).toBeNull();
    fireEvent.click(screen.getByRole('combobox', { name: 'How to record' }));
    expect(screen.getByRole('option', { name: /Use the earlier acceptance \(#6990\)/ })).toBeTruthy();
  });
  it('4418 (the person may not read the source): "Details not available to you" and never null, 0 or a blank', async () => {
    await open(4418);
    expect(screen.getAllByText(/Details not available to you/).length).toBeGreaterThan(0);
    expect(document.body.textContent).not.toMatch(/\bnull\b|undefined|Invalid Date/);
  });
  it('4419 (changes, then withdrawn): the withdrawn reply is a read-only row and no form offers withdrawn', async () => {
    await open(4419);
    expect(screen.getByText(/Reply 2 · Withdrawn/)).toBeTruthy();
    expect(screen.getByText(/Reply 1 · Changes requested · Ngozi Bello · Email/)).toBeTruthy();
    expect(document.body.textContent).not.toMatch(/Withdrawn by the recorder/);
    expect(screen.queryByRole('option', { name: /withdrawn/i })).toBeNull();
  });
  it('4429 reads "This record is unavailable."', async () => {
    render(<ToastProvider><LiveWorkItemView id="4429" tab="overview" /></ToastProvider>);
    expect((await screen.findAllByText('This record is unavailable.')).length).toBeGreaterThan(0);
  });
  it('4413 (changes asked for): the quoted note and Prepare v2, no sign-off form; with no capture entry the finding is the reason', async () => {
    await open(4413);
    expect(screen.getAllByText(/“Add the bureau outage contact to the incident plan\.”/).length).toBeGreaterThan(0);
    expect(screen.getByText('Only the person who sent the document records the reply.')).toBeTruthy();
    expect(screen.queryByRole('button', { name: /Record signatures/ })).toBeNull();
    expect(screen.getByRole('button', { name: 'Prepare v2' })).toBeTruthy();
    expect(screen.queryByRole('button', { name: /Record the reply|Record reply/ })).toBeNull();
  });
  it('4421 (a reply may be recorded): the write is held with its reason and nothing can be sent', async () => {
    await open(4421);
    expect(screen.getByText(/Recording the client’s reply isn’t available here yet/)).toBeTruthy();
    expect(screen.queryByText('Only the person who sent the document records the reply.')).toBeNull();
    expect(screen.queryByRole('button', { name: /Record the reply|Record reply|Review the remediation/ })).toBeNull();
  });
});

describe('the signed copy (AC2, AC22)', () => {
  it('a copy is kept only after the box is ticked: one proofs call with role Client, the receipt and the held case revision', async () => {
    await open(4411);
    await upload(1);
    const adds = screen.getAllByRole('button', { name: 'Add signed copy' }) as HTMLButtonElement[];
    expect(adds[1].disabled).toBe(true);
    fireEvent.click(adds[1]);
    expect(writes()).toHaveLength(0);
    const boxes = screen.getAllByLabelText('I checked this is the signed copy of this go-live document for this signer');
    fireEvent.click(boxes[1]);
    expect((screen.getAllByRole('button', { name: 'Add signed copy' })[1] as HTMLButtonElement).disabled).toBe(false);
    fireEvent.click(screen.getAllByRole('button', { name: 'Add signed copy' })[1]);
    await waitFor(() => expect(writes()).toHaveLength(1));
    expect(await sent()).toEqual([{ path: '/api/v1/work/4411/go-live-signoff/proofs', body: { case_revision: 41, receipt_id: 51, upload_id: 8001, role: 'Client', checked: true } }]);
    expect(posts(/\/files$/).map(([r]) => new URL(r.url).pathname)).toEqual(['/api/v1/cases/00000000-0000-4000-8000-000000004411/files']);
    // the new record is listed from the re-read and is the Client's choice
    await waitFor(() => expect(screen.getByRole('combobox', { name: /Client signature record/ }).textContent).toMatch(/#70/));
    expect(screen.getByRole('combobox', { name: /PM signature record/ }).textContent).toMatch(/Choose a signature record/);
    // the next press uses the new case revision
    expect(calls().filter((c) => c.method === 'GET' && c.path.endsWith('/go-live-signoff')).length).toBeGreaterThan(1);
  });
  it('a file that is not a PDF type or is too large is refused before any request', async () => {
    await open(4411);
    fireEvent.change(fileInput(0), { target: { files: [new File(['MZ'], 'run.exe', { type: 'application/octet-stream' })] } });
    fireEvent.change(fileInput(1), { target: { files: [new File([new ArrayBuffer(40 * 1024 * 1024)], 'big.pdf', { type: 'application/pdf' })] } });
    await new Promise((r) => setTimeout(r, 30));
    expect(uploads).toBe(0);
    expect(writes()).toHaveLength(0);
  });
  it('a lost answer on the proofs call locks it, says so and sends nothing again', async () => {
    await open(4411);
    await upload(0);
    fireEvent.click(screen.getAllByLabelText('I checked this is the signed copy of this go-live document for this signer')[0]);
    scenario = 'wdrop0';
    fireEvent.click(screen.getAllByRole('button', { name: 'Add signed copy' })[0]);
    await screen.findByText('We couldn’t confirm that this happened. Check the page before trying again.');
    expect((screen.getAllByRole('button', { name: 'Add signed copy' })[0] as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(screen.getAllByRole('button', { name: 'Add signed copy' })[0]);
    await new Promise((r) => setTimeout(r, 30));
    expect(writes()).toHaveLength(1);
  });
});

describe('recording the signatures (AC3 to AC8, AC24)', () => {
  it('sends one request with every field from the read and the form, and the result comes from the re-read', async () => {
    await open(4411);
    await ready();
    expect(button('Record signatures').disabled).toBe(false);
    press('Record signatures');
    await screen.findByText(/Go-live accepted/);
    expect(await sent()).toEqual([{ path: '/api/v1/work/4411/go-live-signoff', body: { ...SIGNOFF_BODY, signers: { PM: signer, Client: signer } } }]);
    expect(screen.queryByRole('button', { name: 'Record signatures' })).toBeNull();
    expect(screen.queryByText('Recorded.')).toBeNull();
  });
  it('the same signature record for both signers is refused with the words and nothing is sent', async () => {
    await open(4411);
    await ready();
    choose(/Client signature record/, /#61/);
    expect(screen.getAllByText('Choose a different signature record for each signer').length).toBeGreaterThan(0);
    expect(button('Record signatures').disabled).toBe(true);
    press('Record signatures');
    await new Promise((r) => setTimeout(r, 30));
    expect(writes()).toHaveLength(0);
  });
  it('any empty signer field keeps it off with "Needs reconciliation", for either signer; nothing is prefilled', async () => {
    for (const role of ['PM', 'Client'] as const) {
      cleanup();
      resetScopedWriteLocks();
      await open(4411);
      fillSigner('PM');
      fillSigner('Client');
      choose(/PM signature record/, /#61/);
      choose(/Client signature record/, /#62/);
      type(/^Note/, 'ok');
      expect(button('Record signatures').disabled).toBe(false);
      type(`${role} decision version`, '  ');
      expect(button('Record signatures').disabled).toBe(true);
      expect(screen.getAllByText(/Needs reconciliation/).length).toBeGreaterThan(0);
      press('Record signatures');
      expect(writes()).toHaveLength(0);
    }
  });
  it('a note is needed, and a chosen record must be listed', async () => {
    await open(4411);
    await ready();
    type(/^Note/, '');
    expect(button('Record signatures').disabled).toBe(true);
    expect(screen.getAllByText('Add a note.').length).toBeGreaterThan(0);
  });
  it('4416 binds to the earlier acceptance only when chosen and then sends its id; the default sends null', async () => {
    await open(4416);
    await ready();
    choose('How to record', /Use the earlier acceptance/);
    press('Record signatures');
    await screen.findByText(/Go-live accepted/);
    expect((await sent())[0].body).toMatchObject({ mode: 'metadata_binding', prior_acceptance_id: 6990 });
  });
  it('4416 fresh signatures send prior_acceptance_id null', async () => {
    await open(4416);
    await ready();
    press('Record signatures');
    await screen.findByText(/Go-live accepted/);
    expect((await sent())[0].body).toMatchObject({ mode: 'fresh_signatures', prior_acceptance_id: null });
  });
  it('4417: a 409 says the record changed, re-reads, keeps nothing as recorded, and the next press sends the new revisions', async () => {
    await open(4417);
    await ready();
    press('Record signatures');
    await screen.findByText(/This changed while you were working/);
    expect(screen.queryByText(/Go-live accepted/)).toBeNull();
    expect(writes()).toHaveLength(1);
    await waitFor(() => expect(button('Record signatures').disabled).toBe(false));
    press('Record signatures');
    await screen.findByText(/Go-live accepted/);
    const bodies = (await sent()).map((s) => s.body);
    expect(bodies).toHaveLength(2);
    expect([bodies[0].expected_revision, bodies[0].case_revision]).toEqual([6, 41]);
    expect([bodies[1].expected_revision, bodies[1].case_revision]).toEqual([7, 42]);
  });
  it('a double press sends one request and the button is off while it runs', async () => {
    let release: () => void = () => undefined;
    gate = new Promise((resolve) => (release = resolve));
    await open(4411);
    await ready();
    press('Record signatures');
    await waitFor(() => expect(writes()).toHaveLength(1));
    expect(button('Working…').disabled).toBe(true);
    fireEvent.click(button('Working…'));
    fireEvent.click(button('Working…'));
    release();
    await screen.findByText(/Go-live accepted/);
    expect(writes()).toHaveLength(1);
  });
  it('a double click in one tick sends one request', async () => {
    await open(4411);
    await ready();
    const b = button('Record signatures');
    fireEvent.click(b);
    fireEvent.click(b);
    await screen.findByText(/Go-live accepted/);
    expect(writes()).toHaveLength(1);
  });
  it('csrf_failed: "Press the button again", the session is read once, no second write', async () => {
    await open(4411);
    await ready();
    const before = sessionReads();
    scenario = 'w403csrf';
    press('Record signatures');
    await screen.findByText('Press the button again.');
    await new Promise((r) => setTimeout(r, 30));
    expect(writes()).toHaveLength(1);
    expect(sessionReads() - before).toBe(1);
  });
  it('a lost answer before the write ran locks the form with the words; it is never sent again', async () => {
    await open(4411);
    await ready();
    scenario = 'wdrop0';
    press('Record signatures');
    await screen.findByText('We couldn’t confirm that this happened. Check the page before trying again.');
    expect(button('Record signatures').disabled).toBe(true);
    press('Record signatures');
    await new Promise((r) => setTimeout(r, 30));
    expect(writes()).toHaveLength(1);
    expect(screen.queryByText(/Go-live accepted/)).toBeNull();
  });
  it('a lost answer after the write ran: accepted is said only because the re-read shows it; no second write', async () => {
    await open(4411);
    await ready();
    scenario = 'wdrop';
    press('Record signatures');
    await screen.findByText(/Go-live accepted/);
    await new Promise((r) => setTimeout(r, 30));
    expect(writes()).toHaveLength(1);
  });
  it('403 from the server: "You can’t do this." with its message; whoever may sign is the server\'s rule (no client check)', async () => {
    await open(4411);
    await ready();
    scenario = 'w403';
    press('Record signatures');
    await screen.findByText(/You can’t do this\./);
    expect(screen.getByText(/Only the appointed PM can record this\./)).toBeTruthy();
    expect(writes()).toHaveLength(1);
  });
  it('422 and 429 and 503 show the words and send nothing again', async () => {
    for (const [name, words] of [['w422', /The request was not accepted\. A note is needed\./], ['w429', /Try again shortly\./], ['w503', /Try again shortly\./]] as const) {
      cleanup();
      resetScopedWriteLocks();
      resetGoLiveLive();
      fetchStub.mockClear();
      scenario = undefined;
      await open(4411);
      await ready();
      scenario = name;
      press('Record signatures');
      expect((await screen.findAllByText(words)).length).toBeGreaterThan(0);
      await new Promise((r) => setTimeout(r, 20));
      expect(writes()).toHaveLength(1);
    }
  });
});

describe('prepare v2 (AC16)', () => {
  it('4413 sends the reason, the revisions and four null inputs, once', async () => {
    await open(4413);
    expect(button('Prepare v2').disabled).toBe(true);
    type('Why a new version is needed', 'Add the bureau outage contact');
    press('Prepare v2');
    await waitFor(() => expect(writes()).toHaveLength(1));
    expect(await sent()).toEqual([
      { path: '/api/v1/work/4413/go-live-replies/successor', body: { expected_revision: 6, case_revision: 41, inputs: { template_id: null, checklist: null, incident_reporting: null, rollback: null }, reason: 'Add the bureau outage contact' } },
    ]);
  });
  it('4414 (declined) and 4411 offer no Prepare v2', async () => {
    await open(4414);
    expect(screen.queryByRole('button', { name: 'Prepare v2' })).toBeNull();
  });
});

describe('the decline panel (AC17, AC18)', () => {
  it('4414 shows the quoted note, the rules read only, and the three controls the read supplies', async () => {
    await open(4414);
    expect(screen.getAllByText(/“We are not ready to go live this quarter\.”/).length).toBeGreaterThan(0);
    expect(screen.getByText('Response rules')).toBeTruthy();
    expect(screen.getByText('PM, PMO Lead')).toBeTruthy();
    expect(screen.getByText('Email, Meeting')).toBeTruthy();
    expect(screen.getByText('A new release candidate')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Link the issue' })).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Prepare a new release candidate' })).toBeTruthy();
    expect(screen.getByText(/Reviewing the remediation isn’t available here yet/)).toBeTruthy();
    expect(screen.queryByRole('button', { name: /Review the remediation/ })).toBeNull();
  });
  it('linking an existing issue sends its id and null title, owner and next action', async () => {
    await open(4414);
    choose('Issue', /ISS-0301/);
    type('Note on the issue', 'Tracked');
    press('Link the issue');
    await waitFor(() => expect(writes()).toHaveLength(1));
    expect(await sent()).toEqual([
      { path: '/api/v1/work/4414/go-live-replies', body: { action: 'link_decline_issue', expected_revision: 6, case_revision: 41, reply_id: 21, existing_issue_id: 301, title: null, owner_id: null, next_action: null, note: 'Tracked' } },
    ]);
    await screen.findByText(/1 · #301/);
  });
  it('a new issue sends its title, an owner from the list and the next action, with a null existing id', async () => {
    await open(4414);
    choose('Issue', /Create a new issue/);
    type('Issue title', 'Bureau outage contact missing');
    expect(button('Link the issue').disabled).toBe(true);
    choose('Owner', /Amaka Obi/);
    type(/^Next action/, 'Ask the client for the contact');
    type('Note on the issue', 'New');
    press('Link the issue');
    await waitFor(() => expect(writes()).toHaveLength(1));
    expect((await sent())[0].body).toEqual({ action: 'link_decline_issue', expected_revision: 6, case_revision: 41, reply_id: 21, existing_issue_id: null, title: 'Bureau outage contact missing', owner_id: 32, next_action: 'Ask the client for the contact', note: 'New' });
  });
  it('a new candidate sends the requirements id from the read and the typed reference', async () => {
    await open(4414);
    type('Candidate reference', 'REL-2026-050');
    type('Note on the candidate', 'Start again');
    press('Prepare a new release candidate');
    await waitFor(() => expect(writes()).toHaveLength(1));
    expect((await sent())[0].body).toEqual({ action: 'prepare_new_candidate', expected_revision: 6, case_revision: 41, reply_id: 21, reference: 'REL-2026-050', requirements_id: 81, note: 'Start again' });
  });
  it('4422 (declined, but the read supplies no options): no decline control is drawn', async () => {
    await open(4422);
    expect(screen.queryByRole('button', { name: /Link the issue|Prepare a new release candidate/ })).toBeNull();
    expect(screen.queryByText(/Reviewing the remediation/)).toBeNull();
  });
});

describe('nothing else is sent (AC21)', () => {
  it('a full run touches only the go-live routes, the item and the case file upload', async () => {
    await open(4411);
    await upload(0);
    await ready();
    press('Record signatures');
    await screen.findByText(/Go-live accepted/);
    const other = calls().filter((c) => !/^\/api\/v1\/(me|session)$/.test(c.path) && !GO_LIVE_PATH.test(c.path) && !/^\/api\/v1\/cases\/[^/]+\/files$/.test(c.path));
    expect(other).toEqual([]);
  });
});
