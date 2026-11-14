import { readdirSync, readFileSync } from 'node:fs';
import type { Server } from 'node:http';
import type { AddressInfo } from 'node:net';
import { join } from 'node:path';

import Ajv2020 from 'ajv/dist/2020';
import addFormats from 'ajv-formats';
import { afterAll, beforeAll, beforeEach, describe, expect, it } from 'vitest';

// @ts-expect-error plain ESM module without type declarations
import { OPENAPI_PATH, startMockServer } from '../mock/server.mjs';

type Schema = { content: { 'application/json': { schema: object } } };
type Operation = { operationId: string; responses: Record<string, Schema> };
const openapi = JSON.parse(readFileSync(OPENAPI_PATH, 'utf8')) as { paths: Record<string, Record<string, Operation>> };
const ops = Object.values(openapi.paths).flatMap((byMethod) => Object.values(byMethod));
const byId = (id: string) => ops.find((op) => op && typeof op === 'object' && op.operationId === id)!;

const ajv = new Ajv2020({ allErrors: true, strict: true });
addFormats(ajv);
const errorSchema = byId('E-ME').responses['401'].content['application/json'].schema;
function expectValid(id: string, status: number, body: unknown) {
  const declared = byId(id).responses[String(status)];
  const validate = ajv.compile(declared ? declared.content['application/json'].schema : errorSchema);
  expect(validate(body), `${id} ${status}: ${ajv.errorsText(validate.errors)}`).toBe(true);
}

const workDir = join(__dirname, '../mock/fixtures/work');
const readJson = (name: string) => JSON.parse(readFileSync(join(workDir, name), 'utf8')) as Record<string, unknown>;

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

const COOKIE = 'psl_mock_persona=finance_lead';
const CSRF = 'mock-csrf-finance_lead';

async function post(op: 'claim' | 'decision', taskId: string, body: unknown, init: { raw?: string; headers?: Record<string, string> } = {}) {
  const response = await fetch(`${base}/api/v1/tasks/${taskId}/${op}`, {
    method: 'POST',
    headers: { Cookie: COOKIE, 'X-CSRFToken': CSRF, 'Content-Type': 'application/json', ...init.headers },
    body: init.raw ?? JSON.stringify(body),
  });
  const result = { status: response.status, body: (await response.json()) as Record<string, unknown> };
  expectValid(op === 'claim' ? 'E-TASK-CLAIM' : 'E-TASK-DECIDE', result.status, result.body);
  return result;
}
const claim = (taskId: string, body: unknown, init?: Parameters<typeof post>[3]) => post('claim', taskId, body, init);
const decide = (taskId: string, body: unknown, init?: Parameters<typeof post>[3]) => post('decision', taskId, body, init);

async function getItem(id: string) {
  const response = await fetch(`${base}/api/v1/work/${id}`, { headers: { Cookie: COOKIE } });
  const body = (await response.json()) as Record<string, unknown>;
  expectValid('E-WORK-ITEM', response.status, body);
  return body;
}

