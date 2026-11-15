// F-17: the contract mock's E-WORK-STEP (mock/workspace.mjs). Mock evidence only: the idempotency map proves one
// send per key on the mock, not the backend's promise (unbuilt).
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
const op = openapi.paths['/api/v1/work/{work_id}/steps'].post;
const ajv = new Ajv2020({ allErrors: true, strict: true });
addFormats(ajv);
const reply = (status: number) => ajv.compile(op.responses[String(status)].content['application/json'].schema);
const fixture = (name: string) => JSON.parse(readFileSync(join(__dirname, '../mock/fixtures/work', `${name}.json`), 'utf8'));

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

let n = 0;
const key = () => `00000000-0000-4000-8000-${String(++n).padStart(12, '0')}`;
const HEADERS = { Cookie: 'psl_mock_persona=pm', 'Content-Type': 'application/json', 'X-CSRFToken': 'mock-csrf-pm' };

async function step(workId: string, body: Record<string, unknown>, headers: Record<string, string> = HEADERS) {
  const response = await fetch(`${base}/api/v1/work/${workId}/steps`, { method: 'POST', headers, body: JSON.stringify(body) });
  return { status: response.status, body: (await response.json()) as Record<string, unknown> };
}
const item = async (workId: string) => (await (await fetch(`${base}/api/v1/work/${workId}`, { headers: HEADERS })).json()) as { revision: number; state: string; workspace?: { revision?: number }; reconcile?: unknown };
const log = async () => (await (await fetch(`${base}/__mock/workspace-log`)).json()) as { entries: { idempotency_key: string; status: number; replay: boolean; item_ids?: string[] }[]; sends: Record<string, number> };

describe('E-WORK-STEP on the mock', () => {
  it('a valid step answers done, moves the served revision on, and a repeat of the key replays without a second send', async () => {
    const k = key();
    const first = await step('W-2001', { expected_revision: 3, step: 'approve_send', idempotency_key: k });
    expect(first.status).toBe(200);
    expect(reply(200)(first.body)).toBe(true);
    expect(first.body).toMatchObject({ work_id: 'W-2001', outcome: 'done', revision: 4 });
    expect((await item('W-2001')).workspace?.revision).toBe(4);
    const again = await step('W-2001', { expected_revision: 3, step: 'approve_send', idempotency_key: k });
    expect(again).toEqual(first);
    const recorded = await log();
    expect(recorded.sends[k]).toBe(1);
    expect(recorded.entries.map((e) => [e.status, e.replay])).toEqual([
      [200, false],
      [200, true],
    ]);
  });

  it('checks CSRF, the body against the request schema, the step key and the revision', async () => {
    expect((await step('W-2001', { expected_revision: 3, step: 'approve_send', idempotency_key: key() }, { ...HEADERS, 'X-CSRFToken': 'nope' })).status).toBe(403);
    const bad = await step('W-2001', { expected_revision: 3, step: 'approve_send', note: 'x'.repeat(2001), extra: true });
    expect(bad.status).toBe(422);
    expect(reply(422)(bad.body)).toBe(true);
    expect((bad.body.fields as { name: string }[]).map((f) => f.name).sort()).toEqual(['extra', 'idempotency_key', 'note']);
    expect((await step('W-2001', { expected_revision: 3, step: 'not_a_step', idempotency_key: key() })).status).toBe(404);
    expect((await step('W-2001', { expected_revision: 2, step: 'approve_send', idempotency_key: key() })).status).toBe(409);
    expect((await step('W-2099', { expected_revision: 1, step: 'x', idempotency_key: key() })).status).toBe(404);
    expect((await item('W-2001')).workspace?.revision).toBe(3);
  });

  it('item_ids are recorded as sent', async () => {
    const k = key();
    expect((await step('W-2002', { expected_revision: 7, step: 'accept_selected', item_ids: ['R-07', 'R-09'], idempotency_key: k })).status).toBe(200);
    expect((await log()).entries[0].item_ids).toEqual(['R-07', 'R-09']);
  });

  it('W-2006: a full form body is accepted; the scripted 422 names its fields', async () => {
    const full = await step('W-2006', {
      expected_revision: 2,
      step: 'save_answer',
      inputs: { answer: 'Yes', hours: 12, price: { amount: '4250000.00', currency: 'NGN', unknown: false }, status: 'clarify', covers: { from: '2026-11-01' } },
      note: 'Checked.',
      idempotency_key: key(),
    });
    expect(full.status).toBe(200);
    await fetch(`${base}/__mock/reset`, { method: 'POST' });
    const invalid = await step('W-2006', { expected_revision: 2, step: 'check_answer', inputs: { answer: 'x' }, idempotency_key: key() });
    expect(invalid.status).toBe(422);
    expect(reply(422)(invalid.body)).toBe(true);
    expect(invalid.body.fields).toEqual(fixture('W-2006.steps').check_answer.body.fields);
  });

  it('W-2007: queued keeps the item; the scripted 409 swaps in version 5; 500s answer as scripted', async () => {
    const queued = await step('W-2007', { expected_revision: 4, step: 'reassemble', idempotency_key: key() });
    expect(queued.body).toMatchObject({ outcome: 'queued', revision: 5 });
    await fetch(`${base}/__mock/reset`, { method: 'POST' });
    const stale = await step('W-2007', { expected_revision: 4, step: 'edit_update', inputs: { summary: 'x' }, idempotency_key: key() });
    expect(stale.status).toBe(409);
    expect(reply(409)(stale.body)).toBe(true);
    expect((await item('W-2007')).workspace?.revision).toBe(5);
    expect((await step('W-2007', { expected_revision: 5, step: 'send_now', idempotency_key: key() })).status).toBe(500);
    expect((await step('W-2007', { expected_revision: 5, step: 'refresh_records', idempotency_key: key() })).status).toBe(500);
  });

  it('W-2008: effect_uncertain; the re-read item carries reconcile, and its answer goes through E-WORK-ACTION', async () => {
    const uncertain = await step('W-2008', { expected_revision: 3, step: 'approve_send', idempotency_key: key() });
    expect(uncertain.body).toMatchObject({ outcome: 'effect_uncertain', message: 'Delivery to Lagoon Health couldn’t be confirmed.' });
    const reread = await item('W-2008');
    expect(reread.state).toBe('effect_uncertain');
    expect(reread.reconcile).toBeDefined();
    const answer = await fetch(`${base}/api/v1/work/W-2008/actions`, {
      method: 'POST',
      headers: { ...HEADERS, Cookie: 'psl_mock_persona=finance_lead', 'X-CSRFToken': 'mock-csrf-finance_lead' },
      body: JSON.stringify({ expected_revision: reread.revision, action: 'reconcile', outcome: 'not_delivered' }),
    });
    expect(answer.status).toBe(200);
    expect((await item('W-2008')).state).toBe('action_needed');
  });

  it('a declared scenario wins, and reset clears the log and the served overrides', async () => {
    const scenario = await step('W-2001', { expected_revision: 3, step: 'approve_send', idempotency_key: key() }, { ...HEADERS, 'X-Mock-Scenario': '422' });
    expect(scenario.status).toBe(422);
    await step('W-2001', { expected_revision: 3, step: 'approve_send', idempotency_key: key() });
    expect((await log()).entries).toHaveLength(1);
    await fetch(`${base}/__mock/reset`, { method: 'POST' });
    expect((await log()).entries).toHaveLength(0);
    expect((await item('W-2001')).workspace?.revision).toBe(3);
  });
});
