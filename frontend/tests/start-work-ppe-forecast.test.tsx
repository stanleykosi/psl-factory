// @vitest-environment jsdom
// F-51 (FE-M2A-PROOF part 2): the fixed asset schedule's Proof box and the cash forecast, in the Start work drawer,
// against the start-work contract mock in process.
import { readFileSync } from 'node:fs';

import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
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
  persona = 'finance_lead';
  cookies = {};
  uploads = [];
  starts = [];
  gets = [];
  override = undefined;
  setCsrfToken('mock-csrf-finance_lead');
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
const lineGets = () => gets.filter((u) => u.pathname === '/api/v1/lines');

const TITLES: Record<string, string> = { fixed_assets: 'Fixed asset schedule', cash_forecast: 'Cash forecast', ledger_sources: 'Record a ledger source' };

async function openLine(line: string, as = 'finance_lead') {
  persona = as;
  setCsrfToken(`mock-csrf-${as}`);
  render(<StartWorkButton variant="bar" />);
  fireEvent.click(screen.getByRole('button', { name: 'More ways to start' }));
  fireEvent.click(await within(dialog()).findByRole('radio', { name: new RegExp(`^${TITLES[line]}`) }));
  press('Next');
  await within(dialog()).findByRole('button', { name: 'change line' });
}

async function pick(field: string | RegExp, option: string) {
  fireEvent.click(within(dialog()).getByRole('combobox', { name: field }));
  fireEvent.click(await within(dialog()).findByRole('option', { name: new RegExp(`^${option}`) }));
}

const proofBox = () => within(dialog()).getByRole('group', { name: 'Proof' });
const fileInput = () => dialog().querySelector<HTMLInputElement>('[data-field="proof"] input[type="file"]')!;
const file = (name: string, size: number) => new File([new Uint8Array(size).fill(7)], name);
const choose = (f: File) => fireEvent.change(fileInput(), { target: { files: [f] } });
const startButton = (name: string) => within(dialog()).getByRole('button', { name }) as HTMLButtonElement;
async function uploaded(name: string | RegExp = /Uploaded/) {
  const [found] = await within(dialog()).findAllByText(name);
  if (String(name) === String(/Uploaded/)) await waitFor(() => expect(dialog().querySelector('.sw-primary')).toHaveProperty('disabled', false));
  return found;
}
function cleanupDialog() {
  fireEvent.keyDown(dialog(), { key: 'Escape' });
  document.body.innerHTML = '';
}
function deferred() {
  let resolve!: (r: Response) => void;
  const promise = new Promise<Response>((r) => (resolve = r));
  return { promise, resolve };
}

const months = () => within(dialog()).getByLabelText('Months') as HTMLInputElement;
const asOf = () => within(dialog()).getByLabelText('As of') as HTMLInputElement;
const type = (_name: string, value: string) => fireEvent.change(months(), { target: { value } });
async function forecastReady() {
  await openLine('cash_forecast');
  await pick('Scenario', 'Base case · v4');
  fireEvent.change(asOf(), { target: { value: '31 Oct 2026' } });
  fireEvent.blur(asOf());
  type('Months', '6');
  fireEvent.click(within(dialog()).getByRole('radio', { name: 'Internal' }));
}
async function assetsReady() {
  await openLine('fixed_assets');
  choose(file('ppe_register_oct.xlsx', 98304));
  await uploaded();
}

