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
import { OPENAPI_PATH, startMockServer } from '../mock/server.mjs';

// F-18 contract mock: team input on E-RESPONSE and E-RFP-OUTCOME, checked against v7 (D-RFP-OUTCOME r2, proposed).
type Schema = { content: { 'application/json': { schema: object } } };
type Operation = { operationId: string; responses: Record<string, Schema> };
const openapi = JSON.parse(readFileSync(OPENAPI_PATH, 'utf8')) as { paths: Record<string, Record<string, Operation>> };
const ops = Object.values(openapi.paths).flatMap((byMethod) => Object.values(byMethod));
const byId = (id: string) => ops.find((op) => op && typeof op === 'object' && op.operationId === id)!;

const ajv = new Ajv2020({ allErrors: true, strict: true });
addFormats(ajv);
const validators = new Map<string, ReturnType<typeof ajv.compile>>();
function validator(id: string, status: number) {
  const key = `${id} ${status}`;
  if (!validators.has(key)) validators.set(key, ajv.compile(byId(id).responses[String(status)].content['application/json'].schema));
  return validators.get(key)!;
}
function expectValid(id: string, status: number, body: unknown) {
  const validate = validator(id, status);
  expect(validate(body), `${id} ${status}: ${ajv.errorsText(validate.errors)}`).toBe(true);
}

const workDir = join(__dirname, '../mock/fixtures/response/work');
const RFP_FILES = readdirSync(workDir).filter((name) => name.startsWith('W-21'));
const readWork = (name: string) => JSON.parse(readFileSync(join(workDir, name), 'utf8')) as Record<string, unknown>;

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

const PERSONA = { pm: 'mock-csrf-pm', none: 'mock-csrf-none' } as const;
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
const upload = (caseId: string, kind: string, caseRevision = 3) =>
  post(`/api/v1/cases/${caseId}/evidence`, 'E-EVIDENCE-UPLOAD', { kind, filename: 'proof.pdf', content_base64: Buffer.from('%PDF-1.4 proof').toString('base64'), case_revision: caseRevision });
const claim = (taskId: string, revision: number) => post(`/api/v1/tasks/${taskId}/claim`, 'E-TASK-CLAIM', { expected_revision: revision });
const respond = (taskId: string, body: unknown, init?: Parameters<typeof post>[3]) => post(`/api/v1/tasks/${taskId}/response`, 'E-RESPONSE', body, init);
const outcome = (workId: string, body: unknown, init?: Parameters<typeof post>[3]) => post(`/api/v1/work/${workId}/rfp-outcome`, 'E-RFP-OUTCOME', body, init);

async function getItem(id: string) {
  const response = await fetch(`${base}/api/v1/work/${id}`, { headers: { Cookie: 'psl_mock_persona=pm' } });
  expect(response.status).toBe(200);
  const body = await response.json();
  expectValid('E-WORK-ITEM', 200, body);
  return body as Record<string, unknown> & { revision: number; case_revision: number; state: string; tasks: { id: string; revision: number; response?: { recorded?: Record<string, unknown> } }[]; rfp_outcome?: Record<string, unknown> & { recorded?: Record<string, unknown> } };
}
const fields = (r: Reply) => r.body.message;

function teamBody(evidenceId: string, extra: Record<string, unknown> = {}) {
  return {
    expected_revision: 4,
    who: 'P-KA',
    action: 'estimate',
    responded_at: '2026-11-12T15:10:00+01:00',
    evidence_id: evidenceId,
    attested: true,
    case_revision: 4,
    team: 'security',
    estimate_person_days: 18,
    what: 'Security estimate and data-protection notes',
    ...extra,
  };
}

async function outcomeBody(workId = 'W-2103', extra: Record<string, unknown> = {}) {
  const item = await getItem(workId);
  const proof = await upload(item.case_id as string, 'rfp_outcome_proof', item.case_revision);
  expect(proof.status).toBe(200);
  return {
    expected_revision: item.revision,
    case_revision: proof.body.case_revision,
    submission_id: 'SUB-0031',
    result: 'lost',
    learned_at: '2026-12-04T11:00:00+01:00',
    record_as: 'relationship_owner',
    evidence_id: proof.body.evidence_id,
    ...extra,
  };
}

