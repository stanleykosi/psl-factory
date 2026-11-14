import { readdirSync, readFileSync } from 'node:fs';
import type { Server } from 'node:http';
import type { AddressInfo } from 'node:net';
import { join } from 'node:path';

import Ajv2020 from 'ajv/dist/2020';
import addFormats from 'ajv-formats';
import { afterAll, beforeAll, describe, expect, it } from 'vitest';

// @ts-expect-error plain ESM module without type declarations
import { OPENAPI_PATH, SCENARIO_BODIES, startMockServer } from '../mock/server.mjs';

// E-PROJECTS and E-PROJECT against the openapi the mock loads (v4; both endpoints are identical in v5).
type Response = { content: { 'application/json': { schema: object } } };
const openapi = JSON.parse(readFileSync(OPENAPI_PATH, 'utf8')) as { paths: Record<string, { get: { responses: Record<string, Response> } }> };
const ajv = new Ajv2020({ allErrors: true, strict: true });
addFormats(ajv);
const compile = (path: string) =>
  Object.fromEntries(Object.entries(openapi.paths[path].get.responses).map(([status, r]) => [status, ajv.compile(r.content['application/json'].schema)]));
const listValidators = compile('/api/v1/projects');
const journeyValidators = compile('/api/v1/projects/{case_id}');

const fixtures = join(__dirname, '../mock/fixtures');
const readJson = (path: string) => JSON.parse(readFileSync(path, 'utf8'));
type Item = { case_id: string; title: string; pm: string; stage: string; sample: boolean };
type Line = { line: string; state: string; work_id: string };
type ListBody = { items: Item[]; next_cursor?: string; as_of: string };
type JourneyBody = { case_id: string; title: string; lines: Line[]; next: string };
const rows = readJson(join(fixtures, 'projects/list.json')).rows as { personas: string[]; item: Item }[];
const rowsOf = (persona: string) => rows.filter((r) => r.personas.includes(persona)).map((r) => r.item);
const STATES = [
  'ready',
  'processing',
  'waiting',
  'owner_needed',
  'setup_needed',
  'action_needed',
  'effect_uncertain',
  'awaiting_reconciliation',
  'verified',
  'cancelled',
  'followup_needed',
];

let server: Server;
let base: string;

beforeAll(async () => {
  server = await startMockServer({ port: 0 });
  base = `http://127.0.0.1:${(server.address() as AddressInfo).port}`;
});
afterAll(() => new Promise<void>((resolve) => server.close(() => resolve())));

async function get(path: string, persona: string, validators: Record<string, ReturnType<typeof ajv.compile>>) {
  const response = await fetch(base + path, { headers: { Cookie: `psl_mock_persona=${persona}` } });
  const body = await response.json();
  const validate = validators[String(response.status)];
  expect(validate, `undeclared status ${response.status}`).toBeTruthy();
  expect(validate(body), `${path} ${response.status}: ${ajv.errorsText(validate.errors)}`).toBe(true);
  return { status: response.status, body };
}
const list = (query: string, persona = 'finance_lead') =>
  get(`/api/v1/projects${query ? `?${query}` : ''}`, persona, listValidators) as Promise<{ status: number; body: ListBody }>;
const journey = (caseId: string, persona = 'finance_lead') =>
  get(`/api/v1/projects/${caseId}`, persona, journeyValidators) as Promise<{ status: number; body: JourneyBody }>;

describe('E-PROJECTS mock honours the query', () => {
  for (const persona of ['finance_lead', 'pm', 'none']) {
    for (const limit of [10, 20, 50]) {
      it(`${persona} limit ${limit}: every visible row exactly once, in fixture order, at most ${limit} per page`, async () => {
        const seen: string[] = [];
        let cursor: string | undefined;
        let pages = 0;
        do {
          const { status, body } = await list(`limit=${limit}${cursor ? `&cursor=${cursor}` : ''}`, persona);
          expect(status).toBe(200);
          expect(body.items.length).toBeLessThanOrEqual(limit);
          seen.push(...body.items.map((i) => i.case_id));
          cursor = body.next_cursor;
          if (cursor !== undefined) expect(cursor).not.toBe('');
          pages += 1;
        } while (cursor && pages < 20);
        expect(seen).toEqual(rowsOf(persona).map((i) => i.case_id));
      });
    }
  }

  it('finance_lead pages 3/2/1 at 10/20/50; pm sees 4 PM Tunde Bello rows without P-0102; none sees nothing', async () => {
    expect(rowsOf('finance_lead').length).toBeGreaterThanOrEqual(23);
    expect(rowsOf('finance_lead').length).toBeLessThanOrEqual(30);
    const pm = (await list('', 'pm')).body;
    expect(pm.items).toHaveLength(4);
    expect(pm.items.every((i) => i.pm === 'Tunde Bello')).toBe(true);
    expect(pm.items.map((i) => i.case_id)).not.toContain('P-0102');
    expect(pm).not.toHaveProperty('next_cursor');
    expect((await list('', 'none')).body.items).toEqual([]);
    const first = (await list('')).body;
    expect(first.items).toHaveLength(20);
    expect(first.next_cursor).toBe('o20');
  });

  it('q narrows by title, case-insensitively', async () => {
    expect((await list('q=lagoon')).body.items.map((i) => i.case_id)).toEqual(['P-0101']);
    expect((await list('q=LAGOON&limit=10')).body.items.map((i) => i.case_id)).toEqual(['P-0101']);
    expect((await list('q=zzz')).body.items).toEqual([]);
    expect((await list('q=bank', 'pm')).body.items).toEqual([]);
  });

  it('a bad limit, a bad cursor or an empty q gets 404 invalid_query', async () => {
    for (const query of ['limit=7', 'limit=', 'cursor=nope', 'cursor=', 'q=']) {
      expect(await list(query)).toEqual({ status: 404, body: { code: 'invalid_query', message: 'We could not read that list request.' } });
    }
  });

  it('every row is sample and P-0099 is never listed', () => {
    expect(rows.every((r) => r.item.sample === true)).toBe(true);
    expect(rows.some((r) => r.item.case_id === 'P-0099')).toBe(false);
    expect(new Set(rows.map((r) => r.item.case_id)).size).toBe(rows.length);
  });
});

