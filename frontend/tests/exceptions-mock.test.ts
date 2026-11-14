import { existsSync, readFileSync } from 'node:fs';
import type { Server } from 'node:http';
import type { AddressInfo } from 'node:net';
import { join } from 'node:path';

import Ajv2020 from 'ajv/dist/2020';
import addFormats from 'ajv-formats';
import { afterAll, beforeAll, describe, expect, it } from 'vitest';

// @ts-expect-error plain ESM module without type declarations
import { OPENAPI_PATH, startMockServer } from '../mock/server.mjs';

// E-EXCEPTIONS in the contract mock (F-06): personas, paging, the empty cookie and the row/item match.
type Row = { work_id: string; what: string; title: string; since: string };
type Page = { items: Row[]; next_cursor?: string; as_of: string };

const fixtures = join(__dirname, '..', 'mock', 'fixtures');
const read = (name: string) => JSON.parse(readFileSync(join(fixtures, name), 'utf8'));
const fixture = read('E-EXCEPTIONS.json') as Page;

const openapi = JSON.parse(readFileSync(OPENAPI_PATH, 'utf8'));
const responses = openapi.paths['/api/v1/exceptions'].get.responses;
const ajv = new Ajv2020({ allErrors: true, strict: true });
addFormats(ajv);
const validate200 = ajv.compile(responses['200'].content['application/json'].schema);
const validate403 = ajv.compile(responses['403'].content['application/json'].schema);

let server: Server;
let base: string;
beforeAll(async () => {
  server = await startMockServer({ port: 0 });
  base = `http://127.0.0.1:${(server.address() as AddressInfo).port}`;
});
afterAll(() => new Promise<void>((resolve) => server.close(() => resolve())));

async function get(query = '', cookie = 'psl_mock_persona=finance_lead') {
  const response = await fetch(`${base}/api/v1/exceptions${query}`, { headers: { Cookie: cookie } });
  return { status: response.status, body: (await response.json()) as Page & { code?: string } };
}

describe('mock E-EXCEPTIONS', () => {
  it('the fixture is a valid 200 body with 25 rows, newest first, covering every kind', () => {
    expect(validate200(fixture), ajv.errorsText(validate200.errors)).toBe(true);
    expect(fixture.items).toHaveLength(25);
    expect(fixture.items[0]).toMatchObject({ work_id: 'W-1005', what: 'effect_uncertain', title: 'Kora Logistics · Milestone 1 invoice' });
    expect(fixture.items.slice(1).map((r) => r.work_id)).toEqual(Array.from({ length: 24 }, (_, i) => `W-${1501 + i}`));
    const since = fixture.items.map((r) => r.since);
    expect(since).toEqual([...since].sort().reverse());
    const kinds = fixture.items.map((r) => r.what);
    expect(kinds.filter((k) => k === 'effect_uncertain').length).toBeGreaterThanOrEqual(2);
    for (const kind of ['owner_needed', 'setup_needed', 'blocked', 'followup_needed']) expect(kinds).toContain(kind);
    const lagosDay = (iso: string) => new Date(iso).toLocaleDateString('en-GB', { timeZone: 'Africa/Lagos' });
    expect(fixture.items.some((r) => lagosDay(r.since) !== lagosDay(fixture.as_of))).toBe(true);
  });

  it('pages of 10 follow the cursors through all 25 rows once, in file order', async () => {
    const seen: string[] = [];
    let page = await get('?limit=10');
    expect(page.body.items).toHaveLength(10);
    expect(page.body.next_cursor).toBe('o:10');
    for (;;) {
      expect(page.status).toBe(200);
      expect(validate200(page.body), ajv.errorsText(validate200.errors)).toBe(true);
      seen.push(...page.body.items.map((r) => r.work_id));
      if (!page.body.next_cursor) break;
      page = await get(`?limit=10&cursor=${encodeURIComponent(page.body.next_cursor)}`);
    }
    expect(seen).toEqual(fixture.items.map((r) => r.work_id));
  });

  it('treats any other limit as 20 and a malformed or out-of-range cursor as the first page', async () => {
    const odd = await get('?limit=7');
    expect(odd.body.items).toHaveLength(20);
    expect(odd.body.next_cursor).toBe('o:20');
    for (const cursor of ['nonsense', 'o:99']) {
      const first = await get(`?limit=10&cursor=${cursor}`);
      expect(first.body.items[0].work_id).toBe('W-1005');
    }
    const last = await get('?limit=20&cursor=o:20');
    expect(last.body.items.map((r) => r.work_id)).toEqual(fixture.items.slice(20).map((r) => r.work_id));
    expect(last.body).not.toHaveProperty('next_cursor');
  });

  it('answers pm 403, none an empty list, and the empty cookie an empty list', async () => {
    const pm = await get('', 'psl_mock_persona=pm');
    expect(pm).toEqual({ status: 403, body: { code: 'forbidden', message: 'Only Leads can see all exceptions.' } });
    expect(validate403(pm.body)).toBe(true);
    const none = await get('', 'psl_mock_persona=none');
    expect(none).toEqual({ status: 200, body: { items: [], as_of: fixture.as_of } });
    const empty = await get('', 'psl_mock_persona=finance_lead; psl_mock_exceptions=empty');
    expect(empty).toEqual({ status: 200, body: { items: [], as_of: fixture.as_of } });
    expect(validate200(empty.body)).toBe(true);
  });

  it('rows match their work items', () => {
    const states: Record<string, string[]> = {
      owner_needed: ['owner_needed'],
      setup_needed: ['setup_needed'],
      followup_needed: ['followup_needed'],
      effect_uncertain: ['effect_uncertain', 'awaiting_reconciliation'],
      blocked: ['action_needed'],
    };
    for (const row of fixture.items) {
      const file = join('work', `${row.work_id}.json`);
      expect(existsSync(join(fixtures, file)), file).toBe(true);
      const item = read(file) as { title: string; state: string; sample: boolean; tasks: { you_can_act: boolean }[] };
      expect(item.title, row.work_id).toBe(row.title);
      expect(states[row.what], row.work_id).toContain(item.state);
      expect(item.tasks.some((t) => t.you_can_act), row.work_id).toBe(false);
    }
  });
});
