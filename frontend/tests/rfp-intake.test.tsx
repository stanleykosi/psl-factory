// @vitest-environment jsdom
// F-49 (FE-RFP-INTAKE part 2): "Log a received RFP" in the Start work drawer, against the start-work contract mock
// in process. Every test names the acceptance criterion it covers.
import { readFileSync } from 'node:fs';

import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import Ajv2020 from 'ajv/dist/2020';
import addFormats from 'ajv-formats';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { setCsrfToken } from '@/api/client';
import { StartWorkButton } from '@/features/start-work/StartWorkButton';
import type { Line, Lines } from '@/features/start-work/types';

import { setWhen } from './controls';

// @ts-expect-error plain ESM module without type declarations
import { OPENAPI_PATH } from '../mock/server.mjs';
// @ts-expect-error plain ESM module without type declarations
import { createStartWorkMock } from '../mock/start-work.mjs';

const nav = vi.hoisted(() => ({ pathname: '/my-work', push: vi.fn() }));
vi.mock('next/navigation', () => ({
  usePathname: () => nav.pathname,
  useRouter: () => ({ push: nav.push, replace: vi.fn(), prefetch: vi.fn() }),
}));

const openapi = JSON.parse(readFileSync(OPENAPI_PATH, 'utf8'));
const ajv = new Ajv2020({ allErrors: true, strict: true });
addFormats(ajv);
type Operation = { operationId?: string; requestBody: { content: { 'application/json': { schema: object } } } };
const requestSchema = (path: string, id: string) =>
  (Object.values(openapi.paths[path] as Record<string, Operation>).find((op) => op?.operationId === id) as Operation).requestBody.content['application/json'].schema;
const validStart = ajv.compile(requestSchema('/api/v1/work', 'E-WORK-START'));
const validUpload = ajv.compile(requestSchema('/api/v1/cases/{case_id}/evidence', 'E-EVIDENCE-UPLOAD'));

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });

type Sent = { url: URL; headers: Headers; body: Record<string, unknown> & { intake: Record<string, unknown>; idempotency_key: string; case_revision: number } };
type Handler = (request: Request, url: URL, body: Record<string, unknown>) => Promise<Response | undefined> | Response | undefined;

let mock: ReturnType<typeof createStartWorkMock>;
let cookies: Record<string, string>;
let uploads: Sent[];
let starts: Sent[];
let gets: URL[];
let override: Handler | undefined;

function operationOf(request: Request, url: URL) {
  if (url.pathname === '/api/v1/lines') return 'E-LINES';
  if (url.pathname.startsWith('/api/v1/lines/')) return 'E-LINE-OPTIONS';
  if (url.pathname === '/api/v1/work' && request.method === 'POST') return 'E-WORK-START';
  if (/^\/api\/v1\/cases\/[^/]+\/evidence$/.test(url.pathname) && request.method === 'POST') return 'E-EVIDENCE-UPLOAD';
  throw new Error(`unexpected request ${request.method} ${url.pathname}`);
}

let persona: string;
beforeEach(() => {
  nav.push.mockReset();
  mock = createStartWorkMock(openapi);
  persona = 'pmo_lead';
  cookies = {};
  uploads = [];
  starts = [];
  gets = [];
  override = undefined;
  setCsrfToken('mock-csrf-pmo_lead');
  vi.stubGlobal(
    'fetch',
    vi.fn(async (request: Request) => {
      const url = new URL(request.url);
      const raw = request.method === 'POST' ? await request.clone().text() : '';
      const body = raw ? JSON.parse(raw) : {};
      const operation = operationOf(request, url);
      if (operation === 'E-EVIDENCE-UPLOAD') uploads.push({ url, headers: request.headers, body });
      else if (operation === 'E-WORK-START') starts.push({ url, headers: request.headers, body });
      else gets.push(url);
      const custom = await override?.(request, url, body);
      if (custom) return custom;
      if (request.method === 'POST' && request.headers.get('X-CSRFToken') !== `mock-csrf-${persona}`)
        return json(403, { code: 'csrf_failed', message: 'Your session check failed. Reload and try again.' });
      const [status, reply] = mock.handle(operation, { url, raw, persona, cookies });
      return json(status, reply);
    }),
  );
});
afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  setCsrfToken(null);
});

