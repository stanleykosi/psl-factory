// F-45: the ledger source fixtures (W-4201 to W-4213) and the contract mock's upload, step, claim and decide on them. Every
// item and sidecar validates against the generated E-WORK-ITEM schema once the two overlay fields are removed:
// `steps[].verdict` (F-33 G-C-1) and `workspace.links` (X-LINKS, checked in mock-contract). Contract mock only: nothing is
// read from or sent to QuickBooks, and nothing is posted.
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
type Operation = { operationId: string; responses: Record<string, Schema>; requestBody?: Schema };
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

type Body = Record<string, unknown>;
type Item = {
  id: string;
  state: string;
  sample: boolean;
  revision: number;
  reference: string;
  title: string;
  case_id: string;
  case_revision: number;
  tasks: { id: string; you_can_act: boolean; revision: number; required_role: string; cannot_act_reason?: string }[];
  workspace: { line_key: string; screen: string; revision: number; links?: unknown; steps?: { key: string; task_id?: string; verdict?: unknown; disabled_reason?: string; fields?: { name: string; evidence_kind?: string }[] }[]; status: { label: string; tone?: string }; sections: { key: string; title?: string; items: Body[] }[]; next?: string[] };
};

/** The overlay fields removed before the contract check: each step's `verdict` (approve or reject here, only with a task_id) and the links. */
function stripped(body: Item): unknown {
  const copy = structuredClone(body);
  for (const step of copy.workspace.steps ?? []) {
    if (step.verdict === undefined) continue;
    expect(typeof step.task_id, step.key).toBe('string');
    expect(['approve', 'reject'], step.key).toContain(step.verdict);
    delete step.verdict;
  }
  delete copy.workspace.links;
  return copy;
}

const workDir = join(__dirname, '../mock/fixtures/work');
const names = readdirSync(workDir).filter((name) => /^W-42\d\d(\.[a-z]+)?\.json$/.test(name));
const items = names.filter((name) => !name.includes('.steps'));
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

async function send(method: string, path: string, persona = 'finance_lead', body?: unknown) {
  const headers: Record<string, string> = { Cookie: `psl_mock_persona=${persona}` };
  if (method !== 'GET') {
    headers['Content-Type'] = 'application/json';
    headers['X-CSRFToken'] = `mock-csrf-${persona}`;
  }
  const response = await fetch(`${base}${path}`, { method, headers, body: body === undefined ? undefined : JSON.stringify(body) });
  return { status: response.status, body: (await response.json().catch(() => ({}))) as Body };
}
async function task(op: 'claim' | 'decision', taskId: string, body: unknown, persona = 'finance_lead') {
  const result = await send('POST', `/api/v1/tasks/${taskId}/${op}`, persona, body);
  expectValid(op === 'claim' ? 'E-TASK-CLAIM' : 'E-TASK-DECIDE', result.status, result.body);
  return result;
}
async function getItem(id: string) {
  const { status, body } = await send('GET', `/api/v1/work/${id}`);
  expect(status).toBe(200);
  expectValid('E-WORK-ITEM', 200, stripped(body as unknown as Item));
  return body as unknown as Item;
}
const uploadBody = (kind = 'ledger_observation', caseRevision = 4) => ({ kind, filename: 'qb-screenshot-je7741.png', content_base64: 'iVBORw0KGgo=', case_revision: caseRevision });
const upload = async (kind?: string, persona = 'finance_lead', caseRevision?: number) => {
  const result = await send('POST', '/api/v1/cases/C-LED-0052/evidence', persona, uploadBody(kind, caseRevision));
  expectValid('E-EVIDENCE-UPLOAD', result.status, result.body);
  return result;
};
const observe = (id: string, found: string, evidenceIds: unknown[], key: string, revision = 2) =>
  send('POST', `/api/v1/work/${id}/steps`, 'finance_lead', { expected_revision: revision, step: 'record_observation', inputs: { found }, evidence_ids: evidenceIds, idempotency_key: key });
const log = async () => (await send('GET', '/__mock/workspace-log')).body as { entries: { work_id: string; status: number; replay: boolean; idempotency_key: string }[]; sends: Record<string, number> };

