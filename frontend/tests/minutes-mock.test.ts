// F-23: the contract mock's minutes fixtures W-2301 to W-2308 through E-WORK-STEP, the decide sidecars, E-LINE-OPTIONS and
// E-DOCUMENT. Mock evidence only: the idempotency map proves one send per key on the mock, not the backend's promise (unbuilt).
import { readFileSync } from 'node:fs';
import type { Server } from 'node:http';
import type { AddressInfo } from 'node:net';
import { join } from 'node:path';

import Ajv2020 from 'ajv/dist/2020';
import addFormats from 'ajv-formats';
import { afterAll, beforeAll, beforeEach, describe, expect, it } from 'vitest';

// @ts-expect-error plain ESM module without type declarations
import { OPENAPI_PATH, startMockServer } from '../mock/server.mjs';

const openapi = JSON.parse(readFileSync(OPENAPI_PATH, 'utf8'));
const ajv = new Ajv2020({ allErrors: true, strict: true });
addFormats(ajv);
const stepReply = (status: number) => ajv.compile(openapi.paths['/api/v1/work/{work_id}/steps'].post.responses[String(status)].content['application/json'].schema);
const documentSchema = ajv.compile(openapi.paths['/api/v1/documents/{document_id}/versions/{version}'].get.responses['200'].content['application/json'].schema);
const dir = join(__dirname, '../mock/fixtures/work');
const fixture = (name: string) => JSON.parse(readFileSync(join(dir, `${name}.json`), 'utf8'));
const IDS = ['W-2301', 'W-2302', 'W-2303', 'W-2304', 'W-2305', 'W-2306', 'W-2307', 'W-2308'];

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

type Body = { outcome?: string; revision?: number; state?: string; fields: { name: string }[]; workspace: { view: string; revision: number; line_key: string }; reconcile?: unknown; allowed_actions?: string[]; tasks: { id: string; you_can_act: boolean }[] };
let n = 0;
const key = () => `00000000-0000-4000-9000-${String(++n).padStart(12, '0')}`;
const HEADERS = { Cookie: 'psl_mock_persona=pm', 'Content-Type': 'application/json', 'X-CSRFToken': 'mock-csrf-pm' };
const step = async (workId: string, body: Record<string, unknown>) => {
  const response = await fetch(`${base}/api/v1/work/${workId}/steps`, { method: 'POST', headers: HEADERS, body: JSON.stringify(body) });
  return { status: response.status, body: (await response.json()) as Body };
};
const get = async (workId: string) => (await fetch(`${base}/api/v1/work/${workId}`, { headers: HEADERS })).json() as Promise<Body>;
const post = async (path: string, body: unknown) => {
  const response = await fetch(`${base}${path}`, { method: 'POST', headers: HEADERS, body: JSON.stringify(body) });
  return { status: response.status, body: (await response.json()) as Body };
};
const log = async () => (await (await fetch(`${base}/__mock/workspace-log`)).json()) as { sends: Record<string, number>; entries: { item_ids?: string[]; status: number; replay: boolean }[] };

describe('minutes fixtures', () => {
  it('W-2301 to W-2308 are served as their own fixtures, sample, on the minutes line', async () => {
    for (const id of IDS) {
      const served = await get(id);
      expect(served, id).toEqual(fixture(id));
      expect(served.workspace.line_key, id).toBe('minutes');
    }
  });

  it('every script names only steps its item offers', () => {
    for (const id of ['W-2301', 'W-2303', 'W-2306']) {
      const keys = fixture(id).workspace.steps.map((s: { key: string }) => s.key);
      for (const name of Object.keys(fixture(`${id}.steps`))) expect(keys, `${id} ${name}`).toContain(name);
    }
  });
});