const dialog = () => screen.getByRole('dialog');
const press = (name: string | RegExp) => fireEvent.click(within(dialog()).getByRole('button', { name }));
const logPress = () => press('Log RFP');
const lineGets = () => gets.filter((u) => u.pathname === '/api/v1/lines');

async function open(as = 'pmo_lead') {
  persona = as;
  setCsrfToken(`mock-csrf-${as}`);
  render(<StartWorkButton variant="bar" />);
  fireEvent.click(screen.getByRole('button', { name: 'More ways to start' }));
  fireEvent.click(await within(dialog()).findByRole('radio', { name: /^Log a received RFP/ }));
  press('Next');
  await within(dialog()).findByRole('button', { name: 'change line' });
}

function cleanupDialog() {
  const open = screen.queryByRole('dialog');
  if (open) fireEvent.keyDown(open, { key: 'Escape' });
  document.body.innerHTML = '';
}

async function pick(field: string, option: string) {
  fireEvent.click(within(dialog()).getByRole('combobox', { name: field }));
  fireEvent.click(await within(dialog()).findByRole('option', { name: new RegExp(`^${option}`) }));
}
// A date and a time is picked from the shared dropdown (D-158); anything else is typed.
const text = (label: string, value: string) =>
  /^\d{4}-\d\d-\d\dT\d\d:\d\d$/.test(value) ? setWhen(label, value, within(dialog())) : fireEvent.change(within(dialog()).getByLabelText(label), { target: { value } });
const radio = (group: string, name: string) => fireEvent.click(within(within(dialog()).getByRole('radiogroup', { name: group })).getByRole('radio', { name }));
const fileInput = () => dialog().querySelector<HTMLInputElement>('[data-field="rfp_document"] input[type="file"]')!;
const documentBox = () => within(dialog()).getByRole('group', { name: 'The RFP document' });
const file = (name: string, size: number) => new File([new Uint8Array(size).fill(7)], name);
const choose = (f: File) => fireEvent.change(fileInput(), { target: { files: [f] } });
const MB_2_4 = Math.round(2.4 * 1024 * 1024);
async function uploaded() {
  const [found] = await within(dialog()).findAllByText(/Uploaded/);
  await waitFor(() => expect(dialog().querySelector('.sw-primary')).toHaveProperty('disabled', false));
  return found;
}
const iso = (local: string) => new Date(local).toISOString();

const RECEIVED = '2026-11-12T09:40';
const DEADLINE = '2026-11-28T17:00';

/** The board's values, up to the file; the file is chosen by the caller. */
async function fillTop(client = 'Tamarind Loans Ltd') {
  await pick('Client or prospect', client);
  text('RFP reference', 'TL-RFP-2026-014');
}
async function fillRest(method = 'Email') {
  text('Received', RECEIVED);
  radio('How the client wants it submitted', method);
}
/** Everything the board draws, with a Stated deadline. */
async function fillBoard() {
  await fillTop();
  choose(file('Tamarind-Loans-RFP-loan-origination.pdf', MB_2_4));
  await uploaded();
  await fillRest();
  text('Submit to (optional)', 'procurement@tamarindloans.example');
  radio('Submission deadline', 'Stated');
  text('Deadline (optional)', DEADLINE);
  text('Note (optional)', 'Received from their procurement lead by email.');
}

function deferred() {
  let resolve!: (r: Response) => void;
  const promise = new Promise<Response>((r) => (resolve = r));
  return { promise, resolve };
}

const rfpLine = () => (mock.handle('E-LINES', { url: new URL('http://x/api/v1/lines'), raw: '', persona: 'pmo_lead', cookies })[1] as Lines).items.find((l: Line) => l.key === 'rfp_intake')!;
/** E-LINES with a change to the RFP line, as the backend might serve it. */
function serveLine(change: (line: Line) => Line) {
  const lines = mock.handle('E-LINES', { url: new URL('http://x/api/v1/lines'), raw: '', persona: 'pmo_lead', cookies })[1] as Lines;
  const changed = { ...lines, items: lines.items.map((l: Line) => (l.key === 'rfp_intake' ? change(l) : l)) };
  override = (_, url) => (url.pathname === '/api/v1/lines' ? json(200, changed) : undefined);
}

