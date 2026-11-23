// F-103: the mock's forecast answers keep the contract's shapes (contract 1.25.0), so the page built on them matches the real API.
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import Ajv2020 from 'ajv/dist/2020';
import addFormats from 'ajv-formats';
import { describe, expect, it } from 'vitest';

// @ts-expect-error plain ESM module without type declarations
import { forecastLive } from '../mock/forecast-live.mjs';

type Op = { responses: Record<string, { content?: { 'application/json': { schema: object } } }> };
const contract = JSON.parse(readFileSync(join(__dirname, '../../contracts/psl-factory.openapi.json'), 'utf8')) as { paths: Record<string, Record<string, Op>> };
const ajv = new Ajv2020({ allErrors: true, strict: false });
addFormats(ajv);
const validator = (path: string) => ajv.compile(contract.paths[path].get.responses['200'].content!['application/json'].schema);
const get = (path: string, scenario?: string) => forecastLive({ method: 'get', url: new URL(path, 'http://m.local'), scenario, persona: 'finance_lead' }) as [number, unknown];

describe('the forecast mock', () => {
  it.each([4301, 4302, 4303, 4304, 4305, 4306])('forecast %i and its work item are valid answers', (id) => {
    const forecast = validator('/api/v1/work/{work_id}/forecast');
    const work = validator('/api/v1/work/{work_id}');
    expect(forecast(get(`/api/v1/work/${id}/forecast`)[1]), JSON.stringify(forecast.errors)).toBe(true);
    expect(work(get(`/api/v1/work/${id}`)[1]), JSON.stringify(work.errors)).toBe(true);
  });

  it('the month answers are valid, and 4307, an unlisted month and a scenario answer 404 or their status', () => {
    const month = validator('/api/v1/work/{work_id}/forecast/actuals/{month}');
    for (const m of ['2026-11', '2026-09', '2026-10']) expect(month(get(`/api/v1/work/4301/forecast/actuals/${m}`)[1]), JSON.stringify(month.errors)).toBe(true);
    expect(get('/api/v1/work/4307/forecast')[0]).toBe(404);
    expect(get('/api/v1/work/4307')[0]).toBe(404);
    expect(get('/api/v1/work/4301/forecast/actuals/2026-12')[0]).toBe(404);
    expect(get('/api/v1/work/4301/forecast', 'forecast:409')[0]).toBe(409);
    expect(get('/api/v1/work/4301', 'forecast:409')[0]).toBe(200);
  });

  it('4308 is the poisoned variant: it breaks the contract on purpose (a staff name and pay on an item), so only the page guard is tested on it', () => {
    const forecast = validator('/api/v1/work/{work_id}/forecast');
    expect(forecast(get('/api/v1/work/4308/forecast')[1])).toBe(false);
  });

  it('is read only', () => {
    expect(forecastLive({ method: 'post', url: new URL('/api/v1/work/4301/forecast', 'http://m.local'), persona: 'finance_lead' })[0]).toBe(405);
  });
});
