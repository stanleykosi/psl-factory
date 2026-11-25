import { readFileSync } from 'node:fs';
import type { Server } from 'node:http';
import type { AddressInfo } from 'node:net';
import { join } from 'node:path';

import Ajv2020 from 'ajv/dist/2020';
import addFormats from 'ajv-formats';
import { afterAll, beforeAll, describe, expect, it } from 'vitest';

// @ts-expect-error plain ESM module without type declarations
import { startMockServer } from '../mock/server.mjs';

// The clients reads answer the live shape (F-73) and every 200 is checked against the live contract.
type Operation = { responses: Record<string, { content: { 'application/json': { schema: object } } }> };
const contract = JSON.parse(readFileSync(join(__dirname, '../../contracts/psl-factory.openapi.json'), 'utf8')) as { paths: Record<string, { get: Operation }>; components: { schemas: { Error: object } } };
const ajv = new Ajv2020({ allErrors: true, strict: true });
addFormats(ajv);
const compile = (path: string) => ajv.compile(contract.paths[path].get.responses['200'].content['application/json'].schema);
const valid = {
  directory: compile('/api/v1/clients'),
  group: compile('/api/v1/clients/groups/{group}'),
  workspace: compile('/api/v1/clients/{case_id}'),
  history: compile('/api/v1/clients/{case_id}/contacts/history'),
};
const validError = ajv.compile(contract.components.schemas.Error);

const ACME = 'a1b2c3d4'.repeat(8);
const HARMATTAN = 'b2c3d4e5'.repeat(8);
const LAGOON = 'c3d4e5f6'.repeat(8);
const SABI = 'd4e5f607'.repeat(8);
const TAMARIND = 'e5f60718'.repeat(8);
const id = (n: number) => `0b6f9e1a-3c44-4d0a-9d52-${String(n).padStart(12, '0')}`;

let server: Server;
let base: string;
beforeAll(async () => {
  server = await startMockServer({ port: 0 });
  base = `http://127.0.0.1:${(server.address() as AddressInfo).port}`;
});
afterAll(() => new Promise<void>((resolve) => server.close(() => resolve())));

type Body = Record<string, any>; // eslint-disable-line @typescript-eslint/no-explicit-any -- parsed mock replies
async function read(path: string, check: keyof typeof valid | null, { persona = 'finance_lead', cookie = '' }: { persona?: string; cookie?: string } = {}) {
  const response = await fetch(base + path, { headers: { Cookie: `psl_mock_persona=${persona}${cookie ? `; ${cookie}` : ''}` } });
  const body = (await response.json()) as Body;
  if (response.status === 200 && check) expect(valid[check](body), `${path}: ${ajv.errorsText(valid[check].errors)}`).toBe(true);
  else expect(validError(body), path).toBe(true);
  return { status: response.status, body };
}
const directory = (query = '', options = {}) => read(`/api/v1/clients${query}`, 'directory', options);
const group = (key: string, query = '', options = {}) => read(`/api/v1/clients/groups/${key}${query}`, 'group', options);
const workspace = (caseId: string, options = {}) => read(`/api/v1/clients/${caseId}`, 'workspace', options);
const history = (caseId: string, query = '?purpose=billing') => read(`/api/v1/clients/${caseId}/contacts/history${query}`, 'history');

describe('GET /clients', () => {
  it('serves groups first and the ungrouped projects, in the live shape', async () => {
    const { status, body } = await directory();
    expect(status).toBe(200);
    expect(body.groups.map((g: Body) => [g.label, g.project_count, g.contacts_needed])).toEqual([
      ['Acme Logistics', 3, 1],
      ['Harmattan Bank', 27, 9],
      ['Lagoon Health', 1, 1],
      ['Sabi Market', 2, 0],
      ['Tamarind Loans', 1, 0],
    ]);
    expect(body.projects.map((p: Body) => [p.client, p.billing])).toEqual([['Kora Foods', 'needed'], [null, 'unknown'], ['Delta Print', 'recorded']]);
    expect(body.next_group_page).toBeNull();
    expect(body.next_page).toBeNull();
  });

  it('filters by billing and q, and refuses a value the contract does not allow', async () => {
    expect((await directory('?billing=unknown')).body.projects.map((p: Body) => p.title)).toEqual(['Office move']);
    expect((await directory('?q=kora')).body.projects).toHaveLength(1);
    expect((await directory('?billing=bogus')).status).toBe(400);
    expect((await directory(`?q=${'x'.repeat(101)}`)).status).toBe(400);
    expect((await directory('?page=0')).status).toBe(400);
    expect((await directory('?clients_page=abc')).status).toBe(400);
  });

  it('the many state has two pages of groups and two of projects, and every call returns both lists', async () => {
    const cookie = 'psl_mock_clients=many';
    const first = (await directory('', { cookie })).body;
    expect([first.groups.length, first.next_group_page, first.projects.length, first.next_page]).toEqual([25, 2, 25, 2]);
    const groups2 = (await directory('?clients_page=2', { cookie })).body;
    expect([groups2.groups.length, groups2.next_group_page, groups2.projects.length]).toEqual([5, null, 25]);
    const projects2 = (await directory('?page=2', { cookie })).body;
    expect([projects2.projects.length, projects2.next_page, projects2.groups.length]).toEqual([5, null, 25]);
  });

  it('the empty state has no rows, and persona none is refused', async () => {
    const empty = (await directory('', { cookie: 'psl_mock_clients=empty' })).body;
    expect([empty.groups, empty.projects, empty.next_group_page, empty.next_page]).toEqual([[], [], null, null]);
    expect((await directory('', { persona: 'none' })).status).toBe(403);
  });
});

