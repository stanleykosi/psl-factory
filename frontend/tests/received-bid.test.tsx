// @vitest-environment jsdom
// F-88 SCR-23: log a received RFP on the live API. The fetch stand-in is the mock itself (mock/received-bids.mjs), so the multipart
// body, the replay by `start_key` and the error answers are the mock's own shapes.
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { setCsrfToken } from '@/api/client';
import { fetchOrganisations, logFormData, type LogInput } from '@/features/rfp/receivedBids';
import { StartWorkDrawer } from '@/features/start-work/StartWorkDrawer';
import { ownLineFor } from '@/features/start-work/lines';
import { inputOf, problemsOf, receivedBid, refuseDocument, type Draft } from '@/features/start-work/lines/receivedBid';

// @ts-expect-error plain ESM module without type declarations
import { parseMultipart, receivedBids, receivedBidsLog, resetReceivedBids } from '../mock/received-bids.mjs';
// @ts-expect-error plain ESM module without type declarations
import { resetStartLive, startLive } from '../mock/start-live.mjs';

import { useNodeUploads } from './assistant-bridge';

const nav = vi.hoisted(() => ({ push: vi.fn() }));
vi.mock('next/navigation', () => ({
  usePathname: () => '/my-work',
  useRouter: () => ({ push: nav.push, replace: vi.fn(), prefetch: vi.fn() }),
}));

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
const TOKEN = 'mock-csrf-pm';
let scenario: string | undefined;
let persona = 'finance_lead';
let fetchStub: ReturnType<typeof vi.fn<(request: Request) => Promise<Response>>>;
let makeFile: (name: string, type?: string, size?: number) => File;
const requests = () => fetchStub.mock.calls.map(([r]) => r);
const hits = (path: RegExp, method?: string) => requests().filter((r) => path.test(new URL(r.url).pathname) && (!method || r.method === method));
const writes = () => (receivedBidsLog() as { requests: { form: { fields: Record<string, string>; files: Record<string, { filename: string; bytes: number }> }; status: number }[] }).requests;

beforeEach(async () => {
  makeFile = await useNodeUploads();
  resetStartLive();
  resetReceivedBids();
  scenario = undefined;
  persona = 'finance_lead';
  nav.push.mockReset();
  setCsrfToken(TOKEN);
  fetchStub = vi.fn(async (request: Request) => {
    const url = new URL(request.url);
    if (url.pathname === '/api/v1/session') return json(200, { csrf_token: 'fresh', signed_in: true, next_url: '/' });
    const csrfOk = request.headers.get('x-csrftoken') === TOKEN;
    if (url.pathname.startsWith('/api/v1/received-bids')) {
      const rawBytes = request.method === 'GET' ? new Uint8Array() : new Uint8Array(await request.clone().arrayBuffer());
      const [status, body] = receivedBids({ method: request.method.toLowerCase(), url, raw: Buffer.from(rawBytes).toString('utf8'), rawBytes, contentType: request.headers.get('content-type'), scenario, csrfOk, persona });
      return json(status, body);
    }
    const [status, body] = startLive({ method: request.method.toLowerCase(), url, raw: '', scenario: undefined, csrfOk, persona });
    return json(status, body);
  });
  vi.stubGlobal('fetch', fetchStub);
});
afterEach(() => {
  vi.unstubAllGlobals();
  setCsrfToken(null);
});

const Own = receivedBid.Own;
const open = async () => {
  const view = render(<Own onBack={vi.fn()} onClose={vi.fn()} pathname="/my-work" />);
  await screen.findByRole('combobox', { name: 'Client' }).catch(() => undefined);
  return view;
};
async function choose(name: string, option: string) {
  fireEvent.click(screen.getByRole('combobox', { name }));
  fireEvent.click(await screen.findByRole('option', { name: option }));
}
function pickNow(label: string) {
  fireEvent.click(screen.getByLabelText(label));
  fireEvent.click(screen.getByRole('button', { name: 'Use now' }));
}
const attach = (file: File) => fireEvent.change(document.querySelector('input[type="file"]') as HTMLInputElement, { target: { files: [file] } });
/** Everything the form needs, as a person fills it. */
async function fill({ file = makeFile('rfp.pdf', 'application/pdf', 600), reference = 'RFP-2026-041', deadline = 'Not known' } = {}) {
  await choose('Client', 'Northwind Bank');
  fireEvent.change(screen.getByLabelText('RFP reference'), { target: { value: reference } });
  attach(file);
  pickNow('Actually received');
  fireEvent.click(screen.getByRole('radio', { name: deadline }));
}
const press = (name = 'Log RFP') => fireEvent.click(screen.getByRole('button', { name }));

