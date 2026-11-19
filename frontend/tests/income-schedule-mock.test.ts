// F-33: the income schedule fixtures (W-2701 to W-2711) and the contract mock's claim, decide and step on them. Every item
// and sidecar validates against the generated E-WORK-ITEM schema once the two overlay fields are removed: `steps[].verdict`
// (G-C-1) and `workspace.links` (X-LINKS, checked in mock-contract). Contract mock only.
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

type Item = { id: string; state: string; sample: boolean; revision: number; tasks: { id: string; you_can_act: boolean; revision: number; cannot_act_reason?: string }[]; workspace: { revision: number; links?: unknown; steps?: { key: string; task_id?: string; verdict?: unknown }[]; status: { label: string } } };

/** The overlay fields removed before the contract check: each step's `verdict` (one of three, only with a task_id) and the links. */
function stripped(body: Item): unknown {
  const copy = structuredClone(body);
  for (const step of copy.workspace.steps ?? []) {
    if (step.verdict === undefined) continue;
    expect(typeof step.task_id, step.key).toBe('string');
    expect(typeof step.verdict, step.key).toBe('string');
    delete step.verdict;
  }
  delete copy.workspace.links;
  return copy;
}

const workDir = join(__dirname, '../mock/fixtures/work');
const names = readdirSync(workDir).filter((name) => /^W-27\d\d(\.[a-z]+)?\.json$/.test(name));
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

const COOKIE = 'psl_mock_persona=finance_lead';
const CSRF = 'mock-csrf-finance_lead';
const headers = { Cookie: COOKIE, 'X-CSRFToken': CSRF, 'Content-Type': 'application/json' };

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

describe('F-33 fixtures', () => {
  it('twelve items and their sidecars are schema-valid once the overlay is stripped, and every one is sample', () => {
    expect(names.filter((name) => /^W-27\d\d\.json$/.test(name))).toHaveLength(12);
    expect(names.filter((name) => !/^W-27\d\d\.json$/.test(name)).sort()).toEqual(['W-2702.approve.json', 'W-2702.reject.json', 'W-2702.return.json', 'W-2703.next.json', 'W-2703.steps.json', 'W-2712.approve.json', 'W-2712.reject.json', 'W-2712.return.json']);
    for (const name of names.filter((n) => !n.includes('.steps'))) {
      const body = readItem(name);
      expectValid('E-WORK-ITEM', 200, stripped(body));
      expect(body.sample, name).toBe(true);
      expect((body as unknown as { workspace: { line_key: string } }).workspace.line_key, name).toBe('income_schedules');
    }
  });

  it('every amount is a decimal string, or unknown with no amount; no review fixture has a next sidecar (it would make the first decide 409)', () => {
    for (const name of names.filter((n) => !n.includes('.steps'))) {
      const text = readFileSync(join(workDir, name), 'utf8');
      for (const money of text.match(/"money": \{[^}]*\}/g) ?? []) {
        const value = JSON.parse(money.slice(money.indexOf('{'))) as { amount?: string; unknown: boolean };
        if (value.unknown) expect(value.amount, name).toBeUndefined();
        else expect(value.amount, name).toMatch(/^-?\d+\.\d{2}$/);
      }
    }
    expect(names).not.toContain('W-2702.next.json');
  });

  it('the verdict overlay appears only on W-27xx (and F-35 W-32xx, F-39 W-36xx, F-42 W-39xx, F-43 W-40xx) steps that carry a task id; W-2706 names no reviewer and has no task', () => {
    const all = readdirSync(workDir).filter((name) => name.endsWith('.json'));
    const carrying = all.filter((name) => /"verdict"/.test(readFileSync(join(workDir, name), 'utf8')));
    // F-39's escalation boards (W-36xx) reuse the same overlay for their decide steps
    // F-35 reuses the overlay on the leadership report's review fixtures (W-32xx)
    expect(carrying.every((name) => /^W-(27|32|36|39|40)/.test(name))).toBe(true);
    const hold = readItem('W-2706.json');
    expect(hold.tasks).toEqual([]);
    expect(hold.workspace.steps).toBeUndefined();
    expect(JSON.stringify(hold)).not.toMatch(/Ada Okafor|Schedules reviewer/);
  });
});

