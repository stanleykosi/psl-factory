// F-43: the cash forecast fixtures (W-4001 to W-4013), their decide and reconcile sidecars, and the contract mock's
// claim, decide and reconcile on them. Every item and sidecar validates against the generated E-WORK-ITEM schema once
// the two overlay fields are removed: `steps[].verdict` (F-33 G-C-1) and `workspace.links` (X-LINKS, checked in
// mock-contract). Contract mock only: nothing here proves the backend's rules.
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
  case_id?: string;
  case_revision?: number;
  allowed_actions?: string[];
  reconcile?: { outcomes: string[] };
  tasks: { id: string; you_can_act: boolean; revision: number; required_role?: string; cannot_act_reason?: string }[];
  workspace: { line_key: string; revision: number; links?: unknown; steps?: { key: string; task_id?: string; verdict?: unknown }[]; status: { label: string; tone?: string }; sections: { key: string; title?: string }[]; next?: string[] };
};

/** The overlay fields removed before the contract check: each step's `verdict` (one of three, only with a task_id) and the links. */
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
const responseDir = join(__dirname, '../mock/fixtures/response');
const names = readdirSync(workDir).filter((name) => /^W-40\d\d(\.[a-z_]+)?\.json$/.test(name));
const sidecars = readdirSync(responseDir).filter((name) => /^W-40\d\d\.[a-z_]+\.json$/.test(name));
const readItem = (name: string) => JSON.parse(readFileSync(join(workDir, name), 'utf8')) as Item;
const readSidecar = (name: string) => JSON.parse(readFileSync(join(responseDir, name), 'utf8')) as Item;
const all = () => [...names.map((n) => [n, readItem(n)] as const), ...sidecars.map((n) => [`response/${n}`, readSidecar(n)] as const)];

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
async function reconcile(workId: string, body: Record<string, unknown>) {
  const response = await fetch(`${base}/api/v1/work/${workId}/actions`, { method: 'POST', headers, body: JSON.stringify({ action: 'reconcile', ...body }) });
  return { status: response.status, body: (await response.json()) as Record<string, unknown> };
}
async function upload(caseId: string, caseRevision: number) {
  const response = await fetch(`${base}/api/v1/cases/${caseId}/evidence`, {
    method: 'POST',
    headers,
    body: JSON.stringify({ kind: 'delivery_receipt', filename: 'ceo-receipt.pdf', content_base64: 'JVBERi0xLjQK', case_revision: caseRevision }),
  });
  expect(response.status).toBe(200);
  return (await response.json()) as { evidence_id: string; case_revision?: number };
}
async function getItem(id: string) {
  const response = await fetch(`${base}/api/v1/work/${id}`, { headers: { Cookie: COOKIE } });
  const body = (await response.json()) as Item;
  expectValid('E-WORK-ITEM', response.status, stripped(body));
  return body;
}