describe('F-45 fixtures (AC 2, 4, 5, 22)', () => {
  it('thirteen items and their sidecars are schema-valid once the overlay is stripped; every one is sample, on the ledger_sources line and on C-LED-0052', () => {
    expect(names.filter((name) => /^W-42\d\d\.json$/.test(name))).toHaveLength(13);
    expect(names.filter((name) => !/^W-42\d\d\.json$/.test(name)).sort()).toEqual([
      'W-4202.next.json',
      'W-4202.steps.json',
      'W-4203.approve.json',
      'W-4203.reject.json',
      'W-4208.next.json',
      'W-4208.steps.json',
      'W-4212.approve.json',
      'W-4212.reject.json',
      'W-4213.next.json',
      'W-4213.steps.json',
    ]);
    for (const name of items) {
      const body = readItem(name);
      expectValid('E-WORK-ITEM', 200, stripped(body));
      expect(body.sample, name).toBe(true);
      expect(body, name).toMatchObject({ reference: 'LED-0052', title: 'QuickBooks journal JE-7741 · October', case_id: 'C-LED-0052', case_revision: 4, workspace: { line_key: 'ledger_sources', screen: 'SCR-58' } });
      expect(body.revision, name).toBe(body.workspace.revision);
    }
  });

  it('no fixture carries money, a currency sign or a digit-group amount (part 1 shows no amount)', () => {
    for (const name of names) {
      const text = readFileSync(join(workDir, name), 'utf8');
      expect(text, name).not.toMatch(/"money"|₦|NGN|\d{1,3}(,\d{3})+|\d+\.\d{2}\b/);
    }
  });

  it('the review fixtures have no next sidecar (it would make the first decide 409); the verdict overlay is approve and reject only', () => {
    for (const id of ['W-4203', 'W-4206', 'W-4207', 'W-4212']) expect(names, id).not.toContain(`${id}.next.json`);
    const verdicts = items.flatMap((name) => (readItem(name).workspace.steps ?? []).map((s) => s.verdict).filter(Boolean));
    expect(new Set(verdicts)).toEqual(new Set(['approve', 'reject']));
  });

  it('W-4205 holds for the unset reviewer: no task, no step, no reviewer name or role; no fixture offers a ledger setup key as a control', () => {
    const hold = readItem('W-4205.json');
    expect(hold.state).toBe('setup_needed');
    expect(hold.tasks).toEqual([]);
    expect(hold.workspace.steps).toBeUndefined();
    expect(JSON.stringify(hold)).not.toMatch(/Ada Okafor|Ledger reviewer|required_role/);
    for (const name of items) expect(JSON.stringify(readItem(name).workspace.steps ?? []), name).not.toMatch(/finance\.ledger_sources|setup_rules/);
  });

  it('W-4209 (and the W-4208 re-read) holds after Unknown at station 3 with no step and no task', () => {
    for (const name of ['W-4209.json', 'W-4208.next.json']) {
      const body = readItem(name);
      expect(body.workspace.status).toEqual({ label: 'CHECK HELD', tone: 'stopped' });
      expect((body as unknown as { stations: { status: string }[] }).stations[2].status).toBe('stopped');
      expect(body.tasks).toEqual([]);
      expect(body.workspace.steps).toBeUndefined();
    }
  });

  it('W-4211 leaves Treatment without a value and the third agent step without a source (never 0, blank or a dash)', () => {
    const body = readItem('W-4211.json') as unknown as { workspace: Item['workspace']; agent: { steps: Body[] } };
    const treatment = body.workspace.sections[0].items.find((i) => i.label === 'Treatment')!;
    expect(treatment).not.toHaveProperty('value');
    expect(body.agent.steps[2]).not.toHaveProperty('source');
  });
});

describe('the proof upload on C-LED-0052 (AC 10, 11)', () => {
  it('takes a ledger_observation upload, issues EV-C-LED-0052-1 and moves every served item of the case to revision 5', async () => {
    const first = await upload();
    expect(first).toMatchObject({ status: 200, body: { evidence_id: 'EV-C-LED-0052-1', case_revision: 5 } });
    expect((await getItem('W-4202')).case_revision).toBe(5);
    expect((await getItem('W-4205')).case_revision).toBe(5);
  });

  it('refuses a kind no served step names (422), a stale case revision (409) and the none persona (403)', async () => {
    expect((await upload('deployment_note')).status).toBe(422);
    expect((await upload('ledger_observation', 'finance_lead', 3)).status).toBe(409);
    expect((await upload('ledger_observation', 'none')).status).toBe(403);
  });

  it('the upload request is the generated E-EVIDENCE-UPLOAD body', () => {
    const op = byId('E-EVIDENCE-UPLOAD');
    const validate = ajv.compile(op.requestBody!.content['application/json'].schema);
    expect(validate(uploadBody()), ajv.errorsText(validate.errors)).toBe(true);
  });
});

