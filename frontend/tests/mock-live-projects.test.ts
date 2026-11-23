import { readdirSync, readFileSync } from 'node:fs';
import type { Server } from 'node:http';
import type { AddressInfo } from 'node:net';
import { join } from 'node:path';

import Ajv2020 from 'ajv/dist/2020';
import addFormats from 'ajv-formats';
import { afterAll, beforeAll, describe, expect, it } from 'vitest';

// @ts-expect-error plain ESM module without type declarations
import { PERSONAS, SCENARIO_BODIES, startMockServer } from '../mock/server.mjs';

// GET /projects and GET /projects/{case_id} in the contract mock against the live contract (1.22.0): every fixture and
// every served body, for every persona and state, validates; case_id values are UUIDs.
type Responses = Record<string, { content: { 'application/json': { schema: object } } }>;
const contract = JSON.parse(readFileSync(join(__dirname, '../../contracts/psl-factory.openapi.json'), 'utf8')) as {
  paths: Record<string, Record<string, { responses: Responses }>>;
};
const ajv = new Ajv2020({ allErrors: true, strict: true });
addFormats(ajv);
const schemaOf = (path: string) => ajv.compile(contract.paths[path].get.responses['200'].content['application/json'].schema);
const validList = schemaOf('/api/v1/projects');
const validJourney = schemaOf('/api/v1/projects/{case_id}');

const fixtures = join(__dirname, '../mock/fixtures');
const readJson = (path: string) => JSON.parse(readFileSync(path, 'utf8'));
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const uuid = (n: string) => `00000000-0000-4000-8000-${n.padStart(12, '0')}`;

type Item = { case_id: string; title: string; manager: string | null; phase: string | null; reviews: number | null; exceptions: number | null; sample: boolean };
type ListBody = { items: Item[]; next_cursor: string | null; as_of: string; totals: Record<'all' | 'active' | 'closed', number> };
type Journey = { case_id: string; title: string; items: { id: number; reference: string | null }[]; page: number; next_page: number | null; facts: { total: number; finance: unknown; engagement: unknown }; tabs: { key: string }[] };
const rows = readJson(join(fixtures, 'projects/list.json')).rows as { id: string; personas: string[]; status: string; item: Item }[];
const journeyFiles = readdirSync(join(fixtures, 'projects')).filter((name) => /^P-\d+\.json$/.test(name));

let server: Server;
let base: string;
beforeAll(async () => {
  server = await startMockServer({ port: 0 });
  base = `http://127.0.0.1:${(server.address() as AddressInfo).port}`;
});
afterAll(() => new Promise<void>((resolve) => server.close(() => resolve())));

const read = async (path: string, persona: string) => {
  const response = await fetch(base + path, { headers: { Cookie: `psl_mock_persona=${persona}` } });
  return { status: response.status, body: await response.json() };
};
const list = async (query: string, persona = 'finance_lead') => {
  const result = await read(`/api/v1/projects${query ? `?${query}` : ''}`, persona);
  if (result.status === 200) expect(validList(result.body), `${query}: ${ajv.errorsText(validList.errors)}`).toBe(true);
  return result as { status: number; body: ListBody };
};
const journey = async (id: string, persona = 'finance_lead', query = '') => {
  const result = await read(`/api/v1/projects/${id}${query}`, persona);
  if (result.status === 200) expect(validJourney(result.body), `${id}${query}: ${ajv.errorsText(validJourney.errors)}`).toBe(true);
  return result as { status: number; body: Journey };
};