describe('the drawer and its fields', () => {
  it('1: the line is drawn from data: fields in order, words, button and eyebrow', async () => {
    await open();
    expect(dialog().querySelector('.psl-drawer__eyebrow')!.textContent).toBe('START WORK · PRE-SALE');
    expect(within(dialog()).getByText('Log a received RFP')).toBeTruthy();
    // the deadline and Submit to are conditional (overlay), so only the unconditional fields show first
    expect([...dialog().querySelectorAll('[data-field]')].map((box) => box.getAttribute('data-field'))).toEqual([
      'client',
      'rfp_reference',
      'rfp_document',
      'received_at',
      'submission_method',
      'deadline_status',
      'note',
    ]);
    expect(within(dialog()).getByText('Client or prospect')).toBeTruthy();
    // the help stays under its own field here, not under the document box
    expect(within(dialog()).getByText('As written on their document').closest('[data-field]')!.getAttribute('data-field')).toBe('rfp_reference');
    expect(within(documentBox()).getByRole('button', { name: 'Choose a file' })).toBeTruthy();
    expect(within(dialog()).getByText('When it actually arrived, not when you log it')).toBeTruthy();
    expect(within(within(dialog()).getByRole('radiogroup', { name: 'How the client wants it submitted' })).getAllByRole('radio').map((r) => r.textContent)).toEqual([
      'Email',
      'Client portal',
      'By hand',
      'Not stated',
    ]);
    expect(within(within(dialog()).getByRole('radiogroup', { name: 'Submission deadline' })).getAllByRole('radio').map((r) => r.textContent)).toEqual(['Unknown', 'Stated', 'Not stated']);
    expect(within(dialog()).getByLabelText('Note (optional)')).toBeTruthy();
    expect(within(dialog()).getByRole('button', { name: 'Log RFP' })).toBeTruthy();
    expect(dialog().textContent).not.toMatch(/Tola|has read|its own case|workspace|client register/);
  });

  it('1: Submit to and Deadline are drawn after the choices that ask for them, in the order returned', async () => {
    await open();
    radio('How the client wants it submitted', 'Email');
    radio('Submission deadline', 'Stated');
    expect([...dialog().querySelectorAll('[data-field]')].map((box) => box.getAttribute('data-field'))).toEqual([
      'client',
      'rfp_reference',
      'rfp_document',
      'received_at',
      'submission_method',
      'submission_target',
      'deadline_status',
      'deadline_at',
      'note',
    ]);
    expect(within(dialog()).getByText('Where the client wants it sent.')).toBeTruthy();
    expect(within(dialog()).getByText('Enter it as the RFP states it.')).toBeTruthy();
  });

  it('3: the client picker lists exactly the three clients served, with no typed-in option and no "New client" row', async () => {
    await open();
    fireEvent.click(within(dialog()).getByRole('combobox', { name: 'Client or prospect' }));
    const options = await within(dialog()).findAllByRole('option');
    expect(options.map((o) => o.textContent)).toEqual(['Tamarind Loans Ltd', 'Harmattan Bank', 'Kora Logistics']);
    expect(within(dialog()).queryByText('New client')).toBeNull();
    const reads = gets.filter((u) => u.pathname === '/api/v1/lines/rfp_intake/fields/client/options');
    expect(reads.length).toBeGreaterThan(0);
  });

  it('QA-2-1: Log RFP with every required field empty names each one, moves focus to the first, and sends nothing', async () => {
    await open();
    logPress();
    for (const label of ['Client or prospect', 'RFP reference', 'The RFP document', 'Received', 'How the client wants it submitted', 'Submission deadline']) {
      expect(await within(dialog()).findByText(`${label} is required.`)).toBeTruthy();
    }
    expect(starts).toHaveLength(0);
    expect(nav.push).not.toHaveBeenCalled();
    expect(document.activeElement).toBe(within(dialog()).getByRole('combobox', { name: 'Client or prospect' }));
  });

  it('4: with the overlay the picker ends with "New client" and a required name; an empty name sends nothing', async () => {
    cookies = { psl_mock_rfp: 'new_client' };
    await open();
    fireEvent.click(within(dialog()).getByRole('combobox', { name: 'Client or prospect' }));
    const options = await within(dialog()).findAllByRole('option');
    expect(options.map((o) => o.textContent)).toEqual(['Tamarind Loans Ltd', 'Harmattan Bank', 'Kora Logistics', 'New client']);
    fireEvent.click(options[3]);
    const name = within(dialog()).getByLabelText('Name of the new client');
    text('RFP reference', 'AC-1');
    logPress();
    expect(await within(dialog()).findByText('Client or prospect is required.')).toBeTruthy();
    expect(starts).toHaveLength(0);
    fireEvent.change(name, { target: { value: 'Acme Foods' } });
    expect(within(dialog()).queryByText('Client or prospect is required.')).toBeNull();
    choose(file('acme.pdf', 4096));
    await uploaded();
    await fillRest();
    radio('Submission deadline', 'Unknown');
    logPress();
    await waitFor(() => expect(nav.push).toHaveBeenCalledWith('/work/W-3351'));
    expect(starts[0].body.intake.client).toEqual({ new: { name: 'Acme Foods' } });
    expect(validStart(starts[0].body)).toBe(true);
    expect(document.body.textContent).not.toMatch(/client register/);
  });

  it('4: without the overlay no {new: …} is ever sent, even if the page were asked for one', async () => {
    await open();
    await fillTop();
    choose(file('a.pdf', 2048));
    await uploaded();
    await fillRest();
    radio('Submission deadline', 'Unknown');
    logPress();
    await waitFor(() => expect(starts).toHaveLength(1));
    expect(starts[0].body.intake.client).toBe('CL-3506');
    // and the mock refuses the shape without the overlay
    const refused = mock.handle('E-WORK-START', {
      url: new URL('http://x/api/v1/work'),
      raw: JSON.stringify({ ...starts[0].body, idempotency_key: 'other', intake: { ...starts[0].body.intake, client: { new: { name: 'Acme' } } } }),
      persona: 'pmo_lead',
      cookies,
    });
    expect(refused).toEqual([422, expect.objectContaining({ fields: [{ name: 'client', message: 'Choose one from the list.' }] })]);
  });
});