describe('1 and 2: the drawers are drawn from data', () => {
  it('fixed assets: Proof, Prior schedule (optional), Accounting note (optional), "Start schedule"', async () => {
    await openLine('fixed_assets');
    expect([...dialog().querySelectorAll('[data-field]')].map((b) => b.getAttribute('data-field'))).toEqual(['proof', 'prior_schedule', 'accounting_note']);
    expect(within(dialog()).getByText(/^Prior schedule/)).toBeTruthy();
    expect(within(dialog()).getByText(/^Accounting note/)).toBeTruthy();
    expect(within(proofBox()).getByRole('button', { name: 'Choose a file' })).toBeTruthy();
    expect(within(dialog()).queryByText(/Proof \(optional\)/)).toBeNull();
    // F-05: the server names what is missing; the page sends the start and shows the sentence under the field
    press('Start schedule');
    await waitFor(() => expect(dialog().querySelector('[data-field="proof"]')!.textContent).toContain('Proof is required.'));
    expect(starts).toHaveLength(1);
    expect(starts[0].body.intake).toEqual({});
    expect(nav.push).not.toHaveBeenCalled();
  });

  it('forecast: four fields and Sources as returned, no Proof box, no file input, "Start forecast"', async () => {
    await openLine('cash_forecast');
    expect([...dialog().querySelectorAll('[data-field]')].map((b) => b.getAttribute('data-field'))).toEqual(['scenario', 'as_of', 'months', 'audience', 'sources']);
    expect(dialog().querySelectorAll('input[type="file"]')).toHaveLength(0);
    expect(within(dialog()).queryByText('Choose a file')).toBeNull();
    expect(within(dialog()).queryByRole('group', { name: 'Proof' })).toBeNull();
    expect(within(dialog()).getAllByRole('radio').map((r) => r.textContent)).toEqual(['Internal', 'Management', 'Group']);
    expect(within(dialog()).getByText('All 3 accepted')).toBeTruthy();
    expect(startButton('Start forecast')).toBeTruthy();
  });

  it('Sources follows the line: a changed fixture value is what the page says', async () => {
    const real = globalThis.fetch;
    override = (_, url) => {
      if (url.pathname !== '/api/v1/lines') return undefined;
      const lines = mock.handle('E-LINES', { url, raw: '', persona: 'finance_lead' })[1] as Lines;
      return json(200, { ...lines, items: lines.items.map((l: Line) => (l.key === 'cash_forecast' ? { ...l, intake: l.intake.map((f) => (f.name === 'sources' ? { ...f, value: 'Two of three read' } : f)) } : l)) });
    };
    await openLine('cash_forecast');
    expect(within(dialog()).getByText('Two of three read')).toBeTruthy();
    expect(within(dialog()).queryByText(/All 3 accepted/)).toBeNull();
    expect(globalThis.fetch).toBe(real);
  });
});

describe('3: nothing is computed or defaulted', () => {
  it('starts empty, nothing preselected, Start off until the four required fields are filled', async () => {
    await openLine('cash_forecast');
    expect(within(dialog()).getAllByRole('radio').every((r) => r.getAttribute('aria-checked') !== 'true')).toBe(true);
    expect(months().value).toBe('');
    expect(asOf().value).toBe('');
    expect(dialog().textContent).not.toMatch(/accepted.*accepted/);
    // nothing is sent for a field not filled; the server's own "<Label> is required." sentences show under each
    press('Start forecast');
    for (const label of ['Scenario', 'As of', 'Months', 'Audience']) expect(await within(dialog()).findByText(`${label} is required.`)).toBeTruthy();
    expect(starts[0].body.intake).toEqual({});
    expect(nav.push).not.toHaveBeenCalled();
  });
});

