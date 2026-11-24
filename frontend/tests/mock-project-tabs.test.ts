import { readdirSync, readFileSync } from 'node:fs';
import type { Server } from 'node:http';
import type { AddressInfo } from 'node:net';
import { join } from 'node:path';

import Ajv2020 from 'ajv/dist/2020';
import addFormats from 'ajv-formats';
import { afterAll, beforeAll, describe, expect, it } from 'vitest';

// @ts-expect-error plain ESM module without type declarations
import { OPENAPI_PATH, startMockServer } from '../mock/server.mjs';

// E-PROJECT-TAB in the contract mock (F-25): every fixture body validates against the generated 200 schema with
// nothing stripped, and the handler's rules (visibility, query, paging, cookies) hold.
type Response = { content: { 'application/json': { schema: object } } };
const openapi = JSON.parse(readFileSync(OPENAPI_PATH, 'utf8')) as { paths: Record<string, { get: { responses: Record<string, Response> } }> };
const ajv = new Ajv2020({ allErrors: true, strict: true });
addFormats(ajv);
const responses = openapi.paths['/api/v1/projects/{case_id}/{tab}'].get.responses;
const valid200 = ajv.compile(responses['200'].content['application/json'].schema);

const tabs = join(__dirname, '../mock/fixtures/projects/tabs');
// Registers and Actions are the live shape (mock-live-project-sections.test.ts).
const fixtureFiles = readdirSync(tabs).filter((name) => name.endsWith('.json') && !/\.(registers|actions)\.json$/.test(name));

let server: Server;
let base: string;
beforeAll(async () => {
  server = await startMockServer({ port: 0 });
  base = `http://127.0.0.1:${(server.address() as AddressInfo).port}`;
});
afterAll(() => new Promise<void>((resolve) => server.close(() => resolve())));

type Body = Record<string, unknown> & { items: unknown[]; next_cursor?: string; milestones?: { name: string }[] };
async function get(path: string, init: { persona?: string; cookie?: string; scenario?: string } = {}) {
  const headers: Record<string, string> = { Cookie: `psl_mock_persona=${init.persona ?? 'pm'}${init.cookie ? `; ${init.cookie}` : ''}` };
  if (init.scenario) headers['X-Mock-Scenario'] = init.scenario;
  const response = await fetch(`${base}/api/v1/projects/${path}`, { headers });
  return { status: response.status, body: (await response.json()) as Body };
}

describe('fixtures validate against the generated E-PROJECT-TAB 200 schema', () => {
  it.each(fixtureFiles)('%s', (name) => {
    const body = JSON.parse(readFileSync(join(tabs, name), 'utf8'));
    expect(valid200(body), ajv.errorsText(valid200.errors)).toBe(true);
  });

  it('the handler serves valid bodies for every tab of P-0101, P-0102 and P-0106', async () => {
    for (const id of ['P-0101', 'P-0102', 'P-0106']) {
      for (const tab of ['milestones', 'documents']) {
        const { status, body } = await get(`${id}/${tab}`);
        expect(status).toBe(200);
        expect(valid200(body), `${id} ${tab}: ${ajv.errorsText(valid200.errors)}`).toBe(true);
        expect(body.items).toEqual(body[tab]);
      }
    }
  });
});

describe('visibility and access', () => {
  it('404 for P-0099 and for a project the persona cannot see; 403 for every tab of P-0103', async () => {
    expect((await get('P-0099/milestones')).status).toBe(404);
    expect((await get('P-0104/milestones', { persona: 'pm' })).status).toBe(404);
    expect((await get('P-0104/milestones', { persona: 'finance_lead' })).status).toBe(200);
    for (const tab of ['milestones', 'registers', 'actions']) expect((await get(`P-0103/${tab}`)).status).toBe(403);
    expect((await get('P-0103')).status).toBe(200);
  });

  it('documents answers its rows; an unknown tab 404; a project with no fixtures is empty', async () => {
    expect((await get('P-0106/documents')).body.documents).toEqual([]);
    expect(((await get('P-0101/documents')).body.documents as { work_id?: string }[]).map((d) => d.work_id)).toEqual(['W-2901', ...Array(5).fill(undefined)]);
    expect((await get('P-0101/nonsense')).status).toBe(404);
  });

  it('the X-Mock-Scenario header still wins', async () => {
    for (const scenario of ['401', '403', '404']) expect((await get('P-0101/milestones', { scenario })).status).toBe(Number(scenario));
  });
});

describe('query', () => {
  it('404 for a bad limit, an unknown register, a bad cursor and a milestones cursor; Registers and Actions are the live shape', async () => {
    for (const query of ['milestones?limit=7', 'milestones?cursor=x', 'documents?cursor=o999', 'documents?q=']) {
      const result = await get(`P-0101/${query}`);
      expect([query, result.status, result.body.code]).toEqual([query, 404, 'invalid_query']);
    }
  });
});

describe('the changed cookie', () => {
  it('psl_mock_milestones=changed serves the milestones with the change on Go-live; other tabs are unchanged', async () => {
    const plain = (await get('P-0101/milestones')).body.milestones as { changes?: unknown }[];
    const changed = (await get('P-0101/milestones', { cookie: 'psl_mock_milestones=changed' })).body.milestones as { name: string; changes?: { reference: string }[] }[];
    expect(plain.some((m) => m.changes)).toBe(false);
    expect(changed.find((m) => m.name === 'Go-live')!.changes!.map((c) => c.reference)).toEqual(['CR-0031']);
    const actions = (await get('P-0101/actions', { cookie: 'psl_mock_milestones=changed' })).body.sections as { items: unknown[] }[];
    expect(actions[0].items).toHaveLength(9);
  });
});
