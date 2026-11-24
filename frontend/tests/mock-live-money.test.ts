import { readdirSync, readFileSync } from 'node:fs';
import type { Server } from 'node:http';
import type { AddressInfo } from 'node:net';
import { join } from 'node:path';

import Ajv2020 from 'ajv/dist/2020';
import addFormats from 'ajv-formats';
import { afterAll, beforeAll, describe, expect, it } from 'vitest';

// @ts-expect-error plain ESM module without type declarations
import { PERSONAS, startMockServer } from '../mock/server.mjs';

// F-71: the money tab, the milestones tab and one recorded completion in the contract mock against the live contract
// (1.26.0). Every money fixture and every body the mock serves for them validates, with UUID case_id values; a project
// named by its P-nnnn id still resolves; a project the persona cannot see answers 404 from both routes.
type Responses = Record<string, { content: { 'application/json': { schema: object } } }>;
const contract = JSON.parse(readFileSync(join(__dirname, '../../contracts/psl-factory.openapi.json'), 'utf8')) as {
  paths: Record<string, Record<string, { responses: Responses }>>;
};
const ajv = new Ajv2020({ allErrors: true, strict: true });
addFormats(ajv);
const schemaOf = (path: string) => ajv.compile(contract.paths[path].get.responses['200'].content['application/json'].schema);
const validMoney = schemaOf('/api/v1/projects/{case_id}/money');
const validTab = schemaOf('/api/v1/projects/{case_id}/{tab}');
const validCompletion = schemaOf('/api/v1/projects/{case_id}/milestones/{milestone_id}');

const fixtures = join(__dirname, '../mock/fixtures/projects');
const readJson = (path: string) => JSON.parse(readFileSync(path, 'utf8'));
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const uuid = (id: string) => `00000000-0000-4000-8000-${id.slice(2).padStart(12, '0')}`;
const moneyFiles = readdirSync(join(fixtures, 'money')).filter((name) => /^P-\d+(\.changed)?\.json$/.test(name));
const milestoneFiles = readdirSync(join(fixtures, 'tabs')).filter((name) => /^P-\d+\.milestones\.json$/.test(name));
const CASES = ['P-0101', 'P-0102', 'P-0103', 'P-0105', 'P-0106'];

type Item = { key: string; amount: string | null; milestone_id: number | null; stage_position: number | null; completed_at: string | null; contract_stage: boolean; missing_reason: string | null; invoices: { paid: string | null; owed: string | null; status: string }[]; sources: { reference: string | null }[]; changes: { additional_amount: null }[] };
type MoneyBody = { items: Item[]; limited: boolean };
type TabBody = { case_id: string; sections: { key: string; items: { record_id: number }[]; page: number; has_more: boolean; total: number }[] };

let server: Server;
let base: string;
beforeAll(async () => {
  server = await startMockServer({ port: 0 });
  base = `http://127.0.0.1:${(server.address() as AddressInfo).port}`;
});
afterAll(() => new Promise<void>((resolve) => server.close(() => resolve())));

const read = async (path: string, persona = 'finance_lead', cookie = '') => {
  const response = await fetch(base + path, { headers: { Cookie: `psl_mock_persona=${persona}${cookie ? `; ${cookie}` : ''}` } });
  return { status: response.status, body: await response.json() };
};
const money = async (id: string, query = '', persona = 'finance_lead', cookie = '') => {
  const result = await read(`/api/v1/projects/${id}/money${query}`, persona, cookie);
  if (result.status === 200) expect(validMoney(result.body), `${id}${query}: ${ajv.errorsText(validMoney.errors)}`).toBe(true);
  return result as { status: number; body: MoneyBody };
};
const milestones = async (id: string, query = '', persona = 'finance_lead') => {
  const result = await read(`/api/v1/projects/${id}/milestones${query}`, persona);
  if (result.status === 200) expect(validTab(result.body), `${id}${query}: ${ajv.errorsText(validTab.errors)}`).toBe(true);
  return result as { status: number; body: TabBody };
};