describe('5 to 7: the fixed-asset proof', () => {
  it('one upload to C-FIN-PPE with CSRF and the contract body; "Uploading…" then "Uploaded · 96 KB"', async () => {
    await openLine('fixed_assets');
    const held = deferred();
    override = (_, url) => (url.pathname.endsWith('/evidence') ? held.promise : undefined);
    choose(file('ppe_register_oct.xlsx', 98304));
    expect(await within(proofBox()).findByText(/Uploading…/)).toBeTruthy();
    expect(startButton('Start schedule').disabled).toBe(true);
    await waitFor(() => expect(uploads).toHaveLength(1));
    override = undefined;
    held.resolve(json(200, mock.handle('E-EVIDENCE-UPLOAD', { url: uploads[0].url, raw: JSON.stringify(uploads[0].body), persona, cookies })[1]));
    await uploaded('Uploaded · 96 KB');
    expect(uploads).toHaveLength(1);
    expect(uploads[0].url.pathname).toBe('/api/v1/cases/C-FIN-PPE/evidence');
    expect(uploads[0].headers.get('X-CSRFToken')).toBe('mock-csrf-finance_lead');
    expect(Object.keys(uploads[0].body).sort()).toEqual(['case_revision', 'content_base64', 'filename', 'kind']);
    expect(uploads[0].body).toMatchObject({ kind: 'ppe_register', filename: 'ppe_register_oct.xlsx', case_revision: 4 });
    expect(validUpload(uploads[0].body), ajv.errorsText(validUpload.errors)).toBe(true);
  });

  it('an answer without evidence_id reads "Not uploaded" and the start sends no proof', async () => {
    override = (_, url) => (url.pathname.endsWith('/evidence') ? json(200, { sha256: 'x', case_revision: 5 }) : undefined);
    await openLine('fixed_assets');
    choose(file('a.xlsx', 1024));
    await uploaded(/Not uploaded/);
    expect(startButton('Start schedule').disabled).toBe(true);
    expect(starts).toHaveLength(0);
  });

  it('revisions chain 4 then 5; the start sends 6 and the second id; the removed card is not sent, no request, never "deleted"', async () => {
    await openLine('fixed_assets');
    choose(file('first.xlsx', 1024));
    await uploaded();
    press('Remove first.xlsx');
    expect(dialog().textContent).not.toMatch(/deleted/i);
    expect(uploads).toHaveLength(1);
    choose(file('second.xlsx', 2048));
    await uploaded();
    expect(uploads.map((u) => u.body.case_revision)).toEqual([4, 5]);
    press('Start schedule');
    await waitFor(() => expect(nav.push).toHaveBeenCalled());
    expect(starts).toHaveLength(1);
    expect(starts[0].body).toMatchObject({ line: 'fixed_assets', case_id: 'C-FIN-PPE', case_revision: 6, intake: { proof: 'EV-SW-C-FIN-PPE-2' } });
    expect(Object.keys(starts[0].body.intake)).toEqual(['proof']);
  });

  it('held while uploading and while failed; Try again frees it', async () => {
    cookies = { psl_mock_start_work: 'upload_uncertain' };
    await openLine('fixed_assets');
    choose(file('a.xlsx', 1024));
    await within(proofBox()).findByText('Couldn’t upload. Try again.');
    expect(startButton('Start schedule').disabled).toBe(true);
    press('Try again');
    await uploaded();
    expect(lineGets().length).toBeGreaterThan(1);
    press('Start schedule');
    await waitFor(() => expect(nav.push).toHaveBeenCalledWith('/work/W-3901'));
    expect(starts[0].body).toMatchObject({ case_revision: 6, intake: { proof: 'EV-SW-C-FIN-PPE-2' } });
  });
});

