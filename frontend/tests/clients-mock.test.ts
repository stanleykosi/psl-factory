import { readdirSync, readFileSync } from 'node:fs';
import type { Server } from 'node:http';
import type { AddressInfo } from 'node:net';
import { join } from 'node:path';

import Ajv2020 from 'ajv/dist/2020';
import addFormats from 'ajv-formats';
import { afterAll, beforeAll, beforeEach, describe, expect, it } from 'vitest';

// @ts-expect-error plain ESM module without type declarations
import { OPENAPI_PATH, startMockServer } from '../mock/server.mjs';

// E-CLIENTS, E-CLIENT and E-CLIENT-CONTACT against the v7 openapi the mock loads (D-CLIENTS-VIEW r1, proposed).
type Operation = { responses: Record<string, { content: { 'application/json': { schema: object } } }> };
const openapi = JSON.parse(readFileSync(OPENAPI_PATH, 'utf8')) as { paths: Record<string, Record<string, Operation>> };
const ajv = new Ajv2020({ allErrors: true, strict: true });
addFormats(ajv);
const compile = (path: string, method: string) =>
  Object.fromEntries(Object.entries(openapi.paths[path][method].responses).map(([status, r]) => [status, ajv.compile(r.content['application/json'].schema)]));
const validators = {
  list: compile('/api/v1/clients', 'get'),
  detail: compile('/api/v1/clients/{client_id}', 'get'),
  contact: compile('/api/v1/clients/{client_id}/billing-contact', 'put'),
};

const fixtureDir = join(__dirname, '../mock/fixtures/clients');
const csrfOf = (persona: string) => JSON.parse(readFileSync(join(__dirname, `../mock/fixtures/me.${persona}.json`), 'utf8')).csrf_token as string;

let server: Server;
let base: string;
beforeAll(async () => {
  server = await startMockServer({ port: 0 });
  base = `http://127.0.0.1:${(server.address() as AddressInfo).port}`;
});
afterAll(() => new Promise<void>((resolve) => server.close(() => resolve())));
beforeEach(async () => {
  await fetch(`${base}/__mock/reset`, { method: 'POST' });
});