describe('claim and decide validation', () => {
  it('claim: missing and extra properties name the field; a wrong revision is 409; the right one claims', async () => {
    expect(await claim('T-1201', {})).toEqual({ status: 422, body: { code: 'invalid', message: 'Check these fields: expected_revision.' } });
    expect(await claim('T-1201', { expected_revision: 2, x: 1 })).toEqual({ status: 422, body: { code: 'invalid', message: 'Check these fields: x.' } });
    const stale = await claim('T-1201', { expected_revision: 1 });
    expect(stale.status).toBe(409);
    expect(stale.body.code).toBe('stale_revision');
    expect(await claim('T-1201', { expected_revision: 2 })).toEqual({
      status: 200,
      body: { task_id: 'T-1201', revision: 2, claimed_by: 'Ada Okafor' },
    });
    // idempotent, and it does not move the revision
    expect((await claim('T-1201', { expected_revision: 2 })).status).toBe(200);
  });

  it('claim names the persona that claims', async () => {
    const result = await claim('T-1201', { expected_revision: 2 }, { headers: { Cookie: 'psl_mock_persona=pm', 'X-CSRFToken': 'mock-csrf-pm' } });
    expect(result.body.claimed_by).toBe('Tunde Bello');
  });

  it('decide: an unknown verdict, a missing or blank note to return or reject, and an over-long note are 422', async () => {
    const maybe = await decide('T-1201', { expected_revision: 2, verdict: 'maybe' });
    expect(maybe).toEqual({ status: 422, body: { code: 'invalid', message: 'Check these fields: verdict.' } });
    const noteError = { status: 422, body: { code: 'invalid', message: 'Check these fields: note.' } };
    expect(await decide('T-1201', { expected_revision: 2, verdict: 'return' })).toEqual(noteError);
    expect(await decide('T-1201', { expected_revision: 2, verdict: 'reject', note: '   ' })).toEqual(noteError);
    expect(await decide('T-1201', { expected_revision: 2, verdict: 'return', note: 'x'.repeat(2001) })).toEqual(noteError);
    expect(await decide('T-1201', { expected_revision: 2, verdict: 'approve', note: 'x'.repeat(2001) })).toEqual(noteError);
    expect(await decide('T-1201', { expected_revision: 2, verdict: 'approve', note: 3 })).toEqual(noteError);
    // nothing was decided
    expect(((await getItem('W-1201')).tasks as { you_can_act: boolean }[])[0].you_can_act).toBe(true);
  });

  it('decide: revoke with a note is not mocked', async () => {
    const result = await decide('T-1201', { expected_revision: 2, verdict: 'revoke', note: 'Withdrawn' });
    expect(result).toEqual({ status: 501, body: { code: 'not_mocked', message: 'Not available in the mock yet.' } });
  });

  it('a task you cannot act on is 403, an unknown task 404 and invalid JSON 422', async () => {
    expect(await claim('T-1203', { expected_revision: 2 })).toEqual({
      status: 403,
      body: { code: 'forbidden', message: 'Your role does not allow this.' },
    });
    expect((await decide('T-1204', { expected_revision: 2, verdict: 'approve' })).status).toBe(403);
    expect(await claim('T-9999', { expected_revision: 2 })).toEqual({
      status: 404,
      body: { code: 'not_found', message: 'We could not find that record.' },
    });
    expect(await claim('T-1201', null, { raw: '{"expected_revision":' })).toEqual({
      status: 422,
      body: { code: 'invalid', message: 'Check these fields: body.' },
    });
    expect(await claim('T-1201', [])).toEqual({ status: 422, body: { code: 'invalid', message: 'Check these fields: body.' } });
  });

  it('scenarios still win, and a write without the CSRF header is 403 csrf_failed', async () => {
    const scenario = await claim('T-1201', { expected_revision: 2 }, { headers: { Cookie: `${COOKIE}; psl_mock_scenario=409` } });
    expect(scenario.status).toBe(409);
    const response = await fetch(`${base}/api/v1/tasks/T-1201/decision`, {
      method: 'POST',
      headers: { Cookie: COOKIE, 'Content-Type': 'application/json' },
      body: JSON.stringify({ expected_revision: 2, verdict: 'approve' }),
    });
    expect(response.status).toBe(403);
    expect(((await response.json()) as { code: string }).code).toBe('csrf_failed');
  });
});

