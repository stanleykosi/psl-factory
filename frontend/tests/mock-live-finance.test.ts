import { readFileSync } from 'node:fs';
import type { Server } from 'node:http';
import type { AddressInfo } from 'node:net';
import { join } from 'node:path';

import Ajv2020 from 'ajv/dist/2020';
import addFormats from 'ajv-formats';
import { afterAll, beforeAll, describe, expect, it } from 'vitest';

// @ts-expect-error plain ESM module without type declarations
import { startMockServer } from '../mock/server.mjs';

type Responses = Record<string, { content: { 'application/json': { schema: object } } }>;
const contract = JSON.parse(readFileSync(join(__dirname, '../../contracts/psl-factory.openapi.json'), 'utf8')) as {
  paths: Record<string, Record<string, { responses: Responses }>>;
  components: { schemas: { Error: object } };
};
const ajv = new Ajv2020({ allErrors: true, strict: true });
addFormats(ajv);
const schemaOf = (path: string) => ajv.compile(contract.paths[path].get.responses['200'].content['application/json'].schema);
const validMonthEnd = schemaOf('/api/v1/month-end');
const validPayments = schemaOf('/api/v1/payments');
const validError = ajv.compile(contract.components.schemas.Error);

const fixtures = join(__dirname, '../mock/fixtures/finance');
const read = (name: string) => JSON.parse(readFileSync(join(fixtures, name), 'utf8')) as Record<string, unknown>;

let server: Server;
let base: string;
beforeAll(async () => {
  server = await startMockServer({ port: 0 });
  base = `http://127.0.0.1:${(server.address() as AddressInfo).port}`;
});
afterAll(() => new Promise<void>((resolve) => server.close(() => resolve())));

type Reply = { items: { reference: string }[]; cursor: string | null; page: number; next_page: number | null } & Record<string, unknown>;

async function get(path: string, persona = 'finance_lead', cookie = '') {
  const response = await fetch(base + path, { headers: { Cookie: `psl_mock_persona=${persona}${cookie ? `; ${cookie}` : ''}` } });
  return { status: response.status, body: (await response.json()) as Reply };
}

const MONTH_END_VARIANTS = ['empty', 'one-page', 'cash-unavailable', 'two-currency', 'more-cash', 'unnamed', 'zero'];
const PAYMENTS_VARIANTS = ['board', 'known', 'unknown', 'empty', 'paged', 'limited', 'currencies', 'links'];

describe('the mock speaks the live GET /month-end', () => {
  it('has fixtures that validate against the live 200 schema', () => {
    for (const name of ['month-end.live.json', 'month-end.page2.json']) expect(validMonthEnd(read(name)), `${name} ${JSON.stringify(validMonthEnd.errors)}`).toBe(true);
  });

  it.each(['', ...MONTH_END_VARIANTS])('variant %s: the served body validates, with no field outside the contract', async (variant) => {
    const { status, body } = await get('/api/v1/month-end?month=2026-10', 'finance_lead', variant ? `psl_mock_month_end=${variant}` : '');
    expect(status).toBe(200);
    expect(validMonthEnd(body), JSON.stringify(validMonthEnd.errors)).toBe(true);
  });

  it('serves page 1 with a next page and page 2 with none', async () => {
    const one = await get('/api/v1/month-end?month=2026-10');
    expect(one.body.page).toBe(1);
    expect(one.body.next_page).toBe(2);
    const two = await get('/api/v1/month-end?month=2026-10&page=2');
    expect(validMonthEnd(two.body)).toBe(true);
    expect(two.body.page).toBe(2);
    expect(two.body.next_page).toBeNull();
  });

  it('refuses a persona without finance with the contract error, and another month with 404', async () => {
    for (const persona of ['pm', 'none']) {
      const { status, body } = await get('/api/v1/month-end?month=2026-10', persona);
      expect(status).toBe(403);
      expect(validError(body)).toBe(true);
    }
    expect((await get('/api/v1/month-end?month=2026-09')).status).toBe(404);
  });

  it('does not serve the retired v7 path', async () => {
    expect((await get('/api/v1/finance/month-end?period=2026-10')).status).not.toBe(200);
  });
});

describe('the mock speaks the live GET /payments', () => {
  it.each(PAYMENTS_VARIANTS.filter((v) => ['board', 'known', 'unknown', 'empty'].includes(v)))('fixture %s validates against the live 200 schema', (name) => {
    expect(validPayments(read(`invoices.${name}.json`)), JSON.stringify(validPayments.errors)).toBe(true);
  });

  it.each(PAYMENTS_VARIANTS)('variant %s: the served body validates, with no field outside the contract', async (variant) => {
    const { status, body } = await get('/api/v1/payments', 'finance_lead', `psl_mock_invoices=${variant}`);
    expect(status).toBe(200);
    expect(validPayments(body), JSON.stringify(validPayments.errors)).toBe(true);
  });

  it('filters by q and state, and ignores a state outside the five', async () => {
    expect((await get('/api/v1/payments?q=kora')).body.items.map((r) => r.reference)).toEqual(['INV-0388', 'INV-0402']);
    expect((await get('/api/v1/payments?state=overdue')).body.items.map((r) => r.reference)).toEqual(['INV-0391']);
    expect((await get('/api/v1/payments?state=bogus')).body.items).toHaveLength(4);
  });

  it('pages by an opaque cursor', async () => {
    const cookie = 'psl_mock_invoices=paged';
    const one = await get('/api/v1/payments', 'finance_lead', cookie);
    expect(one.body.items).toHaveLength(2);
    expect(one.body.cursor).toBe('c2');
    const two = await get('/api/v1/payments?cursor=c2', 'finance_lead', cookie);
    expect(two.body.items.map((r) => r.reference)).toEqual(['INV-0388', 'INV-0402']);
    expect(two.body.cursor).toBeNull();
  });

  it('a null amount stays null (Unknown), never 0', async () => {
    const { body } = await get('/api/v1/payments?q=INV-0402');
    expect(body.items[0]).toMatchObject({ owed: null, paid: null, face: '3100000.00' });
  });

  it('refuses a persona without finance, and answers the error variant with a contract error', async () => {
    for (const persona of ['pm', 'none']) {
      const { status, body } = await get('/api/v1/payments', persona);
      expect(status).toBe(403);
      expect(validError(body)).toBe(true);
    }
    const error = await get('/api/v1/payments', 'finance_lead', 'psl_mock_invoices=error');
    expect(error.status).toBe(500);
    expect(validError(error.body)).toBe(true);
  });
});
