// F-39: the escalation fixtures (W-3601 to W-3609) and the contract mock's claim, decide and step on them. Every item and
// sidecar validates against the generated E-WORK-ITEM schema once the two overlay fields are removed: `steps[].verdict`
// (F-33 G-C-1) and `workspace.links` (X-LINKS). Nothing here is sent to anyone: contract mock only.
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

type Item = { id: string; state: string; sample: boolean; revision: number; tasks: { id: string; you_can_act: boolean; revision: number; cannot_act_reason?: string }[]; workspace: { line_key: string; revision: number; links?: unknown; steps?: { key: string; task_id?: string; verdict?: unknown; sends?: unknown }[]; status: { label: string } } };

function stripped(body: Item): unknown {
  const copy = structuredClone(body);
  for (const step of copy.workspace.steps ?? []) {
    if (step.verdict === undefined) continue;
    expect(typeof step.task_id, step.key).toBe('string');
    delete step.verdict;
  }
  delete copy.workspace.links;
  return copy;
}

const workDir = join(__dirname, '../mock/fixtures/work');
const names = readdirSync(workDir).filter((name) => /^W-36\d\d(\.[a-z]+)?\.json$/.test(name));
const readItem = (name: string) => JSON.parse(readFileSync(join(workDir, name), 'utf8')) as Item;

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

const COOKIE = 'psl_mock_persona=pm';
const headers = { Cookie: COOKIE, 'X-CSRFToken': 'mock-csrf-pm', 'Content-Type': 'application/json' };

async function task(op: 'claim' | 'decision', taskId: string, body: unknown) {
  const response = await fetch(`${base}/api/v1/tasks/${taskId}/${op}`, { method: 'POST', headers, body: JSON.stringify(body) });
  const result = { status: response.status, body: (await response.json()) as Record<string, unknown> };
  expectValid(op === 'claim' ? 'E-TASK-CLAIM' : 'E-TASK-DECIDE', result.status, result.body);
  return result;
}
async function getItem(id: string) {
  const response = await fetch(`${base}/api/v1/work/${id}`, { headers: { Cookie: COOKIE } });
  const body = (await response.json()) as Item;
  expectValid('E-WORK-ITEM', response.status, stripped(body));
  return body;
}

describe('F-39 fixtures', () => {
  it('nine items and their sidecars are schema-valid once the overlay is stripped, and every one is sample', () => {
    expect(names.filter((name) => /^W-36\d\d\.json$/.test(name))).toHaveLength(9);
    expect(names.filter((name) => !/^W-36\d\d\.json$/.test(name)).sort()).toEqual(['W-3602.approve.json', 'W-3602.reject.json', 'W-3604.next.json', 'W-3604.steps.json', 'W-3607.approve.json']);
    for (const name of names.filter((n) => !n.includes('.steps'))) {
      const body = readItem(name);
      expectValid('E-WORK-ITEM', 200, stripped(body));
      expect(body.sample, name).toBe(true);
    }
  });

  it('no step sets sends, and no decide fixture has a next sidecar (it would make the first decide 409)', () => {
    for (const name of names) expect(readFileSync(join(workDir, name), 'utf8'), name).not.toContain('"sends"');
    expect(names).not.toContain('W-3602.next.json');
  });

  it('W-3608 holds Send for review with the backend reason and names no reviewer', () => {
    const hold = readItem('W-3608.json');
    expect(hold.workspace.steps).toHaveLength(1);
    expect(hold.workspace.steps![0]).toMatchObject({ key: 'send_for_review', disabled_reason: expect.stringContaining('No one is set to review') });
    expect(JSON.stringify(hold)).not.toMatch(/Kemi|Ada Okafor/);
  });
});

describe('F-39 claim, decide and step on the mock', () => {
  it('claim then approve on W-3602 serves the drafted sidecar; a second decide is refused', async () => {
    expect((await task('claim', 'T-3602', { expected_revision: 1 })).status).toBe(200);
    const result = await task('decision', 'T-3602', { verdict: 'approve', expected_revision: 1 });
    expect(result).toMatchObject({ status: 200, body: { task_id: 'T-3602', verdict: 'approve', work_state: 'action_needed' } });
    const now = await getItem('W-3602');
    expect(now.workspace.status.label).toBe('MESSAGE DRAFTED');
    expect(now.tasks[0]).toMatchObject({ you_can_act: false, cannot_act_reason: 'already_decided', revision: 2 });
    expect((await task('decision', 'T-3602', { verdict: 'approve', expected_revision: 1 })).status).toBe(409);
  });

  it('reject without a note is 422; with one it serves the not-escalated sidecar', async () => {
    expect((await task('decision', 'T-3602', { verdict: 'reject', expected_revision: 1 })).status).toBe(422);
    expect((await task('decision', 'T-3602', { verdict: 'reject', expected_revision: 1, note: '   ' })).status).toBe(422);
    expect((await task('decision', 'T-3602', { verdict: 'reject', expected_revision: 1, note: 'Their new lead starts Monday.' })).status).toBe(200);
    const now = await getItem('W-3602');
    expect(now.workspace.status.label).toBe('NOT ESCALATED');
    expect(now.state).toBe('cancelled');
  });

  it('a stale revision is 409; W-3605 refuses the decide with 403; reset clears', async () => {
    expect((await task('decision', 'T-3602', { verdict: 'approve', expected_revision: 7 })).status).toBe(409);
    expect((await task('decision', 'T-3605', { verdict: 'approve', expected_revision: 1 })).status).toBe(403);
    expect((await task('claim', 'T-3605', { expected_revision: 1 })).status).toBe(403);
    expect((await task('decision', 'T-3602', { verdict: 'approve', expected_revision: 1 })).status).toBe(200);
    await fetch(`${base}/__mock/reset`, { method: 'POST' });
    expect((await getItem('W-3602')).workspace.status.label).toBe('YOUR DECISION');
  });

  it('W-3607: approve answers 200 with work_state effect_uncertain and the re-read is effect_uncertain', async () => {
    const result = await task('decision', 'T-3607', { verdict: 'approve', expected_revision: 1 });
    expect(result).toMatchObject({ status: 200, body: { verdict: 'approve', work_state: 'effect_uncertain' } });
    const now = await getItem('W-3607');
    expect(now.state).toBe('effect_uncertain');
    expect(now.workspace.status.label).toBe('RESULT NOT CONFIRMED');
  });

  it('the W-3604 send_for_review step serves the next sidecar: waiting for review, the PMO Lead cannot act on it here', async () => {
    const response = await fetch(`${base}/api/v1/work/W-3604/steps`, {
      method: 'POST',
      headers,
      body: JSON.stringify({ expected_revision: 2, step: 'send_for_review', inputs: {}, idempotency_key: crypto.randomUUID() }),
    });
    expect(response.status).toBe(200);
    expect(await response.json()).toMatchObject({ work_id: 'W-3604', outcome: 'done' });
    const now = await getItem('W-3604');
    expect(now.workspace.status.label).toBe('WAITING FOR REVIEW');
    expect(now.tasks[0]).toMatchObject({ id: 'T-3610', you_can_act: false, cannot_act_reason: 'not_your_role' });
    await fetch(`${base}/__mock/reset`, { method: 'POST' });
    expect((await getItem('W-3604')).workspace.status.label).toBe('MESSAGE DRAFTED');
  });
});
