import { spawnSync } from 'node:child_process';
import { readdirSync, readFileSync } from 'node:fs';
import type { Server } from 'node:http';
import type { AddressInfo } from 'node:net';
import { join } from 'node:path';

import Ajv2020 from 'ajv/dist/2020';
import addFormats from 'ajv-formats';
import { afterAll, beforeAll, describe, expect, it } from 'vitest';

// @ts-expect-error plain ESM module without type declarations
import { M1_OPERATIONS, OPENAPI_PATH, PERSONAS, startMockServer } from '../mock/server.mjs';
// @ts-expect-error plain ESM module without type declarations
import { contractBody } from '../mock/exceptions.mjs';

type Operation = { operationId: string; responses: Record<string, { content: { 'application/json': { schema: object } } }> };
const openapi = JSON.parse(readFileSync(OPENAPI_PATH, 'utf8')) as { paths: Record<string, Record<string, Operation>> };

const ajv = new Ajv2020({ allErrors: true, strict: true });
addFormats(ajv);

const operations = Object.entries(openapi.paths).flatMap(([path, ops]) =>
  Object.entries(ops)
    .filter(([, op]) => op && typeof op === 'object' && 'operationId' in op)
    .map(([method, op]) => ({ path, method: method.toUpperCase(), op })),
);
const byId = (id: string) => operations.find((o) => o.op.operationId === id)!;

const PATH_VALUES: Record<string, string> = { work_id: 'W-1001', task_id: 'T-2001' };
const QUERY: Record<string, string> = { 'E-WORK-LIST': '?queue=needs_me', 'E-WORK-HISTORY': '?kind=all' };
const BODY: Record<string, unknown> = {
  'E-TASK-CLAIM': { expected_revision: 2 },
  'E-TASK-DECIDE': { expected_revision: 2, verdict: 'approve' },
};
// Operations a persona may not use answer the declared status instead of 200 (E-EXCEPTIONS is Leads only).
const PERSONA_STATUS: Record<string, Record<string, number>> = { 'E-EXCEPTIONS': { pm: 403 } };
// Engineering-proposal fields the mock serves ahead of the contract are removed before the schema check (F-06).
const CONTRACT_BODY: Record<string, (body: unknown) => unknown> = { 'E-EXCEPTIONS': contractBody };
const errorSchema = byId('E-ME').op.responses['401'].content['application/json'].schema;

let server: Server;
let base: string;

beforeAll(async () => {
  server = await startMockServer({ port: 0 });
  base = `http://127.0.0.1:${(server.address() as AddressInfo).port}`;
});
afterAll(() => new Promise<void>((resolve) => server.close(() => resolve())));

async function request(id: string, init: { persona?: string; scenario?: string; csrf?: string | null } = {}) {
  const { path, method } = byId(id);
  const url = base + path.replace(/\{(\w+)\}/g, (_, name: string) => PATH_VALUES[name] ?? 'X-1') + (QUERY[id] ?? '');
  const headers: Record<string, string> = { Cookie: `psl_mock_persona=${init.persona ?? 'finance_lead'}` };
  if (init.scenario) headers['X-Mock-Scenario'] = init.scenario;
  if (method !== 'GET' && init.csrf !== null) headers['X-CSRFToken'] = init.csrf ?? `mock-csrf-${init.persona ?? 'finance_lead'}`;
  let body: string | undefined;
  if (method !== 'GET') {
    headers['Content-Type'] = 'application/json';
    body = JSON.stringify(BODY[id] ?? {});
  }
  const response = await fetch(url, { method, headers, body });
  expect(response.headers.get('content-type')).toBe('application/json');
  return { status: response.status, body: (await response.json()) as Record<string, unknown> };
}

function expectValid(id: string, status: number, body: unknown) {
  const declared = byId(id).op.responses[String(status)];
  const schema = declared ? declared.content['application/json'].schema : errorSchema;
  const validate = ajv.compile(schema);
  const valid = validate(CONTRACT_BODY[id]?.(body) ?? body);
  expect(valid, `${id} ${status}: ${ajv.errorsText(validate.errors)}`).toBe(true);
}