describe('fixtures (D-RFP-OUTCOME r2)', () => {
  const validateItem = ajv.compile(byId('E-WORK-ITEM').responses['200'].content['application/json'].schema);
  it.each(RFP_FILES)('%s validates against the generated v7 E-WORK-ITEM schema with nothing stripped', (name) => {
    const body = readWork(name);
    expect(validateItem(body), `${name}: ${ajv.errorsText(validateItem.errors)}`).toBe(true);
    expect(body.sample).toBe(true);
  });

  it('the W-2101 sidecar validates too', () => {
    const body = JSON.parse(readFileSync(join(__dirname, '../mock/fixtures/response/W-2101.recorded.json'), 'utf8'));
    expect(validateItem(body), ajv.errorsText(validateItem.errors)).toBe(true);
  });

  it('W-2110 carries every optional r2 field absent', () => {
    const body = readWork('W-2110.json') as { rfp: Record<string, unknown>; rfp_outcome: Record<string, unknown> & { submission: Record<string, unknown> } };
    expect(Object.keys(body.rfp).sort()).toEqual(['reference', 'status']);
    expect(Object.keys(body.rfp.status as object).sort()).toEqual(['kind', 'label']);
    expect(Object.keys(body.rfp_outcome).sort()).toEqual(['record_as', 'results', 'submission']);
    expect(Object.keys(body.rfp_outcome.submission).sort()).toEqual(['id', 'label']);
  });

  it('E-RFP-OUTCOME is a response-mock operation', () => {
    expect(RESPONSE_OPERATIONS).toContain('E-RFP-OUTCOME');
  });
});

describe('E-RESPONSE team input', () => {
  it('claims, then records once with the team rules and swaps in the sidecar', async () => {
    const proof = await upload('C-2101', 'team_input_proof');
    expect(proof.status).toBe(200);
    expect((await claim('T-2101', 4)).status).toBe(200);
    const r = await respond('T-2101', teamBody(proof.body.evidence_id as string));
    expect(r.status).toBe(200);
    expectValid('E-RESPONSE', 200, r.body);
    const after = await getItem('W-2101');
    expect(after.tasks[0].response!.recorded).toMatchObject({ by: { name: 'Tunde Bello' } });
    expect((await respond('T-2101', teamBody(proof.body.evidence_id as string))).status).toBe(409);
  });

  it('422 for a team not returned, a missing estimate for a team that needs one, or a blank what', async () => {
    const proof = await upload('C-2101', 'team_input_proof');
    const id = proof.body.evidence_id as string;
    expect(fields(await respond('T-2101', teamBody(id, { team: 'legal' })))).toBe('Check these fields: team.');
    const { estimate_person_days: _drop, ...noEstimate } = teamBody(id);
    void _drop;
    expect(fields(await respond('T-2101', noEstimate))).toBe('Check these fields: estimate_person_days.');
    expect(fields(await respond('T-2101', teamBody(id, { what: '  ' })))).toBe('Check these fields: what.');
    expect((await respond('T-2101', { ...noEstimate, team: 'product', action: 'input' })).status).toBe(200);
  });

  it('W-2102 (not yours) cannot use proof it could not upload (422); persona none answers 403', async () => {
    const proof = await upload('C-2101', 'team_input_proof');
    expect((await respond('T-2102', teamBody(proof.body.evidence_id as string))).status).toBe(422);
    expect((await respond('T-2101', teamBody('EV-x'), { persona: 'none' })).status).toBe(403);
  });

  it('record-then-fail records, then answers 502', async () => {
    const proof = await upload('C-2101', 'team_input_proof');
    const r = await respond('T-2101', teamBody(proof.body.evidence_id as string), { headers: { 'X-Mock-Scenario': 'record-then-fail' } });
    expect(r.status).toBe(502);
    expect((await getItem('W-2101')).tasks[0].response!.recorded).toBeTruthy();
  });
});

describe('E-EVIDENCE-UPLOAD for the outcome', () => {
  it('accepts rfp_outcome.evidence_kind on an item with rfp_outcome and refuses it on W-2109', async () => {
    expect((await upload('C-2103', 'rfp_outcome_proof')).status).toBe(200);
    expect((await upload('C-2109', 'rfp_outcome_proof')).status).toBe(422);
  });
});

