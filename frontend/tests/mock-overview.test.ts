import { readFileSync } from 'node:fs';
import type { Server } from 'node:http';
import type { AddressInfo } from 'node:net';
import { join } from 'node:path';

import Ajv2020 from 'ajv/dist/2020';
import addFormats from 'ajv-formats';
import { afterAll, beforeAll, describe, expect, it } from 'vitest';

// @ts-expect-error plain ESM module without type declarations
import { overview, OVERVIEW_VARIANTS } from '../mock/overview.mjs';
// @ts-expect-error plain ESM module without type declarations
import { OPENAPI_PATH, startMockServer } from '../mock/server.mjs';

// E-OVERVIEW fixtures against the v4 200 schema (the mock's contract).
type Op = { operationId: string; responses: Record<string, { content: { 'application/json': { schema: object } } }> };
const openapi = JSON.parse(readFileSync(OPENAPI_PATH, 'utf8')) as { paths: Record<string, Record<string, Op>> };
const schema = openapi.paths['/api/v1/overview'].get.responses['200'].content['application/json'].schema;
const ajv = new Ajv2020({ allErrors: true, strict: true });
addFormats(ajv);
const validate = ajv.compile(schema);

const fixtures = join(__dirname, '../mock/fixtures');
const read = (path: string) => JSON.parse(readFileSync(join(fixtures, path), 'utf8'));
const DEFAULT = read('E-OVERVIEW.json');

let server: Server;
let base: string;
beforeAll(async () => {
  server = await startMockServer({ port: 0 });
  base = `http://127.0.0.1:${(server.address() as AddressInfo).port}`;
});
afterAll(() => new Promise<void>((resolve) => server.close(() => resolve())));

describe('E-OVERVIEW mock', () => {
  it('lists the four variants', () => {
    expect(OVERVIEW_VARIANTS).toEqual(['empty', 'zero', 'changed', 'status']);
  });

  it('the status variant is the default plus a status (label and tone) per line, valid under v7', () => {
    const status = read('overview/status.json');
    expect(validate(status), ajv.errorsText(validate.errors)).toBe(true);
    type Line = { line: string; status: { label: string; tone: string } };
    expect((status.lines as Line[]).map((l) => l.status.tone)).toEqual(['neutral', 'stopped', 'uncertain', 'verified', 'neutral', 'verified', 'verified', 'person']);
    const { lines, ...rest } = status;
    expect(rest).toEqual({ as_of: DEFAULT.as_of, totals: DEFAULT.totals });
    expect((lines as Line[]).map((line) => Object.fromEntries(Object.entries(line).filter(([k]) => k !== 'status')))).toEqual(DEFAULT.lines);
  });

  for (const file of ['E-OVERVIEW.json', 'overview/empty.json', 'overview/zero.json', 'overview/changed.json']) {
    it(`${file} is schema-valid`, () => {
      expect(validate(read(file)), ajv.errorsText(validate.errors)).toBe(true);
    });
  }

  it('the default fixture is the SCR-06 board, and its station counts do not add up to the totals', () => {
    expect(DEFAULT.as_of).toBe('2026-11-14T15:40:00Z');
    expect(DEFAULT.totals).toEqual({ in_progress: 18, need_a_person: 5, stopped: 3, verified_this_month: 28 });
    type Line = { line: string; note: string; stations: { count: number; needs_person: boolean }[] };
    const lines = DEFAULT.lines as Line[];
    expect(lines.map((l) => [l.line, l.stations.length, l.note])).toEqual([
      ['Pre-sale', 5, '1 WAITING'],
      ['Planning', 5, '1 STOPPED'],
      ['Release', 5, '1 UNCERTAIN'],
      ['Closing', 4, 'ON TRACK'],
      ['Invoices', 7, '2 WAITING'],
      ['Month-end', 5, 'ON TRACK'],
      ['Cash and BU', 4, 'ON TRACK'],
      ['Payroll', 5, '2 PROBLEMS'],
    ]);
    const board = lines.map((l) => l.stations.map((s) => (s.needs_person ? 'O' : s.count > 0 ? 'D' : 'W')).join(''));
    expect(board).toEqual(['DWOWW', 'DWOWD', 'DDWOW', 'WDWD', 'DWDOWWD', 'WDWDW', 'DWWW', 'WDOWW']);
    expect(lines.flatMap((l) => l.stations).reduce((a, s) => a + s.count, 0)).toBe(21);
  });

  it('empty and zero variants hold what their names say; changed is later with changed figures', () => {
    const empty = read('overview/empty.json');
    expect(empty.lines).toEqual([]);
    expect(Object.values(empty.totals)).toEqual([0, 0, 0, 0]);
    const zero = read('overview/zero.json');
    expect(zero.lines).toHaveLength(8);
    expect(zero.lines.flatMap((l: { stations: object[] }) => l.stations).every((s: { count: number; needs_person: boolean }) => s.count === 0 && !s.needs_person)).toBe(true);
    expect(Object.values(zero.totals)).toEqual([0, 0, 0, 0]);
    const changed = read('overview/changed.json');
    expect(changed.as_of).toBe('2026-11-14T15:40:15Z');
    expect(changed.totals).not.toEqual(DEFAULT.totals);
  });

  it('overview() picks the variant named by the cookie, and the default otherwise', () => {
    for (const v of OVERVIEW_VARIANTS as string[]) {
      expect(overview({ cookies: { psl_mock_overview: v } })).toEqual({ status: 200, body: read(`overview/${v}.json`) });
    }
    expect(overview({ cookies: { psl_mock_overview: 'nonsense' } })).toEqual({ status: 200, body: DEFAULT });
    expect(overview({ cookies: {} })).toEqual({ status: 200, body: DEFAULT });
  });

  it('GET /api/v1/overview through the mock server honours the cookie', async () => {
    const get = async (cookie: string) => {
      const response = await fetch(`${base}/api/v1/overview`, { headers: { Cookie: cookie } });
      return { status: response.status, body: await response.json() };
    };
    expect(await get('psl_mock_overview=changed')).toEqual({ status: 200, body: read('overview/changed.json') });
    expect(await get('psl_mock_persona=pm; psl_mock_overview=empty')).toEqual({ status: 200, body: read('overview/empty.json') });
    expect(await get('psl_mock_persona=none')).toEqual({ status: 200, body: DEFAULT });
  });
});