describe('record what you found (AC 6, 10, 16)', () => {
  it('W-4202: the upload, then the step, serves the review as the observer sees it (prepared_by_you); a repeated key is a replay', async () => {
    const proof = await upload();
    const reply = await observe('W-4202', 'found', [proof.body.evidence_id], 'k-observe');
    expectValid('E-WORK-STEP', reply.status, reply.body);
    expect(reply).toMatchObject({ status: 200, body: { outcome: 'done', message: 'Observation recorded.' } });
    const now = await getItem('W-4202');
    expect(now.workspace.status.label).toBe('AWAITING FINANCE DECISION');
    expect(now.tasks[0]).toMatchObject({ id: 'T-4202', you_can_act: false, cannot_act_reason: 'prepared_by_you' });
    expect((await observe('W-4202', 'found', [proof.body.evidence_id], 'k-observe')).body).toEqual(reply.body);
    expect((await log()).sends['k-observe']).toBe(1);
  });

  it('W-4208: Unknown serves the CHECK HELD re-read with no step', async () => {
    const proof = await upload();
    expect((await observe('W-4208', 'unknown', [proof.body.evidence_id], 'k-unknown')).status).toBe(200);
    const now = await getItem('W-4208');
    expect(now.workspace.status.label).toBe('CHECK HELD');
    expect(now.workspace.steps).toBeUndefined();
  });

  it('W-4213: the step is written and then answers 500; the re-read is the review; the same key again is a replay; one applied step', async () => {
    const proof = await upload();
    expect((await observe('W-4213', 'found', [proof.body.evidence_id], 'k-uncertain')).status).toBe(500);
    const now = await getItem('W-4213');
    expect(now.workspace.status.label).toBe('AWAITING FINANCE DECISION');
    expect(now.workspace.steps?.some((s) => s.key === 'record_observation')).toBe(false);
    await observe('W-4213', 'found', [proof.body.evidence_id], 'k-uncertain');
    const entries = (await log()).entries.filter((e) => e.work_id === 'W-4213');
    expect(entries.filter((e) => !e.replay)).toHaveLength(1);
    expect((await log()).sends['k-uncertain']).toBe(1);
  });

  it('a stale revision is 409; W-4210 offers the step only with its disabled reason', async () => {
    expect((await observe('W-4202', 'found', [], 'k-stale', 1)).status).toBe(409);
    expect((await getItem('W-4210')).workspace.steps?.[0].disabled_reason).toBe('You captured this source, so someone else must look it up.');
  });
});

describe('the review on the mock (AC 12, 14, 15, 22)', () => {
  it('claim then approve on W-4203 serves the verified sidecar; a second decide is refused', async () => {
    expect((await task('claim', 'T-4203', { expected_revision: 1 })).status).toBe(200);
    const result = await task('decision', 'T-4203', { verdict: 'approve', expected_revision: 1 });
    expect(result).toMatchObject({ status: 200, body: { task_id: 'T-4203', verdict: 'approve', work_state: 'verified' } });
    const now = await getItem('W-4203');
    expect(now.state).toBe('verified');
    expect(now.workspace.status.label).toBe('VERIFIED');
    expect(now.workspace.steps).toBeUndefined();
    expect(now.tasks[0]).toMatchObject({ you_can_act: false, cannot_act_reason: 'already_decided', revision: 2 });
    expect((await task('decision', 'T-4203', { verdict: 'approve', expected_revision: 1 })).status).toBe(409);
  });

  it('reject without a note is 422; with a note it serves REJECTED read-only with no step', async () => {
    expect((await task('decision', 'T-4203', { verdict: 'reject', expected_revision: 1 })).status).toBe(422);
    expect((await task('decision', 'T-4203', { verdict: 'reject', note: '   ', expected_revision: 1 })).status).toBe(422);
    expect((await task('decision', 'T-4203', { verdict: 'reject', note: 'Wrong journal.', expected_revision: 1 })).body.work_state).toBe('cancelled');
    const now = await getItem('W-4203');
    expect(now.workspace.status).toEqual({ label: 'REJECTED', tone: 'stopped' });
    expect(now.workspace.steps).toBeUndefined();
  });

  it('a stale revision is 409; W-4206 (took part) and W-4207 (not the role) answer 403', async () => {
    expect((await task('decision', 'T-4203', { verdict: 'approve', expected_revision: 7 })).status).toBe(409);
    expect((await task('decision', 'T-4206', { verdict: 'approve', expected_revision: 1 })).status).toBe(403);
    expect((await task('claim', 'T-4207', { expected_revision: 1 })).status).toBe(403);
  });

  it('W-4212 answers effect_uncertain on approve and on reject, and the re-read is CHECKING, never verified', async () => {
    expect((await task('decision', 'T-4212', { verdict: 'approve', expected_revision: 1 })).body.work_state).toBe('effect_uncertain');
    expect((await getItem('W-4212')).workspace.status).toEqual({ label: 'CHECKING', tone: 'uncertain' });
    await fetch(`${base}/__mock/reset`, { method: 'POST' });
    expect((await task('decision', 'T-4212', { verdict: 'reject', note: 'Wrong period.', expected_revision: 1 })).body.work_state).toBe('effect_uncertain');
    expect((await getItem('W-4212')).state).toBe('effect_uncertain');
  });
});

describe('reset (AC 22)', () => {
  it('clears every override and the issued evidence ids', async () => {
    const proof = await upload();
    await observe('W-4202', 'found', [proof.body.evidence_id], 'k-reset');
    await task('decision', 'T-4203', { verdict: 'approve', expected_revision: 1 });
    await fetch(`${base}/__mock/reset`, { method: 'POST' });
    expect((await getItem('W-4202')).workspace.status.label).toBe('RECORD WHAT YOU FOUND');
    expect((await getItem('W-4203')).workspace.status.label).toBe('AWAITING FINANCE DECISION');
    expect((await getItem('W-4202')).case_revision).toBe(4);
    expect((await upload()).body.evidence_id).toBe('EV-C-LED-0052-1');
    expect((await log()).entries).toHaveLength(0);
  });
});
