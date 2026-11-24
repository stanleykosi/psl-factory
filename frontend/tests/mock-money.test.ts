import { readFileSync } from 'node:fs';
import type { Server } from 'node:http';
import type { AddressInfo } from 'node:net';
import { join } from 'node:path';

import { afterAll, beforeAll, describe, expect, it } from 'vitest';

// @ts-expect-error plain ESM module without type declarations
import { SCENARIO_BODIES, startMockServer } from '../mock/server.mjs';

// F-71: the money tab and one recorded completion in the contract mock (the live shape is checked in
// mock-live-money.test.ts). The scripted answers are test cases, not access rules.
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

describe('the mock serves money', () => {
  it('P-0101 serves the fixture as stored, for finance_lead and pm, with no report read', async () => {
    for (const persona of ['finance_lead', 'pm']) {
      expect(await get('/api/v1/projects/P-0101/money', persona)).toEqual({ status: 200, body: readJson(join(fixtures, 'projects/money/P-0101.json')) });
    }
  });

  it.each([
    ['/api/v1/projects/P-0107/money', 'finance_lead', 403],
    ['/api/v1/projects/P-0108/money', 'finance_lead', 404],
    ['/api/v1/projects/P-0099/money', 'finance_lead', 404],
    ['/api/v1/projects/P-0104/money', 'pm', 404],
    ['/api/v1/projects/P-0107/money', 'pm', 404],
    ['/api/v1/projects/P-0101/money?figure=nope', 'finance_lead', 404],
    ['/api/v1/projects/P-0101/money', 'none', 404],
  ])('%s as %s answers %i with the standard body and nothing from the fixture', async (path, persona, status) => {
    expect(await get(path, persona)).toEqual({ status, body: SCENARIO_BODIES[status] });
  });

  it('there is no report route any more: the old report read is not answered with a report', async () => {
    expect((await get('/api/v1/reports/R-0101')).body).not.toHaveProperty('figures');
  });

  it('a case with no money fixture still answers exactly 501', async () => {
    expect(await get('/api/v1/projects/P-0109/money')).toEqual({ status: 501, body: NOT_MOCKED });
  });

  it('X-Mock-Scenario and psl_mock_scenario still win on money and on one completion', async () => {
    expect((await get('/api/v1/projects/P-0101/money', 'finance_lead', { 'X-Mock-Scenario': '403' })).status).toBe(403);
    expect((await get('/api/v1/projects/P-0101/milestones/3101', 'finance_lead', { 'X-Mock-Scenario': '401' })).status).toBe(401);
    const response = await fetch(`${base}/api/v1/projects/P-0101/money`, { headers: { Cookie: 'psl_mock_persona=finance_lead; psl_mock_scenario=404' } });
    expect(response.status).toBe(404);
  });
});