describe('deadline and conditional fields', () => {
  async function ready(method = 'Email') {
    await fillTop();
    choose(file('a.pdf', 2048));
    await uploaded();
    await fillRest(method);
  }

  it('5: Unknown or Not stated sends no date, even after one was typed under Stated; Stated sends an instant', async () => {
    await open();
    await ready();
    radio('Submission deadline', 'Stated');
    text('Deadline (optional)', DEADLINE);
    radio('Submission deadline', 'Unknown');
    expect(within(dialog()).queryByLabelText('Deadline (optional)')).toBeNull();
    logPress();
    await waitFor(() => expect(starts).toHaveLength(1));
    expect(starts[0].body.intake.deadline_status).toBe('unknown');
    expect(starts[0].body.intake).not.toHaveProperty('deadline_at');
    cleanupDialog();

    await open();
    await ready();
    radio('Submission deadline', 'Stated');
    text('Deadline (optional)', DEADLINE);
    radio('Submission deadline', 'Not stated');
    radio('Submission deadline', 'Stated');
    // the date was dropped when the choice changed: nothing fills it back in
    expect((within(dialog()).getByLabelText('Deadline (optional)') as HTMLInputElement).value).toBe('');
    text('Deadline (optional)', DEADLINE);
    logPress();
    await waitFor(() => expect(starts).toHaveLength(2));
    expect([starts[1].body.intake.deadline_status, starts[1].body.intake.deadline_at]).toEqual(['stated', iso(DEADLINE)]);
    for (const start of starts) expect(validStart(start.body)).toBe(true);
  });

  it('5: a Not stated choice sends its own value and no date', async () => {
    await open();
    await ready();
    radio('Submission deadline', 'Not stated');
    logPress();
    await waitFor(() => expect(starts).toHaveLength(1));
    expect(starts[0].body.intake.deadline_status).toBe('not_stated');
    expect(Object.keys(starts[0].body.intake)).not.toContain('deadline_at');
  });

  it('6: with the overlay, Submit to is drawn for Email and Client portal only, and By hand drops what was typed', async () => {
    await open();
    await ready();
    expect(within(dialog()).getByLabelText('Submit to (optional)')).toBeTruthy();
    text('Submit to (optional)', 'x@y.example');
    radio('How the client wants it submitted', 'Client portal');
    expect(within(dialog()).getByLabelText('Submit to (optional)')).toBeTruthy();
    radio('How the client wants it submitted', 'By hand');
    expect(within(dialog()).queryByLabelText('Submit to (optional)')).toBeNull();
    radio('How the client wants it submitted', 'Not stated');
    expect(within(dialog()).queryByLabelText('Submit to (optional)')).toBeNull();
    radio('Submission deadline', 'Unknown');
    logPress();
    await waitFor(() => expect(starts).toHaveLength(1));
    expect(starts[0].body.intake).not.toHaveProperty('submission_target');
    expect(starts[0].body.intake.submission_method).toBe('not_stated');
  });

  it('6: without the overlay every field is drawn, and a stated deadline with no date is refused only by the 422', async () => {
    serveLine((line) => ({
      ...line,
      intake: line.intake.map((field: Line['intake'][number] & { show_when?: unknown }) => ({ ...field, show_when: undefined })),
    }));
    await open();
    expect([...dialog().querySelectorAll('[data-field]')].map((box) => box.getAttribute('data-field'))).toContain('deadline_at');
    expect(within(dialog()).getByLabelText('Submit to (optional)')).toBeTruthy();
    await ready('By hand');
    radio('Submission deadline', 'Stated');
    logPress();
    expect(await within(dialog()).findByText('Enter the deadline the RFP states.')).toBeTruthy();
    expect(starts).toHaveLength(1);
    expect(within(dialog()).getByLabelText('Deadline (optional)').closest('[data-field]')!.textContent).toContain('Enter the deadline the RFP states.');
  });

  it('6: a malformed show_when is treated as absent: the field is drawn', async () => {
    serveLine((line) => ({
      ...line,
      intake: line.intake.map((f: Line['intake'][number]) => (f.name === 'deadline_at' ? { ...f, show_when: { field: 7, equals: 'unknown' } } : f)),
    }));
    await open();
    expect(within(dialog()).getByLabelText('Deadline (optional)')).toBeTruthy();
  });
});

