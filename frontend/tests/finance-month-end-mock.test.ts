import { readFileSync } from 'node:fs';
import type { Server } from 'node:http';
import type { AddressInfo } from 'node:net';
import { join } from 'node:path';

import Ajv2020 from 'ajv/dist/2020';
import addFormats from 'ajv-formats';
import { afterAll, beforeAll, describe, expect, it } from 'vitest';

// @ts-expect-error plain ESM module without type declarations
import { contractBody } from '../mock/finance.mjs';
// @ts-expect-error plain ESM module without type declarations
import { OPENAPI_PATH, startMockServer } from '../mock/server.mjs';

type Spec = { paths: Record<string, Record<string, { responses: Record<string, { content: { 'application/json': { schema: object } } }> }>> };
const schemaOf = (file: string, status: string) =>
  (JSON.parse(readFileSync(file, 'utf8')) as Spec).paths['/api/v1/finance/month-end'].get.responses[status].content['application/json']
    .schema;
const ajv = new Ajv2020({ allErrors: true, strict: false });
addFormats(ajv);
const v4 = ajv.compile(schemaOf(OPENAPI_PATH, '200'));
const v4Error = ajv.compile(schemaOf(OPENAPI_PATH, '403'));
// v7 (proposal D-MONTH-END-VIEW r1) is read by this test only; the mock and the app stay on v4.
const v7 = ajv.compile(schemaOf(join(__dirname, '../../architecture/packages/v7/openapi.json'), '200'));

const fixtures = join(__dirname, '../mock/fixtures');
const read = (name: string) => JSON.parse(readFileSync(join(fixtures, name), 'utf8')) as Record<string, unknown>;
const VARIANTS = ['board-phone', 'known', 'unknown', 'empty'];

let server: Server;
let base: string;
beforeAll(async () => {
  server = await startMockServer({ port: 0 });
  base = `http://127.0.0.1:${(server.address() as AddressInfo).port}`;
});
afterAll(() => new Promise<void>((resolve) => server.close(() => resolve())));

async function get(query: string, cookie = '') {
  const response = await fetch(`${base}/api/v1/finance/month-end${query}`, { headers: { Cookie: cookie } });
  return { status: response.status, body: (await response.json()) as Record<string, unknown> };
}

describe('E-MONTH-END mock', () => {
  it('serves the default fixture to finance_lead for 2026-10', async () => {
    const { status, body } = await get('?period=2026-10', 'psl_mock_persona=finance_lead');
    expect(status).toBe(200);
    expect(body).toEqual(read('E-MONTH-END.json'));
  });

  it('refuses pm and none with the declared 403 shape', async () => {
    for (const persona of ['pm', 'none']) {
      const { status, body } = await get('?period=2026-10', `psl_mock_persona=${persona}`);
      expect(status).toBe(403);
      expect(body).toEqual({ code: 'forbidden', message: 'Month-end is for Finance.' });
      expect(v4Error(body)).toBe(true);
    }
  });

  it('answers 404 for another period, a missing one and a repeated one', async () => {
    for (const query of ['?period=2026-09', '', '?period=2026-10&period=2026-11']) {
      const { status, body } = await get(query);
      expect(status, query).toBe(404);
      expect(body).toEqual({ code: 'not_found', message: 'We could not find that record.' });
    }
  });

  it('serves each variant by cookie, the contract body, and the default for anything else', async () => {
    for (const name of VARIANTS) {
      expect((await get('?period=2026-10', `psl_mock_month_end=${name}`)).body).toEqual(read(`finance/month-end.${name}.json`));
    }
    expect((await get('?period=2026-10', 'psl_mock_month_end=contract')).body).toEqual(contractBody(read('E-MONTH-END.json')));
    expect((await get('?period=2026-10', 'psl_mock_month_end=other')).body).toEqual(read('E-MONTH-END.json'));
  });

  it('every served body is v7-valid as served and v4-valid after contractBody, with no sample key', () => {
    const bodies = [read('E-MONTH-END.json'), ...VARIANTS.map((name) => read(`finance/month-end.${name}.json`))];
    for (const body of bodies) {
      expect(v7(body), ajv.errorsText(v7.errors)).toBe(true);
      expect(v4(contractBody(body)), ajv.errorsText(v4.errors)).toBe(true);
      expect(body).not.toHaveProperty('sample');
    }
    expect(v4(read('E-MONTH-END.json'))).toBe(false);
  });

  it('contractBody strips exactly the proposal keys', () => {
    const body = contractBody(read('E-MONTH-END.json')) as { tasks: Record<string, unknown>[] };
    expect(Object.keys(body).sort()).toEqual(['cash_received', 'period', 'tasks']);
    expect(body.tasks.map((task) => Object.keys(task).sort().join(','))).toEqual([
      ...Array(6).fill('line,state,where,work_id'),
      'line,state,where',
    ]);
  });

  it('variants differ from the default only as the spec says', () => {
    const base = read('E-MONTH-END.json') as Record<string, unknown> & { tasks: unknown[] };
    expect(read('finance/month-end.board-phone.json')).toEqual({ ...base, tasks: base.tasks.slice(0, 6) });
    const { agent_note: _note, next_action: _action, ...rest } = base;
    void _note;
    void _action;
    const known = { amount: '4712500.00', currency: 'NGN', unknown: false };
    expect(read('finance/month-end.known.json')).toEqual({
      ...rest,
      cash_received: known,
      cash_received_detail: { known, has_unknown: false },
    });
    expect(read('finance/month-end.unknown.json')).toEqual({ ...base, cash_received_detail: { has_unknown: true } });
    expect(read('finance/month-end.empty.json')).toEqual({
      ...rest,
      tasks: [],
      summary: { done: 0, waiting: 0, in_progress: 0, total: 0 },
      cash_received_detail: { has_unknown: true },
    });
  });
});
