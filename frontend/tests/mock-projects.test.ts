import { readdirSync, readFileSync } from 'node:fs';
import type { Server } from 'node:http';
import type { AddressInfo } from 'node:net';
import { join } from 'node:path';

import Ajv2020 from 'ajv/dist/2020';
import addFormats from 'ajv-formats';
import { afterAll, beforeAll, describe, expect, it } from 'vitest';

// @ts-expect-error plain ESM module without type declarations
import { OPENAPI_PATH, SCENARIO_BODIES, startMockServer } from '../mock/server.mjs';
// @ts-expect-error plain ESM module without type declarations
import { contractBody, PROPOSED_FIELDS } from '../mock/projects.mjs';

// E-PROJECTS and E-PROJECT against the openapi the mock loads (v6). The mock adds the boards' PROPOSAL fields; a 200
// body is checked without them (contractBody), and in full against the architecture v7 draft (D-PROJECTS-VIEW).
type Response = { content: { 'application/json': { schema: object } } };
const openapi = JSON.parse(readFileSync(OPENAPI_PATH, 'utf8')) as { paths: Record<string, { get: { responses: Record<string, Response> } }> };
const ajv = new Ajv2020({ allErrors: true, strict: true });
addFormats(ajv);
const compile = (path: string) =>
  Object.fromEntries(Object.entries(openapi.paths[path].get.responses).map(([status, r]) => [status, ajv.compile(r.content['application/json'].schema)]));
const listValidators = compile('/api/v1/projects');
const journeyValidators = compile('/api/v1/projects/{case_id}');
const v7 = JSON.parse(readFileSync(join(__dirname, '../../architecture/packages/v7/openapi.json'), 'utf8')) as typeof openapi;
const v7Schema = (path: string) => ajv.compile(v7.paths[path].get.responses['200'].content['application/json'].schema);
const v7Validators: Record<string, ReturnType<typeof ajv.compile>> = {
  'E-PROJECTS': v7Schema('/api/v1/projects'),
  'E-PROJECT': v7Schema('/api/v1/projects/{case_id}'),
};

const fixtures = join(__dirname, '../mock/fixtures');
const readJson = (path: string) => JSON.parse(readFileSync(path, 'utf8'));
type Item = { case_id: string; title: string; pm: string; stage: string; sample: boolean };
type Line = { line: string; state: string; work_id: string };
type ListBody = { items: Item[]; next_cursor?: string; as_of: string; counts?: Record<string, number>; total?: number };
type JourneyBody = { case_id: string; title: string; lines: Line[]; next: string };
const rows = readJson(join(fixtures, 'projects/list.json')).rows as { personas: string[]; status: string; item: Item }[];
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

async function get(path: string, persona: string, operationId: string, validators: Record<string, ReturnType<typeof ajv.compile>>) {
  const response = await fetch(base + path, { headers: { Cookie: `psl_mock_persona=${persona}` } });
  const body = await response.json();
  const validate = validators[String(response.status)];
  expect(validate, `undeclared status ${response.status}`).toBeTruthy();
  const contract = response.status === 200 ? contractBody(operationId, body) : body;
  expect(validate(contract), `${path} ${response.status}: ${ajv.errorsText(validate.errors)}`).toBe(true);
  if (response.status === 200) {
    const full = v7Validators[operationId];
    expect(full(body), `${path} against v7: ${ajv.errorsText(full.errors)}`).toBe(true);
  }
  return { status: response.status, body };
}
const list = (query: string, persona = 'finance_lead') =>
  get(`/api/v1/projects${query ? `?${query}` : ''}`, persona, 'E-PROJECTS', listValidators) as Promise<{ status: number; body: ListBody }>;
const journey = (caseId: string, persona = 'finance_lead') =>
  get(`/api/v1/projects/${caseId}`, persona, 'E-PROJECT', journeyValidators) as Promise<{ status: number; body: JourneyBody }>;

