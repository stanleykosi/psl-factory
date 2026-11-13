import { spawnSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import type { Server } from 'node:http';
import type { AddressInfo } from 'node:net';
import { join } from 'node:path';

import Ajv2020 from 'ajv/dist/2020';
import addFormats from 'ajv-formats';
import { afterAll, beforeAll, describe, expect, it } from 'vitest';

// @ts-expect-error plain ESM module without type declarations
import { M1_OPERATIONS, OPENAPI_PATH, PERSONAS, startMockServer } from '../mock/server.mjs';

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
  const valid = validate(body);
  expect(valid, `${id} ${status}: ${ajv.errorsText(validate.errors)}`).toBe(true);
}

describe('mock server matches openapi.json', () => {
  for (const id of M1_OPERATIONS as string[]) {
    for (const persona of PERSONAS as string[]) {
      it(`${id} succeeds for persona ${persona} with a schema-valid body`, async () => {
        const { status, body } = await request(id, { persona });
        expect(status).toBe(200);
        expectValid(id, 200, body);
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