describe('the fixtures are the live shape', () => {
  it('the list rows and every journey file validate, with UUID case_id values', () => {
    expect(rows.length).toBeGreaterThan(20);
    for (const row of rows) {
      expect(row.item.case_id, row.id).toBe(uuid(row.id.slice(2)));
      expect(UUID.test(row.item.case_id)).toBe(true);
    }
    const totals = { all: rows.length, active: rows.filter((r) => r.status === 'active').length, closed: rows.filter((r) => r.status === 'closed').length };
    expect(validList({ items: rows.map((r) => r.item), next_cursor: null, as_of: '2026-11-23T09:00:00Z', totals }), ajv.errorsText(validList.errors)).toBe(true);
    for (const name of [...journeyFiles, '../E-PROJECT.json']) {
      const body = readJson(join(fixtures, 'projects', name));
      expect(validJourney(body), `${name}: ${ajv.errorsText(validJourney.errors)}`).toBe(true);
      expect(UUID.test(body.case_id), name).toBe(true);
    }
  });

  it('a non-UUID id, a missing required field or an extra field fails the same check', () => {
    const body = readJson(join(fixtures, 'projects/P-0101.json'));
    expect(validJourney({ ...body, case_id: 'P-0101' })).toBe(false);
    expect(validJourney({ ...body, facts: undefined })).toBe(false);
    expect(validJourney({ ...body, counts: {} })).toBe(false);
    expect(validJourney({ ...body, tab_counts: {} })).toBe(false);
    const item = rows[0].item;
    const common = { as_of: '2026-11-23T09:00:00Z', totals: { all: 1, active: 1, closed: 0 } };
    expect(validList({ ...common, items: [{ ...item, case_id: 'P-0101' }], next_cursor: null })).toBe(false);
    expect(validList({ ...common, items: [{ ...item, pm: 'x' }], next_cursor: null })).toBe(false);
    expect(validList({ ...common, items: [item] })).toBe(false);
  });
});

describe('GET /projects', () => {
  it.each(PERSONAS as string[])('%s: status all, active and closed all validate; the rows are the persona’s', async (persona) => {
    const all = await list('', persona);
    const mine = rows.filter((r) => r.personas.includes(persona));
    expect(all.body.items.map((i) => i.case_id)).toEqual(mine.map((r) => r.item.case_id).slice(0, 20));
    const active = await list('status=active', persona);
    expect(active.body.items.every((i) => rows.find((r) => r.item.case_id === i.case_id)?.status === 'active')).toBe(true);
    const closed = await list('status=closed', persona);
    expect(closed.body.items.every((i) => rows.find((r) => r.item.case_id === i.case_id)?.status === 'closed')).toBe(true);
  });

  it('defaults to all and returns status totals before pagination', async () => {
    const all = await list('');
    const explicit = await list('status=all');
    expect(all.body).toEqual(explicit.body);
    const mine = rows.filter((r) => r.personas.includes('finance_lead'));
    expect(all.body.totals).toEqual({ all: mine.length, active: mine.filter((r) => r.status === 'active').length, closed: mine.filter((r) => r.status === 'closed').length });
  });

  it('pages with next_cursor: every visible row once, 20 a page; a limit is ignored', async () => {
    const seen: string[] = [];
    let cursor: string | null = null;
    let pages = 0;
    do {
      const { body } = await list(`status=all${cursor ? `&cursor=${cursor}` : ''}&limit=3`);
      expect(body.items.length).toBeLessThanOrEqual(20);
      seen.push(...body.items.map((i) => i.case_id));
      cursor = body.next_cursor;
      pages += 1;
    } while (cursor);
    expect(seen).toEqual(rows.filter((r) => r.personas.includes('finance_lead')).map((r) => r.item.case_id));
    expect(pages).toBe(2);
  });

  it('q narrows by title, case-insensitively; a q that matches nothing is an empty list', async () => {
    expect((await list('status=all&q=LAGOON')).body.items.map((i) => i.title)).toEqual(['Lagoon Health · patient app']);
    expect(await list('status=all&q=no+such+project')).toMatchObject({ status: 200, body: { items: [], next_cursor: null } });
  });

  it('the no-manager row and the nothing-known row carry null, not 0 or a name', async () => {
    const { body } = await list('status=active', 'pm');
    const bare = body.items.find((i) => i.title === 'Standalone fit-out');
    expect(bare).toMatchObject({ manager: null, phase: null, reviews: null, exceptions: null });
    expect(body.items.some((i) => i.exceptions === 0)).toBe(true);
  });

  it('a bad cursor, an empty q, an unknown status or a q over 120 characters is 422 invalid_filter', async () => {
    for (const query of ['cursor=nope', 'q=', 'status=open', `q=${'x'.repeat(121)}`]) {
      expect(await list(query)).toEqual({ status: 422, body: { code: 'invalid_filter', message: 'We could not read that list request.' } });
    }
  });

  it('every row is sample and the no-access id is never listed', () => {
    expect(rows.every((r) => r.item.sample === true)).toBe(true);
    expect(rows.some((r) => r.id === 'P-0099')).toBe(false);
  });
});