type Kind = keyof typeof validators;
async function request(kind: Kind, path: string, { persona = 'finance_lead', cookie = '', body, headers = {} }: { persona?: string; cookie?: string; body?: unknown; headers?: Record<string, string> } = {}) {
  const response = await fetch(base + path, {
    method: body === undefined ? 'GET' : 'PUT',
    headers: { Cookie: `psl_mock_persona=${persona}${cookie ? `; ${cookie}` : ''}`, 'Content-Type': 'application/json', ...headers },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const json = await response.json();
  const validate = validators[kind][String(response.status)];
  if (response.status !== 403 || json.code !== 'csrf_failed') {
    expect(validate, `undeclared status ${response.status}`).toBeTruthy();
    expect(validate(json), `${path} ${response.status}: ${ajv.errorsText(validate.errors)}`).toBe(true);
  }
  return { status: response.status, body: json };
}
const list = (query = '', options = {}) => request('list', `/api/v1/clients${query}`, options);
const detail = (id: string, options = {}) => request('detail', `/api/v1/clients/${id}`, options);
const save = (id: string, body: unknown, options: { persona?: string; headers?: Record<string, string> } = {}) =>
  request('contact', `/api/v1/clients/${id}/billing-contact`, { body, ...options, headers: { 'X-CSRFToken': csrfOf(options.persona ?? 'finance_lead'), ...options.headers } });
const contact = (revision: number, name = 'Ada Okoye', email = 'ada@example.org') => ({ expected_revision: revision, name, email });

describe('E-CLIENTS', () => {
  it('serves the six board clients in fixture order, two without a billing contact (Lagoon Health, Ojo Foods)', async () => {
    const { status, body } = await list();
    expect(status).toBe(200);
    expect(body.items.map((i: { name: string }) => i.name)).toEqual(['Lagoon Health', 'Harmattan Bank', 'Kora Logistics', 'Ojo Foods', 'Sabi Market', 'Tamarind Loans']);
    expect(body.items.filter((i: { billing_contact_set: boolean }) => !i.billing_contact_set).map((i: { client_id: string }) => i.client_id)).toEqual(['CL-3501', 'CL-3504']);
    expect(body.items[5].projects).toBe(0);
    expect(body.items[5].owed).toBeUndefined();
    expect(body.next_cursor).toBeUndefined();
    expect(body.as_of).toBeTruthy();
  });

  it('empty and many datasets; many pages 10/10/5 by cursor o<N> with no repeat', async () => {
    expect((await list('', { cookie: 'psl_mock_clients=empty' })).body.items).toEqual([]);
    const seen: string[] = [];
    let cursor: string | undefined;
    const sizes: number[] = [];
    do {
      const { status, body } = await list(`?limit=10${cursor ? `&cursor=${cursor}` : ''}`, { cookie: 'psl_mock_clients=many' });
      expect(status).toBe(200);
      sizes.push(body.items.length);
      seen.push(...body.items.map((i: { client_id: string }) => i.client_id));
      cursor = body.next_cursor;
    } while (cursor && sizes.length < 10);
    expect(sizes).toEqual([10, 10, 5]);
    expect(new Set(seen).size).toBe(25);
    expect((await list('?limit=10', { cookie: 'psl_mock_clients=many' })).body.next_cursor).toBe('o10');
    expect((await list('', { cookie: 'psl_mock_clients=many' })).body.items).toHaveLength(20);
  });

  it('refuses a limit outside 10, 20, 50 and a cursor it did not issue', async () => {
    expect((await list('?limit=7')).status).toBe(404);
    expect((await list('?cursor=nope')).status).toBe(404);
  });

  it('persona none gets 403 on all three operations, before anything else', async () => {
    expect((await list('', { persona: 'none' })).status).toBe(403);
    expect((await detail('CL-3501', { persona: 'none' })).status).toBe(403);
    expect((await save('CL-3501', {}, { persona: 'none' })).body.code).toBe('forbidden');
    expect((await save('CL-3599', contact(1), { persona: 'none' })).body.code).toBe('forbidden');
  });
});

describe('E-CLIENT', () => {
  it('CL-3501 is the detail board: revision 3, no contact, the banner line, one project, owed unknown', async () => {
    const { status, body } = await detail('CL-3501');
    expect(status).toBe(200);
    expect(body).toMatchObject({ name: 'Lagoon Health Ltd', revision: 3, can_change: true, billing_contact: { set: false } });
    expect(body.blocked).toEqual(["No billing contact, so invoices for this client can't start. Add one here."]);
    expect(body.projects).toEqual([{ case_id: 'P-0101', title: 'Patient app', stage: 'Delivery' }]);
    expect(body.money.owed).toEqual({ currency: 'NGN', unknown: true });
  });

  it('CL-3503 is read-only; CL-3507 is sample with unknown money; CL-3509 has every optional field absent', async () => {
    expect((await detail('CL-3503')).body.can_change).toBe(false);
    expect((await detail('CL-3507')).body).toMatchObject({ sample: true, money: { owed: { unknown: true } } });
    expect(Object.keys((await detail('CL-3509')).body).sort()).toEqual(['billing_contact', 'client_id', 'name', 'projects', 'revision']);
    expect((await detail('CL-3509')).body.billing_contact).toEqual({ set: false });
  });

  it('a client from the list without its own file gets a minimal detail; CL-3599 and unknown ids are 404', async () => {
    expect((await detail('CL-3504')).body).toEqual({ client_id: 'CL-3504', name: 'Ojo Foods', revision: 1, billing_contact: { set: false }, projects: [] });
    expect((await detail('CL-3599')).status).toBe(404);
    expect((await detail('CL-0000')).status).toBe(404);
  });

  it('every fixture file validates against the v7 schema', () => {
    const files = readdirSync(fixtureDir).filter((name) => name.endsWith('.json'));
    expect(files).toContain('CL-3508.next.json');
    for (const name of files) {
      const body = JSON.parse(readFileSync(join(fixtureDir, name), 'utf8'));
      const validate = name === 'list.json' ? validators.list['200'] : validators.detail['200'];
      expect(validate(body), `${name}: ${ajv.errorsText(validate.errors)}`).toBe(true);
    }
  });
});

describe('E-CLIENT-CONTACT', () => {
  it('a PUT without the CSRF header gets 403', async () => {
    const { status, body } = await request('contact', '/api/v1/clients/CL-3501/billing-contact', { body: contact(3) });
    expect(status).toBe(403);
    expect(body.code).toBe('csrf_failed');
  });

  it('stores the contact, bumps the revision, serves set:true with no banner; a repeat with the old revision is 409', async () => {
    expect(await save('CL-3501', contact(3))).toEqual({ status: 200, body: { client_id: 'CL-3501', revision: 4 } });
    const after = (await detail('CL-3501')).body;
    expect(after.revision).toBe(4);
    expect(after.billing_contact).toEqual({ name: 'Ada Okoye', email: 'ada@example.org', set: true });
    expect(after.blocked).toBeUndefined();
    expect((await list()).body.items[0].billing_contact_set).toBe(true);
    expect((await save('CL-3501', contact(3))).status).toBe(409);
    expect((await save('CL-3501', contact(4, 'Bola', 'bola@example.org'))).body.revision).toBe(5);
    await fetch(`${base}/__mock/reset`, { method: 'POST' });
    expect((await detail('CL-3501')).body.revision).toBe(3);
  });

  it('422 for a request that is not the contract shape, then for blank or malformed fields, named', async () => {
    expect((await save('CL-3501', { name: 'A', email: 'a@b.c' })).status).toBe(422);
    expect((await save('CL-3501', { ...contact(3), extra: 1 })).status).toBe(422);
    expect((await save('CL-3501', { ...contact(3), reason: 5 })).status).toBe(422);
    const blank = await save('CL-3501', contact(3, '  ', ''));
    expect(blank.status).toBe(422);
    expect(blank.body.fields.map((f: { name: string }) => f.name)).toEqual(['name', 'email']);
    const noAt = await save('CL-3501', contact(3, 'Ada', 'not-an-email'));
    expect(noAt.body.fields).toEqual([{ name: 'email', message: expect.any(String) }]);
    expect((await detail('CL-3501')).body.revision).toBe(3);
  });

  it('checks 404, then request shape, then fields, then the revision', async () => {
    expect((await save('CL-3599', {})).status).toBe(404);
    expect((await save('CL-0000', contact(1))).status).toBe(404);
    expect((await save('CL-3501', { expected_revision: 99, name: 'A' })).status).toBe(422);
    expect((await save('CL-3501', contact(99, '', 'x'))).status).toBe(422);
    expect((await save('CL-3501', contact(99))).status).toBe(409);
  });

  it('CL-3508: the first PUT is 409, then the detail serves the newer revision with a different contact', async () => {
    expect((await detail('CL-3508')).body).toMatchObject({ revision: 2, billing_contact: { name: 'Tolu Bank' } });
    expect((await save('CL-3508', contact(2))).status).toBe(409);
    expect((await detail('CL-3508')).body).toMatchObject({ revision: 3, billing_contact: { name: 'Ngozi Eze' } });
    expect((await save('CL-3508', contact(2))).status).toBe(409);
    expect((await save('CL-3508', contact(3))).body.revision).toBe(4);
  });

  it('X-Mock-Scenario codes still apply to the operations that declare them', async () => {
    expect((await list('', { headers: { 'X-Mock-Scenario': '401' } })).status).toBe(401);
    expect((await save('CL-3501', contact(3), { headers: { 'X-Mock-Scenario': '409' } })).status).toBe(409);
  });
});
