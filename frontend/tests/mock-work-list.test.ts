import { readFileSync } from 'node:fs';
import type { Server } from 'node:http';
import type { AddressInfo } from 'node:net';
import { join } from 'node:path';

import Ajv2020 from 'ajv/dist/2020';
import addFormats from 'ajv-formats';
import { afterAll, beforeAll, describe, expect, it } from 'vitest';

// @ts-expect-error plain ESM module without type declarations
import { startMockServer } from '../mock/server.mjs';

// E-WORK-LIST is checked against the v4 package the mock serves (v3 plus the D-WORKLIST-FILTERS proposal fields).
type Response = { content: { 'application/json': { schema: object } } };
const openapi = JSON.parse(readFileSync(join(__dirname, '../../architecture/packages/v4/openapi.json'), 'utf8')) as {
  paths: { '/api/v1/work': { get: { responses: Record<string, Response> } } };
};
const responses = openapi.paths['/api/v1/work'].get.responses;
const ajv = new Ajv2020({ allErrors: true, strict: true });
addFormats(ajv);
const validators = Object.fromEntries(
  Object.entries(responses).map(([status, r]) => [status, ajv.compile(r.content['application/json'].schema)]),
);

type Item = { id: string; title: string; line: string; line_key?: string; reference: string; kind: string; state: string; age_seconds: number; sample: boolean };
type Body = {
  items: Item[];
  next_cursor?: string;
  as_of: string;
  counts?: Record<string, number>;
  filters?: { lines: { key: string; title: string }[] };
  code?: string;
  message?: string;
};

const rows = JSON.parse(readFileSync(join(__dirname, '../mock/fixtures/E-WORK-LIST.rows.json'), 'utf8')).rows as {
  personas: string[];
  queue: string;
  project: string;
  waiting?: string;
  item: Item;
}[];
const rowsOf = (persona: string, queue: string) => rows.filter((r) => r.personas.includes(persona) && r.queue === queue).map((r) => r.item);

let server: Server;
let base: string;

beforeAll(async () => {
  server = await startMockServer({ port: 0 });
  base = `http://127.0.0.1:${(server.address() as AddressInfo).port}`;
});
afterAll(() => new Promise<void>((resolve) => server.close(() => resolve())));

async function list(query: string, persona = 'finance_lead', extraCookie = '') {
  const response = await fetch(`${base}/api/v1/work?${query}`, { headers: { Cookie: `psl_mock_persona=${persona}${extraCookie}` } });
  const body = (await response.json()) as Body;
  const validate = validators[String(response.status)];
  expect(validate, `undeclared status ${response.status}`).toBeTruthy();
  expect(validate(body), `${query} ${response.status}: ${ajv.errorsText(validate.errors)}`).toBe(true);
  return { status: response.status, body };
}

const QUEUES: Record<string, string[]> = {
  finance_lead: ['needs_me', 'waiting_on_others', 'done', 'unassigned'],
  pm: ['needs_me', 'waiting_on_others', 'done'],
  none: ['needs_me', 'waiting_on_others', 'done'],
};