describe('the organisation picker (AC1, AC8)', () => {
  it('offers exactly the served organisations and calls neither /lines nor POST /work', async () => {
    await open();
    fireEvent.click(screen.getByRole('combobox', { name: 'Client' }));
    expect((await screen.findAllByRole('option')).map((o) => o.textContent)).toEqual(['Northwind Bank', 'Harbour Insurance']);
    expect(hits(/^\/api\/v1\/received-bids\/organisations$/)).toHaveLength(1);
    expect(hits(/^\/api\/v1\/(lines|work)$/)).toHaveLength(0);
  });

  it('with no organisations says so and keeps the submit off, with its reason', async () => {
    persona = 'none';
    render(<Own onBack={vi.fn()} onClose={vi.fn()} pathname="/" />);
    expect(await screen.findAllByText('You can’t log a received RFP for any organisation yet.')).not.toHaveLength(0);
    const button = screen.getByRole('button', { name: 'Log RFP' }) as HTMLButtonElement;
    expect(button.disabled).toBe(true);
    expect(document.getElementById(button.getAttribute('aria-describedby')!)!.textContent).toContain('any organisation');
  });

  it('a 403 on the organisation list shows the plain 403 words and no form', async () => {
    scenario = 'rb_orgs_denied';
    await open();
    expect(await screen.findByText('You can’t log RFPs for this organisation.')).toBeTruthy();
    expect(screen.queryByLabelText('RFP reference')).toBeNull();
  });

  it('a 401 shows the signed-out state, not an error', async () => {
    scenario = '401';
    await open();
    expect((await screen.findByRole('link', { name: /sign in/i })).getAttribute('href')).toContain('/sign-in?next=');
  });
});

