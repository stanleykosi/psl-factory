import { readdirSync, readFileSync } from 'node:fs';
import type { Server } from 'node:http';
import type { AddressInfo } from 'node:net';
import { join } from 'node:path';

import Ajv2020 from 'ajv/dist/2020';
import addFormats from 'ajv-formats';
import { afterAll, beforeAll, beforeEach, describe, expect, it } from 'vitest';

// @ts-expect-error plain ESM module without type declarations
import { RESPONSE_OPERATIONS } from '../mock/response.mjs';
// @ts-expect-error plain ESM module without type declarations
import { M1_OPERATIONS, OPENAPI_PATH, startMockServer } from '../mock/server.mjs';

type Schema = { content: { 'application/json': { schema: object } } };
type Operation = { operationId: string; responses: Record<string, Schema> };
const openapi = JSON.parse(readFileSync(OPENAPI_PATH, 'utf8')) as { paths: Record<string, Record<string, Operation>> };
const ops = Object.values(openapi.paths).flatMap((byMethod) => Object.values(byMethod));
const byId = (id: string) => ops.find((op) => op && typeof op === 'object' && op.operationId === id)!;

const ajv = new Ajv2020({ allErrors: true, strict: true });
addFormats(ajv);
const replyValidators = new Map<string, ReturnType<typeof ajv.compile>>();
function expectValid(id: string, status: number, body: unknown) {
  const key = `${id} ${status}`;
  if (!replyValidators.has(key)) replyValidators.set(key, ajv.compile(byId(id).responses[String(status)].content['application/json'].schema));
  const validate = replyValidators.get(key)!;
  expect(validate(body), `${key}: ${ajv.errorsText(validate.errors)}`).toBe(true);
}

const responseDir = join(__dirname, '../mock/fixtures/response');
const files = [
  ...readdirSync(join(responseDir, 'work')).map((name) => `work/${name}`),
  ...readdirSync(responseDir).filter((name) => name.endsWith('.json')),
];

let server: Server;
let base: string;

beforeAll(async () => {
  server = await startMockServer({ port: 0 });
  base = `http://127.0.0.1:${(server.address() as AddressInfo).port}`;
});
afterAll(() => new Promise<void>((resolve) => server.close(() => resolve())));
beforeEach(async () => {
  expect((await fetch(`${base}/__mock/reset`, { method: 'POST' })).status).toBe(204);
});

const PERSONA = { pm: 'mock-csrf-pm', finance_lead: 'mock-csrf-finance_lead', none: 'mock-csrf-none' } as const;
type Persona = keyof typeof PERSONA;
type Reply = { status: number; body: Record<string, unknown> };

async function post(path: string, operationId: string, body: unknown, init: { persona?: Persona; csrf?: string | null; headers?: Record<string, string> } = {}): Promise<Reply> {
  const persona = init.persona ?? 'pm';
  const csrf = init.csrf === undefined ? PERSONA[persona] : init.csrf;
  const response = await fetch(`${base}${path}`, {
    method: 'POST',
    headers: { Cookie: `psl_mock_persona=${persona}`, 'Content-Type': 'application/json', ...(csrf ? { 'X-CSRFToken': csrf } : {}), ...init.headers },
    body: typeof body === 'string' ? body : JSON.stringify(body),
  });
  const result = { status: response.status, body: (await response.json()) as Record<string, unknown> };
  if (byId(operationId).responses[String(result.status)]) expectValid(operationId, result.status, result.body);
  return result;
}
const upload = (caseId: string, body: unknown, init?: Parameters<typeof post>[3]) => post(`/api/v1/cases/${caseId}/evidence`, 'E-EVIDENCE-UPLOAD', body, init);
const respond = (taskId: string, body: unknown, init?: Parameters<typeof post>[3]) => post(`/api/v1/tasks/${taskId}/response`, 'E-RESPONSE', body, init);
const action = (workId: string, body: unknown, init?: Parameters<typeof post>[3]) => post(`/api/v1/work/${workId}/actions`, 'E-WORK-ACTION', body, init);

async function getItem(id: string, persona: Persona = 'pm') {
  const response = await fetch(`${base}/api/v1/work/${id}`, { headers: { Cookie: `psl_mock_persona=${persona}` } });
  expect(response.status).toBe(200);
  return (await response.json()) as Record<string, unknown> & { case_revision?: number; revision: number; state: string; tasks: { id: string; revision: number; you_can_act: boolean; response?: { recorded?: Record<string, unknown> } }[] };
}

const PDF = Buffer.from('%PDF-1.4 sample proof').toString('base64');
const proof = (caseRevision: number, kind = 'client_response_proof') => ({ kind, filename: 'Lagoon_UAT_signoff_11Nov.pdf', content_base64: PDF, case_revision: caseRevision });
const fields = (r: Reply) => r.body.message;