describe('F-33 claim, decide and step on the mock', () => {
  it('claim then approve on W-2702 serves the verified sidecar; a second decide is refused', async () => {
    expect((await task('claim', 'T-2702', { expected_revision: 1 })).status).toBe(200);
    const result = await task('decision', 'T-2702', { verdict: 'approve', expected_revision: 1 });
    expect(result).toMatchObject({ status: 200, body: { task_id: 'T-2702', verdict: 'approve', work_state: 'verified' } });
    const now = await getItem('W-2702');
    expect(now.state).toBe('verified');
    expect(now.workspace.status.label).toBe('VERIFIED');
    expect(now.tasks[0]).toMatchObject({ you_can_act: false, cannot_act_reason: 'already_decided', revision: 2 });
    expect((await task('decision', 'T-2702', { verdict: 'approve', expected_revision: 1 })).status).toBe(409);
  });

  it('return without a note is 422; with one it serves the returned sidecar; reject serves the rejected one', async () => {
    expect((await task('decision', 'T-2702', { verdict: 'return', expected_revision: 1 })).status).toBe(422);
    expect((await task('decision', 'T-2702', { verdict: 'return', expected_revision: 1, note: '   ' })).status).toBe(422);
    expect((await task('decision', 'T-2702', { verdict: 'return', expected_revision: 1, note: 'Row 12.' })).status).toBe(200);
    expect((await getItem('W-2702')).workspace.status.label).toBe('RETURNED · CORRECT AND RESUBMIT');
    await fetch(`${base}/__mock/reset`, { method: 'POST' });
    expect((await task('decision', 'T-2702', { verdict: 'reject', expected_revision: 1, note: 'No.' })).status).toBe(200);
    expect((await getItem('W-2702')).workspace.status.label).toBe('REJECTED');
  });

  it('a stale revision is 409; W-2705 and W-2708 refuse the decide with 403; reset clears', async () => {
    expect((await task('decision', 'T-2702', { verdict: 'approve', expected_revision: 7 })).status).toBe(409);
    expect((await task('decision', 'T-2705', { verdict: 'approve', expected_revision: 1 })).status).toBe(403);
    expect((await task('claim', 'T-2705', { expected_revision: 1 })).status).toBe(403);
    expect((await task('decision', 'T-2708', { verdict: 'approve', expected_revision: 1 })).status).toBe(403);
    expect((await task('decision', 'T-2702', { verdict: 'approve', expected_revision: 1 })).status).toBe(200);
    expect((await getItem('W-2702')).state).toBe('verified');
    await fetch(`${base}/__mock/reset`, { method: 'POST' });
    expect((await getItem('W-2702')).state).toBe('action_needed');
  });

  it('the W-2703 correction step serves the next sidecar: back in review, the preparer cannot act', async () => {
    const response = await fetch(`${base}/api/v1/work/W-2703/steps`, {
      method: 'POST',
      headers,
      body: JSON.stringify({ expected_revision: 4, step: 'correct_and_resubmit', inputs: { row_12_relationship: 'reclassification' }, idempotency_key: crypto.randomUUID() }),
    });
    expect(response.status).toBe(200);
    expect(await response.json()).toMatchObject({ work_id: 'W-2703', outcome: 'done', message: 'Sent back for review.' });
    const now = await getItem('W-2703');
    expect(now.workspace.status.label).toBe('AWAITING FINANCE DECISION');
    expect(now.tasks[0]).toMatchObject({ you_can_act: false, cannot_act_reason: 'prepared_by_you' });
    await fetch(`${base}/__mock/reset`, { method: 'POST' });
    expect((await getItem('W-2703')).workspace.status.label).toBe('RETURNED · CORRECT AND RESUBMIT');
  });

  it('W-2712: a decide answers 200 with work_state effect_uncertain and the re-read is effect_uncertain (QA in a browser)', async () => {
    for (const [verdict, note] of [['approve', undefined], ['return', 'Row 12.'], ['reject', 'No.']] as const) {
      await fetch(`${base}/__mock/reset`, { method: 'POST' });
      const result = await task('decision', 'T-2712', { verdict, expected_revision: 1, ...(note ? { note } : {}) });
      expect(result, verdict).toMatchObject({ status: 200, body: { verdict, work_state: 'effect_uncertain' } });
      expect((await getItem('W-2712')).state).toBe('effect_uncertain');
    }
  });
});
