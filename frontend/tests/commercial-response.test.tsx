// @vitest-environment jsdom
// F-136: the client's response and SOW signature (SCR-16) on the live work item, against the live-shaped mock (mock/commercial-live.mjs).
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import Ajv2020 from 'ajv/dist/2020';
import addFormats from 'ajv-formats';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { setCsrfToken } from '@/api/client';
import { ToastProvider } from '@/components';
import { commercialCommands, commercialSections, signingOpen, type CommercialDesk } from '@/features/response/commercialModel';
import { LiveWorkItemView } from '@/features/work-item/live/LiveWorkItemView';
import { resetScopedWriteLocks } from '@/features/workspace/useWriteLock';

// @ts-expect-error plain ESM module without type declarations
import { COMMERCIAL_PATH, commercialLive, resetCommercialLive } from '../mock/commercial-live.mjs';

vi.mock('@/shell/AppShell', () => ({ usePhoneBack: () => undefined }));
vi.mock('next/navigation', () => ({ usePathname: () => '/work/4660', useRouter: () => ({ replace: vi.fn(), push: vi.fn(), prefetch: vi.fn() }) }));

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
const me = { name: 'Tunde Bello', destinations: [], startable_lines: [], csrf_token: 't', assistant_agents: [] };
let scenario: string | undefined;
let dropWrites = false;
let fetchStub: ReturnType<typeof vi.fn<(request: Request) => Promise<Response>>>;
const posts = () => fetchStub.mock.calls.filter(([r]) => r.method === 'POST');
const sent = async () => Promise.all(posts().map(async ([r]) => ({ path: new URL(r.url).pathname, body: JSON.parse(await r.clone().text()) as Record<string, unknown> })));