describe('the one POST (AC2, AC3, AC7)', () => {
  it('sends the fixed multipart keys with no `definition`, reads the receipt, and says RFP logged with the reference', async () => {
    await open();
    await fill();
    press();
    expect(await screen.findByText('RFP logged.')).toBeTruthy();
    const [sent] = writes();
    expect(Object.keys(sent.form.fields).sort()).toEqual(['authority', 'deadline_status', 'received_at', 'reference', 'start_key']);
    expect(sent.form.fields).toMatchObject({ authority: '11', reference: 'RFP-2026-041', deadline_status: 'unknown' });
    expect(sent.form.fields.received_at).toMatch(/Z$/);
    expect(sent.form.files.document).toMatchObject({ filename: 'rfp.pdf' });
    const post = hits(/^\/api\/v1\/received-bids$/, 'POST');
    expect(post).toHaveLength(1);
    expect(post[0].headers.get('content-type')).toMatch(/^multipart\/form-data; boundary=/);
    expect(post[0].headers.get('x-csrftoken')).toBe(TOKEN);
    expect(hits(/receipts\/501$/, 'GET')).toHaveLength(1);
    expect(screen.getByText('RFP-2026-041')).toBeTruthy();
    expect(screen.getByText(/rfp\.pdf/)).toBeTruthy();
    expect(screen.getByRole('link', { name: 'Open Unassigned' }).getAttribute('href')).toBe('/my-work?queue=unassigned');
    // no work item is named and none is opened
    expect(document.body.textContent).not.toMatch(/work item|W-\d/i);
    expect(hits(/^\/api\/v1\/(work|cases)/)).toHaveLength(0);
  });

  it('a stated deadline needs its date: the form says so and sends nothing; with a date it sends deadline_at, otherwise never', async () => {
    await open();
    await fill({ deadline: 'A date is stated' });
    press();
    expect((await screen.findByRole('alert')).textContent).toContain('Choose the deadline date and time.');
    expect(writes()).toHaveLength(0);
    pickNow('Deadline date and time');
    press();
    await screen.findByText('RFP logged.');
    expect(writes()[0].form.fields.deadline_at).toMatch(/Z$/);
  });

  it('a note travels as `note`, comes back in the receipt, and one over 4000 characters is refused before sending', async () => {
    await open();
    await fill();
    fireEvent.change(screen.getByLabelText(/^Note/), { target: { value: 'x'.repeat(4001) } });
    press();
    expect((await screen.findByRole('alert')).textContent).toContain('Use 4000 characters or fewer.');
    expect(writes()).toHaveLength(0);
    fireEvent.change(screen.getByLabelText(/^Note/), { target: { value: 'Client wants a draft by Friday.' } });
    press();
    await screen.findByText('RFP logged.');
    expect(writes()[0].form.fields.note).toBe('Client wants a draft by Friday.');
    expect(screen.getByText('Client wants a draft by Friday.')).toBeTruthy();
  });

  it('the confirmation tick-box shows only with a name or a submission detail, and is sent only when ticked', async () => {
    await open();
    await fill();
    expect(screen.queryByLabelText(/I confirm the client name/)).toBeNull();
    fireEvent.change(screen.getByLabelText(/Client name as written in the RFP/), { target: { value: 'Northwind Bank plc' } });
    fireEvent.click(screen.getByLabelText(/I confirm the client name/));
    press();
    await screen.findByText('RFP logged.');
    expect(writes()[0].form.fields).toMatchObject({ prospect_name: 'Northwind Bank plc', context_attested: 'true' });
  });

  it('a receipt that cannot be read after a 200 says so, and "Read the receipt again" never sends the POST again', async () => {
    scenario = 'rb_receipt_down';
    await open();
    await fill();
    press();
    expect(await screen.findByText('RFP logged. We couldn’t read the receipt back.')).toBeTruthy();
    scenario = undefined;
    fireEvent.click(screen.getByRole('button', { name: 'Read the receipt again' }));
    expect(await screen.findByText('RFP-2026-041')).toBeTruthy();
    expect(hits(/^\/api\/v1\/received-bids$/, 'POST')).toHaveLength(1);
  });

  it('focus moves to the success message', async () => {
    await open();
    await fill();
    press();
    await screen.findByText('RFP logged.');
    await waitFor(() => expect(document.activeElement?.getAttribute('role')).toBe('status'));
  });
});