describe('E-WORK-STEP on the minutes fixtures (AC 27)', () => {
  it('a bad body is 422, a wrong revision 409, an unknown step 404, a repeated key replays with send count 1', async () => {
    expect((await step('W-2301', { expected_revision: 4, step: 'save_for_later' })).status).toBe(422);
    expect((await step('W-2301', { expected_revision: 3, step: 'save_for_later', idempotency_key: key() })).status).toBe(409);
    expect((await step('W-2301', { expected_revision: 4, step: 'nope', idempotency_key: key() })).status).toBe(404);
    const k = key();
    const first = await step('W-2301', { expected_revision: 4, step: 'save_for_later', idempotency_key: k });
    expect(first.body).toMatchObject({ outcome: 'done', revision: 5 });
    expect(stepReply(200)(first.body)).toBe(true);
    expect(await step('W-2301', { expected_revision: 4, step: 'save_for_later', idempotency_key: k })).toEqual(first);
    expect((await log()).sends[k]).toBe(1);
  });

  it('confirm_minutes records the ids sent and moves W-2301 to the drafted view; send_for_review moves W-2303 to the review view', async () => {
    const confirm = await step('W-2301', { expected_revision: 4, step: 'confirm_minutes', item_ids: ['D-1', 'A-1'], inputs: { audience: 'client' }, idempotency_key: key() });
    expect(confirm.body).toMatchObject({ outcome: 'done', revision: 5 });
    expect((await log()).entries[0].item_ids).toEqual(['D-1', 'A-1']);
    expect((await get('W-2301')).workspace.view).toBe('drafted');
    const send = await step('W-2303', { expected_revision: 5, step: 'send_for_review', idempotency_key: key() });
    expect(send.body).toMatchObject({ outcome: 'done', revision: 6 });
    expect((await get('W-2303')).workspace.view).toBe('review');
  });

  it('W-2301 edit, remove and add keep the same view at the next revision', async () => {
    for (const [name, rev] of [['edit_item', 4], ['remove_item', 5], ['add_action', 6]] as const) {
      expect((await step('W-2301', { expected_revision: rev, step: name, item_ids: ['A-1'], idempotency_key: key() })).status).toBe(200);
    }
    const now = await get('W-2301');
    expect(now.workspace.view).toBe('default');
    expect(now.workspace.revision).toBe(7);
  });

  it('W-2306: confirm answers a 409 once and swaps in revision 5; add_action is a 422 naming text; save_for_later a 500', async () => {
    expect((await step('W-2306', { expected_revision: 4, step: 'confirm_minutes', idempotency_key: key() })).status).toBe(409);
    expect((await get('W-2306')).workspace.revision).toBe(5);
    expect((await step('W-2306', { expected_revision: 5, step: 'confirm_minutes', item_ids: ['D-1'], inputs: { audience: 'client' }, idempotency_key: key() })).status).toBe(200);
    await fetch(`${base}/__mock/reset`, { method: 'POST' });
    const bad = await step('W-2306', { expected_revision: 4, step: 'add_action', inputs: { text: '' }, idempotency_key: key() });
    expect(bad.status).toBe(422);
    expect(stepReply(422)(bad.body)).toBe(true);
    expect(bad.body.fields.map((f) => f.name)).toEqual(['text']);
    expect((await step('W-2306', { expected_revision: 4, step: 'save_for_later', idempotency_key: key() })).status).toBe(500);
  });

  it('the review items’ approve and return are task_id links; the mock has no step to answer for them', () => {
    for (const [id, task] of [['W-2304', 'T-2304'], ['W-2305', 'T-2305']]) {
      const steps = fixture(id).workspace.steps as { key: string; task_id?: string }[];
      expect(steps.map((s) => [s.key, s.task_id])).toEqual([['approve_send', task], ['return', task]]);
    }
  });
});

describe('the decide sidecars (AC 27)', () => {
  it('W-2304: claim then approve applies the approve sidecar once, and a second decide is a 409', async () => {
    expect((await post('/api/v1/tasks/T-2304/claim', { expected_revision: 2 })).status).toBe(200);
    const decided = await post('/api/v1/tasks/T-2304/decision', { expected_revision: 2, verdict: 'approve' });
    expect(decided.status).toBe(200);
    const now = await get('W-2304');
    expect(now).toEqual(fixture('W-2304.approve'));
    expect(now.tasks[0].you_can_act).toBe(false);
    expect((await post('/api/v1/tasks/T-2304/decision', { expected_revision: 2, verdict: 'approve' })).status).toBe(409);
  });

  it('W-2304 return needs a note and applies the return sidecar', async () => {
    expect((await post('/api/v1/tasks/T-2304/decision', { expected_revision: 2, verdict: 'return' })).status).toBe(422);
    expect((await post('/api/v1/tasks/T-2304/decision', { expected_revision: 2, verdict: 'return', note: 'Fix the third action.' })).status).toBe(200);
    expect(await get('W-2304')).toEqual(fixture('W-2304.return'));
  });

  it('W-2305: approve answers effect_uncertain, and the re-read carries reconcile with allowed_actions reconcile only', async () => {
    const decided = await post('/api/v1/tasks/T-2305/decision', { expected_revision: 2, verdict: 'approve' });
    expect(decided.body).toMatchObject({ work_state: 'effect_uncertain' });
    const reread = await get('W-2305');
    expect(reread.state).toBe('effect_uncertain');
    expect(reread.reconcile).toBeDefined();
    expect(reread.allowed_actions).toEqual(['reconcile']);
  });
});

describe('E-LINE-OPTIONS minutes/owner and E-DOCUMENT (AC 27)', () => {
  it('serves owner.json with no mock-only keys, and hints for the client and the PM-recorded owner', async () => {
    const response = await fetch(`${base}/api/v1/lines/minutes/fields/owner/options`, { headers: { Cookie: 'psl_mock_persona=pm' } });
    expect(response.status).toBe(200);
    const page = (await response.json()) as { items: Record<string, unknown>[] };
    const file = JSON.parse(readFileSync(join(__dirname, '../mock/fixtures/start-work/options/owner.json'), 'utf8')).items as Record<string, unknown>[];
    expect(page.items.map((i) => i.value)).toEqual(file.map((i) => i.value));
    for (const item of page.items) expect(Object.keys(item).some((k) => k.startsWith('_'))).toBe(false);
    expect(page.items.map((i) => i.hint).filter(Boolean)).toEqual(['recorded by PM', 'client']);
    expect((await fetch(`${base}/api/v1/lines/minutes/fields/owner/options`, { headers: { Cookie: 'psl_mock_persona=none' } })).status).toBe(404);
  });

  it('serves D-2304 version 1 as a test template; any other document stays unmocked; the scenario header wins', async () => {
    const response = await fetch(`${base}/api/v1/documents/D-2304/versions/1`, { headers: HEADERS });
    expect(response.status).toBe(200);
    const body = await response.json();
    expect(documentSchema(body)).toBe(true);
    expect(body.test_template).toBe(true);
    expect((await fetch(`${base}/api/v1/documents/D-1/versions/1`, { headers: HEADERS })).status).toBe(501);
    expect((await fetch(`${base}/api/v1/documents/D-2304/versions/1`, { headers: { ...HEADERS, 'X-Mock-Scenario': '404' } })).status).toBe(404);
  });
});