async function uploaded(caseId = 'C-1601', revision = 4, persona: Persona = 'pm', kind?: string) {
  const r = await upload(caseId, proof(revision, kind), { persona });
  expect(r.status).toBe(200);
  return r.body as { evidence_id: string; case_revision: number };
}

function recordBody(evidenceId: string, extra: Record<string, unknown> = {}) {
  return {
    expected_revision: 2,
    who: 'P-AO',
    action: 'approved',
    responded_at: '2026-11-11T16:20:00+01:00',
    evidence_id: evidenceId,
    attested: true,
    case_revision: 5,
    version_id: 'V-240',
    received_via: 'email',
    ...extra,
  };
}

describe('fixtures', () => {
  const validateItem = ajv.compile(byId('E-WORK-ITEM').responses['200'].content['application/json'].schema);
  it.each(files)('%s is valid v7 E-WORK-ITEM sample data', (name) => {
    const body = JSON.parse(readFileSync(join(responseDir, name), 'utf8')) as { sample?: boolean };
    expect(validateItem(body), `${name}: ${ajv.errorsText(validateItem.errors)}`).toBe(true);
    expect(body.sample).toBe(true);
  });

  it('the base keeps v4 and its M-1 list, and no fixtures/work/W-16 file exists', () => {
    expect(OPENAPI_PATH).toMatch(/packages\/v4\/openapi\.json$/);
    expect(M1_OPERATIONS).toEqual(['E-ME', 'E-WORK-LIST', 'E-WORK-ITEM', 'E-WORK-HISTORY', 'E-TASK-CLAIM', 'E-TASK-DECIDE']);
    expect(RESPONSE_OPERATIONS).toEqual(['E-EVIDENCE-UPLOAD', 'E-RESPONSE', 'E-WORK-ACTION']);
    expect(readdirSync(join(__dirname, '../mock/fixtures/work')).filter((n) => n.startsWith('W-16'))).toEqual([]);
  });
});

describe('E-EVIDENCE-UPLOAD', () => {
  it('stores the proof, returns its sha256 and the next case revision', async () => {
    const r = await upload('C-1601', proof(4));
    expect(r.status).toBe(200);
    expect(r.body.evidence_id).toBe('EV-C-1601-1');
    expect(r.body.sha256).toMatch(/^[0-9a-f]{64}$/);
    expect(r.body.case_revision).toBe(5);
    expect((await getItem('W-1601')).case_revision).toBe(5);
    const second = await upload('C-1601', proof(5));
    expect(second.body).toMatchObject({ evidence_id: 'EV-C-1601-2', case_revision: 6 });
  });

  it('a wrong kind is 422 kind, a stale case revision 409, an empty file 422', async () => {
    expect(await upload('C-1601', proof(4, 'delivery_receipt'))).toEqual({ status: 422, body: { code: 'invalid', message: 'Check these fields: kind.' } });
    expect((await upload('C-1601', proof(3))).status).toBe(409);
    expect(fields(await upload('C-1601', { ...proof(4), content_base64: '====' }))).toBe('Check these fields: content_base64.');
    expect(fields(await upload('C-1601', { ...proof(4), extra: 1 }))).toBe('Check these fields: extra.');
  });

  it('needs a grant on the item, CSRF and a known case', async () => {
    expect((await upload('C-1604', proof(5, 'delivery_receipt'), { persona: 'finance_lead' })).status).toBe(403);
    expect((await upload('C-1603', proof(5, 'delivery_receipt'), { persona: 'finance_lead' })).status).toBe(200);
    expect((await upload('C-1601', proof(4), { csrf: null })).body.code).toBe('csrf_failed');
    expect((await upload('C-1601', proof(4), { persona: 'none' })).status).toBe(403);
    expect((await upload('C-9999', proof(4))).status).toBe(404);
  });
});