beforeEach(() => {
  resetScopedWriteLocks();
  resetCommercialLive();
  scenario = undefined;
  dropWrites = false;
  setCsrfToken('t');
  fetchStub = vi.fn(async (request: Request) => {
    const url = new URL(request.url);
    if (url.pathname === '/api/v1/me') return json(200, me);
    if (url.pathname === '/api/v1/session') return json(200, { csrf_token: 't', signed_in: true, next_url: '/' });
    if (!COMMERCIAL_PATH.test(url.pathname)) return json(404, { code: 'not_found', message: 'This record is unavailable.' });
    // the connection is cut: the answer never arrives and the re-read shows nothing new
    if (dropWrites && request.method === 'POST') throw new TypeError('network down');
    const rawBytes = request.method === 'POST' ? Buffer.from(await request.clone().text()) : undefined;
    const [status, body] = commercialLive({ method: request.method.toLowerCase(), url, scenario, csrfOk: request.headers.get('X-CSRFToken') === 't', persona: 'finance_lead', rawBytes }) as [number, unknown];
    return json(status, body);
  });
  vi.stubGlobal('fetch', fetchStub);
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const open = async (id: number) => {
  render(
    <ToastProvider>
      <LiveWorkItemView id={String(id)} tab="overview" />
    </ToastProvider>,
  );
  await screen.findAllByText('What is to be signed');
};
const choose = (label: string | RegExp, option: string | RegExp) => {
  fireEvent.click(screen.getByRole('combobox', { name: label }));
  fireEvent.click(screen.getByRole('option', { name: typeof option === 'string' ? new RegExp(`^${option}`) : option }));
};
const type = (label: RegExp | string, value: string) => fireEvent.change(screen.getByLabelText(label), { target: { value } });
const fillWitness = (outcome = 'Signed') => {
  choose('What the client answered', /Statement of work/);
  type('Name of the person who answered', 'Dayo Adesina');
  choose('Answer', outcome);
  type('When the client answered', '2026-11-24T15:20');
  fireEvent.click(screen.getByRole('checkbox', { name: 'client-email-reply.pdf' }));
  type('Note', 'The client replied by email and attached the signed page.');
  fireEvent.click(screen.getByRole('checkbox', { name: /This is the client’s own response/ }));
};

describe('the contract and the mock agree', () => {
  const spec = JSON.parse(readFileSync(join(__dirname, '../../contracts/psl-factory.openapi.json'), 'utf8')) as { paths: Record<string, Record<string, object>> };
  const ajv = new Ajv2020({ allErrors: true, strict: false });
  addFormats(ajv);
  ajv.addSchema({ $id: 'spec', ...spec });
  const DESK = '/api/v1/projects/{case_id}/commercial-response';
  const ref = (path: string, tail: string) => `spec#/paths/${path.replaceAll('/', '~1')}/${tail}`;
  const reply = (path: string, method = 'get', extra: object = {}) => commercialLive({ method, url: new URL(path, 'http://m.local'), scenario: undefined, csrfOk: true, persona: 'finance_lead', ...extra }) as [number, unknown];
  const caseOf = (id: number) => `/api/v1/projects/00000000-0000-4000-8000-00000000${id}/commercial-response`;

  it('every desk read and the work item answer their operation’s 200 shape, and the work item names the panel', () => {
    const validate = ajv.compile({ $ref: ref(DESK, 'get/responses/200/content/application~1json/schema') });
    for (const id of [4660, 4661, 4662, 4663, 4664, 4665, 4666]) {
      const [status, body] = reply(caseOf(id));
      expect(status).toBe(200);
      expect(validate(body), `${id}: ${ajv.errorsText(validate.errors)}`).toBe(true);
    }
    const item = ajv.compile({ $ref: ref('/api/v1/work/{work_id}', 'get/responses/200/content/application~1json/schema') });
    const [status, body] = reply('/api/v1/work/4660');
    expect(status).toBe(200);
    expect(item(body), ajv.errorsText(item.errors)).toBe(true);
    expect((body as { panels: { key: string }[] }).panels[0].key).toBe('commercial-response');
  });

  it('the three bodies the page sends are the contract’s bodies, and the mock refuses what the contract refuses', () => {
    const validate = ajv.compile({ $ref: ref(DESK, 'post/requestBody/content/application~1json/schema') });
    const witness = { action: 'witness', case_revision: 89, revision_id: 2, receipt_id: 5, client_name: 'D', responded_at: '2026-11-24T15:20:00.000Z', outcome: 'signed', genuine: true, proof_ids: [31], note: 'n', operation_key: '6c2f1d3e-1a4b-4b8e-9d0a-0a1b2c3d4e5f', predecessor_id: null, party_ref: null };
    const one = { evidence_id: 7, party_ref: 'client-signer', method: 'Wet ink', locator: 'Page 9', human_verified: true };
    const signatures = { action: 'signatures', case_revision: 89, response_id: 9, prd_id: 142, signatures: { sow: one, prd: { ...one, evidence_id: 143 } }, note: 'n', operation_key: 'k1', predecessor_id: null };
    const adopt = { action: 'adopt', case_revision: 89, response_id: 9 };
    for (const body of [witness, { ...witness, received_via: 'email' }, signatures, adopt]) expect(validate(body), JSON.stringify(body)).toBe(true);
    const bads = [{ ...witness, genuine: false }, { ...witness, proof_ids: [] }, { ...witness, extra: 1 }, { ...witness, outcome: 'approved' }, { ...witness, received_via: 'fax' }, { ...signatures, signatures: { sow: one } }, { ...adopt, note: 'x' }];
    for (const bad of bads) {
      const [status] = reply(caseOf(4660), 'post', { rawBytes: Buffer.from(JSON.stringify(bad)) });
      expect(status, JSON.stringify(bad)).toBe(400);
    }
    for (const body of [witness, signatures, adopt]) {
      const [status] = reply(caseOf(4660), 'post', { rawBytes: Buffer.from(JSON.stringify(body)) });
      expect(status).not.toBe(400);
    }
  });
});

describe('the model', () => {
  const desk = (patch: Partial<CommercialDesk> = {}) => commercialLive({ method: 'get', url: new URL('http://m.local/api/v1/projects/00000000-0000-4000-8000-000000004660/commercial-response'), csrfOk: true, persona: 'finance_lead' })[1] as CommercialDesk & typeof patch;
  const commands = (d: CommercialDesk) => commercialCommands(d, { caseId: 'c1' });
  const reason = (d: CommercialDesk, id: string) => commands(d).find((c) => c.id === id)?.disabledReason;

  it('says why each write is held, from the read and nothing else', () => {
    const d = desk();
    expect(reason(d, 'commercial-response.witness')).toBeUndefined();
    expect(reason({ ...d, can_record: false }, 'commercial-response.witness')).toMatch(/isn’t open to you/);
    expect(reason({ ...d, receipts: [] }, 'commercial-response.witness')).toMatch(/Nothing has been sent/);
    expect(reason({ ...d, owned_files: [] }, 'commercial-response.witness')).toMatch(/no proof file/);
    expect(reason({ ...d, current_revision_id: null }, 'commercial-response.witness')).toMatch(/no current version/);
    expect(reason(d, 'commercial-response.signatures')).toMatch(/signed response must be recorded first/);
    expect(reason(d, 'commercial-response.adopt')).toMatch(/signed response must be recorded first/);
    expect(signingOpen(d)).toBe(false);
  });

  it('the write bodies carry only what the contract names; the key is a uuid for a response and absent for adopt', () => {
    const d = desk();
    const [witness, , adopt] = commands(d);
    const body = witness.body({ receipt_id: 5 });
    expect(Object.keys(body).sort()).toEqual(['action', 'case_revision', 'operation_key', 'predecessor_id', 'receipt_id', 'revision_id']);
    expect(body.operation_key).toMatch(/^[0-9a-f-]{36}$/);
    expect(body.predecessor_id).toBeNull();
    expect(Object.keys(adopt.body({})).sort()).toEqual(['action', 'case_revision', 'response_id']);
  });

  it('a value the read does not give reads Not recorded, never a guess', () => {
    const d = { ...desk(), current_revision_id: null };
    const facts = commercialSections(d).find((s) => s.key === 'tosign')!;
    expect(facts.items[0].value).toBe('Not recorded');
    expect(facts.items[1].value).toBe('1 delivery');
  });
});

describe('reads (SCR-16)', () => {
  it('a delivery with nothing recorded: what is to be signed, the proof files, who may record, and the response form', async () => {
    await open(4660);
    expect(screen.getByText('Version record 2')).toBeTruthy();
    expect(screen.getByText(/Statement of work · v1 · client · Delivered 24 Nov 2026/)).toBeTruthy();
    expect(screen.getByText('No response from the client has been recorded yet.')).toBeTruthy();
    expect(screen.getByText(/Available to attach: client-email-reply\.pdf \(182 KB\)/)).toBeTruthy();
    expect(screen.getByText('You may record it')).toBeTruthy();
    expect(screen.getByText('Not adopted yet')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Record the client’s response' })).toBeTruthy();
    expect(screen.queryByRole('button', { name: /Record the signatures|Adopt/ })).toBeNull();
    expect(posts()).toHaveLength(0);
  });

  it('a signed response: the answer, how it came, the signatures not yet captured, and signing open', async () => {
    await open(4661);
    expect(screen.getByText('Dayo Adesina')).toBeTruthy();
    expect(screen.getByText('Signed', { selector: '.psl-tag, .psl-tag *' })).toBeTruthy();
    expect(screen.getByText('Email')).toBeTruthy();
    expect(screen.getAllByText('Not captured yet')).toHaveLength(2);
    expect(screen.getByRole('button', { name: 'Record the signatures' })).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Adopt the signed baseline' })).toBeNull();
  });

  it('an adopted baseline shows it, says no provider checked the signatures, and offers nothing to press', async () => {
    await open(4663);
    expect(screen.getByText('Adopted')).toBeTruthy();
    expect(screen.getAllByText('Human reference captured')).toHaveLength(2);
    expect(screen.queryByRole('button', { name: /Record|Adopt/ })).toBeNull();
  });

  it('nothing sent yet: the form is held with its reason', async () => {
    await open(4664);
    expect(screen.getByText('Nothing sent yet')).toBeTruthy();
    const press = screen.getByRole('button', { name: 'Record the client’s response' });
    expect((press as HTMLButtonElement).disabled).toBe(true);
    expect(screen.getByText('Nothing has been sent to the client yet.')).toBeTruthy();
  });

  it('a person who may not record sees where it stands and no form', async () => {
    await open(4665);
    expect(screen.getByText('Not open to you')).toBeTruthy();
    expect(screen.queryByRole('button', { name: /Record/ })).toBeNull();
    expect(screen.queryByRole('combobox')).toBeNull();
  });

  it('a request for changes is not drawn as signed', async () => {
    await open(4666);
    expect(screen.getByText('Asked for changes')).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Record the signatures' })).toBeNull();
  });
});

describe('writes (SCR-16)', () => {
  it('record the response, the signatures, then adopt: each body is the contract’s, and each result is told from the re-read', async () => {
    await open(4660);
    fireEvent.click(screen.getByRole('button', { name: 'Record the client’s response' }));
    expect(posts()).toHaveLength(0);
    expect(screen.getByText('Choose what the client was sent.')).toBeTruthy();
    fillWitness();
    choose(/How the answer reached us/, 'Email');
    fireEvent.click(screen.getByRole('button', { name: 'Record the client’s response' }));
    await screen.findByRole('button', { name: 'Record the signatures' });
    const [first] = await sent();
    expect(first.path).toBe('/api/v1/projects/00000000-0000-4000-8000-000000004660/commercial-response');
    expect(first.body).toMatchObject({ action: 'witness', case_revision: 89, revision_id: 2, receipt_id: 5, client_name: 'Dayo Adesina', outcome: 'signed', genuine: true, proof_ids: [31], party_ref: null, predecessor_id: null, received_via: 'email' });
    expect(first.body.responded_at).toBe(new Date('2026-11-24T15:20').toISOString());
    expect(first.body.operation_key).toMatch(/^[0-9a-f-]{36}$/);
    // done only from the re-read
    expect(screen.getByText('Dayo Adesina')).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Record the client’s response' })).toBeTruthy();

    // signatures: needs every field and the tick
    fireEvent.click(screen.getByRole('button', { name: 'Record the signatures' }));
    expect(posts()).toHaveLength(1);
    expect(screen.getByText('Choose the document.')).toBeTruthy();
    const block = within(screen.getByRole('region', { name: 'Record the signatures' }));
    const [sowWho, prdWho] = ['sow', 'prd'].map((_, i) => block.getAllByRole('combobox', { name: 'Who signed' })[i]);
    fireEvent.click(sowWho);
    fireEvent.click(screen.getByRole('option', { name: 'Client representative' }));
    const how = block.getAllByLabelText(/How it was signed/);
    const where = block.getAllByLabelText(/Where in the document/);
    fireEvent.change(how[0], { target: { value: 'Wet ink' } });
    fireEvent.change(where[0], { target: { value: 'Page 9' } });
    choose('Document', /Requirements, version 1/);
    choose('Signature proof', /version 2/);
    fireEvent.click(prdWho);
    fireEvent.click(screen.getByRole('option', { name: 'Client representative' }));
    fireEvent.change(how[1], { target: { value: 'Typed name' } });
    fireEvent.change(where[1], { target: { value: 'Page 3' } });
    fireEvent.change(block.getByLabelText('Note'), { target: { value: 'Both signed pages checked.' } });
    fireEvent.click(block.getByRole('checkbox'));
    fireEvent.click(screen.getByRole('button', { name: 'Record the signatures' }));
    await screen.findByRole('button', { name: 'Adopt the signed baseline' });
    const signatures = (await sent())[1].body;
    expect(signatures).toMatchObject({
      action: 'signatures',
      case_revision: 90,
      response_id: 9,
      prd_id: 142,
      predecessor_id: null,
      note: 'Both signed pages checked.',
      signatures: {
        sow: { evidence_id: 7, party_ref: 'client-signer', method: 'Wet ink', locator: 'Page 9', human_verified: true },
        prd: { evidence_id: 143, party_ref: 'client-signer', method: 'Typed name', locator: 'Page 3', human_verified: true },
      },
    });
    expect(Object.keys(signatures).sort()).toEqual(['action', 'case_revision', 'note', 'operation_key', 'prd_id', 'predecessor_id', 'response_id', 'signatures']);
    expect(screen.getAllByText('Human reference captured')).toHaveLength(2);

    fireEvent.click(screen.getByRole('button', { name: 'Adopt the signed baseline' }));
    await screen.findByText('Adopted');
    expect((await sent())[2].body).toEqual({ action: 'adopt', case_revision: 91, response_id: 9 });
    expect(screen.queryByRole('button', { name: /Record the signatures|Adopt/ })).toBeNull();
  });

  it('a decline is recorded as declined and opens no signing', async () => {
    await open(4660);
    fillWitness('Declined');
    fireEvent.click(screen.getByRole('button', { name: 'Record the client’s response' }));
    await screen.findByText('Declined');
    expect((await sent())[0].body.outcome).toBe('declined');
    expect(screen.queryByRole('button', { name: 'Record the signatures' })).toBeNull();
  });

  it('a 409 shows the lasting notice and the latest version, and sends nothing more', async () => {
    scenario = 'w409';
    await open(4660);
    fillWitness();
    fireEvent.click(screen.getByRole('button', { name: 'Record the client’s response' }));
    await screen.findByText(/This changed while you were working\. Showing the latest version\./);
    expect(posts()).toHaveLength(1);
  });

  it('a 422 says what the server said and records nothing', async () => {
    scenario = 'w422';
    await open(4660);
    fillWitness();
    fireEvent.click(screen.getByRole('button', { name: 'Record the client’s response' }));
    await screen.findByText(/The request was not accepted\./);
    expect(screen.getByText(/Select one to twelve distinct private proof files\./)).toBeTruthy();
    expect(screen.getByText('No response from the client has been recorded yet.')).toBeTruthy();
  });

  it('a write whose answer is lost is never sent again on its own, and its button stays locked', async () => {
    await open(4660);
    fillWitness();
    dropWrites = true;
    fireEvent.click(screen.getByRole('button', { name: 'Record the client’s response' }));
    await screen.findByText(/We couldn’t confirm that this happened/);
    const press = screen.getByRole('button', { name: 'Record the client’s response' });
    await waitFor(() => expect(press.getAttribute('aria-disabled') === 'true' || (press as HTMLButtonElement).disabled).toBe(true));
    expect(screen.getAllByText('Check the page before trying again.').length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole('button', { name: 'Record the client’s response' }));
    expect(posts()).toHaveLength(1);
  });
});