describe('stale and done flows', () => {
  it('T-1207: decide at revision 4 is 409, then the item is version 3 at revision 5 and can be decided', async () => {
    expect((await claim('T-1207', { expected_revision: 4 })).status).toBe(200);
    expect((await decide('T-1207', { expected_revision: 4, verdict: 'approve' })).status).toBe(409);
    const item = (await getItem('W-1207')) as { revision: number; tasks: { revision: number; decision: { version: { number: number } } }[] };
    expect(item.revision).toBe(5);
    expect(item.tasks[0].revision).toBe(5);
    expect(item.tasks[0].decision.version.number).toBe(3);
    expect((await decide('T-1207', { expected_revision: 4, verdict: 'approve' })).status).toBe(409);
    expect((await claim('T-1207', { expected_revision: 5 })).status).toBe(200);
    const done = await decide('T-1207', { expected_revision: 5, verdict: 'approve' });
    expect(done.status).toBe(200);
    expect(done.body).toMatchObject({ task_id: 'T-1207', verdict: 'approve', decided_by: 'Ada Okafor', work_state: 'waiting' });
  });

  it('T-1201 approve: work_state ready, the approved sidecar is served, and a repeat decide is 409', async () => {
    const result = await decide('T-1201', { expected_revision: 2, verdict: 'approve' });
    expect(result.status).toBe(200);
    expect(result.body).toMatchObject({ task_id: 'T-1201', verdict: 'approve', decided_by: 'Ada Okafor', work_state: 'ready' });
    expect(Number.isNaN(Date.parse(result.body.decided_at as string))).toBe(false);
    expect(await getItem('W-1201')).toEqual(readJson('W-1201.approve.json'));
    expect((await decide('T-1201', { expected_revision: 2, verdict: 'approve' })).status).toBe(409);
  });

  it('T-1201 return with a note serves the returned sidecar', async () => {
    const result = await decide('T-1201', { expected_revision: 2, verdict: 'return', note: 'Wrong PO' });
    expect(result.body.work_state).toBe('action_needed');
    expect(await getItem('W-1201')).toEqual(readJson('W-1201.return.json'));
  });

  it('a decide without a sidecar leaves the item unchanged (W-1001 / T-2001)', async () => {
    const before = await getItem('W-1001');
    const result = await decide('T-2001', { expected_revision: 2, verdict: 'approve' });
    expect(result.body.work_state).toBe('waiting');
    expect(await getItem('W-1001')).toEqual(before);
  });

  it('reset puts W-1201 and W-1207 back to their base fixtures; other ids still get the default item', async () => {
    await decide('T-1201', { expected_revision: 2, verdict: 'approve' });
    await decide('T-1207', { expected_revision: 4, verdict: 'approve' });
    const reset = await fetch(`${base}/__mock/reset`, { method: 'POST' });
    expect(reset.status).toBe(204);
    expect(await getItem('W-1201')).toEqual(readJson('W-1201.json'));
    expect(await getItem('W-1207')).toEqual(readJson('W-1207.json'));
    const fallback = JSON.parse(readFileSync(join(__dirname, '../mock/fixtures/E-WORK-ITEM.json'), 'utf8'));
    expect(await getItem('ANY-OTHER')).toEqual(fallback);
  });
});

describe('F-04 fixtures', () => {
  const files = readdirSync(workDir).filter((name) => /^W-12\d\d(\.\w+)?\.json$/.test(name));
  type Task = { id: string; kind: string; you_can_act: boolean; cannot_act_reason?: string; decision?: object };

  it('cover W-1201 to W-1208 and their sidecars', () => {
    expect(files.sort()).toEqual(
      [
        'W-1201.approve.json',
        'W-1201.json',
        'W-1201.reject.json',
        'W-1201.return.json',
        'W-1202.json',
        'W-1203.json',
        'W-1204.json',
        'W-1205.json',
        'W-1206.json',
        'W-1207.json',
        'W-1207.next.json',
        'W-1208.json',
      ].sort(),
    );
  });

  it.each(files)('%s is valid against v4 E-WORK-ITEM, sample, and gives a reason only when you cannot act', (name) => {
    const body = readJson(name);
    expectValid('E-WORK-ITEM', 200, body);
    expect(body.sample).toBe(true);
    for (const task of body.tasks as Task[]) {
      expect(task.kind).toBe('decide');
      if (task.you_can_act) expect(task).not.toHaveProperty('cannot_act_reason');
      else expect(typeof task.cannot_act_reason).toBe('string');
    }
  });
});