describe('E-RFP-OUTCOME', () => {
  it.each([
    ['won', 'W-2105', { awarded_amount: { currency: 'NGN', amount: '40951000.00', unknown: false } }],
    ['lost', 'W-2106', { reason: 'price', lessons: 'Too expensive' }],
    ['pending', 'W-2107', { expected_decision_on: '2026-12-12', remind_at: '2026-12-12T09:00:00+01:00' }],
    ['unknown', 'W-2108', { remind_at: '2026-12-10T09:00:00+01:00' }],
  ])('%s answers 200 (valid v7) and serves the recorded item %s under W-2103', async (result, source, extra) => {
    const body = await outcomeBody('W-2103', { result, ...extra });
    const r = await outcome('W-2103', body);
    expect(r.status).toBe(200);
    expect(r.body).toMatchObject({ work_id: 'W-2103', result, revision: (body.expected_revision as number) + 1 });
    if (result === 'won') expect(r.body.engagement_work_id).toBe('W-1003');
    else expect(r.body).not.toHaveProperty('engagement_work_id');
    const after = await getItem('W-2103');
    expect(after.id).toBe('W-2103');
    expect(after.case_id).toBe('C-2103');
    expect(after.rfp_outcome!.recorded).toMatchObject({ result, by: 'Tunde Bello' });
    expect(after.rfp_outcome!.recorded!.rows ?? after.rfp_outcome!.recorded!.lessons).toEqual(
      (readWork(`${source}.json`).rfp_outcome as { recorded: { rows?: unknown; lessons?: unknown } }).recorded.rows ??
        (readWork(`${source}.json`).rfp_outcome as { recorded: { lessons?: unknown } }).recorded.lessons,
    );
    // Not idempotent by key: a repeat fails on expected_revision.
    expect((await outcome('W-2103', body)).status).toBe(409);
  });

  it('422 names each refused field', async () => {
    const body = await outcomeBody();
    const cases: [Record<string, unknown>, string][] = [
      [{ submission_id: 'SUB-9' }, 'submission_id'],
      [{ result: 'won', record_as: 'ceo' }, 'record_as'],
      [{ reason: 'mood' }, 'reason'],
      [{ note: 'x'.repeat(2001) }, 'note'],
      [{ result: 'won', awarded_amount: { currency: 'NGN', amount: '1.00', unknown: true } }, 'awarded_amount'],
      [{ evidence_id: 'EV-C-2103-99' }, 'evidence_id'],
      [{ learned_at: 'yesterday' }, 'learned_at'],
    ];
    for (const [extra, field] of cases) {
      const r = await outcome('W-2103', { ...body, ...extra });
      expect(r.status, field).toBe(422);
      expect(fields(r)).toBe(`Check these fields: ${field}.`);
    }
    const two = await outcomeBody('W-2104');
    expect(fields(await outcome('W-2104', { ...two, result: 'pending', submission_id: 'SUB-0031' }))).toBe('Check these fields: result.');
    expect(fields(await outcome('W-2103', { ...body, extra: true }))).toBe('Check these fields: extra.');
  });

  it('409 on expected_revision or case_revision', async () => {
    const body = await outcomeBody();
    expect((await outcome('W-2103', { ...body, expected_revision: 1 })).status).toBe(409);
    expect((await outcome('W-2103', { ...body, case_revision: 1 })).status).toBe(409);
  });

  it('403 without the block (W-2109), for persona none and without the CSRF header; 404 for an unknown item', async () => {
    const body = await outcomeBody();
    const item = await getItem('W-2109');
    expect((await outcome('W-2109', { ...body, expected_revision: item.revision, case_revision: item.case_revision })).status).toBe(403);
    expect((await outcome('W-2103', body, { persona: 'none' })).body).toMatchObject({ code: 'forbidden' });
    expect((await outcome('W-2103', body, { csrf: null })).body).toEqual({ code: 'csrf_failed', message: 'Your session check failed. Reload and try again.' });
    expect((await outcome('W-2999', body)).status).toBe(404);
  });

  it('checks in order: scenario, CSRF, persona, record, schema, rules, revision, grant', async () => {
    expect((await outcome('W-2999', {}, { csrf: null, headers: { 'X-Mock-Scenario': '401' } })).status).toBe(401);
    expect((await outcome('W-2999', {}, { csrf: null })).body.code).toBe('csrf_failed');
    expect((await outcome('W-2999', {}, { persona: 'none' })).body.code).toBe('forbidden');
    expect((await outcome('W-2999', {})).status).toBe(404);
    expect((await outcome('W-2103', {})).status).toBe(422);
    const body = await outcomeBody();
    expect(fields(await outcome('W-2103', { ...body, result: 'won', expected_revision: 1, record_as: 'ceo' }))).toBe('Check these fields: record_as.');
    for (const status of [401, 403, 404, 409, 422]) {
      const r = await outcome('W-2103', body, { headers: { 'X-Mock-Scenario': String(status) } });
      expect(r.status).toBe(status);
      expect(Object.keys(r.body).sort()).toEqual(['code', 'message']);
    }
  });

  it('record-then-fail records the outcome, then answers 502; the repeat is a 409', async () => {
    const body = await outcomeBody();
    expect((await outcome('W-2103', body, { headers: { 'X-Mock-Scenario': 'record-then-fail' } })).status).toBe(502);
    expect((await getItem('W-2103')).rfp_outcome!.recorded).toMatchObject({ result: 'lost' });
    expect((await outcome('W-2103', body)).status).toBe(409);
  });
});

