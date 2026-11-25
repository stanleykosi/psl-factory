import type { Server } from 'node:http';
import type { AddressInfo } from 'node:net';

import { afterAll, beforeAll, describe, expect, it } from 'vitest';

// @ts-expect-error plain ESM module without type declarations
import { startMockServer } from '../mock/server.mjs';

// E-PROJECT-TAB in the contract mock (F-25): the handler's rules (visibility, query, cookies) hold. Every tab is the live
// sectioned shape and is validated against the live contract in mock-live-project-sections.test.ts and mock-live-money.test.ts.
let server: Server;
let base: string;
beforeAll(async () => {
  server = await startMockServer({ port: 0 });
  base = `http://127.0.0.1:${(server.address() as AddressInfo).port}`;
});
afterAll(() => new Promise<void>((resolve) => server.close(() => resolve())));

type Body = Record<string, unknown>;
async function get(path: string, init: { persona?: string; cookie?: string; scenario?: string } = {}) {
  const headers: Record<string, string> = { Cookie: `psl_mock_persona=${init.persona ?? 'pm'}${init.cookie ? `; ${init.cookie}` : ''}` };
  if (init.scenario) headers['X-Mock-Scenario'] = init.scenario;
  const response = await fetch(`${base}/api/v1/projects/${path}`, { headers });
  return { status: response.status, body: (await response.json()) as Body };
}

describe('visibility and access', () => {
  it('404 for P-0099 and for a project the persona cannot see; 403 for every tab of P-0103', async () => {
    expect((await get('P-0099/milestones')).status).toBe(404);
    expect((await get('P-0104/milestones', { persona: 'pm' })).status).toBe(404);
    expect((await get('P-0104/milestones', { persona: 'finance_lead' })).status).toBe(200);
    for (const tab of ['milestones', 'registers', 'actions']) expect((await get(`P-0103/${tab}`)).status).toBe(403);
    expect((await get('P-0103')).status).toBe(200);
  });

  it('documents answers the live sections; an unknown tab 404; a project with no fixtures is empty', async () => {
    const empty = (await get('P-0106/documents')).body as unknown as { sections: { key: string; items: unknown[] }[] };
    expect(empty.sections.map((s) => [s.key, s.items])).toEqual([['documents', []]]);
    const body = (await get('P-0101/documents')).body as unknown as { tab: string; sections: { items: { api_url: string }[]; total: number; page: number }[] };
    expect(body.tab).toBe('documents');
    expect(body.sections[0]).toMatchObject({ total: 6, page: 1 });
    expect(body.sections[0].items[0].api_url).toMatch(/\/document-reviews\/2901$/);
    expect((await get('P-0101/nonsense')).status).toBe(404);
  });

  it('the X-Mock-Scenario header still wins', async () => {
    for (const scenario of ['401', '403', '404']) expect((await get('P-0101/milestones', { scenario })).status).toBe(Number(scenario));
  });
});

describe('query', () => {
  it('422 for an unreadable page or an empty q on documents', async () => {
    for (const query of ['documents?page=0', 'documents?page=x', 'documents?q=']) {
      const result = await get(`P-0101/${query}`);
      expect([query, result.status, result.body.code]).toEqual([query, 422, 'invalid_filter']);
    }
  });
});
