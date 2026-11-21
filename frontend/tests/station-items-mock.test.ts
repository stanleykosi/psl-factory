/* eslint-disable @typescript-eslint/no-explicit-any -- parsed mock replies, checked against schemas */
// D-162 / G-OVERVIEW-STATION: the mock's station read (mock/station-items.mjs) against its proposal schema, the overview's
// counts, paging and errors, and the live demo's runs standing on the floor.
import { readFileSync } from 'node:fs';
import type { Server } from 'node:http';
import type { AddressInfo } from 'node:net';
import { join } from 'node:path';

import Ajv2020 from 'ajv/dist/2020';
import addFormats from 'ajv-formats';
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';

// @ts-expect-error plain ESM module without type declarations
import { OPENAPI_PATH, startMockServer } from '../mock/server.mjs';

const ajv = new Ajv2020({ allErrors: true, strict: true });
addFormats(ajv);
const proposal = JSON.parse(readFileSync(join(__dirname, '../mock/proposals/overview-station-items.json'), 'utf8'));
const valid = ajv.compile(proposal.response);
const openapi = JSON.parse(readFileSync(OPENAPI_PATH, 'utf8'));
const overviewSchema = openapi.paths['/api/v1/overview'].get.responses['200'].content['application/json'].schema;
const validOverview = ajv.compile(overviewSchema);
const fixture = (name: string) => JSON.parse(readFileSync(join(__dirname, '../mock/fixtures', name), 'utf8'));

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

const get = async (path: string, cookie = 'psl_mock_persona=ceo') => {
  const response = await fetch(base + path, { headers: { Cookie: cookie } });
  return { status: response.status, body: (await response.json()) as any };
};
const read = (line: string, station: string, extra = '', cookie?: string) =>
  get(`/api/v1/overview/stations/items?line=${encodeURIComponent(line)}&station=${encodeURIComponent(station)}${extra}`, cookie);

describe('the station read', () => {
  it('answers every station of the overview with as many rows as it counts, valid against the proposal', async () => {
    for (const variant of ['E-OVERVIEW.json', 'overview/changed.json', 'overview/zero.json']) {
      const cookie = variant === 'E-OVERVIEW.json' ? 'psl_mock_persona=ceo' : `psl_mock_persona=ceo; psl_mock_overview=${variant.slice(9, -5)}`;
      for (const line of fixture(variant).lines) {
        for (const station of line.stations) {
          const reply = await read(line.line, station.name, '&limit=50', cookie);
          expect(reply.status, `${line.line} ${station.name}`).toBe(200);
          expect(valid(reply.body), ajv.errorsText(valid.errors)).toBe(true);
          expect([reply.body.total, reply.body.items.length]).toEqual([station.count, station.count]);
          for (const item of reply.body.items) expect(item.work_id).toMatch(/^W-\d+$/);
          expect(reply.body.items.filter((i: any) => i.needs_person)).toHaveLength(reply.body.needs_person_count);
        }
      }
    }
  });

  it('puts the row that needs a person first, and reads in pages by cursor', async () => {
    const { body } = await read('Planning', 'Scope', '&limit=1');
    expect(body.items).toHaveLength(1);
    expect(body.total).toBe(2);
    expect(body.next_cursor).toBe('o1');
    const rest = await read('Planning', 'Scope', '&limit=1&cursor=o1');
    expect(rest.body.items).toHaveLength(1);
    expect(rest.body.next_cursor).toBeUndefined();
    const costing = await read('Planning', 'Costing');
    expect(costing.body.items[0]).toMatchObject({ needs_person: true, state: 'waiting', held_by: { kind: 'role' } });
  });

  it('refuses what it cannot read: unknown station, bad limit or cursor, missing names, and the scenario cookie', async () => {
    expect((await read('Planning', 'Nope')).status).toBe(404);
    expect((await read('Planning', 'Scope', '&limit=0')).body.code).toBe('invalid_query');
    expect((await read('Planning', 'Scope', '&limit=51')).status).toBe(404);
    expect((await read('Planning', 'Scope', '&cursor=x')).body.code).toBe('invalid_query');
    expect((await read('Planning', 'Scope', '&cursor=o9')).body.code).toBe('invalid_query');
    expect((await get('/api/v1/overview/stations/items?line=Planning')).status).toBe(404);
    expect((await read('Planning', 'Scope', '', 'psl_mock_persona=ceo; psl_mock_scenario=403')).status).toBe(403);
  });
});

describe('the live demo on the floor', () => {
  const DEMO = 'psl_mock_persona=ceo; psl_mock_demo=on; psl_mock_speed=fast';
  beforeEach(() => vi.useFakeTimers({ toFake: ['Date'] }).setSystemTime(new Date('2026-11-20T09:00:00Z')));
  afterEach(() => vi.useRealTimers());

  it('counts a started line run at its floor station, and the read lists it', async () => {
    const before = (await get('/api/v1/overview', DEMO)).body;
    const options = (await get('/api/v1/lines/weekly_report/fields/project/options', DEMO)).body.items[0];
    const started = await fetch(`${base}/api/v1/work`, {
      method: 'POST',
      headers: { Cookie: DEMO, 'X-CSRFToken': 'mock-csrf-ceo', 'Content-Type': 'application/json' },
      body: JSON.stringify({ line: 'weekly_report', case_id: options.case_id, case_revision: options.case_revision, idempotency_key: 'floor-1', intake: { project: options.value, week: { from: '2026-11-09', to: '2026-11-13' } } }),
    });
    const id = ((await started.json()) as any).work_id;
    const after = (await get('/api/v1/overview', DEMO)).body;
    expect(validOverview(after), ajv.errorsText(validOverview.errors)).toBe(true);
    expect(after.totals.in_progress).toBe(before.totals.in_progress + 1);
    const station = after.lines.find((l: any) => l.line === 'Release').stations.find((s: any, i: number) => s.count !== before.lines.find((l: any) => l.line === 'Release').stations[i].count);
    const listed = await read('Release', station.name, '&limit=50', DEMO);
    expect(listed.body.total).toBe(station.count);
    expect(listed.body.items.map((i: any) => i.work_id)).toContain(id);
    expect(listed.body.items.find((i: any) => i.work_id === id)).toMatchObject({ needs_person: false, held_by: { kind: 'agent', name: 'Tola' } });
    // with the demo off the floor is the fixture's, as before
    expect((await get('/api/v1/overview', 'psl_mock_persona=ceo')).body).toEqual(fixture('E-OVERVIEW.json'));
  });
});
