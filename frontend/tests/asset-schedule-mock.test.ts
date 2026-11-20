// F-42: the fixed asset schedule fixtures (W-3901 to W-3912) and the contract mock's claim and decide on them. Every item
// and sidecar validates against the generated E-WORK-ITEM schema once the two overlay fields are removed: `steps[].verdict`
// (F-33 G-C-1) and `workspace.links` (X-LINKS, checked in mock-contract). Contract mock only.
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

type Item = {
  id: string;
  state: string;
  sample: boolean;
  revision: number;
  tasks: { id: string; you_can_act: boolean; revision: number; required_role: string; cannot_act_reason?: string }[];
  workspace: { line_key: string; revision: number; links?: unknown; steps?: { key: string; task_id?: string; verdict?: unknown }[]; status: { label: string; tone?: string }; sections: { key: string; title?: string }[]; next?: string[] };
};

/** The overlay fields removed before the contract check: each step's `verdict` (one of three, only with a task_id) and the links. */
function stripped(body: Item): unknown {
  const copy = structuredClone(body);
  for (const step of copy.workspace.steps ?? []) {
    if (step.verdict === undefined) continue;
    expect(typeof step.task_id, step.key).toBe('string');
    expect(['approve', 'return', 'reject'], step.key).toContain(step.verdict);
    delete step.verdict;
  }
  delete copy.workspace.links;
  return copy;
}

const workDir = join(__dirname, '../mock/fixtures/work');
const names = readdirSync(workDir).filter((name) => /^W-39\d\d(\.[a-z]+)?\.json$/.test(name));
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

describe('F-42 fixtures', () => {
  it('twelve items and their decide sidecars are schema-valid once the overlay is stripped; every one is sample and on the fixed_assets line', () => {
    expect(names.filter((name) => /^W-39\d\d\.json$/.test(name))).toHaveLength(12);
    expect(names.filter((name) => !/^W-39\d\d\.json$/.test(name)).sort()).toEqual([
      'W-3902.approve.json',
      'W-3902.reject.json',
      'W-3902.return.json',
      'W-3903.approve.json',
      'W-3903.reject.json',
      'W-3903.return.json',
      'W-3911.approve.json',
      'W-3911.reject.json',
      'W-3911.return.json',
    ]);
    for (const name of names) {
      const body = readItem(name);
      expectValid('E-WORK-ITEM', 200, stripped(body));
      expect(body.sample, name).toBe(true);
      expect(body.workspace.line_key, name).toBe('fixed_assets');
      expect(body, name).toMatchObject({ reference: 'PPE-0006', title: 'Fixed asset schedule · October', line: 'Fixed asset schedule', workspace: { screen: 'SCR-55' } });
    }
  });

  it('every cost is a decimal string, or unknown with no amount; W-3910 carries the unknown one; no fixture has a next sidecar (it would make the first decide 409)', () => {
    let unknowns = 0;
    for (const name of names) {
      const text = readFileSync(join(workDir, name), 'utf8');
      for (const money of text.match(/"money": \{[^}]*\}/g) ?? []) {
        const value = JSON.parse(money.slice(money.indexOf('{'))) as { amount?: string; unknown: boolean };
        if (value.unknown) {
          expect(value.amount, name).toBeUndefined();
          unknowns += 1;
          expect(name).toBe('W-3910.json');
        } else expect(value.amount, name).toMatch(/^\d+\.\d{2}$/);
      }
    }
    expect(unknowns).toBe(1);
    expect(names.some((name) => name.includes('.next'))).toBe(false);
  });

  it('the W-39xx task ids are unique: no other base fixture in the mock uses one, and no two W-39xx items share one', () => {
    const owners = new Map<string, string[]>();
    for (const name of readdirSync(workDir).filter((n) => /^W-\d+\.json$/.test(n))) {
      for (const t of (JSON.parse(readFileSync(join(workDir, name), 'utf8')) as Item).tasks ?? []) owners.set(t.id, [...(owners.get(t.id) ?? []), name]);
    }
    const ours = [...owners].filter(([id, files]) => id.startsWith('T-39') || files.some((f) => f.startsWith('W-39')));
    expect(ours.length).toBe(13);
    for (const [id, files] of ours) expect(files, id).toHaveLength(1);
    expect(owners.get('T-3902')).toEqual(['W-3902.json']);
    expect(owners.get('T-3903')).toEqual(['W-3903.json']);
  });

  it('the holds W-3907, W-3908 and W-3909 have no step, no task anyone can act on and name no reviewer', () => {
    for (const [name, label] of [
      ['W-3907.json', 'Who reviews assets'],
      ['W-3908.json', 'Register rules'],
      ['W-3909.json', 'Calculation rules'],
    ] as const) {
      const hold = readItem(name);
      expect(hold.state, name).toBe('setup_needed');
      expect(hold.workspace.status).toEqual({ label: 'SETUP NEEDED', tone: 'stopped' });
      expect(hold.workspace.steps, name).toBeUndefined();
      expect(hold.tasks.every((t) => !t.you_can_act && t.cannot_act_reason === 'already_decided'), name).toBe(true);
      expect(JSON.stringify(hold.workspace), name).toContain(label);
      expect(JSON.stringify(hold.workspace), name).not.toMatch(/Ada Okafor|PPE reviewer|PROCESSING|"money"/);
    }
    expect(readItem('W-3907.json').tasks).toEqual([]);
    expect(readItem('W-3908.json').tasks).toEqual([]);
    expect(readItem('W-3909.json').workspace.sections.map((s) => s.key)).toEqual(['held']);
  });

  it('each sidecar leaves no task the person can act on and no verdict step', () => {
    for (const name of names.filter((n) => !/^W-39\d\d\.json$/.test(n))) {
      const body = readItem(name);
      expect(body.tasks.every((t) => !t.you_can_act && t.cannot_act_reason === 'already_decided'), name).toBe(true);
      expect(body.workspace.steps, name).toBeUndefined();
    }
  });
});