describe('F-43 fixtures (AC 5, 25)', () => {
  it('thirteen items, their decide sidecars and three reconcile sidecars are schema-valid once the overlay is stripped; every one is sample and on the cash_forecast line', () => {
    expect(names.filter((name) => /^W-40\d\d\.json$/.test(name))).toHaveLength(13);
    expect(names.filter((name) => !/^W-40\d\d\.json$/.test(name)).sort()).toEqual([
      'W-4002.approve.json',
      'W-4002.reject.json',
      'W-4002.return.json',
      'W-4013.approve.json',
      'W-4013.reject.json',
      'W-4013.return.json',
    ]);
    expect(sidecars.sort()).toEqual(['W-4003.delivered.json', 'W-4003.not_delivered.json', 'W-4003.unknown.json']);
    for (const [name, body] of all()) {
      expectValid('E-WORK-ITEM', 200, stripped(body));
      expect(body.sample, name).toBe(true);
      expect(body.workspace.line_key, name).toBe('cash_forecast');
      expect(body, name).toMatchObject({ reference: 'FC-0014', title: 'Cash forecast · base case, Nov–Apr', line: 'Cash forecast', workspace: { screen: 'SCR-56' } });
      expect(body.id, name).toMatch(/^W-40(0[1-9]|[1-9]\d)$/);
      for (const t of body.tasks) expect(t.id, name).toMatch(/^T-40(0[1-9]|[1-9]\d)$/);
    }
  });

  it('every amount is a decimal string, or unknown with no amount; the review tables carry the six months with Jan IN, Jan CLOSING and Feb–Apr OPENING and CLOSING Unknown', () => {
    for (const [name] of all()) {
      const text = readFileSync(join(name.startsWith('response/') ? responseDir : workDir, name.replace('response/', '')), 'utf8');
      for (const money of text.match(/"money": \{[^}]*\}/g) ?? []) {
        const value = JSON.parse(money.slice(money.indexOf('{'))) as { amount?: string; unknown: boolean };
        if (value.unknown) expect(value.amount, name).toBeUndefined();
        else expect(value.amount, name).toMatch(/^\d+\.\d{2}$/);
      }
    }
    type Row = { id: string; cells: { column: string; text?: string; money?: { amount?: string; unknown: boolean } }[] };
    const rows = (readItem('W-4002.json').workspace.sections[0] as unknown as { items: Row[] }).items;
    expect(rows.map((r) => r.cells[0].text)).toEqual(['Nov', 'Dec', 'Jan', 'Feb', 'Mar', 'Apr']);
    const unknown = rows.flatMap((r) => r.cells.filter((c) => c.money?.unknown).map((c) => `${r.cells[0].text} ${c.column}`));
    expect(unknown).toEqual(['Jan in', 'Jan closing', 'Feb opening', 'Feb closing', 'Mar opening', 'Mar closing', 'Apr opening', 'Apr closing']);
    expect(names.some((name) => name.includes('.next'))).toBe(false);
  });

  it('the W-40xx task ids are unique: no other base fixture uses one, and no two W-40xx items share one', () => {
    const owners = new Map<string, string[]>();
    for (const name of readdirSync(workDir).filter((n) => /^W-\d+\.json$/.test(n))) {
      for (const t of (JSON.parse(readFileSync(join(workDir, name), 'utf8')) as Item).tasks ?? []) owners.set(t.id, [...(owners.get(t.id) ?? []), name]);
    }
    const ours = [...owners].filter(([id, files]) => id.startsWith('T-40') || files.some((f) => f.startsWith('W-40')));
    expect(ours.length).toBe(10);
    for (const [id, files] of ours) expect(files, id).toHaveLength(1);
  });

  it('the holds W-4006 and W-4007 have no task, no step, no reconcile and name no preparer or reviewer', () => {
    for (const [name, label] of [
      ['W-4006.json', 'Forecast preparer'],
      ['W-4007.json', 'Inclusion rule'],
    ] as const) {
      const hold = readItem(name);
      expect(hold.state, name).toBe('setup_needed');
      expect(hold.workspace.status).toEqual({ label: 'SETUP NEEDED', tone: 'stopped' });
      expect(hold.tasks).toEqual([]);
      expect(hold.workspace.steps, name).toBeUndefined();
      expect(hold.allowed_actions, name).toBeUndefined();
      expect(hold.reconcile, name).toBeUndefined();
      expect(JSON.stringify(hold.workspace), name).toContain(label);
      expect(JSON.stringify(hold), name).not.toMatch(/Ada Okafor|Bisi Ade|Forecast reviewer|required_role|"money"/);
    }
  });

  it('only the review fixtures name the "Forecast reviewer" role (the backend’s sample text); no sidecar leaves a task anyone can act on or a verdict step', () => {
    for (const [name, body] of all()) {
      const named = JSON.stringify(body).includes('Forecast reviewer');
      expect(named, name).toBe(body.tasks.some((t) => t.required_role === 'Forecast reviewer'));
      if (!/^W-40\d\d\.json$/.test(name)) {
        expect(body.tasks.every((t) => !t.you_can_act), name).toBe(true);
        expect(body.workspace.steps, name).toBeUndefined();
      }
    }
    // the uncertain delivery offers no cancel, resend or retry
    for (const name of ['W-4003.json', 'W-4012.json']) {
      const body = readItem(name);
      expect(body.allowed_actions ?? [], name).not.toContain('cancel');
      expect(JSON.stringify(body), name).not.toMatch(/resend|retry|cancel/i);
    }
  });
});

