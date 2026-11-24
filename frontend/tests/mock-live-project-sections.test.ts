import { readdirSync, readFileSync } from 'node:fs';
import type { Server } from 'node:http';
import type { AddressInfo } from 'node:net';
import { join } from 'node:path';

import Ajv2020 from 'ajv/dist/2020';
import addFormats from 'ajv-formats';
import { afterAll, beforeAll, describe, expect, it } from 'vitest';

// @ts-expect-error plain ESM module without type declarations
import { startMockServer } from '../mock/server.mjs';

// GET /projects/{case_id}/registers and /actions in the contract mock against the live contract (1.24.0): every fixture and
// every served body, for every persona, id form, page and search, validates; case_id values are UUIDs.
const contract = JSON.parse(readFileSync(join(__dirname, '../../contracts/psl-factory.openapi.json'), 'utf8')) as {
  paths: Record<string, Record<string, { responses: Record<string, { content: { 'application/json': { schema: object } } }> }>>;
};
const ajv = new Ajv2020({ allErrors: true, strict: true });
addFormats(ajv);
const valid = ajv.compile(contract.paths['/api/v1/projects/{case_id}/{tab}'].get.responses['200'].content['application/json'].schema);

const dir = join(__dirname, '../mock/fixtures/projects/tabs');
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const uuid = (n: string) => `00000000-0000-4000-8000-${n.padStart(12, '0')}`;

type Item = { title: string; reference: string | null; detail: string | null; state_code: string; due: string | null; record_id: number };
type Section = { key: string; page: number; has_more: boolean; total: number; counts: { total: number; overdue: number; unassigned: number } | null; items: Item[] };
type Body = { case_id: string; tab: string; as_of: string; sections: Section[] };

let server: Server;
let base: string;
beforeAll(async () => {
  server = await startMockServer({ port: 0 });
  base = `http://127.0.0.1:${(server.address() as AddressInfo).port}`;
});
afterAll(() => new Promise<void>((resolve) => server.close(() => resolve())));

const read = async (path: string, persona = 'finance_lead') => {
  const response = await fetch(base + path, { headers: { Cookie: `psl_mock_persona=${persona}` } });
  return { status: response.status, body: await response.json() };
};
const get = async (id: string, tab: 'registers' | 'actions', query = '', persona = 'finance_lead') => {
  const result = await read(`/api/v1/projects/${id}/${tab}${query ? `?${query}` : ''}`, persona);
  if (result.status === 200) expect(valid(result.body), `${id}/${tab}?${query}: ${ajv.errorsText(valid.errors)}`).toBe(true);
  return result as { status: number; body: Body };
};
const section = (body: Body, key: string) => body.sections.find((s) => s.key === key)!;

describe('the fixtures are the live shape', () => {
  it('every registers and actions fixture validates once the mock has added case_id, paging and totals', async () => {
    const names = readdirSync(dir).filter((name) => /^P-\d+\.(registers|actions)\.json$/.test(name));
    expect(names).toHaveLength(6);
    for (const name of names) {
      const [id, tab] = name.split('.') as [string, 'registers' | 'actions'];
      const served = await get(id, tab, '', 'pm');
      expect(served.status, name).toBe(200);
      expect(UUID.test(served.body.case_id), name).toBe(true);
      expect(served.body.case_id).toBe(uuid(id.slice(2)));
    }
  });

  it('a non-UUID case_id, a missing item field or an extra field fails the same check', async () => {
    const body = (await get('P-0101', 'registers')).body;
    expect(valid({ ...body, case_id: 'P-0101' })).toBe(false);
    expect(valid({ ...body, sections: body.sections.map((s) => ({ ...s, total: undefined })) })).toBe(false);
    expect(valid({ ...body, sections: body.sections.map((s) => ({ ...s, items: s.items.map((i) => ({ ...i, state_code: undefined })) })) })).toBe(false);
    expect(valid({ ...body, rows: [] })).toBe(false);
  });
});

