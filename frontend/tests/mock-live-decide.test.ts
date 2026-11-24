import { readFileSync } from 'node:fs';
import type { Server } from 'node:http';
import type { AddressInfo } from 'node:net';
import { join } from 'node:path';

import Ajv2020 from 'ajv/dist/2020';
import addFormats from 'ajv-formats';
import { afterAll, beforeAll, beforeEach, describe, expect, it } from 'vitest';

// @ts-expect-error plain ESM module without type declarations
import { startMockServer } from '../mock/server.mjs';

// The mock's live decision desk (mock/live-decide.mjs) answers in the shapes of the live contract.
type Responses = Record<string, { content: { 'application/json': { schema: object } } }>;
type Op = { responses: Responses };
const contract = JSON.parse(readFileSync(join(__dirname, '../../contracts/psl-factory.openapi.json'), 'utf8')) as {
  paths: Record<string, Record<string, Op>>;
  components: { schemas: { Error: object } };
};
const ajv = new Ajv2020({ allErrors: true, strict: true, allowUnionTypes: true });
addFormats(ajv);
const validError = ajv.compile(contract.components.schemas.Error);
function expectValid(path: string, method: 'get' | 'post', status: number, body: unknown) {
  const declared = contract.paths[path][method].responses[String(status)];
  const validate = status === 200 ? ajv.compile(declared.content['application/json'].schema) : validError;
  expect(validate(body), `${method} ${path} ${status}: ${ajv.errorsText(validate.errors)}`).toBe(true);
}

type Body = Record<string, ReturnType<typeof JSON.parse>>;
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

const CSRF = 'mock-csrf-finance_lead';
const cookie = (extra = '') => `psl_mock_persona=finance_lead${extra}`;