describe('E-PROJECTS mock honours the query', () => {
  for (const persona of ['finance_lead', 'pm', 'none']) {
    for (const limit of [10, 20, 50]) {
      it(`${persona} limit ${limit}: every visible row exactly once, in fixture order, at most ${limit} per page`, async () => {
        const seen: string[] = [];
        let cursor: string | undefined;
        let pages = 0;
        do {
          const { status, body } = await list(`status=all&limit=${limit}${cursor ? `&cursor=${cursor}` : ''}`, persona);
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

  it('finance_lead pages 3/2/1 at 10/20/50; pm sees the five SCR-22 board rows without P-0104; none sees nothing', async () => {
    expect(rowsOf('finance_lead').length).toBeGreaterThanOrEqual(23);
    expect(rowsOf('finance_lead').length).toBeLessThanOrEqual(30);
    const pm = (await list('status=all', 'pm')).body;
    expect(pm.items.map((i) => [i.title, i.pm, i.stage])).toEqual([
      ['Lagoon Health · patient app', 'Tunde Bello', 'Release · UAT with client'],
      ['Harmattan Bank · mobile onboarding', 'Kunle Ade', 'Go-live · report sent'],
      ['Kora Logistics · fleet tracker', 'Tunde Bello', 'Pre-sale · costing approval'],
      ['Ojo Foods · ordering app', 'Sola Martins', 'Planning · held'],
      ['Sabi Market · web store', 'Kemi Adebayo', 'Closed 09 Nov'],
    ]);
    expect(pm.items.map((i) => i.case_id)).not.toContain('P-0104');
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
    expect((await list('q=bank', 'pm')).body.items.map((i) => i.case_id)).toEqual(['P-0102']);
    expect((await list('q=delta', 'pm')).body.items).toEqual([]);
  });

  it('PROPOSAL status: none answers Active, closed and all narrow; counts cover every row; total counts the match', async () => {
    const active = ['P-0101', 'P-0102', 'P-0103', 'P-0106'];
    const all = (await list('status=all', 'pm')).body;
    expect([all.counts, all.total]).toEqual([{ active: 4, closed: 1, all: 5 }, 5]);
    expect((await list('', 'pm')).body).toMatchObject({ total: 4, counts: { active: 4, closed: 1, all: 5 } });
    expect((await list('', 'pm')).body.items.map((i) => i.case_id)).toEqual(active);
    expect((await list('status=active', 'pm')).body.items.map((i) => i.case_id)).toEqual(active);
    expect((await list('status=closed', 'pm')).body.items.map((i) => i.case_id)).toEqual(['P-0105']);
    expect((await list('status=closed&q=lagoon', 'pm')).body).toMatchObject({ items: [], total: 0, counts: { active: 4, closed: 1, all: 5 } });
    expect((await list('q=lagoon', 'pm')).body).toMatchObject({ total: 1, counts: { active: 4, closed: 1, all: 5 } });
    const finance = (await list('limit=10')).body;
    expect([finance.items.length, finance.total]).toEqual([10, rows.filter((r) => r.status === 'active').length]);
    expect((await list('limit=50')).body.items.map((i) => i.case_id)).toEqual(rows.filter((r) => r.status === 'active').map((r) => r.item.case_id));
    expect((await list('', 'none')).body).toMatchObject({ counts: { active: 0, closed: 0, all: 0 }, total: 0 });
    expect(await list('status=open')).toEqual({ status: 404, body: { code: 'invalid_query', message: 'We could not read that list request.' } });
  });

  it('PROPOSAL row fields: the board values for P-0101 and a missing next milestone for closed P-0105', async () => {
    const [p0101, , , , p0105] = (await list('status=all', 'pm')).body.items as (Item & Record<string, unknown>)[];
    expect([p0101.next_milestone, p0101.needs_person, p0101.stopped]).toEqual([{ name: 'UAT sign-off', due: { date: '2026-11-14', unknown: false } }, 2, 1]);
    expect(p0105).not.toHaveProperty('next_milestone');
    expect([p0105.needs_person, p0105.stopped]).toEqual([0, 0]);
    expect(PROPOSED_FIELDS.row).toEqual(['reference', 'next_milestone', 'needs_person', 'stopped']);
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

  it('a listed project the persona cannot see is 404: P-0104 for pm, P-0101 for none', async () => {
    expect(await journey('P-0104', 'pm')).toEqual({ status: 404, body: SCENARIO_BODIES[404] });
    expect(await journey('P-0101', 'none')).toEqual({ status: 404, body: SCENARIO_BODIES[404] });
    expect((await journey('P-0104')).body.title).toBe('Delta Foods · ordering app');
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

  it('P-0101 is the SCR-07 board; the default journey covers all 11 states; P-0105 has no lines', async () => {
    const p0101 = (await journey('P-0101', 'pm')).body as JourneyBody & Record<string, unknown>;
    expect(p0101.lines.map((l) => (l as Line & { title: string }).title)).toEqual([
      'RFP response',
      'Log an engagement',
      'Commercial submission',
      'Plan a project',
      'Invoice · Milestone 1',
      'Prepare for release',
      'Invoice · Milestone 2',
      'Invoice · Milestone 3',
    ]);
    expect(new Set(p0101.lines.map((l) => l.line)).size).toBe(6);
    expect(p0101).toMatchObject({ pm: { name: 'Tunde Bello' }, route: 'Route A from RFP-0031', revision: 7 });
    expect((p0101.facts as { label: string }[]).map((f) => f.label)).toEqual(['CONTRACT STAGES', 'INVOICES VERIFIED', 'WAITING ON PEOPLE', 'STOPPED', 'NEXT MILESTONE', 'PAID']);
    expect(p0101.agent_summary).toMatchObject({ agent: 'tola' });
    expect(p0101.tab_counts).toEqual({ milestones: 4, documents: 6, registers: 6, actions: 9 });
    const fallback = (await journey('X-1', 'none')).body;
    expect(fallback).toEqual(readJson(join(fixtures, 'E-PROJECT.json')));
    expect(new Set(fallback.lines.map((l) => l.state))).toEqual(new Set(STATES));
    expect((await journey('P-0105', 'pm')).body.lines).toEqual([]);
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

const validate200 = (body: unknown) => journeyValidators['200'](body);

describe('project fixtures', () => {
  const journeyFiles = [
    join(fixtures, 'E-PROJECT.json'),
    ...readdirSync(join(fixtures, 'projects'))
      .filter((name) => /^P-\d+\.json$/.test(name))
      .map((name) => join(fixtures, 'projects', name)),
  ];

  it('every journey file and the default list body are schema-valid (v6 without PROPOSAL fields, v7 in full)', () => {
    expect(journeyFiles.length).toBeGreaterThan(20);
    for (const path of journeyFiles) {
      const validate = journeyValidators['200'];
      expect(validate(contractBody('E-PROJECT', readJson(path))), `${path}: ${ajv.errorsText(validate.errors)}`).toBe(true);
      const full = v7Validators['E-PROJECT'];
      expect(full(readJson(path)), `${path} against v7: ${ajv.errorsText(full.errors)}`).toBe(true);
    }
    expect(validate200(readJson(join(fixtures, 'E-PROJECT.json'))), 'the fallback has no PROPOSAL fields').toBe(true);
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