describe('E-WORK-LIST mock honours the query', () => {
  for (const [persona, queues] of Object.entries(QUEUES)) {
    for (const queue of queues) {
      for (const limit of [10, 20, 50]) {
        it(`${persona} ${queue} limit ${limit}: every row exactly once, at most ${limit} per page`, async () => {
          const seen: string[] = [];
          let cursor: string | undefined;
          let pages = 0;
          do {
            const { status, body } = await list(`queue=${queue}&limit=${limit}${cursor ? `&cursor=${cursor}` : ''}`, persona);
            expect(status).toBe(200);
            expect(body.items.length).toBeLessThanOrEqual(limit);
            seen.push(...body.items.map((i) => i.id));
            cursor = body.next_cursor;
            if (cursor !== undefined) expect(cursor).not.toBe('');
            pages += 1;
          } while (cursor && pages < 20);
          const expected = rowsOf(persona, queue);
          expect(seen.length).toBe(expected.length);
          expect(new Set(seen)).toEqual(new Set(expected.map((i) => i.id)));
        });
      }
    }
  }

  it('counts equal the row totals per queue; unassigned only for finance_lead', async () => {
    expect((await list('queue=needs_me')).body.counts).toEqual({ needs_me: 24, waiting_on_others: 12, done: 6, unassigned: 2 });
    expect((await list('queue=needs_me', 'pm')).body.counts).toEqual({ needs_me: 0, waiting_on_others: 3, done: 2 });
    expect((await list('queue=needs_me', 'none')).body).toEqual({
      items: [],
      as_of: '2026-11-10T09:42:00Z',
      counts: { needs_me: 0, waiting_on_others: 0, done: 0 },
      filters: { lines: [] },
    });
  });

  it('defaults to 20 rows and sorts by age then id', async () => {
    const { body } = await list('queue=needs_me');
    expect(body.items).toHaveLength(20);
    expect(body.next_cursor).toBeTruthy();
    const ages = body.items.map((i) => i.age_seconds);
    expect(ages).toEqual([...ages].sort((a, b) => a - b));
    const rest = await list(`queue=needs_me&cursor=${body.next_cursor}`);
    expect(rest.body.items).toHaveLength(4);
    expect(rest.body.next_cursor).toBeUndefined();
  });

  it('q, line (by key), project, waiting_on and state narrow the results and leave counts unfiltered', async () => {
    const q = await list('queue=needs_me&q=LAGOON');
    expect(q.body.items.map((i) => i.id).sort()).toEqual(['W-1001', 'W-1004']);
    expect(q.body.counts?.needs_me).toBe(24);
    expect((await list('queue=needs_me&q=inv-0412')).body.items.map((i) => i.id)).toEqual(['W-1001']);
    const filtered = await list('queue=needs_me&line=invoice&state=action_needed');
    expect(filtered.body.items.length).toBeGreaterThan(0);
    expect(filtered.body.items.every((i) => i.line_key === 'invoice' && i.line === 'Prepare an invoice' && i.state === 'action_needed')).toBe(true);
    expect((await list('queue=needs_me&line=Prepare%20an%20invoice')).body.items).toEqual([]);
    const project = await list('queue=needs_me&project=C-LAGOON-HEALTH');
    expect(project.body.items.map((i) => i.id).sort()).toEqual(['W-1001', 'W-1004']);
    const agents = await list('queue=waiting_on_others&waiting_on=agent');
    expect(agents.body.items.map((i) => i.id).sort()).toEqual(rows.filter((r) => r.personas.includes('finance_lead') && r.waiting === 'agent').map((r) => r.item.id).sort());
    expect(agents.body.items.every((i) => i.state === 'processing')).toBe(true);
    expect((await list('queue=needs_me&waiting_on=agent')).body.items).toEqual([]);
    expect((await list('queue=needs_me&q=zzz')).body.items).toEqual([]);
  });

  it('a malformed query gets 404 invalid_query', async () => {
    // QA-2-1: an empty optional parameter (minLength 1) is malformed too.
    for (const query of ['', 'queue=bogus', 'queue=needs_me&limit=7', 'queue=needs_me&cursor=nope', 'queue=needs_me&q=', 'queue=needs_me&line=', 'queue=needs_me&waiting_on=everyone']) {
      expect(await list(query)).toEqual({ status: 404, body: { code: 'invalid_query', message: 'We could not read that list request.' } });
    }
  });

  it('pm asking for unassigned gets 403 queue_not_open; persona none gets it empty', async () => {
    expect(await list('queue=unassigned', 'pm')).toEqual({ status: 403, body: { code: 'queue_not_open', message: 'Only Leads can see unassigned work.' } });
    expect(await list('queue=unassigned', 'none')).toEqual({
      status: 200,
      body: { items: [], as_of: '2026-11-10T09:42:00Z', counts: { needs_me: 0, waiting_on_others: 0, done: 0 }, filters: { lines: [] } },
    });
  });

  it('lists the lines the persona has work on, by key, A–Z', async () => {
    const { body } = await list('queue=done');
    const titles = body.filters!.lines.map((l) => l.title);
    expect(titles).toEqual([...titles].sort((a, b) => a.localeCompare(b)));
    expect(body.filters!.lines).toContainEqual({ key: 'invoice', title: 'Prepare an invoice' });
    expect(new Set(titles)).toEqual(new Set(rows.filter((r) => r.personas.includes('finance_lead')).map((r) => r.item.line)));
  });

  it('psl_mock_worklist=board serves the SCR-01 boards\' sample rows, still on contract', async () => {
    const lead = await list('queue=needs_me', 'finance_lead', '; psl_mock_worklist=board');
    expect(lead.body.counts).toEqual({ needs_me: 3, waiting_on_others: 5, done: 28, unassigned: 1 });
    expect(lead.body.items.map((i) => i.title)).toContain('Lagoon Health · Milestone 2 invoice');
    expect(lead.body.filters!.lines[0]).toEqual({ key: 'invoice', title: 'Invoice preparation and delivery' });
    const pm = await list('queue=waiting_on_others&waiting_on=outside_party', 'pm', '; psl_mock_worklist=board');
    expect(pm.body.items.map((i) => i.reference)).toEqual(['REL-0077', 'COM-0233']);
    expect((await list('queue=needs_me', 'none', '; psl_mock_worklist=board')).body.items).toEqual([]);
  });

  it('the X-Mock-Scenario header still wins', async () => {
    const response = await fetch(`${base}/api/v1/work?queue=needs_me`, { headers: { 'X-Mock-Scenario': '401' } });
    expect(response.status).toBe(401);
  });
});

