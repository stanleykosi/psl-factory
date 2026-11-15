// F-21: the contract mock's weekly fixtures W-2201 to W-2208 through E-WORK-STEP and E-LINE-OPTIONS. Mock evidence
// only: the idempotency map proves one send per key on the mock, not the backend's promise (unbuilt).
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
const itemSchema = ajv.compile(openapi.paths['/api/v1/work/{work_id}'].get.responses['200'].content['application/json'].schema);
const stepReply = (status: number) => ajv.compile(openapi.paths['/api/v1/work/{work_id}/steps'].post.responses[String(status)].content['application/json'].schema);
const dir = join(__dirname, '../mock/fixtures/work');
const fixture = (name: string) => JSON.parse(readFileSync(join(dir, `${name}.json`), 'utf8'));
const IDS = ['W-2201', 'W-2202', 'W-2203', 'W-2204', 'W-2205', 'W-2206', 'W-2207', 'W-2208'];

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

type Body = { outcome?: string; revision?: number; fields: { name: string }[]; workspace: { view: string; revision: number; line_key: string }; reconcile?: unknown; allowed_actions?: string[]; sample?: boolean };
let n = 0;
const key = () => `00000000-0000-4000-9000-${String(++n).padStart(12, '0')}`;
const HEADERS = { Cookie: 'psl_mock_persona=pm', 'Content-Type': 'application/json', 'X-CSRFToken': 'mock-csrf-pm' };
const step = async (workId: string, body: Record<string, unknown>) => {
  const response = await fetch(`${base}/api/v1/work/${workId}/steps`, { method: 'POST', headers: HEADERS, body: JSON.stringify(body) });
  return { status: response.status, body: (await response.json()) as Body };
};
const get = async (workId: string) => (await fetch(`${base}/api/v1/work/${workId}`, { headers: HEADERS })).json() as Promise<Body>;
const log = async () => (await (await fetch(`${base}/__mock/workspace-log`)).json()) as { sends: Record<string, number> };

describe('weekly fixtures', () => {
  it('W-2201 to W-2208 are served as their own fixtures, schema-valid, sample, on the weekly_report line', async () => {
    for (const id of IDS) {
      const served = await get(id);
      expect(served, id).toEqual(fixture(id));
      expect(itemSchema(served), id).toBe(true);
      expect(served.sample, id).toBe(true);
      expect(served.workspace.line_key, id).toBe('weekly_report');
      expect(JSON.stringify(served), id).not.toMatch(/"(returned|received)"/);
    }
  });

  it('every script names only steps its item offers; every sidecar item is schema-valid', () => {
    for (const id of IDS) {
      let script: Record<string, { status: number; body?: unknown }> = {};
      try {
        script = fixture(`${id}.steps`);
      } catch {
        continue;
      }
      const keys = fixture(id).workspace.steps.map((s: { key: string }) => s.key);
      for (const [name, entry] of Object.entries(script)) {
        expect(keys, `${id} ${name}`).toContain(name);
        if (entry.status === 422) expect(stepReply(422)(entry.body)).toBe(true);
      }
    }
    for (const id of ['W-2201', 'W-2205', 'W-2206']) expect(itemSchema(fixture(`${id}.next`)), id).toBe(true);
  });

  it('the four cite fields have the same eight descriptors on both steps of the default items', () => {
    for (const id of ['W-2201', 'W-2202', 'W-2206', 'W-2207']) {
      const steps = fixture(id).workspace.steps;
      expect(steps.map((s: { key: string }) => s.key)).toEqual(['send_to_tola', 'save_draft']);
      for (const s of steps) {
        expect(s.fields.map((f: { name: string }) => f.name)).toEqual(['status', 'status_cites', 'risks', 'risks_cites', 'timeline', 'timeline_cites', 'next_steps', 'next_steps_cites']);
        for (const f of s.fields) expect(f.required, `${id} ${f.name}`).toBe(false);
        for (const f of s.fields.filter((x: { type: string }) => x.type === 'records')) expect(f).toMatchObject({ multiple: true, options_source: 'line_options' });
      }
    }
  });
});