describe('F-43 claim and decide on the mock (AC 13, 14, 16, 17, 25)', () => {
  it('claim then approve on W-4002 serves APPROVED (waiting, never verified); a second decide is refused', async () => {
    expect((await task('claim', 'T-4002', { expected_revision: 1 })).status).toBe(200);
    const result = await task('decision', 'T-4002', { verdict: 'approve', expected_revision: 1 });
    expect(result).toMatchObject({ status: 200, body: { task_id: 'T-4002', verdict: 'approve', work_state: 'waiting' } });
    const now = await getItem('W-4002');
    expect(now.state).toBe('waiting');
    expect(now.workspace.status).toEqual({ label: 'APPROVED', tone: 'neutral' });
    expect(now.tasks[0]).toMatchObject({ you_can_act: false, cannot_act_reason: 'already_decided', revision: 2 });
    expect((await task('decision', 'T-4002', { verdict: 'approve', expected_revision: 1 })).status).toBe(409);
  });

  it('return without a note is 422; with one it serves RETURNED; reject serves REJECTED (cancelled)', async () => {
    expect((await task('decision', 'T-4002', { verdict: 'return', expected_revision: 1 })).status).toBe(422);
    expect((await task('decision', 'T-4002', { verdict: 'reject', expected_revision: 1, note: '   ' })).status).toBe(422);
    expect((await task('decision', 'T-4002', { verdict: 'return', expected_revision: 1, note: 'Check January.' })).status).toBe(200);
    expect((await getItem('W-4002')).workspace.status).toEqual({ label: 'RETURNED', tone: 'person' });
    await fetch(`${base}/__mock/reset`, { method: 'POST' });
    expect((await task('decision', 'T-4002', { verdict: 'reject', expected_revision: 1, note: 'No.' })).status).toBe(200);
    const rejected = await getItem('W-4002');
    expect(rejected.state).toBe('cancelled');
    expect(rejected.workspace.status).toEqual({ label: 'REJECTED', tone: 'stopped' });
  });

  it('a stale revision is 409; W-4005 and W-4008 refuse with 403; reset clears', async () => {
    expect((await task('decision', 'T-4002', { verdict: 'approve', expected_revision: 7 })).status).toBe(409);
    expect((await task('decision', 'T-4005', { verdict: 'approve', expected_revision: 1 })).status).toBe(403);
    expect((await task('claim', 'T-4005', { expected_revision: 1 })).status).toBe(403);
    expect((await task('decision', 'T-4008', { verdict: 'approve', expected_revision: 1 })).status).toBe(403);
    expect((await task('decision', 'T-4002', { verdict: 'approve', expected_revision: 1 })).status).toBe(200);
    expect((await getItem('W-4002')).state).toBe('waiting');
    await fetch(`${base}/__mock/reset`, { method: 'POST' });
    expect((await getItem('W-4002')).state).toBe('action_needed');
  });

  it('W-4013: each verdict answers 200 with work_state effect_uncertain and the re-read is DECISION NOT CONFIRMED', async () => {
    for (const [verdict, note] of [['approve', undefined], ['return', 'Check January.'], ['reject', 'No.']] as const) {
      await fetch(`${base}/__mock/reset`, { method: 'POST' });
      const result = await task('decision', 'T-4013', { verdict, expected_revision: 1, ...(note ? { note } : {}) });
      expect(result, verdict).toMatchObject({ status: 200, body: { verdict, work_state: 'effect_uncertain' } });
      const now = await getItem('W-4013');
      expect(now.state).toBe('effect_uncertain');
      expect(now.workspace.status).toEqual({ label: 'DECISION NOT CONFIRMED', tone: 'uncertain' });
      expect(JSON.stringify(now)).not.toContain('"reconcile"');
    }
  });
});

describe('F-43 reconcile on the mock (AC 18, 19, 25)', () => {
  it('an outcome not offered is 422; delivered without an issued proof is 422; a stale revision is 409', async () => {
    expect((await reconcile('W-4003', { expected_revision: 5, outcome: 'resent' })).status).toBe(422);
    expect((await reconcile('W-4003', { expected_revision: 5, outcome: 'delivered', evidence_id: 'EV-NOT-ISSUED' })).status).toBe(422);
    expect((await reconcile('W-4003', { expected_revision: 4, outcome: 'unknown' })).status).toBe(409);
    expect((await getItem('W-4003')).state).toBe('effect_uncertain');
  });

  it('each W-4003 outcome serves its sidecar: delivered with proof → VERIFIED; not delivered → NOT DELIVERED · HELD; unknown → HELD; none resends', async () => {
    const proof = await upload('C-4003', 2);
    const delivered = await reconcile('W-4003', { expected_revision: 5, outcome: 'delivered', evidence_id: proof.evidence_id, case_revision: proof.case_revision });
    expect(delivered).toMatchObject({ status: 200, body: { work_id: 'W-4003', state: 'verified', revision: 6 } });
    const verified = await getItem('W-4003');
    expect(verified.workspace.status).toEqual({ label: 'VERIFIED', tone: 'verified' });
    expect(verified.reconcile).toBeUndefined();
    for (const [outcome, state, label] of [
      ['not_delivered', 'action_needed', 'NOT DELIVERED · HELD'],
      ['unknown', 'waiting', 'HELD'],
    ] as const) {
      await fetch(`${base}/__mock/reset`, { method: 'POST' });
      expect((await reconcile('W-4003', { expected_revision: 5, outcome })).status, outcome).toBe(200);
      const now = await getItem('W-4003');
      expect(now.state, outcome).toBe(state);
      expect(now.workspace.status, outcome).toEqual({ label, tone: 'person' });
      expect(now.workspace.steps, outcome).toBeUndefined();
      expect(now.allowed_actions, outcome).toEqual([]);
      expect(JSON.stringify(now), outcome).not.toMatch(/resend|"retry"/i);
    }
  });

  it('W-4012 (reconcile present, no grant) refuses with 403; W-4004 and W-4002 have nothing to reconcile', async () => {
    expect((await reconcile('W-4012', { expected_revision: 5, outcome: 'unknown' })).status).toBe(403);
    expect((await getItem('W-4012')).state).toBe('effect_uncertain');
    expect((await reconcile('W-4004', { expected_revision: 7, outcome: 'unknown' })).status).toBe(422);
    expect((await reconcile('W-4002', { expected_revision: 1, outcome: 'unknown' })).status).toBe(422);
  });
});