describe('E-WORK-LIST fixture content', () => {
  const all = rows.map((r) => r.item);

  it('finance_lead Needs me holds only decide, do and fix, with the required states over 4+ lines', () => {
    const needs = rowsOf('finance_lead', 'needs_me');
    expect(needs).toHaveLength(24);
    expect(needs.every((i) => ['decide', 'do', 'fix'].includes(i.kind))).toBe(true);
    for (const state of ['effect_uncertain', 'owner_needed', 'setup_needed', 'ready', 'followup_needed']) {
      expect(needs.some((i) => i.state === state), state).toBe(true);
    }
    expect(new Set(needs.map((i) => i.line)).size).toBeGreaterThanOrEqual(4);
  });

  it('waiting on others is all started; done includes verified and cancelled', () => {
    const waiting = rowsOf('finance_lead', 'waiting_on_others');
    expect(waiting).toHaveLength(12);
    expect(waiting.every((i) => i.kind === 'started')).toBe(true);
    expect(new Set(waiting.map((i) => i.state))).toEqual(new Set(['processing', 'waiting', 'awaiting_reconciliation']));
    const done = rowsOf('finance_lead', 'done');
    expect(done).toHaveLength(6);
    expect(done.map((i) => i.state)).toEqual(expect.arrayContaining(['verified', 'cancelled']));
    expect(rowsOf('finance_lead', 'unassigned')).toHaveLength(2);
    expect([rowsOf('pm', 'needs_me'), rowsOf('pm', 'waiting_on_others'), rowsOf('pm', 'done'), rowsOf('pm', 'unassigned')].map((r) => r.length)).toEqual([0, 3, 2, 0]);
  });

  it('keeps the shared ids and states, all sample, no payroll lines and no W-1099', () => {
    const original = JSON.parse(readFileSync(join(__dirname, '../mock/fixtures/E-WORK-LIST.json'), 'utf8')).items as Item[];
    const byId = (id: string) => rows.find((r) => r.item.id === id && r.personas.includes('finance_lead'))!.item;
    for (const item of original) expect(byId(item.id)).toMatchObject(item);
    expect([byId('W-1004').state, byId('W-1005').state, byId('W-1006').state]).toEqual(['ready', 'effect_uncertain', 'verified']);
    expect(all.every((i) => i.sample === true)).toBe(true);
    expect(all.some((i) => /payroll/i.test(i.line))).toBe(false);
    expect(all.some((i) => i.id === 'W-1099')).toBe(false);
  });
});
