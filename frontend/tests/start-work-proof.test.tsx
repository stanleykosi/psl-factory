// @vitest-environment jsdom
// F-47 (FE-M2A-PROOF): the Proof box in the Start work drawer, against the start-work contract mock in process.
import { readFileSync } from 'node:fs';

import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import Ajv2020 from 'ajv/dist/2020';
import addFormats from 'ajv-formats';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { setCsrfToken } from '@/api/client';
import { StartWorkButton } from '@/features/start-work/StartWorkButton';
import type { Line, Lines } from '@/features/start-work/types';

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
const uploadSchema = Object.values(openapi.paths['/api/v1/cases/{case_id}/evidence'] as Record<string, { operationId?: string; requestBody: { content: { 'application/json': { schema: object } } } }>).find(
  (op) => op?.operationId === 'E-EVIDENCE-UPLOAD',
)!.requestBody.content['application/json'].schema;
const validUpload = ajv.compile(uploadSchema);

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });

type Sent = { url: URL; headers: Headers; body: Record<string, unknown> & { intake: Record<string, unknown>; idempotency_key: string } };
type Handler = (request: Request, url: URL, body: Record<string, unknown>) => Promise<Response | undefined> | Response | undefined;

let mock: ReturnType<typeof createStartWorkMock>;
let persona: string;
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

