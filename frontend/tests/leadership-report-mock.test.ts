// F-35: the leadership report fixtures (W-3201 to W-3212) and the contract mock's claim, decide and step on them. Every item
// and sidecar validates against the generated E-WORK-ITEM schema once the two overlay fields are removed: `steps[].verdict`
// (F-33 G-C-1) and `workspace.links` (X-LINKS, checked in mock-contract). Contract mock only: nothing is sent to anyone.
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

type Row = { text?: string; receipt?: string; tag?: { label: string } };
type Item = {
  id: string;
  state: string;
  sample: boolean;
  revision: number;
  tasks: { id: string; you_can_act: boolean; revision: number; cannot_act_reason?: string }[];
  workspace: { line_key: string; revision: number; links?: unknown; next?: string[]; sections: { kind: string; items: Row[] }[]; steps?: { key: string; task_id?: string; verdict?: unknown }[]; status: { label: string } };
};

/** The overlay fields removed before the contract check: each step's `verdict` (only with a task_id) and the links. */
function stripped(body: Item): unknown {
  const copy = structuredClone(body);
  for (const step of copy.workspace.steps ?? []) {
    if (step.verdict === undefined) continue;
    expect(typeof step.task_id, step.key).toBe('string');
    expect(['approve', 'return'], step.key).toContain(step.verdict);
    delete step.verdict;
  }
  delete copy.workspace.links;
  return copy;
}

const workDir = join(__dirname, '../mock/fixtures/work');
const names = readdirSync(workDir).filter((name) => /^W-32\d\d(\.[a-z]+)?\.json$/.test(name));
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

const COOKIE = 'psl_mock_persona=ceo';
const CSRF = 'mock-csrf-ceo';
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
async function step(id: string, body: Record<string, unknown>) {
  const response = await fetch(`${base}/api/v1/work/${id}/steps`, { method: 'POST', headers, body: JSON.stringify(body) });
  return { status: response.status, body: (await response.json()) as Record<string, unknown> };
}

describe('F-35 fixtures', () => {
  it('twelve items and their sidecars are schema-valid once the overlay is stripped; every one is sample and on the leadership report line', () => {
    expect(names.filter((name) => /^W-32\d\d\.json$/.test(name))).toHaveLength(12);
    expect(names.filter((name) => !/^W-32\d\d\.json$/.test(name)).sort()).toEqual(['W-3202.approve.json', 'W-3202.return.json', 'W-3205.next.json', 'W-3205.steps.json', 'W-3209.approve.json', 'W-3212.steps.json']);
    for (const name of names.filter((n) => !n.includes('.steps'))) {
      const body = readItem(name);
      expectValid('E-WORK-ITEM', 200, stripped(body));
      expect(body.sample, name).toBe(true);
      expect(body.workspace.line_key, name).toBe('leadership_report');
      expect((body as unknown as { case_id?: string }).case_id, name).toBeUndefined();
      expect((body.workspace as { context?: { project?: unknown } }).context?.project, name).toBeUndefined();
    }
  });

  it('no fixture carries money, reconcile or allowed_actions; no review fixture has a next sidecar (it would make the first decide 409)', () => {
    for (const name of names.filter((n) => !n.includes('.steps'))) {
      const text = readFileSync(join(workDir, name), 'utf8');
      expect(text, name).not.toMatch(/"money"|"amount"|"reconcile"|"allowed_actions"/);
    }
    for (const id of ['W-3202', 'W-3206', 'W-3208', 'W-3209', 'W-3210']) expect(names).not.toContain(`${id}.next.json`);
  });

  it('W-3207 names no reviewer and has no task or step; nothing names a hidden project', () => {
    const hold = readItem('W-3207.json');
    expect(hold.tasks).toEqual([]);
    expect(hold.workspace.steps).toBeUndefined();
    expect(JSON.stringify(hold)).not.toMatch(/Ifeoma|required_role/);
    const rows = (JSON.parse(readFileSync(join(__dirname, '../mock/fixtures/projects/list.json'), 'utf8')) as { rows: { item: { title?: string } }[] }).rows;
    const titles = rows.map((r) => r.item.title).filter((t): t is string => typeof t === 'string');
    expect(titles.length).toBeGreaterThan(0);
    const partial = readFileSync(join(workDir, 'W-3210.json'), 'utf8');
    for (const title of titles) expect(partial, title).not.toContain(title);
  });

  it('SEC-1-1: W-3210 (3 of 5 projects visible) carries only visible records: Tola’s steps cite 3 projects and no escalation id', () => {
    const body = readItem('W-3210.json') as unknown as Item & { agent: { steps: { text: string; source?: string }[] } };
    const agentText = body.agent.steps.map((s) => `${s.text} ${s.source ?? ''}`).join(' ');
    expect(agentText).toContain('3 PROJECTS');
    const all = JSON.stringify(body);
    for (const hidden of ['5 PROJECTS', '41 MEETINGS', '12 ISSUES', '3 MILESTONES', '2 INVOICES']) expect(all, hidden).not.toContain(hidden);
    expect(all).not.toMatch(/ESC-\d+|\bP-\d{4}\b|"case_id"|"work_id"/);
  });

  it('a receipt the backend is still checking is never received, and only W-3204 says received by every recipient', () => {
    for (const name of names.filter((n) => !n.includes('.steps'))) {
      const body = readItem(name);
      for (const row of body.workspace.sections.flatMap((s) => (s.kind === 'recipients' ? s.items : []))) {
        if (row.tag?.label === 'CHECKING') expect(row.receipt, name).toBe('uncertain');
      }
      if (name !== 'W-3204.json') expect(body.workspace.status.label, name).not.toMatch(/RECEIVED/);
    }
  });
});

