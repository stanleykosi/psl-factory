import { readdirSync, readFileSync } from 'node:fs';
import type { Server } from 'node:http';
import type { AddressInfo } from 'node:net';
import { join } from 'node:path';

import Ajv2020 from 'ajv/dist/2020';
import addFormats from 'ajv-formats';
import { afterAll, beforeAll, describe, expect, it } from 'vitest';

// @ts-expect-error plain ESM module without type declarations
import { OPENAPI_PATH, SCENARIO_BODIES, startMockServer } from '../mock/server.mjs';

// F-26: E-PROJECT-TAB (money) and E-REPORT in the contract mock, against the openapi the mock loads (architecture v7).
// Every 200 body is checked in full, with no field stripped; the scripted answers are test cases, not access rules.
type Response = { content: { 'application/json': { schema: object } } };
const openapi = JSON.parse(readFileSync(OPENAPI_PATH, 'utf8')) as { paths: Record<string, { get: { responses: Record<string, Response> } }> };
const ajv = new Ajv2020({ allErrors: true, strict: true });
addFormats(ajv);
const compile = (path: string) =>
  Object.fromEntries(Object.entries(openapi.paths[path].get.responses).map(([status, r]) => [status, ajv.compile(r.content['application/json'].schema)]));
const tab = compile('/api/v1/projects/{case_id}/{tab}');
const report = compile('/api/v1/reports/{report_id}');

const fixtures = join(__dirname, '../mock/fixtures');
const readJson = (path: string) => JSON.parse(readFileSync(path, 'utf8'));
const NOT_MOCKED = { code: 'not_mocked', message: 'Not available in the mock yet.' };

let server: Server;
let base: string;

beforeAll(async () => {
  server = await startMockServer({ port: 0 });
  base = `http://127.0.0.1:${(server.address() as AddressInfo).port}`;
});
afterAll(() => new Promise<void>((resolve) => server.close(() => resolve())));

async function get(path: string, persona = 'finance_lead', headers: Record<string, string> = {}) {
  const response = await fetch(base + path, { headers: { Cookie: `psl_mock_persona=${persona}`, ...headers } });
  expect(response.headers.get('content-type')).toBe('application/json');
  return { status: response.status, body: (await response.json()) as Record<string, unknown> };
}

describe('money and report fixtures match the contract', () => {
  const moneyFiles = readdirSync(join(fixtures, 'projects/money')).filter((n) => /^P-\d+\.json$/.test(n));
  const reportFiles = readdirSync(join(fixtures, 'reports')).filter((n) => /^R-\d+\.json$/.test(n));

  it.each(moneyFiles)('money %s validates as an E-PROJECT-TAB 200 body', (name) => {
    const body = readJson(join(fixtures, 'projects/money', name));
    expect(tab['200'](body), ajv.errorsText(tab['200'].errors)).toBe(true);
    expect(Array.isArray(body.money)).toBe(true);
  });

  it.each(reportFiles)('report %s validates as an E-REPORT 200 body', (name) => {
    const body = readJson(join(fixtures, 'reports', name));
    expect(report['200'](body), ajv.errorsText(report['200'].errors)).toBe(true);
  });

  it('an unknown amount is never 0: unknown amounts carry no amount field', () => {
    for (const name of moneyFiles) {
      const text = readFileSync(join(fixtures, 'projects/money', name), 'utf8');
      expect(text).not.toMatch(/"amount": "-?0+\.00"/);
      for (const row of readJson(join(fixtures, 'projects/money', name)).money as { amount: { unknown: boolean; amount?: string } }[]) {
        if (row.amount.unknown) expect(row.amount.amount).toBeUndefined();
      }
    }
  });
});

describe('the mock serves money and reports', () => {
  it('P-0101 serves the board body as stored, for finance_lead and pm', async () => {
    for (const persona of ['finance_lead', 'pm']) {
      const result = await get('/api/v1/projects/P-0101/money', persona);
      expect(result.status).toBe(200);
      expect(result.body).toEqual(readJson(join(fixtures, 'projects/money/P-0101.json')));
      expect(tab['200'](result.body)).toBe(true);
    }
    const r = await get('/api/v1/reports/R-0101');
    expect(r).toEqual({ status: 200, body: readJson(join(fixtures, 'reports/R-0101.json')) });
    expect(report['200'](r.body)).toBe(true);
  });

  it('every served 200 body validates', async () => {
    for (const id of ['P-0101', 'P-0102', 'P-0103', 'P-0105', 'P-0106']) {
      const result = await get(`/api/v1/projects/${id}/money`);
      expect(result.status, id).toBe(200);
      expect(tab['200'](result.body), `${id}: ${ajv.errorsText(tab['200'].errors)}`).toBe(true);
    }
    for (const id of ['R-0101', 'R-0102']) {
      const result = await get(`/api/v1/reports/${id}`);
      expect(result.status, id).toBe(200);
      expect(report['200'](result.body), id).toBe(true);
    }
  });

  it.each([
    ['/api/v1/projects/P-0107/money', 'finance_lead', 403],
    ['/api/v1/projects/P-0108/money', 'finance_lead', 404],
    ['/api/v1/projects/P-0099/money', 'finance_lead', 404],
    ['/api/v1/projects/P-0104/money', 'pm', 404],
    ['/api/v1/projects/P-0107/money', 'pm', 404],
    ['/api/v1/reports/R-0106', 'finance_lead', 403],
    ['/api/v1/reports/R-0101', 'none', 404],
    ['/api/v1/reports/R-9999', 'finance_lead', 404],
  ])('%s as %s answers %i with the standard body and nothing from the fixture', async (path, persona, status) => {
    const result = await get(path, persona);
    expect(result).toEqual({ status, body: SCENARIO_BODIES[status] });
    const validate = path.includes('/reports/') ? report : tab;
    expect(validate[String(status)](result.body)).toBe(true);
  });

  it('R-0103 answers 500 server_error', async () => {
    const result = await get('/api/v1/reports/R-0103');
    expect(result).toEqual({ status: 500, body: { code: 'server_error', message: 'Something went wrong on our side.' } });
  });

  it('the other tabs, and a case with no money fixture, still answer exactly 501', async () => {
    for (const path of ['/api/v1/projects/P-0101/milestones', '/api/v1/projects/P-0101/documents', '/api/v1/projects/P-0101/registers', '/api/v1/projects/P-0101/actions', '/api/v1/projects/P-0109/money']) {
      const result = await get(path);
      expect(result, path).toEqual({ status: 501, body: NOT_MOCKED });
    }
  });

  it('X-Mock-Scenario and psl_mock_scenario still win on money and reports', async () => {
    expect((await get('/api/v1/projects/P-0101/money', 'finance_lead', { 'X-Mock-Scenario': '403' })).status).toBe(403);
    expect((await get('/api/v1/reports/R-0101', 'finance_lead', { 'X-Mock-Scenario': '401' })).status).toBe(401);
    const response = await fetch(`${base}/api/v1/projects/P-0101/money`, { headers: { Cookie: 'psl_mock_persona=finance_lead; psl_mock_scenario=404' } });
    expect(response.status).toBe(404);
  });
});