describe('E-RESPONSE', () => {
  it('records the response, after which W-1601 serves the recorded sidecar; a repeat is 409', async () => {
    const { evidence_id } = await uploaded();
    const r = await respond('T-1601', recordBody(evidence_id));
    expect(r.status).toBe(200);
    expect(r.body).toMatchObject({ task_id: 'T-1601', work_state: 'ready', revision: 3 });
    expect(r.body.recorded).toMatchObject({ by: { name: 'Tunde Bello', role: 'PM', is_you: true }, received_via: 'email', proof_count: 1, summary: 'Client UAT sign-off for Lagoon Health' });
    expect(r.body.next).toEqual(['The release line moves on to go-live readiness.', 'Milestone 2 can now be marked complete, which lets Chidi draft its invoice.']);
    const item = await getItem('W-1601');
    expect(item.state).toBe('ready');
    expect(item.tasks[0].you_can_act).toBe(false);
    expect(item.tasks[0].response?.recorded).toEqual(r.body.recorded);
    expect((await respond('T-1601', recordBody(evidence_id))).status).toBe(409);
  });

  it('counts every proof file', async () => {
    const first = await uploaded();
    const second = await uploaded('C-1601', 5);
    const r = await respond('T-1601', recordBody(first.evidence_id, { evidence_ids: [second.evidence_id], case_revision: 6 }));
    expect((r.body.recorded as { proof_count: number }).proof_count).toBe(2);
  });

  it('rejects a body without the attestation, the proof, or the offered options', async () => {
    const { evidence_id } = await uploaded();
    const body = recordBody(evidence_id);
    const { attested: _attested, ...unattested } = body;
    void _attested;
    expect(fields(await respond('T-1601', unattested))).toBe('Check these fields: attested.');
    expect(fields(await respond('T-1601', { ...body, attested: false }))).toBe('Check these fields: attested.');
    expect(fields(await respond('T-1601', { ...body, evidence_id: 'EV-forged' }))).toBe('Check these fields: evidence_id.');
    expect(fields(await respond('T-1601', { ...body, evidence_ids: ['EV-forged'] }))).toBe('Check these fields: evidence_ids.');
    expect(fields(await respond('T-1601', { ...body, who: 'P-XX' }))).toBe('Check these fields: who.');
    expect(fields(await respond('T-1601', { ...body, action: 'signed' }))).toBe('Check these fields: action.');
    expect(fields(await respond('T-1601', { ...body, version_id: 'V-999' }))).toBe('Check these fields: version_id.');
    expect(fields(await respond('T-1601', { ...body, received_via: 'fax' }))).toBe('Check these fields: received_via.');
    expect(fields(await respond('T-1601', { ...body, note: 'x'.repeat(2001) }))).toBe('Check these fields: note.');
    expect(fields(await respond('T-1601', { ...body, colour: 'blue' }))).toBe('Check these fields: colour.');
    expect(fields(await respond('T-1601', '{not json'))).toBe('Check these fields: body.');
    // nothing was recorded
    expect((await getItem('W-1601')).tasks[0].you_can_act).toBe(true);
  });

  it('checks revisions, the grant, the persona and CSRF', async () => {
    const { evidence_id } = await uploaded();
    expect((await respond('T-1601', recordBody(evidence_id, { expected_revision: 1 }))).status).toBe(409);
    expect((await respond('T-1601', recordBody(evidence_id, { case_revision: 4 }))).status).toBe(409);
    // T-1608 is in the same case (C-1601) but you_can_act is false: everything else is right, so the grant decides.
    expect((await respond('T-1608', recordBody(evidence_id))).status).toBe(403);
    expect((await respond('T-1601', recordBody(evidence_id), { persona: 'none' })).status).toBe(403);
    const noCsrf = await respond('T-1601', recordBody(evidence_id), { csrf: null });
    expect(noCsrf).toEqual({ status: 403, body: { code: 'csrf_failed', message: 'Your session check failed. Reload and try again.' } });
    expect((await respond('T-9999', recordBody(evidence_id))).status).toBe(404);
    expect((await getItem('W-1601')).tasks[0].you_can_act).toBe(true);
  });

  it('answers a declared scenario with its body, and record-then-fail records and then answers 502', async () => {
    const { evidence_id } = await uploaded();
    const scenario = await respond('T-1601', recordBody(evidence_id), { headers: { 'X-Mock-Scenario': '422' } });
    expect(scenario).toEqual({ status: 422, body: { code: 'invalid', message: 'Check the highlighted fields and try again.' } });
    const lost = await respond('T-1601', recordBody(evidence_id), { headers: { 'X-Mock-Scenario': 'record-then-fail' } });
    expect(lost).toEqual({ status: 502, body: { code: 'mock_lost', message: 'The mock dropped this reply.' } });
    expect((await getItem('W-1601')).tasks[0].response?.recorded).toBeDefined();
  });

  it('W-1606 answers the bare 200 and the reload carries only who recorded it and when', async () => {
    const { evidence_id } = await uploaded('C-1606', 1);
    const r = await respond('T-1606', { expected_revision: 2, who: 'P-IM', action: 'approved', responded_at: '2026-11-11T16:20:00+01:00', evidence_id, attested: true, case_revision: 2, version_id: 'V-120' });
    expect(r).toEqual({ status: 200, body: { task_id: 'T-1606', work_state: 'ready' } });
    expect(Object.keys((await getItem('W-1606')).tasks[0].response?.recorded ?? {})).toEqual(['by', 'at']);
  });

  it('claim on T-1605 goes through F-04’s handler', async () => {
    const response = await fetch(`${base}/api/v1/tasks/T-1605/claim`, {
      method: 'POST',
      headers: { Cookie: 'psl_mock_persona=pm', 'X-CSRFToken': PERSONA.pm, 'Content-Type': 'application/json' },
      body: JSON.stringify({ expected_revision: 3 }),
    });
    expect(response.status).toBe(200);
    expect(await response.json()).toEqual({ task_id: 'T-1605', revision: 3, claimed_by: 'Tunde Bello' });
  });
});

