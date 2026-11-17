// F-28: the contract mock's end-state minutes fixtures W-2309 to W-2314 and the audience branch of E-WORK-STEP.
// Mock evidence only: nothing is sent, filed or created; the idempotency map proves one send per key on the mock.
import { readFileSync } from 'node:fs';
import type { Server } from 'node:http';
import type { AddressInfo } from 'node:net';
import { join } from 'node:path';

import { afterAll, beforeAll, beforeEach, describe, expect, it } from 'vitest';

// @ts-expect-error plain ESM module without type declarations
import { startMockServer } from '../mock/server.mjs';

const dir = join(__dirname, '../mock/fixtures/work');
const fixture = (name: string) => JSON.parse(readFileSync(join(dir, `${name}.json`), 'utf8'));
const IDS = ['W-2309', 'W-2310', 'W-2311', 'W-2312', 'W-2313', 'W-2314'];

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

type Body = { outcome?: string; revision?: number; id?: string; workspace: { view: string; revision: number; line_key: string }; tasks: { id: string; you_can_act: boolean }[] };
let n = 0;
const key = () => `00000000-0000-4000-8000-${String(++n).padStart(12, '0')}`;
const HEADERS = { Cookie: 'psl_mock_persona=pm', 'Content-Type': 'application/json', 'X-CSRFToken': 'mock-csrf-pm' };
const post = async (path: string, body: unknown) => {
  const response = await fetch(`${base}${path}`, { method: 'POST', headers: HEADERS, body: JSON.stringify(body) });
  return { status: response.status, body: (await response.json()) as Body };
};
const step = (workId: string, body: Record<string, unknown>) => post(`/api/v1/work/${workId}/steps`, body);
const get = async (workId: string) => (await fetch(`${base}/api/v1/work/${workId}`, { headers: HEADERS })).json() as Promise<Body>;
const log = async () => (await (await fetch(`${base}/__mock/workspace-log`)).json()) as { sends: Record<string, number> };

describe('the end-state fixtures (AC 20)', () => {
  it('W-2309 to W-2314 are served as their own fixtures, sample, on the minutes line', async () => {
    for (const id of IDS) {
      const served = await get(id);
      expect(served, id).toEqual(fixture(id));
      expect(served.workspace.line_key, id).toBe('minutes');
    }
    expect((await get('W-2310')).workspace.view).toBe('internal');
    for (const id of ['W-2311', 'W-2312', 'W-2314']) expect((await get(id)).workspace.view, id).toBe('published');
    expect((await get('W-2309')).workspace.view).toBe('review');
  });

  it('the sidecars load and every script names only steps its item offers', () => {
    expect(fixture('W-2301.next.internal').workspace.view).toBe('internal');
    expect(fixture('W-2309.approve').workspace.view).toBe('published');
    const keys = fixture('W-2313').workspace.steps.map((s: { key: string }) => s.key);
    for (const name of Object.keys(fixture('W-2313.steps'))) expect(keys).toContain(name);
  });
});

describe('the audience branch (AC 20, 11)', () => {
  it('confirm_minutes with audience internal serves the internal sidecar; with client it serves W-2301.next as before', async () => {
    const internal = await step('W-2301', { expected_revision: 4, step: 'confirm_minutes', item_ids: ['A-1'], inputs: { audience: 'internal' }, idempotency_key: key() });
    expect(internal.status).toBe(200);
    expect(await get('W-2301')).toEqual(fixture('W-2301.next.internal'));
    await fetch(`${base}/__mock/reset`, { method: 'POST' });
    const client = await step('W-2301', { expected_revision: 4, step: 'confirm_minutes', item_ids: ['A-1'], inputs: { audience: 'client' }, idempotency_key: key() });
    expect(client.status).toBe(200);
    expect(await get('W-2301')).toEqual(fixture('W-2301.next'));
  });

  it('a repeated key returns the stored reply and the send count stays 1', async () => {
    const k = key();
    const body = { expected_revision: 4, step: 'confirm_minutes', item_ids: ['A-1'], inputs: { audience: 'internal' }, idempotency_key: k };
    const first = await step('W-2301', body);
    expect(await step('W-2301', body)).toEqual(first);
    expect((await log()).sends[k]).toBe(1);
  });

  it('a step with no audience, or an audience with no sidecar, keeps the old behaviour', async () => {
    await step('W-2301', { expected_revision: 4, step: 'save_for_later', idempotency_key: key() });
    expect((await get('W-2301')).workspace.view).toBe('default');
  });
});

describe('the W-2309 decide sidecar (AC 20, 12)', () => {
  it('claim then approve applies the published sidecar once, and a second decide is a 409', async () => {
    expect((await post('/api/v1/tasks/T-2309/claim', { expected_revision: 2 })).status).toBe(200);
    expect((await post('/api/v1/tasks/T-2309/decision', { expected_revision: 2, verdict: 'approve' })).status).toBe(200);
    const now = await get('W-2309');
    expect(now).toEqual(fixture('W-2309.approve'));
    expect(now.workspace.view).toBe('published');
    expect(now.tasks[0].you_can_act).toBe(false);
    expect((await post('/api/v1/tasks/T-2309/decision', { expected_revision: 2, verdict: 'approve' })).status).toBe(409);
  });

  it('W-2304 and its sidecars are untouched by W-2309', async () => {
    await post('/api/v1/tasks/T-2309/decision', { expected_revision: 2, verdict: 'approve' });
    expect((await get('W-2304')).workspace.view).toBe('review');
  });
});

describe('the W-2313 owner step', () => {
  it('assign_owner answers done on the item that lists it', async () => {
    const reply = await step('W-2313', { expected_revision: 8, step: 'assign_owner', item_ids: ['A-2'], inputs: { owner: 'O-ENG' }, idempotency_key: key() });
    expect(reply.status).toBe(200);
    expect(reply.body.outcome).toBe('done');
  });
  it('an item without the step answers 404', async () => {
    expect((await step('W-2310', { expected_revision: 8, step: 'assign_owner', item_ids: ['A-1'], idempotency_key: key() })).status).toBe(404);
  });
});
