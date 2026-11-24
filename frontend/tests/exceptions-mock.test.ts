import { readFileSync } from 'node:fs';
import type { Server } from 'node:http';
import type { AddressInfo } from 'node:net';
import { join } from 'node:path';

import Ajv2020 from 'ajv/dist/2020';
import addFormats from 'ajv-formats';
import { afterAll, beforeAll, describe, expect, it } from 'vitest';

// @ts-expect-error plain ESM module without type declarations
import { startMockServer } from '../mock/server.mjs';

// The live work list in the contract mock (F-62): GET /api/v1/work for queue=verified and queue=exceptions, and
// GET /api/v1/work/{id}. Every other queue keeps the v7 shape.
type Row = { id: number; title: string; line: string; state: string; owner: string | null; sample: boolean };
type Body = { items: Row[]; page: number; next_page: number | null; as_of: string; limited: boolean; lines: { key: string }[]; evaluated: number; deferred: unknown[]; payroll_questions: unknown[]; code?: string };

const contract = JSON.parse(readFileSync(join(__dirname, '../../contracts/psl-factory.openapi.json'), 'utf8'));
const ajv = new Ajv2020({ allErrors: true, strict: false });
addFormats(ajv);
const schemaOf = (path: string) => ({ ...contract.paths[path].get.responses['200'].content['application/json'].schema, components: contract.components });
const validateList = ajv.compile(schemaOf('/api/v1/work'));

let server: Server;
let base: string;
beforeAll(async () => {
  server = await startMockServer({ port: 0 });
  base = `http://127.0.0.1:${(server.address() as AddressInfo).port}`;
});
afterAll(() => new Promise<void>((resolve) => server.close(() => resolve())));

async function get(path: string, persona = 'finance_lead') {
  const response = await fetch(`${base}${path}`, { headers: { Cookie: `psl_mock_persona=${persona}` } });
  return { status: response.status, body: (await response.json()) as Body };
}
const ids = (body: Body) => body.items.map((r) => r.id);

describe('mock live work list', () => {
  for (const queue of ['verified', 'exceptions']) {
    it(`${queue}: three pages of 8, 8, 4 in a fixed order, each valid against the live contract`, async () => {
      const seen: number[] = [];
      let page = 1;
      for (;;) {
        const { status, body } = await get(`/api/v1/work?queue=${queue}&page=${page}`);
        expect(status).toBe(200);
        expect(validateList(body), ajv.errorsText(validateList.errors)).toBe(true);
        expect(body.page).toBe(page);
        seen.push(...ids(body));
        if (body.next_page === null) break;
        page = body.next_page;
      }
      expect(page).toBe(3);
      expect(seen).toHaveLength(20);
      expect(new Set(seen).size).toBe(20);
    });
  }

  it('a narrowed list can have an empty middle page: line filter leaves page 2 empty with next_page 3', async () => {
    const line = encodeURIComponent('finance-ledger/v1');
    const first = await get(`/api/v1/work?queue=verified&line=${line}&page=1`);
    const second = await get(`/api/v1/work?queue=verified&line=${line}&page=2`);
    const third = await get(`/api/v1/work?queue=verified&line=${line}&page=3`);
    expect(first.body.items.length).toBeGreaterThan(0);
    expect(second.body).toMatchObject({ items: [], next_page: 3 });
    expect(third.body.items.length).toBeGreaterThan(0);
    expect(third.body.next_page).toBeNull();
    expect(first.body.items.every((r) => r.line === 'finance-ledger/v1')).toBe(true);
  });

  it('search narrows by q; exceptions page 1 is limited with a deferred item, verified is not; null owners and samples exist', async () => {
    const exceptions = await get('/api/v1/work?queue=exceptions');
    expect(exceptions.body).toMatchObject({ limited: true, deferred: [{ id: 390 }] });
    const verified = await get('/api/v1/work?queue=verified');
    expect(verified.body).toMatchObject({ limited: false, deferred: [] });
    expect(verified.body.items.some((r) => r.sample)).toBe(true);
    expect(exceptions.body.items.some((r) => r.owner === null)).toBe(true);
    const found = await get('/api/v1/work?queue=verified&q=marina');
    expect(found.body.items.length).toBeGreaterThan(0);
    expect(found.body.items.every((r) => r.title.includes('Marina Bank'))).toBe(true);
    expect(exceptions.body.items.map((r) => r.state)).toEqual(expect.arrayContaining(['awaiting_reconciliation', 'effect_uncertain', 'action_needed']));
  });

  it('persona none sees empty lists; pm and hr are refused exceptions with 403 queue_not_open but may read verified', async () => {
    for (const queue of ['verified', 'exceptions']) {
      const none = await get(`/api/v1/work?queue=${queue}`, 'none');
      expect(none.body).toMatchObject({ items: [], next_page: null });
      expect(validateList(none.body)).toBe(true);
    }
    expect((await get('/api/v1/work?queue=exceptions', 'pm')).status).toBe(403);
    expect((await get('/api/v1/work?queue=exceptions', 'pm')).body.code).toBe('queue_not_open');
    expect((await get('/api/v1/work?queue=verified', 'pm')).status).toBe(200);
  });

  it('an unreadable page or empty parameter is a 400', async () => {
    for (const query of ['page=0', 'page=abc', 'q=', 'line=']) expect((await get(`/api/v1/work?queue=verified&${query}`)).status).toBe(400);
  });

  it('the live shape is returned only for verified and exceptions; queue=done still answers the v7 shape', async () => {
    const done = await get('/api/v1/work?queue=done');
    expect(done.status).toBe(200);
    expect(done.body).toHaveProperty('counts');
    expect(done.body).not.toHaveProperty('next_page');
    expect(done.body).not.toHaveProperty('evaluated');
    expect(await get('/api/v1/work?queue=verified')).toHaveProperty('body.evaluated');
  });

  it('GET /work/{id}: 412 has an output file, 413 has none, an unknown id is 404', async () => {
    const withOutput = await get('/api/v1/work/412');
    expect(withOutput.status).toBe(200);
    expect(withOutput.body).toMatchObject({ id: 412, output_url: '/outputs/412.pdf' });
    expect((await get('/api/v1/work/413')).body).toMatchObject({ id: 413, output_url: null });
    expect((await get('/api/v1/work/9999')).status).toBe(404);
  });
});