beforeEach(() => {
  nav.push.mockReset();
  mock = createStartWorkMock(openapi);
  persona = 'pm';
  cookies = {};
  uploads = [];
  starts = [];
  gets = [];
  override = undefined;
  setCsrfToken('mock-csrf-pm');
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
      // CSRF as server.mjs checks it on the M1 path and on the start-work upload branch.
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
const startPress = (name: string) => fireEvent.click(within(dialog()).getByRole('button', { name }));
const lineGets = () => gets.filter((u) => u.pathname === '/api/v1/lines');
const optionGets = (field: string) => gets.filter((u) => u.pathname.endsWith(`/fields/${field}/options`));

const TITLES: Record<string, string> = {
  minutes: 'Formal minutes and action handoff',
  change_request: 'Controlled change and signed closure',
  income_schedules: 'Income detail or schedule inventory',
  ledger_sources: 'Record a ledger source',
};

async function openLine(line: string, as = line.startsWith('income') || line.startsWith('ledger') ? 'finance_lead' : 'pm') {
  persona = as;
  setCsrfToken(`mock-csrf-${as}`);
  render(<StartWorkButton variant="bar" />);
  fireEvent.click(screen.getByRole('button', { name: 'More ways to start' }));
  fireEvent.click(await within(dialog()).findByRole('radio', { name: new RegExp(`^${TITLES[line]}`) }));
  press('Next');
  await within(dialog()).findByRole('button', { name: 'change line' });
}

async function pick(field: string, option: string) {
  fireEvent.click(within(dialog()).getByRole('combobox', { name: field }));
  fireEvent.click(await within(dialog()).findByRole('option', { name: new RegExp(`^${option}`) }));
}

const proofBox = () => within(dialog()).getByRole('group', { name: 'Proof' });
const fileInput = () => dialog().querySelector<HTMLInputElement>('[data-field="proof"] input[type="file"]')!;
const file = (name: string, size: number) => new File([new Uint8Array(size).fill(7)], name);
const choose = (f: File) => fireEvent.change(fileInput(), { target: { files: [f] } });
/** The card's state line; for "Uploaded", also waits until the form has the id (Start no longer held). */
async function uploaded(name = /Uploaded/) {
  // the card's line; a failure's words are also in the hidden announcement (UX-1-1)
  const [found] = await within(dialog()).findAllByText(name);
  if (String(name) === String(/Uploaded/)) {
    await waitFor(() => expect(dialog().querySelector('.sw-primary')).toHaveProperty('disabled', false));
  }
  return found;
}

/** A promise the test resolves: an answer held back. */
function deferred() {
  let resolve!: (r: Response) => void;
  const promise = new Promise<Response>((r) => (resolve = r));
  return { promise, resolve };
}

async function minutesReady() {
  await openLine('minutes');
  await pick('Project', 'Lagoon Health · patient app');
  await pick('Meeting', 'Weekly sync');
  fireEvent.click(within(dialog()).getByRole('radio', { name: 'Client' }));
}

async function ledgerReady() {
  await openLine('ledger_sources');
  fireEvent.change(within(dialog()).getByRole('textbox', { name: 'Key' }), { target: { value: 'QB-JE-7741' } });
}

describe('the four drawers', () => {
  it('draw their fields, Proof box and button words from data', async () => {
    await openLine('minutes');
    const labels = () => [...dialog().querySelectorAll('[data-field]')].map((box) => box.getAttribute('data-field'));
    expect(labels()).toEqual(['project', 'meeting', 'audience', 'proof']);
    expect(within(dialog()).getByRole('button', { name: 'Start minutes' })).toBeTruthy();
    cleanupDialog();
    await openLine('change_request');
    expect(labels()).toEqual(['project', 'request', 'proof']);
    const help = within(dialog()).getByText('Emergency changes for an incident use "Emergency change" instead.');
    expect(help.closest('[data-field]')!.getAttribute('data-field')).toBe('proof');
    expect(within(dialog()).getByRole('button', { name: 'Log change' })).toBeTruthy();
    cleanupDialog();
    await openLine('income_schedules');
    expect(labels()).toEqual(['kind', 'reference', 'mapping_run', 'proof']);
    expect(within(dialog()).getAllByRole('radio').map((r) => r.closest('label, [role="radio"]')!.textContent)).toEqual(['Income detail', 'Inventory']);
    expect(within(dialog()).getByText('Mapping note')).toBeTruthy();
    expect(within(dialog()).getByRole('button', { name: 'Start schedule' })).toBeTruthy();
    cleanupDialog();
    await openLine('ledger_sources');
    expect(labels()).toEqual(['key', 'proof', 'continues']);
    expect(within(dialog()).getByText('Continues (optional)')).toBeTruthy();
    expect(within(dialog()).getByText('Only for a correction of an earlier capture')).toBeTruthy();
    expect(within(dialog()).getByRole('button', { name: 'Record source' })).toBeTruthy();
    // Proof has no "(optional)" (the boards draw none)
    expect(within(dialog()).queryByText(/Proof \(optional\)/)).toBeNull();
  });
});

function cleanupDialog() {
  fireEvent.keyDown(dialog(), { key: 'Escape' });
  document.body.innerHTML = '';
}

describe('project first', () => {
  it('minutes: the disabled box until a project is chosen, no upload; then "Choose a file"', async () => {
    await openLine('minutes');
    expect(within(proofBox()).getByText('Choose the project first.')).toBeTruthy();
    expect(within(proofBox()).queryByRole('button')).toBeNull();
    expect(fileInput()).toBeNull();
    expect(uploads).toHaveLength(0);
    await pick('Project', 'Lagoon Health · patient app');
    expect(within(proofBox()).getByRole('button', { name: 'Choose a file' })).toHaveProperty('disabled', false);
  });

  it('the schedule and ledger drawers show "Choose a file" at once', async () => {
    await openLine('income_schedules');
    expect(within(proofBox()).getByRole('button', { name: 'Choose a file' })).toHaveProperty('disabled', false);
    cleanupDialog();
    await openLine('ledger_sources');
    expect(within(proofBox()).getByRole('button', { name: 'Choose a file' })).toHaveProperty('disabled', false);
  });
});

describe('uploads', () => {
  it('one POST to the case with CSRF and the request schema; "Uploading…" until the answer, then "Uploaded · 38 KB"', async () => {
    const held = deferred();
    override = (_, url) => (url.pathname.endsWith('/evidence') ? held.promise : undefined);
    await minutesReady();
    choose(file('weekly-sync-notes-17nov.docx', 38912));
    await waitFor(() => expect(uploads).toHaveLength(1));
    const [sent] = uploads;
    expect(sent.url.pathname).toBe('/api/v1/cases/C-0101/evidence');
    expect(sent.headers.get('X-CSRFToken')).toBe('mock-csrf-pm');
    expect(Object.keys(sent.body).sort()).toEqual(['case_revision', 'content_base64', 'filename', 'kind']);
    expect(validUpload(sent.body)).toBe(true);
    expect([sent.body.kind, sent.body.filename, sent.body.case_revision]).toEqual(['meeting_notes', 'weekly-sync-notes-17nov.docx', 6]);
    expect(within(proofBox()).getByText(/Uploading…/)).toBeTruthy();
    expect(within(dialog()).getByRole('button', { name: 'Start minutes' })).toHaveProperty('disabled', true);
    await act(async () => held.resolve(json(200, { evidence_id: 'EV-SW-C-0101-1', sha256: 'x', case_revision: 7 })));
    expect((await uploaded()).textContent).toBe('Uploaded · 38 KB');
    expect(within(dialog()).getByRole('button', { name: 'Start minutes' })).toHaveProperty('disabled', false);
  });

  it('a 200 without an evidence_id reads "Not uploaded", holds Start, and no proof is sent', async () => {
    override = (_, url) => (url.pathname.endsWith('/evidence') ? json(200, { sha256: 'x', case_revision: 7 }) : undefined);
    await minutesReady();
    choose(file('notes.docx', 2048));
    expect((await uploaded(/Not uploaded/)).textContent).toContain('Not uploaded');
    expect(within(proofBox()).getByText('Couldn’t upload. Try again.')).toBeTruthy();
    expect(within(dialog()).queryByText(/^Uploaded/)).toBeNull();
    expect(within(dialog()).getByRole('button', { name: 'Start minutes' })).toHaveProperty('disabled', true);
    press('Remove notes.docx');
    startPress('Start minutes');
    await waitFor(() => expect(starts).toHaveLength(1));
    expect(starts[0].body.intake).not.toHaveProperty('proof');
  });

  it('ledger: two uploads send revision 2 then 3; the start sends 4 and the second id', async () => {
    await ledgerReady();
    choose(file('first.pdf', 1024));
    await uploaded();
    press('Remove first.pdf');
    choose(file('qb_export_je7741.pdf', 45056));
    expect((await uploaded()).textContent).toBe('Uploaded · 44 KB');
    expect(uploads.map((u) => u.body.case_revision)).toEqual([2, 3]);
    startPress('Record source');
    await waitFor(() => expect(nav.push).toHaveBeenCalledWith('/work/W-4201'));
    expect(starts).toHaveLength(1);
    expect([starts[0].body.case_revision, starts[0].body.intake]).toEqual([4, { key: 'QB-JE-7741', proof: 'EV-SW-C-FIN-LEDGER-2' }]);
  });

  it('a multiple field sends every id in upload order; a file chosen while one uploads is not sent', async () => {
    const lines = mock.handle('E-LINES', { url: new URL('http://x/api/v1/lines'), raw: '', persona: 'finance_lead' })[1] as Lines;
    const multi = { ...lines, items: lines.items.map((l: Line) => (l.key === 'ledger_sources' ? { ...l, intake: l.intake.map((f) => (f.name === 'proof' ? { ...f, multiple: true } : f)) } : l)) };
    let open!: () => void;
    const gate = new Promise<void>((r) => (open = r));
    let first = true;
    override = async (_, url) => {
      if (url.pathname === '/api/v1/lines') return json(200, multi);
      if (url.pathname.endsWith('/evidence') && first) {
        first = false;
        await gate; // the first answer is held back, then the mock answers it
      }
      return undefined;
    };
    await ledgerReady();
    choose(file('a.pdf', 1024));
    await waitFor(() => expect(uploads).toHaveLength(1));
    choose(file('b.pdf', 1024));
    await new Promise((r) => setTimeout(r, 20));
    expect(uploads).toHaveLength(1);
    await act(async () => open());
    await within(dialog()).findByText(/a\.pdf/);
    await waitFor(() => expect(within(proofBox()).getByRole('button', { name: 'Add another file' })).toHaveProperty('disabled', false));
    choose(file('c.pdf', 1024));
    await waitFor(() => expect(uploads).toHaveLength(2));
    expect(uploads[1].body.case_revision).toBe(3);
    await within(dialog()).findByRole('button', { name: 'Remove c.pdf' });
    await waitFor(() => expect(dialog().querySelector('.sw-primary')).toHaveProperty('disabled', false));
    startPress('Record source');
    await waitFor(() => expect(starts).toHaveLength(1));
    expect(starts[0].body.intake.proof).toEqual(['EV-SW-C-FIN-LEDGER-1', 'EV-SW-C-FIN-LEDGER-2']);
    expect(starts[0].body.case_revision).toBe(4);
  });
});

describe('the start', () => {
  it.each([
    ['minutes', 'W-1403'],
    ['change_request', 'W-1405'],
    ['income_schedules', 'W-4401'],
    ['ledger_sources', 'W-4201'],
  ])('%s: filled as on the board, one start for a double press, with the key made when the drawer opened', async (line, workId) => {
    const keys: string[] = [];
    const real = crypto.randomUUID.bind(crypto);
    vi.spyOn(crypto, 'randomUUID').mockImplementation(() => {
      const k = real();
      keys.push(k);
      return k;
    });
    if (line === 'minutes') await minutesReady();
    else await openLine(line);
    if (line === 'change_request') {
      await pick('Project', 'Lagoon Health · patient app');
      fireEvent.change(within(dialog()).getByRole('textbox', { name: 'What the client asked for' }), { target: { value: 'Add WhatsApp reminders as well as SMS' } });
    }
    if (line === 'income_schedules') {
      fireEvent.click(within(dialog()).getByRole('radio', { name: 'Income detail' }));
      fireEvent.change(within(dialog()).getByRole('textbox', { name: 'Reference' }), { target: { value: 'SCH-INC-2026-10' } });
      await pick('Mapping note', 'Mapping run MR-0044');
    }
    if (line === 'ledger_sources') fireEvent.change(within(dialog()).getByRole('textbox', { name: 'Key' }), { target: { value: 'QB-JE-7741' } });
    const keysAtOpen = keys.length;
    choose(file('proof.pdf', 20480));
    await uploaded();
    expect(keys).toHaveLength(keysAtOpen);
    const button = within(dialog()).getAllByRole('button').find((b) => b.className.includes('psl-btn--start'))!;
    fireEvent.click(button);
    fireEvent.click(button);
    await waitFor(() => expect(nav.push).toHaveBeenCalledWith(`/work/${workId}`));
    expect(starts).toHaveLength(1);
    expect(starts[0].body.idempotency_key).toBe(keys[keysAtOpen - 1]);
    expect(starts[0].body.intake.proof).toMatch(/^EV-SW-/);
  });

  it('held while uploading and while failed; removing the failed file, or a good Try again, frees it', async () => {
    let fail = true;
    override = (_, url) => {
      if (url.pathname.endsWith('/evidence') && fail) return json(500, { code: 'server', message: 'Down.' });
      return undefined;
    };
    await ledgerReady();
    choose(file('x.pdf', 1024));
    await uploaded(/Not uploaded/);
    const start = () => within(dialog()).getByRole('button', { name: 'Record source' });
    expect(start()).toHaveProperty('disabled', true);
    fireEvent.click(start());
    expect(starts).toHaveLength(0);
    fail = false;
    press('Try again');
    await uploaded();
    expect(start()).toHaveProperty('disabled', false);
  });

  it('"×" removes the card, sends nothing, and the start leaves that id out; nothing says deleted', async () => {
    await minutesReady();
    choose(file('weekly-sync-notes-17nov.docx', 38912));
    await uploaded();
    const before = uploads.length + starts.length + gets.length;
    press('Remove weekly-sync-notes-17nov.docx');
    expect(uploads.length + starts.length + gets.length).toBe(before);
    expect(within(dialog()).queryByText('weekly-sync-notes-17nov.docx')).toBeNull();
    expect(dialog().textContent).not.toMatch(/deleted|removed from the record/i);
    startPress('Start minutes');
    await waitFor(() => expect(starts).toHaveLength(1));
    expect(starts[0].body.intake).toEqual({ project: 'P-0101', meeting: 'MTG-0417', audience: 'client' });
  });

  it('changing the project drops the proof with a line, and the next upload goes to the new case (ceo)', async () => {
    const held = deferred();
    let hold = true;
    override = (_, url) => {
      if (url.pathname.endsWith('/evidence') && hold) {
        hold = false;
        return held.promise;
      }
      return undefined;
    };
    await openLine('minutes', 'ceo');
    await pick('Project', 'Lagoon Health · patient app');
    choose(file('lagoon.docx', 1024));
    await waitFor(() => expect(uploads).toHaveLength(1));
    expect(within(dialog()).getByRole('combobox', { name: 'Project' })).toHaveProperty('disabled', true);
    await act(async () => held.resolve(json(200, { evidence_id: 'EV-SW-C-0101-1', sha256: 'x', case_revision: 7 })));
    await uploaded();
    await pick('Project', 'Harmattan Bank · mobile onboarding');
    expect(within(dialog()).queryByText('lagoon.docx')).toBeNull();
    expect(within(dialog()).getByRole('status').textContent).toBe('Proof removed: it was added to the other project. Add it again.');
    choose(file('harmattan.docx', 1024));
    await uploaded();
    expect([uploads[1].url.pathname, uploads[1].body.case_revision]).toEqual(['/api/v1/cases/C-0102/evidence', 3]);
    // the mock serves no Harmattan meeting, so one and the start's answer are stubbed: only what is sent matters here
    override = (_, url) => {
      if (url.pathname.endsWith('/fields/meeting/options')) return json(200, { items: [{ value: 'MTG-0999', label: 'Harmattan sync' }] });
      return url.pathname === '/api/v1/work' ? json(201, { work_id: 'W-1403', state: 'processing' }) : undefined;
    };
    await pick('Meeting', 'Harmattan sync');
    fireEvent.click(within(dialog()).getByRole('radio', { name: 'Internal' }));
    startPress('Start minutes');
    await waitFor(() => expect(starts).toHaveLength(1));
    expect([starts[0].body.case_id, starts[0].body.case_revision, starts[0].body.intake.proof]).toEqual(['C-0102', 4, 'EV-SW-C-0102-1']);
  });
});

describe('F-49 QA-2-1 (shared): required fields left empty send nothing', () => {
  it('income schedules: each empty required field is named, focus goes to the first, nothing is sent', async () => {
    await openLine('income_schedules');
    startPress('Start schedule');
    for (const label of ['Kind', 'Reference', 'Mapping note', 'Proof']) expect(await within(dialog()).findByText(`${label} is required.`)).toBeTruthy();
    expect(starts).toHaveLength(0);
    expect(dialog().querySelector('[data-field="kind"]')!.contains(document.activeElement)).toBe(true);
  });

  it('minutes (project first): the start stays off until a project is chosen; with one, the other empty fields are named and nothing is sent', async () => {
    await openLine('minutes');
    expect((within(dialog()).getByRole('button', { name: 'Start minutes' }) as HTMLButtonElement).disabled).toBe(true);
    await pick('Project', 'Lagoon Health · patient app');
    startPress('Start minutes');
    for (const label of ['Meeting', 'Audience']) expect(await within(dialog()).findByText(`${label} is required.`)).toBeTruthy();
    expect(within(dialog()).queryByText('Proof is required.')).toBeNull();
    expect(starts).toHaveLength(0);
  });
});

describe('round 2: announced, linked, and no upload to a dropped case', () => {
  it('UX-1-1: each upload failure is announced with its words (role="alert"), and nothing is announced once it is fixed', async () => {
    let mode: 'exe' | 'down' | 'stale' | 'noid' | 'ok' = 'exe';
    override = (_, url) => {
      if (!url.pathname.endsWith('/evidence')) return undefined;
      if (mode === 'down') return json(500, { code: 'server', message: 'Down.' });
      if (mode === 'stale') return json(409, { code: 'stale_revision', message: 'Changed.' });
      if (mode === 'noid') return json(200, { sha256: 'x', case_revision: 3 });
      return undefined;
    };
    await ledgerReady();
    const alerts = () => within(dialog()).queryAllByRole('alert').map((a) => a.textContent);
    choose(file('setup.exe', 1024));
    await waitFor(() => expect(alerts()).toContain("setup.exe: Not uploaded. EXE files can't be used as proof."));
    press('Remove setup.exe');
    expect(alerts()).toEqual([]);
    for (const [now, words] of [
      ['down', 'Couldn’t upload. Try again.'],
      ['stale', 'This item changed. Add the file again.'],
      ['noid', 'Couldn’t upload. Try again.'],
    ] as const) {
      mode = now;
      choose(file(`${now}.pdf`, 1024));
      await waitFor(() => expect(alerts()).toContain(`${now}.pdf: Not uploaded. ${words}`));
      press(`Remove ${now}.pdf`);
    }
    mode = 'ok';
    choose(file('good.pdf', 1024));
    await uploaded();
    expect(alerts()).toEqual([]);
  });

  it('TECH-1-3: a 422 for Proof describes the Proof box (aria-describedby) and marks it invalid', async () => {
    override = (_, url) => (url.pathname.endsWith('/evidence') ? json(200, { evidence_id: 'EV-ELSEWHERE', sha256: 'x', case_revision: 2 }) : undefined);
    await ledgerReady();
    const box = () => dialog().querySelector<HTMLElement>('[data-field="proof"]')!;
    expect(box().getAttribute('aria-describedby')).toBeNull();
    choose(file('qb.pdf', 1024));
    await uploaded();
    startPress('Record source');
    const message = await within(dialog()).findByText("That proof isn't on this record. Add it again.");
    const error = message.closest('.psl-error')!;
    expect(box().getAttribute('aria-describedby')).toBe(error.id);
    expect(box().getAttribute('aria-invalid')).toBe('true');
  });

  it('TECH-1-1: Try again sends nothing once the fixed case is no longer served', async () => {
    let gone = false;
    override = (_, url) => {
      if (url.pathname.endsWith('/evidence')) return json(500, { code: 'server', message: 'Down.' });
      if (url.pathname === '/api/v1/lines' && gone) {
        const lines = mock.handle('E-LINES', { url, raw: '', persona: 'finance_lead' })[1] as Lines;
        return json(200, { ...lines, items: lines.items.filter((l: Line) => l.key !== 'ledger_sources') });
      }
      return undefined;
    };
    await ledgerReady();
    choose(file('qb.pdf', 1024));
    await within(proofBox()).findByText('Couldn’t upload. Try again.');
    gone = true;
    press('Try again');
    expect(await within(dialog()).findByText('You can’t add proof to this item.')).toBeTruthy();
    await new Promise((r) => setTimeout(r, 50));
    expect(uploads).toHaveLength(1);
    expect(within(dialog()).queryByText('qb.pdf')).toBeNull();
  });

  it('TECH-1-1: Try again sends nothing once the chosen project is no longer served (the project is cleared with a note)', async () => {
    let gone = false;
    override = (_, url) => {
      if (url.pathname.endsWith('/evidence')) return json(500, { code: 'server', message: 'Down.' });
      if (url.pathname.endsWith('/fields/project/options') && gone) return json(200, { items: [], as_of: '2026-11-14T09:00:00Z' });
      return undefined;
    };
    await minutesReady();
    choose(file('notes.docx', 1024));
    await within(proofBox()).findByText('Couldn’t upload. Try again.');
    gone = true;
    press('Try again');
    expect(await within(dialog()).findByText('That choice is no longer available. Choose again.')).toBeTruthy();
    await new Promise((r) => setTimeout(r, 50));
    expect(uploads).toHaveLength(1);
    expect(within(proofBox()).getByText('Choose the project first.')).toBeTruthy();
  });
});

describe('upload errors', () => {
  it('403 and 404 read the same: "You can’t add proof to this item.", the file is not kept', async () => {
    const texts: string[] = [];
    for (const status of [403, 404]) {
      override = (_, url) => (url.pathname.endsWith('/evidence') ? json(status, { code: status === 403 ? 'forbidden' : 'not_found', message: `m${status}` }) : undefined);
      await ledgerReady();
      choose(file('x.pdf', 1024));
      await within(dialog()).findByText('You can’t add proof to this item.');
      await waitFor(() => expect(within(dialog()).queryByText('x.pdf')).toBeNull());
      expect(within(dialog()).queryByText(/Uploaded/)).toBeNull();
      texts.push(dialog().textContent!);
      cleanupDialog();
    }
    expect(texts[0]).toBe(texts[1]);
  });

  it('401 shows the signed-out state with next set to this page', async () => {
    override = (_, url) => (url.pathname.endsWith('/evidence') ? json(401, { code: 'not_signed_in', message: 'Sign in.' }) : undefined);
    await ledgerReady();
    choose(file('x.pdf', 1024));
    expect(await within(dialog()).findByText('You’re signed out.')).toBeTruthy();
    expect(within(dialog()).getByRole('link', { name: 'Sign in' }).getAttribute('href')).toBe('/accounts/login/?next=%2Fmy-work');
  });

  it('422 shows the backend message word for word: the mock’s .exe sample and another message as text', async () => {
    await ledgerReady();
    choose(file('setup.exe', 1024));
    expect(await within(proofBox()).findByText("EXE files can't be used as proof.")).toBeTruthy();
    press('Remove setup.exe');
    override = (_, url) => (url.pathname.endsWith('/evidence') ? json(422, { code: 'invalid', message: 'Files over 20 MB <b>bold</b> are refused.' }) : undefined);
    choose(file('big.pdf', 1024));
    expect(await within(proofBox()).findByText('Files over 20 MB <b>bold</b> are refused.')).toBeTruthy();
    expect(dialog().querySelector('b')).toBeNull();
  });

  it('409 on a fixed line re-reads E-LINES, keeps the values, and the next upload sends the re-read revision', async () => {
    let stale = true;
    override = (_, url) => {
      if (url.pathname.endsWith('/evidence') && stale) {
        stale = false;
        return json(409, { code: 'stale_revision', message: 'Changed.' });
      }
      return undefined;
    };
    await ledgerReady();
    const before = lineGets().length;
    // someone else moved the case on
    mock.handle('E-EVIDENCE-UPLOAD', { url: new URL('http://x/api/v1/cases/C-FIN-LEDGER/evidence'), raw: JSON.stringify({ kind: 'ledger_source', filename: 'o.pdf', content_base64: 'AAAA', case_revision: 2 }), persona: 'finance_lead' });
    choose(file('x.pdf', 1024));
    expect(await within(proofBox()).findByText('This item changed. Add the file again.')).toBeTruthy();
    expect(lineGets().length).toBe(before + 1);
    expect(within(dialog()).getByRole('textbox', { name: 'Key' })).toHaveProperty('value', 'QB-JE-7741');
    press('Remove x.pdf');
    choose(file('y.pdf', 1024));
    await uploaded();
    expect(uploads.map((u) => u.body.case_revision)).toEqual([2, 3]);
  });

  it('409 on a project line re-reads E-LINE-OPTIONS', async () => {
    let stale = true;
    override = (_, url) => {
      if (url.pathname.endsWith('/evidence') && stale) {
        stale = false;
        return json(409, { code: 'stale_revision', message: 'Changed.' });
      }
      return undefined;
    };
    await minutesReady();
    const before = optionGets('project').length;
    choose(file('x.docx', 1024));
    await within(proofBox()).findByText('This item changed. Add the file again.');
    expect(optionGets('project').length).toBe(before + 1);
    expect(within(dialog()).getByRole('radio', { name: 'Client' }).getAttribute('aria-checked') ?? 'true').toBeTruthy();
  });

  it('500 or a network failure: "Couldn’t upload. Try again."; nothing resends by itself; Try again re-reads first, then one upload', async () => {
    let mode: 'down' | 'net' | 'ok' = 'down';
    override = (_, url) => {
      if (!url.pathname.endsWith('/evidence')) return undefined;
      if (mode === 'down') return json(500, { code: 'server', message: 'Down.' });
      if (mode === 'net') throw new TypeError('network');
      return undefined;
    };
    await ledgerReady();
    choose(file('x.pdf', 1024));
    await within(proofBox()).findByText('Couldn’t upload. Try again.');
    await act(async () => {
      await new Promise((r) => setTimeout(r, 200));
    });
    expect(uploads).toHaveLength(1);
    mode = 'net';
    const lines = lineGets().length;
    press('Try again');
    await waitFor(() => expect(uploads).toHaveLength(2));
    expect(lineGets().length).toBe(lines + 1);
    await within(proofBox()).findByText('Couldn’t upload. Try again.');
    mode = 'ok';
    press('Try again');
    await uploaded();
    expect(uploads).toHaveLength(3);
  });

  it('no second upload after 60 s without a press', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    override = (_, url) => (url.pathname.endsWith('/evidence') ? json(500, { code: 'server', message: 'Down.' }) : undefined);
    await ledgerReady();
    choose(file('x.pdf', 1024));
    await within(proofBox()).findByText('Couldn’t upload. Try again.');
    await act(async () => {
      await vi.advanceTimersByTimeAsync(60000);
    });
    expect(uploads).toHaveLength(1);
  });

  it('upload_uncertain: "Not uploaded", Try again re-reads and gets a second id; the start sends only it', async () => {
    cookies = { psl_mock_start_work: 'upload_uncertain' };
    await ledgerReady();
    choose(file('qb_export_je7741.pdf', 45056));
    await within(proofBox()).findByText('Couldn’t upload. Try again.');
    expect(within(dialog()).queryByText(/^Uploaded/)).toBeNull();
    press('Try again');
    await uploaded();
    expect(uploads.map((u) => u.body.case_revision)).toEqual([2, 3]);
    startPress('Record source');
    await waitFor(() => expect(nav.push).toHaveBeenCalledWith('/work/W-4201'));
    expect([starts[0].body.case_revision, starts[0].body.intake.proof]).toEqual([4, 'EV-SW-C-FIN-LEDGER-2']);
  });
});

describe('start errors with proof', () => {
  it('a stale 409 keeps the card, re-reads the revision, and the next press sends it with a new key', async () => {
    await ledgerReady();
    choose(file('qb.pdf', 1024));
    await uploaded();
    // someone else moved the case on after this upload
    mock.handle('E-EVIDENCE-UPLOAD', { url: new URL('http://x/api/v1/cases/C-FIN-LEDGER/evidence'), raw: JSON.stringify({ kind: 'ledger_source', filename: 'o.pdf', content_base64: 'AAAA', case_revision: 3 }), persona: 'finance_lead' });
    startPress('Record source');
    await within(dialog()).findByText(/This record changed since you opened the form/);
    expect(within(dialog()).getByText('qb.pdf')).toBeTruthy();
    startPress('Record source');
    await waitFor(() => expect(nav.push).toHaveBeenCalledWith('/work/W-4201'));
    expect(starts.map((s) => s.body.case_revision)).toEqual([3, 4]);
    expect(starts[1].body.idempotency_key).not.toBe(starts[0].body.idempotency_key);
    expect(starts[1].body.intake.proof).toBe('EV-SW-C-FIN-LEDGER-1');
  });

  it('start_uncertain: "Check again" and the My work line, never "started"; Check again sends the same body and key and lands', async () => {
    cookies = { psl_mock_start_work: 'start_uncertain' };
    await ledgerReady();
    choose(file('qb.pdf', 1024));
    await uploaded();
    startPress('Record source');
    await within(dialog()).findByRole('button', { name: 'Check again' });
    expect(within(dialog()).getByText('If it started, it will appear in My work.')).toBeTruthy();
    expect(dialog().textContent!.replace('If it started, it will appear in My work.', '').replace('if it already started', '')).not.toMatch(/started/i);
    expect(within(proofBox()).getByRole('button', { name: 'Remove qb.pdf' }).matches(':disabled')).toBe(true);
    press('Check again');
    await waitFor(() => expect(nav.push).toHaveBeenCalledWith('/work/W-4201'));
    expect(starts[1].body).toEqual(starts[0].body);
    expect(mock.started.size).toBe(1);
  });

  it('a proof id not on this record: the 422 sits under the Proof box, not as its own box', async () => {
    override = (_, url) => (url.pathname.endsWith('/evidence') ? json(200, { evidence_id: 'EV-ELSEWHERE', sha256: 'x', case_revision: 2 }) : undefined);
    await ledgerReady();
    choose(file('qb.pdf', 1024));
    await uploaded();
    startPress('Record source');
    const message = await within(dialog()).findByText("That proof isn't on this record. Add it again.");
    expect(message.closest('[data-field]')!.getAttribute('data-field')).toBe('proof');
    expect(dialog().querySelectorAll('[data-field="proof"]')).toHaveLength(1);
  });

  it('403 and 404 on the start read "You can’t start this here."; 401 shows signed out', async () => {
    for (const status of [403, 404]) {
      override = (_, url) => (url.pathname === '/api/v1/work' ? json(status, { code: 'x', message: 'No.' }) : undefined);
      await ledgerReady();
      choose(file('qb.pdf', 1024));
      await uploaded();
      startPress('Record source');
      expect(await within(dialog()).findByText('You can’t start this here.')).toBeTruthy();
      cleanupDialog();
      mock.reset();
    }
    override = (_, url) => (url.pathname === '/api/v1/work' ? json(401, { code: 'not_signed_in', message: 'Sign in.' }) : undefined);
    await ledgerReady();
    choose(file('qb.pdf', 1024));
    await uploaded();
    startPress('Record source');
    expect(await within(dialog()).findByText('You’re signed out.')).toBeTruthy();
  });
});

describe('access and safety', () => {
  it('persona none gets no lines and no Proof box', async () => {
    persona = 'none';
    setCsrfToken('mock-csrf-none');
    render(<StartWorkButton variant="bar" />);
    fireEvent.click(screen.getByRole('button', { name: 'More ways to start' }));
    await waitFor(() => expect(lineGets()).toHaveLength(1));
    await waitFor(() => expect(screen.queryByRole('status')).toBeNull());
    expect(within(dialog()).queryAllByRole('radio')).toHaveLength(0);
    expect(within(dialog()).queryByRole('group', { name: 'Proof' })).toBeNull();
  });

  it('an upload without the right CSRF answers 403 csrf_failed: the generic try-again notice shows (csrf is its own kind, not no-permission) and nothing reads "Uploaded"', async () => {
    await ledgerReady();
    setCsrfToken('wrong');
    choose(file('qb.pdf', 1024));
    expect(await within(dialog()).findByText('Couldn’t upload. Try again.')).toBeTruthy();
    expect(within(dialog()).queryByText(/Uploaded/)).toBeNull();
  });

  it('file names and messages are plain text; no link comes from data; the file input has no accept', async () => {
    await ledgerReady();
    expect(fileInput().hasAttribute('accept')).toBe(false);
    expect(fileInput().hasAttribute('capture')).toBe(false);
    choose(file('<img src=x onerror=alert(1)>.pdf', 1024));
    expect(await within(dialog()).findByText('<img src=x onerror=alert(1)>.pdf')).toBeTruthy();
    await uploaded();
    expect(document.querySelector('img')).toBeNull();
    expect([...dialog().querySelectorAll('a')].map((a) => a.getAttribute('href'))).toEqual([]);
  });

  it('a fixed line without case_revision cannot start here and sends nothing', async () => {
    const lines = mock.handle('E-LINES', { url: new URL('http://x/api/v1/lines'), raw: '', persona: 'finance_lead' })[1] as Lines;
    const noRevision = { ...lines, items: lines.items.map((l: Line) => (l.key === 'ledger_sources' ? { ...l, case_revision: undefined } : l)) };
    override = (_, url) => (url.pathname === '/api/v1/lines' ? json(200, noRevision) : undefined);
    await openLine('ledger_sources');
    expect(within(dialog()).getByText(/You can’t start this line from here yet\./)).toBeTruthy();
    expect(within(dialog()).queryByRole('group', { name: 'Proof' })).toBeNull();
    expect(uploads.length + starts.length).toBe(0);
  });

  it('an upload 200 without case_revision: the start sends the last known revision, never 0 or blank', async () => {
    override = (_, url) => (url.pathname.endsWith('/evidence') ? json(200, { evidence_id: 'EV-X', sha256: 'x' }) : url.pathname === '/api/v1/work' ? json(201, { work_id: 'W-4402', state: 'processing' }) : undefined);
    await ledgerReady();
    choose(file('qb.pdf', 0));
    await uploaded();
    expect(within(dialog()).queryByText(/0 KB/)).toBeNull();
    startPress('Record source');
    await waitFor(() => expect(starts).toHaveLength(1));
    expect(starts[0].body.case_revision).toBe(2);
  });

  it('the same lines file draws the same Proof box for pm, ceo and finance_lead', async () => {
    const lines = mock.handle('E-LINES', { url: new URL('http://x/api/v1/lines'), raw: '', persona: 'finance_lead' })[1] as Lines;
    override = (_, url) => (url.pathname === '/api/v1/lines' ? json(200, lines) : undefined);
    const boxes: string[] = [];
    for (const who of ['pm', 'ceo', 'finance_lead']) {
      await openLine('ledger_sources', who);
      boxes.push(proofBox().outerHTML.replace(/_r_[^"]*_|:r[0-9a-z]+:|«r[0-9a-z]+»/g, ''));
      cleanupDialog();
    }
    expect(new Set(boxes).size).toBe(1);
  });
});
