// F-85: the mock's live work item answers keep the contract's shapes (contract 1.22.0), so pages built on them match the real API.
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import Ajv2020 from 'ajv/dist/2020';
import addFormats from 'ajv-formats';
import { describe, expect, it } from 'vitest';

// @ts-expect-error plain ESM module without type declarations
import { workLive } from '../mock/work-live.mjs';

type Op = { responses: Record<string, { content?: { 'application/json': { schema: object } } }> };
const contract = JSON.parse(readFileSync(join(__dirname, '../../contracts/psl-factory.openapi.json'), 'utf8')) as { paths: Record<string, Record<string, Op>> };
const ajv = new Ajv2020({ allErrors: true, strict: false });
addFormats(ajv);
const validator = (path: string, method: string, status: string) => ajv.compile(contract.paths[path][method].responses[status].content!['application/json'].schema);

const get = (path: string, scenario?: string) => workLive({ method: 'get', url: new URL(path, 'http://m.local'), scenario, csrfOk: true, persona: 'finance_lead' }) as [number, unknown];

describe('the live work mock', () => {
  const work = validator('/api/v1/work/{work_id}', 'get', '200');
  it.each([4101, 4102, 4103, 4104, 4105, 4107, 4108])('work %i is a valid GET /work/{id} answer', (id) => {
    const [status, body] = get(`/api/v1/work/${id}`);
    expect(status).toBe(200);
    expect(work(body), JSON.stringify(work.errors)).toBe(true);
  });

  it('history and the weekly report are valid answers', () => {
    const history = validator('/api/v1/work/{work_id}/history', 'get', '200');
    for (const id of [4101, 4108]) expect(history(get(`/api/v1/work/${id}/history`)[1]), JSON.stringify(history.errors)).toBe(true);
    expect(get('/api/v1/work/4108/history')[1]).toMatchObject({ items: expect.any(Array) });
    expect((get('/api/v1/work/4108/history')[1] as { items: unknown[] }).items).toHaveLength(30);
    const report = validator('/api/v1/work/{work_id}/weekly-report', 'get', '200');
    for (const id of [4102, 4107]) expect(report(get(`/api/v1/work/${id}/weekly-report`)[1]), JSON.stringify(report.errors)).toBe(true);
  });

  it('the file routes answer valid shapes', () => {
    const upload = validator('/api/v1/cases/{case_id}/files', 'post', '200');
    const [status, body] = workLive({ method: 'post', url: new URL('/api/v1/cases/c1/files', 'http://m.local'), csrfOk: true, persona: 'finance_lead', rawBytes: new Uint8Array(3) }) as [number, unknown];
    expect(status).toBe(200);
    expect(upload(body), JSON.stringify(upload.errors)).toBe(true);
    const review = validator('/api/v1/cases/{case_id}/file-drafts/{job_id}/review', 'post', '200');
    expect(review(workLive({ method: 'post', url: new URL('/api/v1/cases/c1/file-drafts/6001/review', 'http://m.local'), csrfOk: true, persona: 'finance_lead' })[1])).toBe(true);
  });

  it('4106 and an unknown id are 404 for everyone, with the same body; scenarios and csrf answer as named', () => {
    expect(get('/api/v1/work/4106')).toEqual(get('/api/v1/work/999999'));
    expect(get('/api/v1/work/4106')[0]).toBe(404);
    expect(get('/api/v1/work/4102', '503')[0]).toBe(503);
    expect(get('/api/v1/work/4102', 'csrf_failed')).toEqual([403, expect.objectContaining({ code: 'csrf_failed' })]);
    expect(workLive({ method: 'post', url: new URL('/api/v1/cases/c1/files', 'http://m.local'), csrfOk: false, persona: 'finance_lead' })[0]).toBe(403);
  });
});