describe('E-WORK-STEP on the weekly fixtures', () => {
  it('W-2201 save_draft is done and keeps the default state at the next revision; send_to_tola serves the assembling item', async () => {
    const draft = await step('W-2201', { expected_revision: 4, step: 'save_draft', idempotency_key: key() });
    expect(draft.status).toBe(200);
    expect(stepReply(200)(draft.body)).toBe(true);
    expect((await get('W-2201')).workspace.view).toBe('default');
    expect((await get('W-2201')).workspace.revision).toBe(5);
    await fetch(`${base}/__mock/reset`, { method: 'POST' });
    const send = await step('W-2201', { expected_revision: 4, step: 'send_to_tola', inputs: { status: 'x', status_cites: ['MS-0002'] }, idempotency_key: key() });
    expect(send.body).toMatchObject({ outcome: 'done', revision: 5 });
    expect((await get('W-2201')).workspace.view).toBe('assembling');
  });

  it('W-2202 send_to_tola answers the scripted 422 naming risks and next_steps_cites', async () => {
    const answer = await step('W-2202', { expected_revision: 4, step: 'send_to_tola', inputs: { risks: 'TBD' }, idempotency_key: key() });
    expect(answer.status).toBe(422);
    expect(stepReply(422)(answer.body)).toBe(true);
    expect(answer.body.fields.map((f: { name: string }) => f.name)).toEqual(['risks', 'next_steps_cites', 'parts']);
  });

  it('a bad body is 422, a wrong revision is 409, an unknown step is 404, a repeated key replays with no second send', async () => {
    expect((await step('W-2204', { expected_revision: 3, step: 'approve_send' })).status).toBe(422);
    expect((await step('W-2204', { expected_revision: 2, step: 'approve_send', idempotency_key: key() })).status).toBe(409);
    expect((await step('W-2204', { expected_revision: 3, step: 'nope', idempotency_key: key() })).status).toBe(404);
    const k = key();
    const first = await step('W-2204', { expected_revision: 3, step: 'approve_send', idempotency_key: k });
    expect(first.body).toMatchObject({ outcome: 'done', revision: 4 });
    expect(await step('W-2204', { expected_revision: 3, step: 'approve_send', idempotency_key: k })).toEqual(first);
    expect((await log()).sends[k]).toBe(1);
  });

  it('W-2205 approve_send answers effect_uncertain and the re-read carries reconcile with allowed_actions', async () => {
    const answer = await step('W-2205', { expected_revision: 3, step: 'approve_send', idempotency_key: key() });
    expect(answer.body.outcome).toBe('effect_uncertain');
    const reread = await get('W-2205');
    expect(reread.reconcile).toBeDefined();
    expect(reread.allowed_actions).toEqual(['reconcile']);
  });

  it('W-2206: a 409 swaps in the next version once, then the step succeeds; save_draft is a scripted 500', async () => {
    expect((await step('W-2206', { expected_revision: 4, step: 'send_to_tola', idempotency_key: key() })).status).toBe(409);
    expect((await get('W-2206')).workspace.revision).toBe(5);
    expect((await step('W-2206', { expected_revision: 5, step: 'send_to_tola', idempotency_key: key() })).status).toBe(200);
    await fetch(`${base}/__mock/reset`, { method: 'POST' });
    expect((await step('W-2206', { expected_revision: 4, step: 'save_draft', idempotency_key: key() })).status).toBe(500);
  });
});

describe('E-LINE-OPTIONS for the weekly cite fields', () => {
  const options = async (field: string, persona = 'pm') => fetch(`${base}/api/v1/lines/weekly_report/fields/${field}/options`, { headers: { Cookie: `psl_mock_persona=${persona}` } });

  it('serves this week’s records for each cite field, with no mock-only keys, and the panel references agree', async () => {
    const served = await Promise.all(['status_cites', 'risks_cites', 'timeline_cites', 'next_steps_cites'].map(async (f) => (await options(f)).json() as Promise<{ items: Record<string, unknown>[] }>));
    for (const page of served) {
      expect(page.items.map((i) => i.value)).toEqual(['MS-0002', 'MTG-0141', 'MTG-0140', 'ISS-0233', 'ACT-0412', 'CR-0031']);
      for (const item of page.items) expect(Object.keys(item).some((k) => k.startsWith('_'))).toBe(false);
    }
    // every reference a fixture cites is one of the options
    const values = new Set(served[0].items.map((i) => i.value));
    const cited = (fixture('W-2204').workspace.sections[0].items as { cites: { reference: string }[] }[]).flatMap((i) => i.cites.map((c) => c.reference));
    for (const reference of cited) expect(values.has(reference), reference).toBe(true);
  });

  it('is not served for an unknown field or to a persona without the line', async () => {
    expect((await options('not_a_field')).status).toBe(404);
    expect((await options('status_cites', 'none')).status).toBe(404);
  });
});