describe('GET /projects/{case_id}', () => {
  it.each(PERSONAS as string[])('%s: every visible project opens by UUID and by P-nnnn with the same body', async (persona) => {
    for (const row of rows.filter((r) => r.personas.includes(persona))) {
      const byUuid = await journey(row.item.case_id, persona);
      const byCode = await journey(row.id, persona);
      expect(byUuid.status).toBe(200);
      expect(byUuid.body.case_id).toBe(row.item.case_id);
      expect(byUuid.body.title).toBe(row.item.title);
      expect(byCode.body).toEqual(byUuid.body);
    }
  });

  it('the no-access id is 404 in both forms, for every persona', async () => {
    for (const persona of PERSONAS as string[]) {
      for (const id of ['P-0099', uuid('99')]) expect(await journey(id, persona)).toEqual({ status: 404, body: SCENARIO_BODIES[404] });
    }
  });

  it('a listed project the persona cannot see is 404, in both forms: P-0104 for pm', async () => {
    expect(await journey('P-0104', 'pm')).toEqual({ status: 404, body: SCENARIO_BODIES[404] });
    expect(await journey(uuid('104'), 'pm')).toEqual({ status: 404, body: SCENARIO_BODIES[404] });
  });

  it('P-0101 has three kinds of row: no reference, a repeated title and a plain one; finance limited; tabs from live', async () => {
    const { body } = await journey(uuid('101'), 'pm');
    expect(body.items.some((i) => i.reference === null)).toBe(true);
    expect(body.facts).toMatchObject({ total: 8, finance: { limited: true }, engagement: { manager: 'Tunde Bello' } });
    expect(body.tabs.map((t) => t.key)).toEqual(['journey', 'milestones', 'documents', 'templates', 'money', 'registers', 'actions']);
  });

  it('P-0102 has 24 work items: page 1 has 20 and next_page 2, page 2 has 4 and none', async () => {
    const one = await journey(uuid('102'), 'pm');
    expect([one.body.items.length, one.body.page, one.body.next_page, one.body.facts.total]).toEqual([20, 1, 2, 24]);
    const two = await journey(uuid('102'), 'pm', '?page=2');
    expect([two.body.items.length, two.body.page, two.body.next_page]).toEqual([4, 2, null]);
    expect((await journey(uuid('102'), 'pm', '?page=3')).status).toBe(404);
  });

  it('P-0106 has finance and engagement null and no Assistant; P-0125 has no " · " in its title and no work', async () => {
    const closedFinance = await journey(uuid('106'), 'pm');
    expect(closedFinance.body.facts).toMatchObject({ finance: null, engagement: null });
    const bare = await journey(uuid('125'), 'pm');
    expect(bare.body.title).toBe('Standalone fit-out');
    expect(bare.body.title).not.toContain(' · ');
    expect(bare.body.items).toEqual([]);
  });

  it('an unlisted P-nnnn id answers the sample body under its own UUID; other text is 404', async () => {
    expect((await journey('P-0150')).body.case_id).toBe(uuid('150'));
    expect((await read('/api/v1/projects/not-a-project', 'pm')).status).toBe(404);
  });

  it('the X-Mock-Scenario header still wins', async () => {
    const response = await fetch(`${base}/api/v1/projects/${uuid('101')}`, { headers: { 'X-Mock-Scenario': '403' } });
    expect(response.status).toBe(403);
  });
});