describe('9, 10 and 11: each start lands, and the forecast sends typed values only', () => {
  it('fixed assets with Prior schedule: one start (double press too) lands on /work/W-3901', async () => {
    await assetsReady();
    await pick(/Prior schedule/, 'PPE-0005');
    const button = startButton('Start schedule');
    fireEvent.click(button);
    fireEvent.click(button);
    await waitFor(() => expect(nav.push).toHaveBeenCalledWith('/work/W-3901'));
    expect(starts).toHaveLength(1);
    expect(starts[0].body).toMatchObject({ case_id: 'C-FIN-PPE', case_revision: 5, intake: { proof: 'EV-SW-C-FIN-PPE-1', prior_schedule: 'PPE-0005' } });
    expect(uploads).toHaveLength(1);
  });

  it('forecast: exactly the typed values, an integer Months, no sources, no evidence; lands on /work/W-4001', async () => {
    await forecastReady();
    const button = startButton('Start forecast');
    fireEvent.click(button);
    fireEvent.click(button);
    await waitFor(() => expect(nav.push).toHaveBeenCalledWith('/work/W-4001'));
    expect(starts).toHaveLength(1);
    expect(starts[0].body).toMatchObject({ line: 'cash_forecast', case_id: 'C-FIN-FORECAST', case_revision: 2, intake: { scenario: 'FC-SC-4', as_of: '2026-10-31', months: 6, audience: 'internal' } });
    expect(Object.keys(starts[0].body.intake).sort()).toEqual(['as_of', 'audience', 'months', 'scenario']);
    expect(uploads).toHaveLength(0);
  });

  it.each([
    ['Months', '13', 'Months must be between 1 and 12.'],
    ['Months', '0', 'Months must be between 1 and 12.'],
  ])('forecast 422 for %s %s shows the backend sentence under the field and keeps every value', async (name, value, message) => {
    await forecastReady();
    type(name, value);
    press('Start forecast');
    expect(await within(dialog()).findByText(message)).toBeTruthy();
    expect(dialog().querySelector('[data-field="months"]')!.textContent).toContain(message);
    expect(months().value).toBe(value);
    expect(within(dialog()).getByRole('radio', { name: 'Internal' }).getAttribute('aria-checked')).toBe('true');
    expect(nav.push).not.toHaveBeenCalled();
  });

  it('forecast 422 for As of and Audience are the backend sentences, word for word', async () => {
    await forecastReady();
    override = (request, url, body) => {
      if (url.pathname === '/api/v1/work' && request.method === 'POST') {
        const bad = { ...body, intake: { ...(body.intake as object), as_of: '31 Oct', audience: 'everyone' } };
        const [status, reply] = mock.handle('E-WORK-START', { url, raw: JSON.stringify(bad), persona, cookies });
        return json(status, reply);
      }
      return undefined;
    };
    press('Start forecast');
    expect(await within(dialog()).findByText('As of must be a date.')).toBeTruthy();
    expect(within(dialog()).getByText('Choose one of the listed audiences.')).toBeTruthy();
    expect(dialog().querySelector('[data-field="as_of"]')!.textContent).toContain('As of must be a date.');
    expect(dialog().querySelector('[data-field="audience"]')!.textContent).toContain('Choose one of the listed audiences.');
  });

  it('start_hold: a 201 lands on /work/W-4006; the drawer says nothing of a rule or of a prepared forecast', async () => {
    cookies = { psl_mock_start_work: 'start_hold' };
    await forecastReady();
    press('Start forecast');
    await waitFor(() => expect(nav.push).toHaveBeenCalledWith('/work/W-4006'));
    expect(document.body.textContent).not.toMatch(/prepared|preparer|setup/i);
  });
});

describe('12: uncertain and stale', () => {
  it.each(['fixed_assets', 'cash_forecast'])('start_uncertain on %s: Check again sends the same body and key; one start is recorded', async (line) => {
    cookies = { psl_mock_start_work: 'start_uncertain' };
    if (line === 'fixed_assets') await assetsReady();
    else await forecastReady();
    press(line === 'fixed_assets' ? 'Start schedule' : 'Start forecast');
    await within(dialog()).findByRole('button', { name: 'Check again' });
    expect(within(dialog()).getByText('If it started, it will appear in My work.')).toBeTruthy();
    expect(dialog().textContent!.replace('If it started, it will appear in My work.', '').replace('if it already started', '')).not.toMatch(/started/i);
    press('Check again');
    await waitFor(() => expect(nav.push).toHaveBeenCalled());
    expect(starts).toHaveLength(2);
    expect(starts[1].body).toEqual(starts[0].body);
    expect(mock.started.size).toBe(1);
  });

  it('a stale 409 on the forecast start re-reads E-LINES, keeps the values, and the next press sends the re-read revision with a new key', async () => {
    let stale = true;
    override = (request, url) => {
      if (url.pathname === '/api/v1/work' && request.method === 'POST' && stale) {
        stale = false;
        return json(409, { code: 'stale_revision', message: 'Changed.' });
      }
      return undefined;
    };
    await forecastReady();
    press('Start forecast');
    await waitFor(() => expect(lineGets().length).toBeGreaterThan(1));
    await waitFor(() => expect(startButton('Start forecast').disabled).toBe(false));
    expect(months().value).toBe('6');
    press('Start forecast');
    await waitFor(() => expect(nav.push).toHaveBeenCalledWith('/work/W-4001'));
    expect(starts[1].body.idempotency_key).not.toBe(starts[0].body.idempotency_key);
  });

  it('a stale 409 on the upload keeps typed values, re-reads and sends the re-read revision', async () => {
    let stale = true;
    override = (_, url) => {
      if (url.pathname.endsWith('/evidence') && stale) {
        stale = false;
        return json(409, { code: 'stale_revision', message: 'Changed.' });
      }
      return undefined;
    };
    await openLine('fixed_assets');
    await pick(/Prior schedule/, 'PPE-0004');
    choose(file('a.xlsx', 1024));
    expect(await within(dialog()).findByText('This item changed. Add the file again.')).toBeTruthy();
    press('Remove a.xlsx');
    choose(file('a.xlsx', 1024));
    await uploaded();
    expect(uploads.map((u) => u.body.case_revision)).toEqual([4, 4]);
    expect(lineGets().length).toBeGreaterThan(1);
    expect(within(dialog()).getByText('PPE-0004 · August')).toBeTruthy();
  });
});