describe('uncertain results and replay (AC4, AC6)', () => {
  it('after a 503, "Check again" resends the same body and the same start_key and logs one RFP', async () => {
    scenario = 'rb_uncertain';
    await open();
    await fill();
    press();
    expect(await screen.findByText('Not confirmed. Check before trying again.')).toBeTruthy();
    expect((screen.getByLabelText('RFP reference') as HTMLInputElement).readOnly).toBe(true);
    press('Check again');
    await screen.findByText('RFP logged.');
    const [first, second] = writes();
    expect([first.status, second.status]).toEqual([503, 200]);
    expect(second.form.fields).toEqual(first.form.fields);
    expect(second.form.fields.start_key).toBe(first.form.fields.start_key);
    expect((receivedBidsLog() as { logged: unknown[] }).logged).toHaveLength(1);
  });

  it('a network failure is uncertain too and never sends a second key', async () => {
    await open();
    await fill();
    const real = fetchStub.getMockImplementation()!;
    let down = true;
    fetchStub.mockImplementation(async (request) => {
      if (down && request.method === 'POST' && new URL(request.url).pathname === '/api/v1/received-bids') throw new TypeError('Failed to fetch');
      return real(request);
    });
    press();
    expect(await screen.findByText('Not confirmed. Check before trying again.')).toBeTruthy();
    down = false;
    press('Check again');
    await screen.findByText('RFP logged.');
    expect(writes()).toHaveLength(1);
  });

  it('the same start_key and input again returns the original receipt id (replay)', async () => {
    const input: LogInput = { authority: 11, startKey: '9b2f0c8a-6b0e-4f7a-9d1a-0c5b2f6f1a11', reference: 'RFP-9', receivedAt: '2026-11-20T09:30:00.000Z', deadlineStatus: 'unknown', document: makeFile('rfp.pdf', 'application/pdf', 50) };
    const send = async () => {
      const request = new Request('http://x/api/v1/received-bids', { method: 'POST', body: logFormData(input) });
      const rawBytes = new Uint8Array(await request.clone().arrayBuffer());
      return receivedBids({ method: 'post', url: new URL(request.url), raw: '', rawBytes, contentType: request.headers.get('content-type'), scenario: undefined, csrfOk: true, persona: 'finance_lead' })[1];
    };
    const first = await send();
    expect(await send()).toEqual(first);
    expect((receivedBidsLog() as { logged: unknown[] }).logged).toHaveLength(1);
  });

  it('a new key is made only after a failure that recorded nothing and a field change', async () => {
    scenario = 'rb_invalid';
    await open();
    await fill();
    press();
    expect((await screen.findAllByText('Give an email address for an email submission.')).length).toBeGreaterThan(0);
    press();
    await waitFor(() => expect(writes()).toHaveLength(2));
    expect(writes()[1].form.fields.start_key).toBe(writes()[0].form.fields.start_key);
    fireEvent.change(screen.getByLabelText('RFP reference'), { target: { value: 'RFP-2026-042' } });
    scenario = undefined;
    press();
    await screen.findByText('RFP logged.');
    expect(writes()[2].form.fields.start_key).not.toBe(writes()[0].form.fields.start_key);
  });

  it('a duplicate reference shows the API message in the callout and logs nothing new', async () => {
    const first = await open();
    await fill();
    press();
    await screen.findByText('RFP logged.');
    first.unmount();
    await open();
    await fill();
    press();
    expect((await screen.findByRole('alert')).textContent).toContain('This reference has already been logged for this organisation.');
    expect((receivedBidsLog() as { logged: unknown[] }).logged).toHaveLength(1);
  });
});

describe('refusals (AC5, AC8)', () => {
  it('refuses a 6 MiB file and a .png before sending, in plain words', async () => {
    await open();
    await fill({ file: makeFile('big.pdf', 'application/pdf', 6 * 1024 * 1024) });
    press();
    expect((await screen.findByRole('alert')).textContent).toContain('The file is larger than 5 MB.');
    expect(writes()).toHaveLength(0);
    attach(makeFile('scan.png', 'image/png', 10));
    press();
    await waitFor(() => expect(screen.getByRole('alert').textContent).toContain('Use a Word or PDF file.'));
    expect(writes()).toHaveLength(0);
    expect([refuseDocument({ name: 'a.PDF', size: 1 }), refuseDocument({ name: 'a.docx', size: 1 }), refuseDocument({ name: 'a.pdf.exe', size: 1 }), refuseDocument({ name: 'a', size: 1 })]).toEqual([null, null, 'Use a Word or PDF file.', 'Use a Word or PDF file.']);
  });

  it.each([
    ['rb_too_large', 'The file is larger than 5 MB.'],
    ['rb_unsupported', 'Use a Word or PDF file.'],
    ['429', 'Too many tries. Wait a moment.'],
    ['rb_denied', 'You can’t log RFPs for this organisation.'],
  ])('a server %s answer shows %s and keeps what was typed', async (answer, words) => {
    await open();
    await fill();
    scenario = answer === '429' ? undefined : answer;
    if (answer === '429') {
      const real = fetchStub.getMockImplementation()!;
      fetchStub.mockImplementation(async (request) => (request.method === 'POST' ? json(429, { code: 'rate_limited', message: 'x' }) : real(request)));
    }
    press();
    expect((await screen.findAllByText(words)).length).toBeGreaterThan(0);
    expect((screen.getByLabelText('RFP reference') as HTMLInputElement).value).toBe('RFP-2026-041');
    expect(screen.queryByText('RFP logged.')).toBeNull();
  });

  it('presses Log RFP with nothing filled: every required field is named and nothing is sent', async () => {
    await open();
    press();
    const summary = await screen.findByRole('alert');
    for (const text of ['Client is required.', 'RFP reference is required.', 'RFP document is required.', 'Actually received is required.', 'Deadline is required.']) expect(within(summary).getByText(text)).toBeTruthy();
    expect(writes()).toHaveLength(0);
  });
});