describe('mock server matches openapi.json', () => {
  for (const id of M1_OPERATIONS as string[]) {
    for (const persona of PERSONAS as string[]) {
      const expected = PERSONA_STATUS[id]?.[persona] ?? 200;
      it(`${id} answers ${expected} for persona ${persona} with a schema-valid body`, async () => {
        const { status, body } = await request(id, { persona });
        expect(status).toBe(expected);
        expectValid(id, expected, body);
      });
    }

    const errorStatuses = Object.keys(byId(id).op.responses).filter((s) => Number(s) >= 400);
    for (const status of errorStatuses) {
      it(`${id} returns declared ${status} via X-Mock-Scenario`, async () => {
        const result = await request(id, { scenario: status });
        expect(result.status).toBe(Number(status));
        expectValid(id, result.status, result.body);
      });
    }
  }

  it('ignores a scenario the operation does not declare', async () => {
    const result = await request('E-ME', { scenario: '409' });
    expect(result.status).toBe(200);
  });

  it('a malformed cookie value falls back to the default persona and the mock keeps serving', async () => {
    const malformed = await fetch(`${base}/api/v1/me`, { headers: { Cookie: 'psl_mock_persona=%' } });
    expect(malformed.status).toBe(200);
    expect(((await malformed.json()) as { name: string }).name).toBe('Ada Okafor');
    expect((await request('E-ME', { persona: 'pm' })).body.name).toBe('Tunde Bello');
  });

  it('E-ME carries each persona fixture', async () => {
    const names = await Promise.all((PERSONAS as string[]).map(async (persona) => (await request('E-ME', { persona })).body));
    expect(names.map((me) => [me.name, me.destinations, me.csrf_token])).toEqual([
      ['Ada Okafor', ['my_work', 'projects', 'overview', 'assistant', 'setup'], 'mock-csrf-finance_lead'],
      ['Tunde Bello', ['my_work', 'projects', 'assistant'], 'mock-csrf-pm'],
      ['Sample Person', [], 'mock-csrf-none'],
    ]);
  });

  it('every E-WORK-LIST item and the E-WORK-ITEM record are marked sample', async () => {
    const list = await request('E-WORK-LIST');
    const items = list.body.items as { sample: boolean }[];
    expect(items.length).toBeGreaterThan(0);
    expect(items.every((item) => item.sample === true)).toBe(true);
    expect((await request('E-WORK-ITEM')).body.sample).toBe(true);
  });

  it('a write without X-CSRFToken gets 403 csrf_failed', async () => {
    const result = await request('E-TASK-CLAIM', { csrf: null });
    expect(result).toEqual({ status: 403, body: { code: 'csrf_failed', message: 'Your session check failed. Reload and try again.' } });
    expectValid('E-TASK-CLAIM', 403, result.body);
  });

  it("a write with another persona's token gets 403 csrf_failed", async () => {
    const result = await request('E-TASK-DECIDE', { persona: 'pm', csrf: 'mock-csrf-finance_lead' });
    expect(result.status).toBe(403);
    expect(result.body.code).toBe('csrf_failed');
    expectValid('E-TASK-DECIDE', 403, result.body);
  });

  it('a non-M-1 operation gets 501 not_mocked', async () => {
    const result = await request('E-LINES');
    expect(result).toEqual({ status: 501, body: { code: 'not_mocked', message: 'Not available in the mock yet.' } });
    expectValid('E-LINES', 501, result.body);
  });

  it('refuses to start with NODE_ENV=production', () => {
    const run = spawnSync(process.execPath, [join(__dirname, '../mock/server.mjs')], {
      env: { ...process.env, NODE_ENV: 'production', MOCK_PORT: '0' },
      encoding: 'utf8',
      timeout: 10000,
    });
    expect(run.status).toBe(1);
    expect(run.stderr).toContain('refuses to start');
  });
});