describe('E-PROJECT mock', () => {
  it('P-0099 is 404 for every persona, with the shared not-found body', async () => {
    for (const persona of ['finance_lead', 'pm', 'none']) {
      expect(await journey('P-0099', persona)).toEqual({ status: 404, body: SCENARIO_BODIES[404] });
    }
  });

  it('a listed project the persona cannot see is 404: P-0102 for pm, P-0101 for none', async () => {
    expect(await journey('P-0102', 'pm')).toEqual({ status: 404, body: SCENARIO_BODIES[404] });
    expect(await journey('P-0101', 'none')).toEqual({ status: 404, body: SCENARIO_BODIES[404] });
    expect((await journey('P-0102')).body.title).toBe('Harbour Bank · mobile onboarding');
  });

  it('every visible row opens its own journey, with the same case_id and title', async () => {
    for (const persona of ['finance_lead', 'pm']) {
      for (const item of rowsOf(persona)) {
        const { status, body } = await journey(item.case_id, persona);
        expect(status).toBe(200);
        expect([body.case_id, body.title]).toEqual([item.case_id, item.title]);
      }
    }
  });

  it('P-0101 covers all 11 states; P-0105 has no lines; other ids get the default journey', async () => {
    const p0101 = (await journey('P-0101', 'pm')).body;
    expect(new Set(p0101.lines.map((l) => l.state))).toEqual(new Set(STATES));
    expect((await journey('P-0105', 'pm')).body.lines).toEqual([]);
    expect((await journey('X-1', 'none')).body).toEqual(readJson(join(fixtures, 'E-PROJECT.json')));
  });

  it('E-PROJECT-TAB and E-DOCUMENT still answer 501', async () => {
    for (const path of ['/api/v1/projects/P-0101/milestones', '/api/v1/documents/D-1/versions/1']) {
      const response = await fetch(base + path);
      expect([response.status, await response.json()]).toEqual([501, { code: 'not_mocked', message: 'Not available in the mock yet.' }]);
    }
  });

  it('the X-Mock-Scenario header still wins', async () => {
    const response = await fetch(`${base}/api/v1/projects/P-0101`, { headers: { 'X-Mock-Scenario': '403' } });
    expect(response.status).toBe(403);
  });
});

describe('project fixtures', () => {
  const journeyFiles = [
    join(fixtures, 'E-PROJECT.json'),
    ...readdirSync(join(fixtures, 'projects'))
      .filter((name) => /^P-\d+\.json$/.test(name))
      .map((name) => join(fixtures, 'projects', name)),
  ];

  it('every journey file and the default list body are schema-valid', () => {
    expect(journeyFiles.length).toBeGreaterThan(20);
    for (const path of journeyFiles) {
      const validate = journeyValidators['200'];
      expect(validate(readJson(path)), `${path}: ${ajv.errorsText(validate.errors)}`).toBe(true);
    }
    const validate = listValidators['200'];
    const body = readJson(join(fixtures, 'E-PROJECTS.json'));
    expect(validate(body), ajv.errorsText(validate.errors)).toBe(true);
    expect((body as ListBody).items.every((i) => i.sample === true)).toBe(true);
  });

  it('a line whose work_id has a work fixture carries that fixture line and state', () => {
    const workDir = join(fixtures, 'work');
    const work = new Map<string, { line: string; state: string }>([['W-1001', readJson(join(fixtures, 'E-WORK-ITEM.json'))]]);
    for (const name of readdirSync(workDir).filter((n) => /^W-\d+\.json$/.test(n))) work.set(name.slice(0, -5), readJson(join(workDir, name)));
    let matched = 0;
    for (const path of journeyFiles) {
      for (const line of (readJson(path) as JourneyBody).lines) {
        const item = work.get(line.work_id);
        if (!item) {
          expect(Number(line.work_id.slice(2)), `${path} ${line.work_id}`).toBeGreaterThanOrEqual(1701);
          continue;
        }
        matched += 1;
        expect([line.line, line.state], `${path} ${line.work_id}`).toEqual([item.line, item.state]);
      }
    }
    expect(matched).toBeGreaterThanOrEqual(6);
  });
});