describe('F-42 claim and decide on the mock', () => {
  it('claim then approve on W-3902 serves the waiting sidecar with no date-review task; a second decide is refused', async () => {
    expect((await task('claim', 'T-3902', { expected_revision: 1 })).status).toBe(200);
    const result = await task('decision', 'T-3902', { verdict: 'approve', expected_revision: 1 });
    expect(result).toMatchObject({ status: 200, body: { task_id: 'T-3902', verdict: 'approve' } });
    const now = await getItem('W-3902');
    expect(now.state).toBe('waiting');
    expect(now.tasks).toHaveLength(1);
    expect(now.tasks[0]).toMatchObject({ you_can_act: false, cannot_act_reason: 'already_decided', revision: 2 });
    expect((await task('decision', 'T-3902', { verdict: 'approve', expected_revision: 1 })).status).toBe(409);
  });

  it('claim then approve on W-3903 decides T-3903 only and serves the calculating sidecar', async () => {
    expect((await task('claim', 'T-3903', { expected_revision: 1 })).status).toBe(200);
    expect((await task('decision', 'T-3903', { verdict: 'approve', expected_revision: 1 })).status).toBe(200);
    const now = await getItem('W-3903');
    expect(now.state).toBe('processing');
    expect(now.workspace.status.label).toBe('PROCESSING');
    expect(now.workspace.sections.map((s) => s.title)).toEqual(['Calculation']);
    expect(now.tasks.map((t) => [t.id, t.cannot_act_reason])).toEqual([
      ['T-3931', 'already_decided'],
      ['T-3903', 'already_decided'],
    ]);
  });

  it('the decided register task on W-3903 refuses a claim and a decide', async () => {
    expect((await task('claim', 'T-3931', { expected_revision: 1 })).status).toBeGreaterThanOrEqual(400);
    expect((await task('decision', 'T-3931', { verdict: 'approve', expected_revision: 1 })).status).toBeGreaterThanOrEqual(400);
    expect((await getItem('W-3903')).state).toBe('action_needed');
  });

  it('return without a note is 422; with one it serves RETURNED; reject serves REJECTED (cancelled)', async () => {
    expect((await task('decision', 'T-3902', { verdict: 'return', expected_revision: 1 })).status).toBe(422);
    expect((await task('decision', 'T-3902', { verdict: 'reject', expected_revision: 1, note: '   ' })).status).toBe(422);
    expect((await task('decision', 'T-3902', { verdict: 'return', expected_revision: 1, note: 'Hilux date.' })).status).toBe(200);
    const returned = await getItem('W-3902');
    expect(returned.workspace.status).toEqual({ label: 'RETURNED', tone: 'person' });
    expect(returned.workspace.next).toBeUndefined();
    await fetch(`${base}/__mock/reset`, { method: 'POST' });
    expect((await task('decision', 'T-3903', { verdict: 'reject', expected_revision: 1, note: 'No.' })).status).toBe(200);
    const rejected = await getItem('W-3903');
    expect(rejected.state).toBe('cancelled');
    expect(rejected.workspace.status).toEqual({ label: 'REJECTED', tone: 'stopped' });
  });

  it('a stale revision is 409; W-3905, W-3906 and W-3912 refuse with 403; reset clears', async () => {
    expect((await task('decision', 'T-3902', { verdict: 'approve', expected_revision: 7 })).status).toBe(409);
    expect((await task('decision', 'T-3905', { verdict: 'approve', expected_revision: 1 })).status).toBe(403);
    expect((await task('claim', 'T-3905', { expected_revision: 1 })).status).toBe(403);
    expect((await task('decision', 'T-3906', { verdict: 'approve', expected_revision: 1 })).status).toBe(403);
    expect((await task('decision', 'T-3912', { verdict: 'approve', expected_revision: 1 })).status).toBe(403);
    expect((await task('decision', 'T-3902', { verdict: 'approve', expected_revision: 1 })).status).toBe(200);
    expect((await getItem('W-3902')).state).toBe('waiting');
    await fetch(`${base}/__mock/reset`, { method: 'POST' });
    expect((await getItem('W-3902')).state).toBe('action_needed');
  });

  it('W-3911: each verdict answers 200 with work_state effect_uncertain and the re-read is effect_uncertain', async () => {
    for (const [verdict, note] of [['approve', undefined], ['return', 'Hilux date.'], ['reject', 'No.']] as const) {
      await fetch(`${base}/__mock/reset`, { method: 'POST' });
      const result = await task('decision', 'T-3911', { verdict, expected_revision: 1, ...(note ? { note } : {}) });
      expect(result, verdict).toMatchObject({ status: 200, body: { verdict, work_state: 'effect_uncertain' } });
      const now = await getItem('W-3911');
      expect(now.state).toBe('effect_uncertain');
      expect(now.workspace.status).toEqual({ label: 'DECISION NOT CONFIRMED', tone: 'uncertain' });
    }
  });
});