describe('E-WORK-ACTION', () => {
  const lead = { persona: 'finance_lead' as const };

  it('reconciles "delivered" with proof, after which W-1603 serves the sidecar', async () => {
    const { evidence_id, case_revision } = await uploaded('C-1603', 5, 'finance_lead', 'delivery_receipt');
    const r = await action('W-1603', { expected_revision: 6, action: 'reconcile', outcome: 'delivered', evidence_id, case_revision }, lead);
    expect(r).toEqual({ status: 200, body: { work_id: 'W-1603', state: 'ready', revision: 7 } });
    const item = await getItem('W-1603', 'finance_lead');
    expect(item.state).toBe('ready');
    expect(item).not.toHaveProperty('reconcile');
  });

  it('"not_delivered" and "unknown" need no proof', async () => {
    expect((await action('W-1603', { expected_revision: 6, action: 'reconcile', outcome: 'not_delivered' }, lead)).body).toMatchObject({ state: 'processing' });
    await fetch(`${base}/__mock/reset`, { method: 'POST' });
    expect((await action('W-1603', { expected_revision: 6, action: 'reconcile', outcome: 'unknown' }, lead)).body).toMatchObject({ state: 'awaiting_reconciliation', revision: 7 });
  });

  it('refuses without the grant, the outcome or the proof, and does not mock resume', async () => {
    expect((await action('W-1604', { expected_revision: 6, action: 'reconcile', outcome: 'not_delivered' }, lead)).status).toBe(403);
    expect(fields(await action('W-1603', { expected_revision: 6, action: 'reconcile' }, lead))).toBe('Check these fields: outcome.');
    expect(fields(await action('W-1607', { expected_revision: 6, action: 'reconcile', outcome: 'delivered' }, lead))).toBe('Check these fields: outcome, evidence_id.');
    expect(fields(await action('W-1603', { expected_revision: 6, action: 'reconcile', outcome: 'delivered' }, lead))).toBe('Check these fields: evidence_id.');
    const resume = await action('W-1603', { expected_revision: 6, action: 'resume' }, lead);
    expect(resume).toEqual({ status: 501, body: { code: 'not_mocked', message: 'Not available in the mock yet.' } });
    expect((await action('W-1603', { expected_revision: 5, action: 'reconcile', outcome: 'unknown' }, lead)).status).toBe(409);
    expect((await action('W-1603', { expected_revision: 6, action: 'reconcile', outcome: 'unknown' }, { ...lead, csrf: null })).body.code).toBe('csrf_failed');
    expect((await action('W-1603', { expected_revision: 6, action: 'reconcile', outcome: 'unknown' }, { persona: 'none' })).status).toBe(403);
    expect((await action('W-9999', { expected_revision: 6, action: 'reconcile', outcome: 'unknown' }, lead)).status).toBe(404);
    expect((await getItem('W-1603', 'finance_lead')).state).toBe('awaiting_reconciliation');
  });

  it('record-then-fail applies the answer and then answers 502', async () => {
    const r = await action('W-1603', { expected_revision: 6, action: 'reconcile', outcome: 'not_delivered' }, { ...lead, headers: { 'X-Mock-Scenario': 'record-then-fail' } });
    expect(r.status).toBe(502);
    expect((await getItem('W-1603', 'finance_lead')).state).toBe('processing');
  });
});

describe('reset', () => {
  it('restores W-1601 and W-1603 and forgets the evidence', async () => {
    const { evidence_id } = await uploaded();
    await respond('T-1601', recordBody(evidence_id));
    await action('W-1603', { expected_revision: 6, action: 'reconcile', outcome: 'unknown' }, { persona: 'finance_lead' });
    expect((await fetch(`${base}/__mock/reset`, { method: 'POST' })).status).toBe(204);
    const item = await getItem('W-1601');
    expect(item.case_revision).toBe(4);
    expect(item.tasks[0].you_can_act).toBe(true);
    expect((await getItem('W-1603', 'finance_lead')).revision).toBe(6);
    expect(fields(await respond('T-1601', recordBody(evidence_id, { case_revision: 4 })))).toBe('Check these fields: evidence_id.');
  });
});