describe('GET /clients/groups/{group}', () => {
  it('covers each debt state the page must tell apart', async () => {
    const acme = (await group(ACME)).body;
    expect(acme.projects.map((p: Body) => p.billing)).toEqual(['needed', 'recorded', 'unknown']);
    expect(acme.debt.totals.map((t: Body) => [t.currency, t.known_owed, t.unknown_owed_count])).toEqual([['NGN', '1250000.00', 1], ['USD', null, 2]]);
    expect((await group(HARMATTAN)).body.debt.limited).toBe(true);
    expect((await group(LAGOON)).body.debt.totals).toEqual([]);
    expect((await group(SABI)).body.debt).toBeNull();
    expect((await group(TAMARIND)).body.debt.totals[0]).toMatchObject({ known_owed: null, unknown_owed_count: 1 });
  });

  it('pages a large group by 25 and returns not_found for an unknown or malformed key', async () => {
    const one = (await group(HARMATTAN)).body;
    expect([one.projects.length, one.next_page]).toEqual([25, 2]);
    const two = (await group(HARMATTAN, '?page=2')).body;
    expect([two.projects.length, two.next_page]).toEqual([2, null]);
    expect((await group('f'.repeat(64))).status).toBe(404);
    expect((await group('not-a-key')).status).toBe(404);
    expect((await group(ACME, '?page=0')).status).toBe(400);
    expect((await group(ACME, '', { persona: 'none' })).status).toBe(403);
  });
});

describe('GET /clients/{case_id} and its history', () => {
  it('serves billing and project contacts, the sample flag and no write', async () => {
    const w = (await workspace(id(1))).body;
    expect([w.title, w.sample, w.contacts.map((c: Body) => c.purpose)]).toEqual(['Warehouse portal', true, ['project']]);
    const billed = (await workspace(id(2))).body;
    expect(billed.contacts.map((c: Body) => [c.purpose, c.version])).toEqual([['billing', 2], ['project', 1]]);
    expect((await workspace(id(9999))).status).toBe(404);
    expect((await workspace('CL-3501')).status).toBe(404);
    expect((await workspace(id(1), { persona: 'none' })).status).toBe(403);
    const post = await fetch(`${base}/api/v1/clients/${id(1)}/contacts`, { method: 'POST', headers: { 'Content-Type': 'application/json', Cookie: 'psl_mock_persona=finance_lead' }, body: '{}' });
    expect(post.status).toBeGreaterThanOrEqual(400);
  });

  it('lists billing versions newest first over two pages, and needs a purpose', async () => {
    const one = (await history(id(103))).body;
    expect([one.items.length, one.items[0].version, one.items[24].version, one.next_page]).toEqual([25, 28, 4, 2]);
    const two = (await history(id(103), '?purpose=billing&page=2')).body;
    expect([two.items.map((i: Body) => i.version), two.next_page]).toEqual([[3, 2, 1], null]);
    expect((await history(id(103), '')).status).toBe(400);
    expect((await history(id(9999))).status).toBe(404);
    expect((await history(id(1))).body.items).toEqual([]);
  });
});

describe('the validators', () => {
  it('a wrong shape fails them', () => {
    expect(valid.directory({ groups: [], projects: [], next_page: null })).toBe(false);
    expect(valid.directory({ groups: [{ key: 'short', label: 'x', project_count: 1, contacts_needed: 0, api_url: '/x' }], projects: [], next_group_page: null, next_page: null })).toBe(false);
    expect(valid.group({ key: ACME, label: 'Acme', projects: [], next_page: null })).toBe(false);
    expect(valid.workspace({ case_id: 'CL-3501', title: 'x', revision: 1, sample: false, contacts: [], django_url: '/x' })).toBe(false);
    expect(valid.history({ revision: 1, items: [{ version: 1 }], next_page: null })).toBe(false);
  });
});