async function get(template: string, path: string, extra = '', headers: Record<string, string> = {}) {
  const response = await fetch(base + path, { headers: { Cookie: cookie(extra), ...headers } });
  const body = (await response.json()) as Body;
  expectValid(template, 'get', response.status, body);
  return { status: response.status, body };
}
async function post(template: string, path: string, body: unknown, extra = '') {
  const response = await fetch(base + path, { method: 'POST', headers: { Cookie: cookie(extra), 'X-CSRFToken': CSRF, 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  const reply = (await response.json()) as Body;
  expectValid(template, 'post', response.status, reply);
  return { status: response.status, body: reply };
}
const claim = (id: number, body: unknown, extra?: string) => post('/api/v1/tasks/{task_id}/claim', `/api/v1/tasks/${id}/claim`, body, extra);
const decide = (id: number, body: unknown, extra?: string) => post('/api/v1/tasks/{task_id}/decision', `/api/v1/tasks/${id}/decision`, body, extra);
const comment = (id: number, body: unknown) => post('/api/v1/tasks/{task_id}/comments', `/api/v1/tasks/${id}/comments`, body);
const readTask = (id: number, extra?: string) => get('/api/v1/tasks/{task_id}', `/api/v1/tasks/${id}`, extra);

describe('GET /tasks/{id}, /work/{id}, /work/{id}/history and /work?queue=decisions', () => {
  it('serves the deciding fixture: claimable, two evidence items, a packet, no earlier recipient', async () => {
    const { body } = await readTask(41);
    expect(body.task).toMatchObject({ id: 41, revision: 3, claimed_by_you: false, can_claim: true, can_decide: false, verdicts: ['approve', 'return', 'reject'], url: '/work/17/decide?task=41' });
    expect(body.invoice_packet).toMatchObject({ version: 2, amount: '4250000.00', currency: 'NGN' });
    expect(body.review_evidence.map((e: { id: number }) => e.id)).toEqual([88, 91]);
    expect(body.recipient_change).toEqual({ earlier: null, current: 'Lekki Estates Ltd' });
  });

  it('task 42 cannot be claimed or decided; task 43 has no packet; an unknown task is 404', async () => {
    expect((await readTask(42)).body.task).toMatchObject({ can_claim: false, can_decide: false });
    expect((await readTask(43)).body.invoice_packet).toBeNull();
    expect((await get('/api/v1/tasks/{task_id}', '/api/v1/tasks/999')).status).toBe(404);
    expect((await get('/api/v1/work/{work_id}', '/api/v1/work/999')).status).toBe(404);
  });

  it('the work lists its task with the url the page opens, and the decisions queue lists open work', async () => {
    const work = (await get('/api/v1/work/{work_id}', '/api/v1/work/17')).body;
    expect(work.tasks.map((t: { id: number; url: string }) => [t.id, t.url])).toEqual([[41, '/work/17/decide?task=41']]);
    const queue = (await get('/api/v1/work', '/api/v1/work?queue=decisions')).body;
    expect(queue.items.map((i: { id: number }) => i.id)).toEqual([17, 18, 19]);
  });

  it('scenarios 401, 403 and 404 answer every live decide read', async () => {
    for (const status of [401, 403, 404]) {
      expect((await get('/api/v1/tasks/{task_id}', '/api/v1/tasks/41', '', { 'X-Mock-Scenario': String(status) })).status).toBe(status);
    }
  });
});

describe('claim and decision', () => {
  it('claim: bad bodies are 422 with fields; a wrong revision is 409; the right one claims and opens the decision', async () => {
    expect((await claim(41, {})).body.fields).toEqual([{ name: 'expected_revision', message: 'This field is required.' }]);
    expect((await claim(41, { expected_revision: 3, x: 1 })).status).toBe(422);
    expect((await claim(41, { expected_revision: 2 })).status).toBe(409);
    expect(await claim(41, { expected_revision: 3 })).toEqual({ status: 200, body: { task_id: 41, revision: 3, claimed_by: 'Ada Okafor' } });
    expect((await readTask(41)).body.task).toMatchObject({ claimed_by_you: true, can_decide: true, can_claim: false });
  });

  it('a task nobody may claim answers a claim with 403', async () => {
    expect((await claim(42, { expected_revision: 2 })).status).toBe(403);
  });

  it('decision: needs evidence from the review, a note to return or reject, and a claim; approve takes an empty note', async () => {
    await claim(41, { expected_revision: 3 });
    const base = { expected_revision: 3, verdict: 'approve', evidence_id: 88, note: '' };
    expect((await decide(41, { ...base, evidence_id: 5 })).body.fields).toEqual([{ name: 'evidence_id', message: 'Choose evidence recorded on this review.' }]);
    expect((await decide(41, { ...base, verdict: 'reject' })).body.fields).toEqual([{ name: 'note', message: 'Add a note to return or reject.' }]);
    expect((await decide(41, { ...base, verdict: 'revoke' })).status).toBe(422);
    expect((await decide(41, { expected_revision: 3, verdict: 'approve', evidence_id: 88 })).status).toBe(422);
    expect(await decide(41, base)).toEqual({ status: 200, body: { task_id: 41, review_id: 12, verdict: 'approve', work_state: 'waiting' } });
    // decided: the task is closed, offers nothing and a repeat is 409 at the old revision or 403 at the claimed one
    expect((await readTask(41)).body.task).toMatchObject({ status: 'closed', can_decide: false, verdicts: [] });
    const history = (await get('/api/v1/work/{work_id}/history', '/api/v1/work/17/history?kind=decision')).body;
    expect(history.items).toHaveLength(1);
    expect(history.items[0]).toMatchObject({ task_id: 41, status: 'approve', actor: 'Ada Okafor', evidence_id: 88 });
    expect((await get('/api/v1/work', '/api/v1/work?queue=decisions')).body.items.map((i: { id: number }) => i.id)).toEqual([18, 19]);
  });

  it('deciding before claiming is 403', async () => {
    expect((await decide(41, { expected_revision: 3, verdict: 'approve', evidence_id: 88, note: '' })).status).toBe(403);
  });

  it('cookie stale: the first decision is 409 and the next read is revision 4, version 3, 4300000.00', async () => {
    const extra = '; psl_mock_decide=stale';
    await claim(41, { expected_revision: 3 }, extra);
    expect((await decide(41, { expected_revision: 3, verdict: 'approve', evidence_id: 88, note: '' }, extra)).status).toBe(409);
    const now = (await readTask(41, extra)).body;
    expect(now.task.revision).toBe(4);
    expect(now.invoice_packet).toMatchObject({ version: 3, amount: '4300000.00' });
  });

  it('a wrong CSRF token is 403 csrf_failed', async () => {
    const response = await fetch(`${base}/api/v1/tasks/41/claim`, { method: 'POST', headers: { Cookie: cookie(), 'X-CSRFToken': 'wrong', 'Content-Type': 'application/json' }, body: '{"expected_revision":3}' });
    expect(response.status).toBe(403);
    expect(((await response.json()) as { code: string }).code).toBe('csrf_failed');
  });
});

describe('comments', () => {
  it('a task nobody may decide takes a comment; one that can be decided does not', async () => {
    expect((await comment(42, { revision: 2 })).status).toBe(422);
    expect((await comment(42, { revision: 2, body: '  ' })).status).toBe(422);
    expect(await comment(42, { revision: 2, body: 'Please check the PO.' })).toEqual({ status: 200, body: { comment_id: 1 } });
    expect((await comment(41, { revision: 3, body: 'Hello' })).status).toBe(403);
    expect((await comment(42, { revision: 1, body: 'Hello' })).status).toBe(409);
  });
});