describe('registers', () => {
  it('P-0101: sections by key, totals from the rows, counts null, one case_id for both id forms', async () => {
    const { status, body } = await get('P-0101', 'registers');
    expect(status).toBe(200);
    expect(body.tab).toBe('registers');
    expect(body.sections.map((s) => [s.key, s.total, s.page, s.has_more, s.counts])).toEqual([
      ['issues', 3, 1, false, null],
      ['escalations', 1, 1, false, null],
      ['changes', 2, 1, false, null],
      ['emergencies', 0, 1, false, null],
      ['rfp', 1, 1, false, null],
    ]);
    expect((await get(uuid('101'), 'registers')).body).toEqual(body);
    expect(body.case_id).toBe(uuid('101'));
  });

  it('P-0102: 30 issues, 25 on page 1, the last 5 on page 2, and page 3 answers each section its last page again', async () => {
    const first = (await get('P-0102', 'registers')).body;
    expect([section(first, 'issues').total, section(first, 'issues').items.length, section(first, 'issues').has_more]).toEqual([30, 25, true]);
    const second = (await get('P-0102', 'registers', 'page=2')).body;
    expect([section(second, 'issues').page, section(second, 'issues').items.length, section(second, 'issues').has_more]).toEqual([2, 5, false]);
    expect(section(second, 'issues').items[0].record_id).toBe(1026);
    const third = (await get('P-0102', 'registers', 'page=3')).body;
    for (const s of third.sections) expect([s.key, s.page]).toEqual([s.key, s.key === 'issues' ? 2 : 1]);
    expect(third.sections.every((s) => s.counts === null)).toBe(true);
    expect(section(third, 'changes').items).toHaveLength(1);
  });

  it('P-0106 and an unlisted project: the four drawn sections with no rows and a total of 0', async () => {
    for (const id of ['P-0106', 'P-0140']) {
      const { body } = await get(id, 'registers');
      expect(body.sections.map((s) => [s.key, s.total, s.items.length])).toEqual([['issues', 0, 0], ['changes', 0, 0], ['emergencies', 0, 0], ['rfp', 0, 0]]);
    }
  });

  it('q filters every section on title, reference and detail; badges follow the matches', async () => {
    const { body } = await get('P-0101', 'registers', 'q=ANDROID');
    expect(body.sections.map((s) => [s.key, s.total])).toEqual([['issues', 1], ['escalations', 0], ['changes', 0], ['emergencies', 0], ['rfp', 0]]);
    expect((await get('P-0101', 'registers', 'q=chg-0027')).body.sections.find((s) => s.key === 'changes')!.total).toBe(1);
  });

  it('a person without issue.read gets no Issues or Escalations section', async () => {
    const { body } = await get('P-0101', 'registers', '', 'pmo_lead');
    expect(body.sections.map((s) => s.key)).toEqual(['changes', 'emergencies', 'rfp']);
  });

  it('state, owner and severity are ignored', async () => {
    const plain = (await get('P-0101', 'registers')).body;
    expect((await get('P-0101', 'registers', 'state=closed&owner=x&severity=high')).body).toEqual(plain);
  });
});

describe('actions', () => {
  it('P-0101: one meetings section, counts over the matching rows from the mock rules', async () => {
    const { body } = await get('P-0101', 'actions');
    expect(body.sections.map((s) => s.key)).toEqual(['meetings']);
    expect(body.sections[0].total).toBe(9);
    expect(body.sections[0].counts).toEqual({ total: 9, overdue: 2, unassigned: 1 });
    expect((await get('P-0101', 'actions', 'q=uat')).body.sections[0].counts).toEqual({ total: 3, overdue: 1, unassigned: 0 });
  });

  it('P-0106: the section is there, empty, with counts of 0 (a known 0 from the server)', async () => {
    const { body } = await get('P-0106', 'actions');
    expect(body.sections[0]).toMatchObject({ key: 'meetings', total: 0, items: [], counts: { total: 0, overdue: 0, unassigned: 0 } });
  });
});

describe('access and refusals', () => {
  it('P-0099 and a project the persona cannot see answer 404, P-0103 answers 403', async () => {
    expect((await get('P-0099', 'registers')).status).toBe(404);
    expect((await get('P-0103', 'actions')).status).toBe(403);
    expect((await get('P-0101', 'registers', '', 'none')).status).toBe(404);
  });

  it('page=0, page=x, page=1.5, q= and a q over 120 characters answer 422 invalid_filter', async () => {
    for (const query of ['page=0', 'page=x', 'page=1.5', 'page=-1', 'page=', 'q=', `q=${'a'.repeat(121)}`]) {
      for (const tab of ['registers', 'actions'] as const) {
        const result = await get('P-0101', tab, query);
        expect([query, tab, result.status]).toEqual([query, tab, 422]);
        expect((result.body as unknown as { code: string }).code).toBe('invalid_filter');
      }
    }
    expect((await get('P-0101', 'registers', `q=${'a'.repeat(120)}`)).status).toBe(200);
  });
});