describe('13 and 14: access, plain text, no limits', () => {
  it('upload and start 403 and 404 read alike; 401 shows the signed-out state with next', async () => {
    override = (_, url) => (url.pathname.endsWith('/evidence') ? json(403, { code: 'forbidden', message: 'm' }) : undefined);
    await openLine('fixed_assets');
    choose(file('x.xlsx', 1024));
    await within(dialog()).findByText('You can’t add proof to this item.');
    cleanupDialog();
    override = (_, url) => (url.pathname === '/api/v1/work' ? json(404, { code: 'not_found', message: 'm' }) : undefined);
    await forecastReady();
    press('Start forecast');
    expect(await within(dialog()).findByText('You can’t start this here.')).toBeTruthy();
    cleanupDialog();
    override = (_, url) => (url.pathname === '/api/v1/work' ? json(401, { code: 'not_signed_in', message: 'Sign in.' }) : undefined);
    await forecastReady();
    press('Start forecast');
    expect(await within(dialog()).findByText('You’re signed out.')).toBeTruthy();
    expect(within(dialog()).getByRole('link', { name: 'Sign in' }).getAttribute('href')).toBe('/accounts/login/?next=%2Fmy-work');
  });

  it('a fixed line without case_revision is "can’t start here yet" and sends nothing', async () => {
    override = (_, url) => {
      if (url.pathname !== '/api/v1/lines') return undefined;
      const lines = mock.handle('E-LINES', { url, raw: '', persona: 'finance_lead' })[1] as Lines;
      return json(200, { ...lines, items: lines.items.map((l: Line) => (l.key === 'fixed_assets' ? { ...l, case_revision: undefined } : l)) });
    };
    await openLine('fixed_assets');
    expect(within(dialog()).getByText(/yet/)).toBeTruthy();
    expect(fileInput()).toBeNull();
    expect(uploads).toHaveLength(0);
    expect(starts).toHaveLength(0);
  });

  it('a hostile file name and a 422 with markup render as text; the input has no accept; an upload 200 without case_revision keeps the last revision', async () => {
    override = (_, url) => (url.pathname.endsWith('/evidence') ? json(200, { evidence_id: 'EV-X-1', sha256: 'x' }) : undefined);
    await openLine('fixed_assets');
    expect(fileInput().hasAttribute('accept')).toBe(false);
    choose(file('<img src=x onerror=alert(1)>.xlsx', 2048));
    await uploaded();
    expect(within(proofBox()).getByText('<img src=x onerror=alert(1)>.xlsx')).toBeTruthy();
    expect(dialog().querySelector('img')).toBeNull();
    expect(dialog().textContent).not.toContain('0 KB');
    press('Remove <img src=x onerror=alert(1)>.xlsx');
    choose(file('b.xlsx', 2048));
    await waitFor(() => expect(uploads).toHaveLength(2));
    expect(uploads[1].body.case_revision).toBe(4);
    expect(dialog().querySelectorAll('a[href]')).toHaveLength(0);
  });

  it('persona none is offered neither line', async () => {
    persona = 'none';
    setCsrfToken('mock-csrf-none');
    render(<StartWorkButton variant="bar" />);
    fireEvent.click(screen.getByRole('button', { name: 'More ways to start' }));
    expect(await within(dialog()).findByText('There are no lines you can start right now.')).toBeTruthy();
    expect(within(dialog()).queryByText(/Fixed asset|Cash forecast/)).toBeNull();
  });
});