const followup = (workId: string, body: unknown, init?: Parameters<typeof post>[3]) => post(`/api/v1/work/${workId}/rfp-outcome/followup`, 'E-RFP-FOLLOWUP', body, init);
async function sendBody(workId: string, extra: Record<string, unknown> = {}) {
  const item = (await getItem(workId)) as Awaited<ReturnType<typeof getItem>> & { rfp_outcome: { followup: { version: number } } };
  return { expected_revision: item.revision, version: item.rfp_outcome.followup.version, idempotency_key: `key-${workId}-${Math.random()}`, ...extra };
}

describe('E-RFP-FOLLOWUP', () => {
  it('W-2108 answers sent (valid v7) and serves W-2108.sent; the same key returns the same reply with no second effect', async () => {
    const body = await sendBody('W-2108');
    const first = await followup('W-2108', body);
    expect(first).toEqual({ status: 200, body: { work_id: 'W-2108', status: 'sent', revision: 8 } });
    const after = (await getItem('W-2108')) as unknown as Record<string, unknown> & { revision: number; rfp_outcome: { followup: { status: string; can_send: boolean } } };
    expect(after.rfp_outcome.followup).toMatchObject({ status: 'sent', can_send: false });
    expect(await followup('W-2108', body)).toEqual(first);
    expect((await getItem('W-2108')).revision).toBe(8);
    expect((await followup('W-2108', { ...body, idempotency_key: 'another' })).status).toBe(409);
  });

  it('sends edited text as the draft; 422 for a blank body', async () => {
    const body = await sendBody('W-2108');
    expect(fields(await followup('W-2108', { ...body, body: '  ' }))).toBe('Check these fields: body.');
    expect((await followup('W-2108', { ...body, body: 'Any news?' })).status).toBe(200);
    expect(((await getItem('W-2108')) as unknown as { rfp_outcome: { followup: { body: string } } }).rfp_outcome.followup.body).toBe('Any news?');
  });

  it('W-2111 answers effect_uncertain and serves the draft in that state, with no Send', async () => {
    const r = await followup('W-2111', await sendBody('W-2111'));
    expect(r.body.status).toBe('effect_uncertain');
    expect(((await getItem('W-2111')) as unknown as { rfp_outcome: { followup: Record<string, unknown> } }).rfp_outcome.followup).toMatchObject({ status: 'effect_uncertain', can_send: false });
    expect((await followup('W-2111', await sendBody('W-2111'))).status).toBe(403);
  });

  it('W-2112 answers 409 once and serves v3; a send of v3 then goes', async () => {
    const first = await followup('W-2112', await sendBody('W-2112'));
    expect(first.status).toBe(409);
    const next = await sendBody('W-2112');
    expect(next).toMatchObject({ version: 3, expected_revision: 8 });
    expect((await followup('W-2112', next)).status).toBe(200);
  });

  it('409 on a stale revision or version; 403 without can_send (W-2113), already uncertain (W-2114), for persona none or without CSRF', async () => {
    const body = await sendBody('W-2108');
    expect((await followup('W-2108', { ...body, expected_revision: 1 })).status).toBe(409);
    expect((await followup('W-2108', { ...body, version: 9 })).status).toBe(409);
    expect((await followup('W-2113', await sendBody('W-2113'))).status).toBe(403);
    expect((await followup('W-2114', await sendBody('W-2114'))).status).toBe(403);
    expect((await followup('W-2108', body, { persona: 'none' })).body.code).toBe('forbidden');
    expect((await followup('W-2108', body, { csrf: null })).body.code).toBe('csrf_failed');
    expect((await followup('W-2999', body)).status).toBe(404);
    expect((await followup('W-2108', { ...body, idempotency_key: undefined })).status).toBe(422);
  });

  it('scenarios answer their status; record-then-fail sends, then answers 502, and the same key returns the stored 200', async () => {
    const body = await sendBody('W-2108');
    for (const status of [401, 403, 404, 409, 422]) expect((await followup('W-2108', body, { headers: { 'X-Mock-Scenario': String(status) } })).status).toBe(status);
    expect((await followup('W-2108', body, { headers: { 'X-Mock-Scenario': 'record-then-fail' } })).status).toBe(502);
    expect(((await getItem('W-2108')) as unknown as { rfp_outcome: { followup: { status: string } } }).rfp_outcome.followup.status).toBe('sent');
    expect((await followup('W-2108', body)).body).toMatchObject({ status: 'sent' });
  });
});
