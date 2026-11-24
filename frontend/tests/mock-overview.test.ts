import { readFileSync } from 'node:fs';
import type { Server } from 'node:http';
import type { AddressInfo } from 'node:net';
import { join } from 'node:path';

import Ajv2020 from 'ajv/dist/2020';
import addFormats from 'ajv-formats';
import { afterAll, beforeAll, describe, expect, it } from 'vitest';

// @ts-expect-error plain ESM module without type declarations
import { OVERVIEW_VARIANTS } from '../mock/overview.mjs';
// @ts-expect-error plain ESM module without type declarations
import { startMockServer } from '../mock/server.mjs';

// The mock's two floor reads against the live contract (contracts/psl-factory.openapi.json, 1.24.0).
const contract = JSON.parse(readFileSync(join(__dirname, '../../contracts/psl-factory.openapi.json'), 'utf8')) as {
  paths: Record<string, { get: { responses: Record<string, { content: { 'application/json': { schema: object } } }> } }>;
  components: object;
};
const ajv = new Ajv2020({ allErrors: true, strict: false });
addFormats(ajv);
const compile = (path: string) => ajv.compile({ ...contract.paths[path].get.responses['200'].content['application/json'].schema, components: contract.components });
const validOverview = compile('/api/v1/overview');
const validCounts = compile('/api/v1/work/counts');

let server: Server;
let base: string;
beforeAll(async () => {
  server = await startMockServer({ port: 0 });
  base = `http://127.0.0.1:${(server.address() as AddressInfo).port}`;
});
afterAll(() => new Promise<void>((resolve) => server.close(() => resolve())));

const get = async (path: string, variant?: string) => {
  const res = await fetch(`${base}${path}`, { headers: { cookie: `psl_mock_persona=ceo${variant ? `; psl_mock_overview=${variant}` : ''}` } });
  return { status: res.status, body: await res.json() };
};

describe('GET /overview and GET /work/counts in the mock', () => {
  it('lists the five variants', () => {
    expect(OVERVIEW_VARIANTS).toEqual(['empty', 'limited', 'missing', 'missing-limited', 'no-counts']);
  });

  it('serves exactly {as_of, lines[{key,title,total}]} and the counts shape, both valid under the live contract', async () => {
    const overview = await get('/api/v1/overview');
    expect(overview.status).toBe(200);
    expect(validOverview(overview.body), ajv.errorsText(validOverview.errors)).toBe(true);
    expect(Object.keys(overview.body).sort()).toEqual(['as_of', 'lines']);
    expect(Object.keys(overview.body.lines[0]).sort()).toEqual(['key', 'title', 'total']);
    const counts = await get('/api/v1/work/counts');
    expect(validCounts(counts.body), ajv.errorsText(validCounts.errors)).toBe(true);
    expect(counts.body.limited).toBe(false);
    expect(counts.body.evaluated).toBe(15);
  });

  it('every variant answers a valid body (counts 503 for no-counts)', async () => {
    for (const variant of OVERVIEW_VARIANTS as string[]) {
      const overview = await get('/api/v1/overview', variant);
      expect(validOverview(overview.body), `${variant} overview: ${ajv.errorsText(validOverview.errors)}`).toBe(true);
      const counts = await get('/api/v1/work/counts', variant);
      if (variant === 'no-counts') {
        expect(counts.status).toBe(503);
        continue;
      }
      expect(validCounts(counts.body), `${variant} counts: ${ajv.errorsText(validCounts.errors)}`).toBe(true);
    }
  });

  it('limited has 50 evaluated and null queue totals; missing leaves commercial/v1 out of the counts only', async () => {
    const limited = (await get('/api/v1/work/counts', 'limited')).body;
    expect([limited.limited, limited.evaluated, limited.queues.map((q: { total: number | null }) => q.total)]).toEqual([true, 50, [null]]);
    const missing = (await get('/api/v1/work/counts', 'missing')).body;
    expect(missing.limited).toBe(false);
    expect(missing.lines.map((l: { key: string }) => l.key)).not.toContain('commercial/v1');
    expect((await get('/api/v1/overview', 'missing')).body.lines.map((l: { key: string }) => l.key)).toContain('commercial/v1');
    expect((await get('/api/v1/work/counts', 'missing-limited')).body.limited).toBe(true);
    expect((await get('/api/v1/overview', 'empty')).body.lines).toEqual([]);
  });

  it('keeps no v7 overview and no station read', async () => {
    expect((await get('/api/v1/overview/stations/items?line=Planning&station=Scope')).status).toBe(404);
  });
});