describe('the document and the write', () => {
  it('8: the file uploads when chosen: one POST at revision 5, "Uploading…" then "Uploaded · 2.4 MB", and the start sends 6', async () => {
    const held = deferred();
    override = (_, url) => (url.pathname.endsWith('/evidence') ? held.promise : undefined);
    await open();
    expect(fileInput().hasAttribute('accept')).toBe(false);
    choose(file('Tamarind-Loans-RFP-loan-origination.pdf', MB_2_4));
    await waitFor(() => expect(uploads).toHaveLength(1));
    const [sent] = uploads;
    expect(sent.url.pathname).toBe('/api/v1/cases/C-RFP-INTAKE/evidence');
    expect(sent.headers.get('X-CSRFToken')).toBe('mock-csrf-pmo_lead');
    expect(Object.keys(sent.body).sort()).toEqual(['case_revision', 'content_base64', 'filename', 'kind']);
    expect(validUpload(sent.body)).toBe(true);
    expect([sent.body.kind, sent.body.filename, sent.body.case_revision]).toEqual(['rfp_document', 'Tamarind-Loans-RFP-loan-origination.pdf', 5]);
    expect(within(documentBox()).getByText(/Uploading…/)).toBeTruthy();
    expect(within(dialog()).getByRole('button', { name: 'Log RFP' })).toHaveProperty('disabled', true);
    await act(async () => held.resolve(json(200, { evidence_id: 'EV-SW-C-RFP-INTAKE-1', sha256: 'x', case_revision: 6 })));
    expect((await uploaded()).textContent).toBe('Uploaded · 2.4 MB');
  });

  it('8: a failed upload reads "Not uploaded" and Log RFP sends nothing until the file is removed', async () => {
    override = (_, url) => (url.pathname.endsWith('/evidence') ? json(500, { code: 'server', message: 'Down.' }) : undefined);
    await open();
    await fillTop();
    choose(file('x.pdf', 2048));
    const [found] = await within(dialog()).findAllByText(/Not uploaded/);
    expect(found.textContent).toContain('Not uploaded');
    expect(within(dialog()).getByRole('button', { name: 'Log RFP' })).toHaveProperty('disabled', true);
    logPress();
    await act(async () => {
      await new Promise((r) => setTimeout(r, 100));
    });
    expect(starts).toHaveLength(0);
    press('Remove x.pdf');
    expect(within(dialog()).getByRole('button', { name: 'Log RFP' })).toHaveProperty('disabled', false);
  });

  it('9: one start with the board’s values, exactly the example body, then /work/W-3351; a double press is one', async () => {
    await open();
    await fillBoard();
    const button = within(dialog()).getByRole('button', { name: 'Log RFP' });
    fireEvent.click(button);
    fireEvent.click(button);
    await waitFor(() => expect(nav.push).toHaveBeenCalledWith('/work/W-3351'));
    expect(starts).toHaveLength(1);
    const [sent] = starts;
    expect(sent.headers.get('X-CSRFToken')).toBe('mock-csrf-pmo_lead');
    expect(validStart(sent.body)).toBe(true);
    expect(sent.body).toEqual({
      line: 'rfp_intake',
      case_id: 'C-RFP-INTAKE',
      case_revision: 6,
      intake: {
        client: 'CL-3506',
        rfp_reference: 'TL-RFP-2026-014',
        rfp_document: 'EV-SW-C-RFP-INTAKE-1',
        received_at: iso(RECEIVED),
        submission_method: 'email',
        submission_target: 'procurement@tamarindloans.example',
        deadline_status: 'stated',
        deadline_at: iso(DEADLINE),
        note: 'Received from their procurement lead by email.',
      },
      idempotency_key: sent.body.idempotency_key,
    });
    expect(mock.started.size).toBe(1);
  });

  it('9: the upload made no new key, and opening the drawer again gives another', async () => {
    await open();
    await fillBoard();
    logPress();
    await waitFor(() => expect(starts).toHaveLength(1));
    cleanupDialog();
    mock.reset();
    await open();
    await fillBoard();
    logPress();
    await waitFor(() => expect(starts).toHaveLength(2));
    expect(starts[1].body.idempotency_key).not.toBe(starts[0].body.idempotency_key);
    expect(uploads).toHaveLength(2);
  });

  it('11: a future "Received" and a repeated reference are sent; the page checks nothing and shows the 422 as returned', async () => {
    await open();
    await fillTop();
    choose(file('a.pdf', 2048));
    await uploaded();
    text('Received', '2026-12-31T09:40');
    radio('How the client wants it submitted', 'By hand');
    radio('Submission deadline', 'Unknown');
    expect(dialog().textContent).not.toMatch(/future|already logged/);
    logPress();
    expect(await within(dialog()).findByText("Received can't be in the future.")).toBeTruthy();
    expect(within(dialog()).getByLabelText('Received').closest('[data-field]')!.textContent).toContain("Received can't be in the future.");
    expect(within(dialog()).getByText('1 thing to fix before this can start.')).toBeTruthy();
    expect((within(dialog()).getByLabelText('RFP reference') as HTMLInputElement).value).toBe('TL-RFP-2026-014');
    text('Received', RECEIVED);
    logPress();
    await waitFor(() => expect(nav.push).toHaveBeenCalledWith('/work/W-3351'));
    cleanupDialog();
    // the same reference for the same client again (a new opening, the same file)
    await open();
    await fillTop();
    choose(file('a.pdf', 2048));
    await uploaded();
    await fillRest('By hand');
    radio('Submission deadline', 'Unknown');
    logPress();
    const message = await within(dialog()).findByText('This RFP is already logged for that client.');
    expect(message.closest('[data-field]')!.getAttribute('data-field')).toBe('rfp_reference');
  });

  it('12: a stale 409 keeps the values and the card; the next press sends the re-read revision with a new key', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    await open();
    await fillBoard();
    // someone else moved the case on after this upload
    mock.handle('E-EVIDENCE-UPLOAD', {
      url: new URL('http://x/api/v1/cases/C-RFP-INTAKE/evidence'),
      raw: JSON.stringify({ kind: 'rfp_document', filename: 'o.pdf', content_base64: 'AAAA', case_revision: 6 }),
      persona: 'pmo_lead',
    });
    logPress();
    await within(dialog()).findByText(/This record changed since you opened the form/);
    expect(within(dialog()).getByText('Tamarind-Loans-RFP-loan-origination.pdf')).toBeTruthy();
    expect((within(dialog()).getByLabelText('RFP reference') as HTMLInputElement).value).toBe('TL-RFP-2026-014');
    await act(async () => {
      await vi.advanceTimersByTimeAsync(60000);
    });
    expect(starts).toHaveLength(1);
    logPress();
    await waitFor(() => expect(nav.push).toHaveBeenCalledWith('/work/W-3351'));
    expect(starts.map((s) => s.body.case_revision)).toEqual([6, 7]);
    expect(starts[1].body.idempotency_key).not.toBe(starts[0].body.idempotency_key);
    expect(starts[1].body.intake.rfp_document).toBe('EV-SW-C-RFP-INTAKE-1');
  });

  it('13: start_uncertain never says logged; Check again sends the same body and key and lands; one start is recorded', async () => {
    cookies = { psl_mock_start_work: 'start_uncertain' };
    await open();
    await fillBoard();
    logPress();
    await within(dialog()).findByRole('button', { name: 'Check again' });
    expect(within(dialog()).getByText('If it started, it will appear in My work.')).toBeTruthy();
    expect(dialog().textContent!.replace('If it started, it will appear in My work.', '').replace('if it already started', '')).not.toMatch(/logged|started/i);
    press('Check again');
    await waitFor(() => expect(nav.push).toHaveBeenCalledWith('/work/W-3351'));
    expect(starts[1].body).toEqual(starts[0].body);
    expect(mock.started.size).toBe(1);
  });

  it('13: a network failure on the start behaves the same', async () => {
    let down = true;
    override = (_, url) => {
      if (url.pathname === '/api/v1/work' && down) throw new TypeError('network');
      return undefined;
    };
    await open();
    await fillBoard();
    logPress();
    await within(dialog()).findByRole('button', { name: 'Check again' });
    expect(dialog().textContent).not.toMatch(/logged/i);
    down = false;
    press('Check again');
    await waitFor(() => expect(nav.push).toHaveBeenCalledWith('/work/W-3351'));
    expect(starts[1].body).toEqual(starts[0].body);
  });

  it('13: upload_uncertain reads "Not uploaded"; Try again re-reads the revision and the start sends only the second id', async () => {
    cookies = { psl_mock_start_work: 'upload_uncertain' };
    await open();
    await fillTop();
    choose(file('a.pdf', 4096));
    await within(documentBox()).findByText('Couldn’t upload. Try again.');
    expect(within(dialog()).queryByText(/^Uploaded/)).toBeNull();
    const reads = lineGets().length;
    press('Try again');
    await uploaded();
    expect(lineGets().length).toBe(reads + 1);
    expect(uploads.map((u) => u.body.case_revision)).toEqual([5, 6]);
    await fillRest();
    radio('Submission deadline', 'Unknown');
    logPress();
    await waitFor(() => expect(nav.push).toHaveBeenCalledWith('/work/W-3351'));
    expect([starts[0].body.case_revision, starts[0].body.intake.rfp_document]).toEqual([7, 'EV-SW-C-RFP-INTAKE-2']);
  });
});