describe('pure rules', () => {
  const base: Draft = { authority: '11', reference: 'R', receivedAt: '2026-11-20T09:30', deadlineStatus: 'stated', deadlineAt: '', note: '', prospectName: '', submissionMethod: undefined, submissionTarget: '', attested: false, document: null };
  beforeEach(() => {
    base.document = makeFile('a.pdf', 'application/pdf', 5);
  });

  it('a stated deadline without a date is the only problem; other statuses never send deadline_at', () => {
    expect(problemsOf(base)).toEqual({ deadline_at: 'Choose the deadline date and time.' });
    const keys = (draft: Draft) => [...logFormData(inputOf(draft, 'k')).keys()].sort();
    expect(keys({ ...base, deadlineStatus: 'unknown', deadlineAt: '2026-12-05T17:00' })).not.toContain('deadline_at');
    expect(keys({ ...base, deadlineStatus: 'stated', deadlineAt: '2026-12-05T17:00' })).toContain('deadline_at');
  });

  it('context_attested is sent only when ticked with a name or a detail; whitespace-only optional fields are omitted', () => {
    const keys = (draft: Draft) => [...logFormData(inputOf(draft, 'k')).keys()];
    expect(keys({ ...base, deadlineStatus: 'unknown', attested: true })).not.toContain('context_attested');
    expect(keys({ ...base, deadlineStatus: 'unknown', attested: true, prospectName: ' ' })).not.toContain('prospect_name');
    expect(keys({ ...base, deadlineStatus: 'unknown', attested: true, prospectName: 'N' })).toContain('context_attested');
    expect(keys({ ...base, deadlineStatus: 'unknown', attested: false, prospectName: 'N' })).not.toContain('context_attested');
  });

  it('the multipart reader reads what the form builds', async () => {
    const request = new Request('http://x/', { method: 'POST', body: logFormData(inputOf({ ...base, deadlineStatus: 'unknown' }, 'abc')) });
    const parsed = parseMultipart(new Uint8Array(await request.arrayBuffer()), request.headers.get('content-type'));
    expect(parsed.fields.start_key).toBe('abc');
    expect(parsed.files.document.filename).toBe('a.pdf');
  });
});

describe('the registry and the chooser (AC17, AC20)', () => {
  it('the received RFP is registered as a line that owns its submit', () => {
    expect(ownLineFor('received-bid')?.ownsSubmit).toBe(true);
    expect(ownLineFor('pmo-weekly-report/v1')).toBeUndefined();
  });

  it('Start work lists it, and Next opens the Log RFP drawer with no project picker', async () => {
    render(<StartWorkDrawer onClose={vi.fn()} />);
    fireEvent.click(await screen.findByRole('radio', { name: /Log a received RFP/ }));
    fireEvent.click(screen.getByRole('button', { name: 'Next' }));
    expect(await screen.findByRole('dialog', { name: 'Log a received RFP' })).toBeTruthy();
    expect(await screen.findByRole('combobox', { name: 'Client' })).toBeTruthy();
    expect(screen.queryByRole('combobox', { name: 'Project' })).toBeNull();
    expect(hits(/^\/api\/v1\/lines\/projects$/)).toHaveLength(0);
  });

  it('fetchOrganisations returns the items', async () => {
    expect(await fetchOrganisations()).toEqual([{ id: 11, organisation: 'Northwind Bank' }, { id: 12, organisation: 'Harbour Insurance' }]);
  });
});