describe('F-35 claim, decide and step on the mock', () => {
  it('claim then approve on W-3202 serves the sent sidecar with four deliveries not yet confirmed; a second decide is refused', async () => {
    expect((await task('claim', 'T-3202', { expected_revision: 1 })).status).toBe(200);
    const result = await task('decision', 'T-3202', { verdict: 'approve', expected_revision: 1 });
    expect(result).toMatchObject({ status: 200, body: { task_id: 'T-3202', verdict: 'approve', work_state: 'processing' } });
    const now = await getItem('W-3202');
    expect(now.workspace.status.label).toBe('SENT · CHECKING DELIVERIES');
    expect(now.workspace.sections[0].items.map((r) => [r.text, r.receipt])).toEqual([
      ['CEO', 'not_yet'],
      ['CTO', 'not_yet'],
      ['PMO Lead', 'not_yet'],
      ['Finance Lead', 'not_yet'],
    ]);
    expect(now.tasks[0]).toMatchObject({ you_can_act: false, cannot_act_reason: 'already_decided', revision: 2 });
    expect(now.revision).toBe(2);
    expect((await task('decision', 'T-3202', { verdict: 'approve', expected_revision: 1 })).status).toBe(409);
  });

  it('return without a note is 422; with one it serves the returned sidecar', async () => {
    expect((await task('decision', 'T-3202', { verdict: 'return', expected_revision: 1 })).status).toBe(422);
    expect((await task('decision', 'T-3202', { verdict: 'return', expected_revision: 1, note: '   ' })).status).toBe(422);
    expect((await task('decision', 'T-3202', { verdict: 'return', expected_revision: 1, note: 'Add the escalation.' })).status).toBe(200);
    expect((await getItem('W-3202')).workspace.status.label).toBe('DRAFTING · RETURNED');
  });

  it('a stale revision is 409; W-3206 and W-3208 refuse claim and decide with 403; reset clears', async () => {
    expect((await task('decision', 'T-3202', { verdict: 'approve', expected_revision: 7 })).status).toBe(409);
    expect((await task('decision', 'T-3206', { verdict: 'approve', expected_revision: 1 })).status).toBe(403);
    expect((await task('claim', 'T-3206', { expected_revision: 1 })).status).toBe(403);
    expect((await task('decision', 'T-3208', { verdict: 'approve', expected_revision: 1 })).status).toBe(403);
    expect((await task('decision', 'T-3202', { verdict: 'approve', expected_revision: 1 })).status).toBe(200);
    expect((await getItem('W-3202')).state).toBe('processing');
    await fetch(`${base}/__mock/reset`, { method: 'POST' });
    expect((await getItem('W-3202')).state).toBe('action_needed');
  });

  it('W-3209: the decide answers 200 with work_state effect_uncertain, and the re-read has one delivery still checking', async () => {
    const result = await task('decision', 'T-3209', { verdict: 'approve', expected_revision: 1 });
    expect(result).toMatchObject({ status: 200, body: { verdict: 'approve', work_state: 'effect_uncertain' } });
    const now = await getItem('W-3209');
    expect(now.state).toBe('effect_uncertain');
    expect(now.workspace.status.label).toBe('SENT · DELIVERY NOT CONFIRMED');
    expect(now.workspace.sections[0].items.find((r) => r.text === 'Finance Lead')).toMatchObject({ receipt: 'uncertain', tag: { label: 'CHECKING' } });
  });

  it('the W-3205 step serves the next sidecar: in review, the preparer cannot act', async () => {
    const result = await step('W-3205', { expected_revision: 3, step: 'send_for_review', idempotency_key: crypto.randomUUID() });
    expect(result).toMatchObject({ status: 200, body: { work_id: 'W-3205', outcome: 'done' } });
    expectValid('E-WORK-STEP', 200, result.body);
    const now = await getItem('W-3205');
    expect(now.workspace.status.label).toBe('AWAITING LEADERSHIP REVIEW');
    expect(now.tasks[0]).toMatchObject({ you_can_act: false, cannot_act_reason: 'prepared_by_you' });
    await fetch(`${base}/__mock/reset`, { method: 'POST' });
    expect((await getItem('W-3205')).workspace.status.label).toBe('DRAFT READY');
  });

  it('the W-3212 step answers effect_uncertain with the backend message', async () => {
    const result = await step('W-3212', { expected_revision: 3, step: 'send_for_review', idempotency_key: crypto.randomUUID() });
    expect(result).toMatchObject({ status: 200, body: { outcome: 'effect_uncertain', message: "We couldn't confirm the report reached the reviewer." } });
    expectValid('E-WORK-STEP', 200, result.body);
  });
});