describe('access and safety', () => {
  async function ready() {
    await fillTop();
    choose(file('a.pdf', 2048));
    await uploaded();
    await fillRest();
    radio('Submission deadline', 'Unknown');
  }

  it('14: 401 shows the signed-out state; 403 and 404 show the same refusal with no client, reference or file name', async () => {
    for (const status of [403, 404]) {
      override = (_, url) => (url.pathname === '/api/v1/work' ? json(status, { code: 'x', message: 'No.' }) : undefined);
      await open();
      await ready();
      logPress();
      expect(await within(dialog()).findByText('You can’t start this here.')).toBeTruthy();
      expect(within(dialog()).queryByText(/Tamarind Loans|TL-RFP/)).toBeTruthy(); // typed entries stay in their boxes
      const notice = within(dialog()).getByText('You can’t start this here.').closest('.psl-callout, [role]')!;
      expect(notice.textContent).not.toMatch(/Tamarind|TL-RFP|a\.pdf/);
      cleanupDialog();
      mock.reset();
    }
    override = (_, url) => (url.pathname === '/api/v1/work' ? json(401, { code: 'not_signed_in', message: 'Sign in.' }) : undefined);
    await open();
    await ready();
    logPress();
    expect(await within(dialog()).findByText('You’re signed out.')).toBeTruthy();
  });

  it('14: a 401 on the upload shows the signed-out state', async () => {
    override = (_, url) => (url.pathname.endsWith('/evidence') ? json(401, { code: 'not_signed_in', message: 'Sign in.' }) : undefined);
    await open();
    choose(file('a.pdf', 2048));
    expect(await within(dialog()).findByText('You’re signed out.')).toBeTruthy();
  });

  it('14: a start without the CSRF header is refused and shows the same refusal', async () => {
    await open();
    await ready();
    setCsrfToken('wrong');
    logPress();
    expect(await within(dialog()).findByText(/You can’t start this here|signed out/)).toBeTruthy();
    expect(nav.push).not.toHaveBeenCalled();
  });

  it('15: references, notes, file names and 422 messages are plain text; no link comes from data', async () => {
    const hostile = '<img src=x onerror=alert(1)>';
    override = (_, url) =>
      url.pathname === '/api/v1/work' ? json(422, { code: 'invalid', message: 'Bad.', fields: [{ name: 'rfp_reference', message: '<b>bold</b>' }] }) : undefined;
    await open();
    await fillTop();
    text('RFP reference', hostile);
    choose(file(`${hostile}.pdf`, 2048));
    await uploaded();
    await fillRest();
    radio('Submission deadline', 'Unknown');
    text('Note (optional)', hostile);
    logPress();
    expect(await within(dialog()).findByText('<b>bold</b>')).toBeTruthy();
    expect(document.querySelector('img, b')).toBeNull();
    expect([...dialog().querySelectorAll('a')].map((a) => a.getAttribute('href'))).toEqual([]);
    expect(starts[0].body.intake.rfp_reference).toBe(hostile);
    expect(dialog().textContent).not.toMatch(/Tola|has read|its own case|workspace/);
  });

  it('16: a line without case_revision cannot start here and sends nothing; an upload 200 without one never sends 0', async () => {
    serveLine((line) => ({ ...line, case_revision: undefined }));
    await open();
    expect(within(dialog()).getByText(/You can’t start this line from here yet\./)).toBeTruthy();
    expect(uploads.length + starts.length).toBe(0);
    cleanupDialog();

    override = (_, url) => (url.pathname.endsWith('/evidence') ? json(200, { evidence_id: 'EV-X', sha256: 'x' }) : undefined);
    await open();
    await fillTop();
    choose(file('a.pdf', 0));
    await uploaded();
    expect(within(dialog()).queryByText(/0 KB/)).toBeNull();
    await fillRest();
    radio('Submission deadline', 'Unknown');
    logPress();
    await waitFor(() => expect(starts).toHaveLength(1));
    expect(starts[0].body.case_revision).toBe(5);
  });

  it('2: other personas are not served the line, and the line is the same for the grant: none, pm, ceo, finance_lead', async () => {
    for (const who of ['pm', 'ceo', 'finance_lead', 'none']) {
      const keys = (mock.handle('E-LINES', { url: new URL('http://x/api/v1/lines'), raw: '', persona: who })[1] as Lines).items.map((l: Line) => l.key);
      expect(keys, who).not.toContain('rfp_intake');
    }
    expect(rfpLine().case_id).toBe('C-RFP-INTAKE');
  });
});