describe('mock work items: per-id fixtures, fallback and history parameters', () => {
  const workDir = join(__dirname, '../mock/fixtures/work');
  const get = async (path: string) => {
    const response = await fetch(base + path, { headers: { Cookie: 'psl_mock_persona=finance_lead' } });
    const text = await response.text();
    return { status: response.status, text, body: JSON.parse(text) as Record<string, unknown> };
  };
  const readJson = (path: string) => JSON.parse(readFileSync(path, 'utf8')) as Record<string, unknown>;
  type Row = { _kind?: string; at: string };
  const w1004 = readJson(join(workDir, 'W-1004.history.json')) as { items: Row[] };

  it('serves the per-id item and 404 for the reserved no-access id', async () => {
    const w1003 = await get('/api/v1/work/W-1003');
    expect(w1003.status).toBe(200);
    expect(w1003.body).toEqual(readJson(join(workDir, 'W-1003.json')));
    expectValid('E-WORK-ITEM', 200, w1003.body);
    for (const path of ['/api/v1/work/W-1099', '/api/v1/work/W-1099/history?kind=all']) {
      const denied = await get(path);
      expect(denied).toMatchObject({ status: 404, body: { code: 'not_found', message: 'We could not find that record.' } });
    }
  });

  it('falls back to the unchanged default fixtures for other ids', async () => {
    const other = await get('/api/v1/work/ANY-OTHER');
    expect(other.status).toBe(200);
    expect(other.body).toEqual(readJson(join(__dirname, '../mock/fixtures/E-WORK-ITEM.json')));
    const otherHistory = await get('/api/v1/work/ANY-OTHER/history?kind=all');
    expect(otherHistory.body).toEqual(readJson(join(__dirname, '../mock/fixtures/E-WORK-HISTORY.json')));
  });

  it('never serves a sidecar file such as W-1004.history as an item', async () => {
    const sidecar = await get('/api/v1/work/W-1004.history');
    expect(sidecar.status).toBe(200);
    expect(sidecar.body).toEqual(readJson(join(__dirname, '../mock/fixtures/E-WORK-ITEM.json')));
  });

  it('filters by kind, pages by limit and cursor, and treats other limits as 20', async () => {
    const decisions = await get('/api/v1/work/W-1004/history?kind=decisions');
    const expected = w1004.items.filter((row) => row._kind === 'decision').map((row) => row.at);
    expect((decisions.body.items as Row[]).map((row) => row.at)).toEqual(expected);
    expect(expected.length).toBeGreaterThan(0);
    expectValid('E-WORK-HISTORY', 200, decisions.body);

    const first = await get('/api/v1/work/W-1004/history?kind=all&limit=10');
    expect((first.body.items as Row[]).map((row) => row.at)).toEqual(w1004.items.slice(0, 10).map((row) => row.at));
    expect(typeof first.body.next_cursor).toBe('string');
    const rest = await get(`/api/v1/work/W-1004/history?kind=all&limit=10&cursor=${encodeURIComponent(first.body.next_cursor as string)}`);
    expect((rest.body.items as Row[]).map((row) => row.at)).toEqual(w1004.items.slice(10).map((row) => row.at));
    expect(rest.body).not.toHaveProperty('next_cursor');

    const odd = await get('/api/v1/work/W-1004/history?limit=7');
    expect((odd.body.items as Row[]).length).toBe(12);
    expect(odd.body).not.toHaveProperty('next_cursor');
    const badCursor = await get('/api/v1/work/W-1004/history?limit=10&cursor=nonsense');
    expect((badCursor.body.items as Row[])[0].at).toBe(w1004.items[0].at);
  });

  it('never sends the mock-only _kind', async () => {
    for (const kind of ['all', 'decisions', 'agent_work', 'evidence']) {
      for (const id of ['W-1001', 'W-1004', 'ANY-OTHER']) {
        const { text, body } = await get(`/api/v1/work/${id}/history?kind=${kind}&limit=50`);
        expect(text).not.toContain('"_kind"');
        expectValid('E-WORK-HISTORY', 200, body);
      }
    }
  });

  it('scenarios still win over the per-id fixtures', async () => {
    const response = await fetch(`${base}/api/v1/work/W-1003`, { headers: { 'X-Mock-Scenario': '403' } });
    expect(response.status).toBe(403);
  });

  it('every fixture in fixtures/work is schema-valid with _kind removed', () => {
    // Item bodies are W-<digits>.json and histories W-<digits>.history.json; other sidecars (F-04's) are not checked here.
    const files = readdirSync(workDir).filter((name) => /^W-\d+(\.history)?\.json$/.test(name));
    expect(files.length).toBeGreaterThanOrEqual(7);
    for (const name of files) {
      const body = readJson(join(workDir, name));
      if (name.endsWith('.history.json')) {
        const items = (body.items as Record<string, unknown>[]).map((item) =>
          Object.fromEntries(Object.entries(item).filter(([key]) => key !== '_kind')),
        );
        expectValid('E-WORK-HISTORY', 200, { ...body, items });
      } else {
        expectValid('E-WORK-ITEM', 200, body);
        expect(body.sample, name).toBe(true);
      }
    }
  });

  it('W-1004 carries the A-WORKITEM given and a 12-row history', () => {
    const item = readJson(join(workDir, 'W-1004.json')) as { facts: { name: string; status: string }[]; agent: { status: string; steps: { text: string; status: string }[] } };
    expect(item.facts.map((f) => `${f.name}:${f.status}`)).toEqual([
      'drafted:earned',
      'reviewed:earned',
      'approved:earned',
      'sent:not_yet',
      'receipt_recorded:unknown',
      'verified:not_yet',
    ]);
    expect(item.agent.status).toBe('done');
    for (const step of item.agent.steps) expect(`${step.text} ${step.status}`).not.toMatch(/approv|send|pay/i);
    const rows = w1004.items as (Row & { actor: string; event: string; restricted: boolean; version?: string; detail?: string })[];
    expect(rows).toHaveLength(12);
    expect([...rows].map((r) => r.at)).toEqual([...rows].map((r) => r.at).sort().reverse());
    const restricted = rows.filter((r) => r.restricted);
    expect(restricted).toHaveLength(1);
    expect(restricted[0]).not.toHaveProperty('version');
    expect(restricted[0]).not.toHaveProperty('detail');
    expect(restricted[0].event).toBe('Restricted');
    expect(rows.filter((r) => !r._kind).map((r) => r.event)).toEqual(['Started the line']);
  });
});