describe('the fixtures are the live shape', () => {
  it.each(moneyFiles)('money %s validates', (name) => {
    const body = readJson(join(fixtures, 'money', name));
    expect(validMoney(body), ajv.errorsText(validMoney.errors)).toBe(true);
    for (const item of body.items as Item[]) expect(item.amount === '0.00' || item.amount === '0').toBe(false);
  });

  it.each(milestoneFiles)('milestones %s serves a valid first page', async (name) => {
    const id = name.slice(0, 6);
    const result = await milestones(id);
    expect(result.status).toBe(200);
    expect(result.body.case_id).toBe(uuid(id));
    expect(UUID.test(result.body.case_id)).toBe(true);
  });

  it('a non-UUID case_id, a missing field or an extra field fails the same check', () => {
    const body = readJson(join(fixtures, 'money/P-0101.json'));
    expect(validMoney({ ...body, items: undefined })).toBe(false);
    expect(validMoney({ ...body, total: '1.00' })).toBe(false);
    expect(validMoney({ ...body, items: [{ ...body.items[0], paid_word: 'Paid' }] })).toBe(false);
    expect(validTab({ case_id: 'P-0101', tab: 'milestones', sections: [], as_of: '2026-11-12T15:40:00Z' })).toBe(false);
  });

  it('P-0101 holds every case the tabs draw', () => {
    const items = readJson(join(fixtures, 'money/P-0101.json')).items as Item[];
    const ms = readJson(join(fixtures, 'tabs/P-0101.milestones.json')).sections[0].items as { record_id: number }[];
    expect(items.map((i) => i.stage_position)).toEqual([1, 2, 3, null, null]);
    expect(items.some((i) => i.milestone_id !== null && ms.some((m) => m.record_id === i.milestone_id))).toBe(true);
    expect(items.some((i) => i.completed_at !== null && i.milestone_id === null)).toBe(true);
    expect(items.some((i) => i.amount === null && i.missing_reason)).toBe(true);
    expect(items.some((i) => i.invoices.some((v) => v.paid === null && v.owed === null))).toBe(true);
    expect(items.some((i) => i.invoices.some((v) => v.paid !== null && v.owed !== null))).toBe(true);
    expect(items.some((i) => i.invoices.length === 2)).toBe(true);
    expect(items.some((i) => !i.contract_stage)).toBe(true);
    expect(items.some((i) => i.sources.some((s) => s.reference) && i.sources.some((s) => s.reference === null))).toBe(true);
    expect(items.some((i) => i.sources.length === 0)).toBe(true);
    const changed = readJson(join(fixtures, 'money/P-0101.changed.json')).items as Item[];
    expect(changed.some((i) => i.changes.some((c) => c.additional_amount === null))).toBe(true);
    expect(readJson(join(fixtures, 'money/P-0102.json')).limited).toBe(true);
    expect(readJson(join(fixtures, 'money/P-0106.json')).items).toEqual([]);
  });
});

describe('the mock serves the live tabs', () => {
  it('every persona and case that answers 200 validates, for money, a figure and milestones', async () => {
    for (const persona of PERSONAS as string[]) {
      for (const id of CASES) {
        const result = await money(id, '', persona);
        if (result.status === 200) {
          for (const item of result.body.items.slice(0, 2)) expect((await money(id, `?figure=${item.key}`, persona)).status).toBe(200);
        }
        await milestones(id, '', persona);
      }
    }
    const paged = await milestones('P-0102', '?page=2');
    expect(paged.body.sections[0]).toMatchObject({ page: 2, has_more: false, total: 27 });
    expect((await money('P-0101', '', 'finance_lead', 'psl_mock_milestones=changed')).body.items.some((i) => i.changes.length > 0)).toBe(true);
    expect((await money('P-0101')).body.items.some((i) => i.changes.length > 0)).toBe(false);
  });

  it('a figure answers the one matching item, and 404 for an unknown key', async () => {
    const one = await money('P-0101', '?figure=kickoff');
    expect(one.body.items.map((i) => i.key)).toEqual(['kickoff']);
    expect((await money('P-0101', '?figure=nope')).status).toBe(404);
  });

  it('a project named by its P-nnnn id or its UUID answers the same', async () => {
    expect(await money('P-0101')).toEqual(await money(uuid('P-0101')));
    expect(await milestones('P-0101')).toEqual(await milestones(uuid('P-0101')));
    const proof = await read(`/api/v1/projects/${uuid('P-0101')}/milestones/3101`);
    expect(proof.status).toBe(200);
    expect(validCompletion(proof.body), ajv.errorsText(validCompletion.errors)).toBe(true);
    expect(proof.body).toMatchObject({ id: 3101, name: 'Kick-off', proof_version: 2 });
  });

  it('the scripted answers: money 403 and 404, milestones 404, milestones 200 beside a refused money', async () => {
    expect((await money('P-0107')).status).toBe(403);
    expect((await money('P-0108')).status).toBe(404);
    expect((await milestones('P-0108')).status).toBe(200);
    expect((await milestones('P-0105')).status).toBe(404);
    expect((await money('P-0105')).status).toBe(200);
  });

  it('wrong user and wrong tenant: P-0099, its UUID and a project outside the persona answer 404 from every route', async () => {
    for (const id of ['P-0099', uuid('P-0099')]) {
      for (const tail of ['money', 'milestones', 'milestones/3101']) expect((await read(`/api/v1/projects/${id}/${tail}`)).status, `${id}/${tail}`).toBe(404);
    }
    for (const tail of ['money', 'milestones', 'milestones/3101']) expect((await read(`/api/v1/projects/P-0107/${tail}`, 'pm')).status, tail).toBe(404);
  });

  it('one recorded completion: 404 for an unknown id, another project and a bad id', async () => {
    expect((await read('/api/v1/projects/P-0101/milestones/9999')).status).toBe(404);
    expect((await read('/api/v1/projects/P-0108/milestones/3102')).status).toBe(404);
    expect((await read('/api/v1/projects/P-0101/milestones/x')).status).toBe(404);
  });

  it('the milestones read pages 25 at a time and refuses a page that does not exist', async () => {
    const first = await milestones('P-0102');
    expect(first.body.sections[0]).toMatchObject({ page: 1, has_more: true, total: 27 });
    expect(first.body.sections[0].items).toHaveLength(25);
    expect((await milestones('P-0102', '?page=2')).body.sections[0].items).toHaveLength(2);
    for (const query of ['?page=3', '?page=0', '?page=x']) expect((await read(`/api/v1/projects/P-0102/milestones${query}`)).status, query).toBe(404);
  });
});
