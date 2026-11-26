// F-116: the archive mock (mock/archive-live.mjs) answers the contract's shapes, and refuses the bodies the contract refuses.
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import Ajv2020 from 'ajv/dist/2020';
import addFormats from 'ajv-formats';
import { describe, expect, it } from 'vitest';

// @ts-expect-error plain ESM module without type declarations
import { ARCHIVE_PATH, archiveLive, resetArchiveLive } from '../mock/archive-live.mjs';

const spec = JSON.parse(readFileSync(join(__dirname, '../../contracts/psl-factory.openapi.json'), 'utf8')) as object;
const ajv = new Ajv2020({ allErrors: true, strict: false });
addFormats(ajv);
ajv.addSchema({ $id: 'spec', ...spec });
const ptr = (path: string) => path.replaceAll('/', '~1');
const schema = (path: string, method: string, tail: string) => `spec#/paths/${ptr(path)}/${method}/${tail}/content/application~1json/schema`;
const reply = (path: string, method = 'get', extra: object = {}) => archiveLive({ method, url: new URL(path, 'http://m.local'), scenario: undefined, csrfOk: true, persona: 'finance_lead', ...extra }) as [number, unknown];
const bytes = (body: object) => ({ rawBytes: Buffer.from(JSON.stringify(body)) });
const IDS = [5301, 5302, 5303, 5304, 5306, 5307, 5308];

describe('the reads are the contract’s shapes', () => {
  it('the work item and the inventory', () => {
    for (const id of IDS) {
      for (const [path, op] of [[`/api/v1/work/${id}`, '/api/v1/work/{work_id}'], [`/api/v1/work/${id}/archive-files`, '/api/v1/work/{work_id}/archive-files']] as const) {
        const [status, body] = reply(path);
        expect(status, path).toBe(200);
        const validate = ajv.compile({ $ref: schema(op, 'get', 'responses/200') });
        // 5307 serves a work read with no revision on purpose
        if (id === 5307 && op === '/api/v1/work/{work_id}') continue;
        expect(validate(body), `${path}: ${ajv.errorsText(validate.errors)}`).toBe(true);
      }
    }
  });
  it('5305 is unavailable to everyone; the ids are its own', () => {
    expect(reply('/api/v1/work/5305/archive-files')[0]).toBe(404);
    expect(ARCHIVE_PATH.test('/api/v1/work/5301/archive-files/3/recovery')).toBe(true);
    expect(ARCHIVE_PATH.test('/api/v1/work/4401/archive-files')).toBe(false);
    expect(ARCHIVE_PATH.test('/api/v1/work/5309/archive-files')).toBe(false);
  });
});

describe('the writes', () => {
  it('a reserve valid for the contract is accepted with the contract’s 202 and the file list then reads queued', () => {
    resetArchiveLive();
    const body = { expected_revision: 7, case_revision: 41, source_ids: [11, 12] };
    expect(ajv.compile({ $ref: schema('/api/v1/work/{work_id}/archive-files', 'post', 'requestBody') })(body)).toBe(true);
    const [status, answer] = reply('/api/v1/work/5304/archive-files', 'post', bytes(body));
    expect(status).toBe(202);
    const validate = ajv.compile({ $ref: schema('/api/v1/work/{work_id}/archive-files', 'post', 'responses/202') });
    expect(validate(answer), ajv.errorsText(validate.errors)).toBe(true);
    const read = reply('/api/v1/work/5304/archive-files')[1] as { files: unknown[]; can_reserve: boolean };
    expect(read.files).toHaveLength(3);
    expect(read.can_reserve).toBe(false);
  });
  it('refuses an empty or unlisted source list, an extra member and an old version', () => {
    resetArchiveLive();
    expect(reply('/api/v1/work/5304/archive-files', 'post', bytes({ expected_revision: 7, case_revision: 41, source_ids: [] }))[0]).toBe(422);
    expect(reply('/api/v1/work/5304/archive-files', 'post', bytes({ expected_revision: 7, case_revision: 41, source_ids: [99] }))[0]).toBe(422);
    expect(reply('/api/v1/work/5304/archive-files', 'post', bytes({ expected_revision: 7, case_revision: 41, source_ids: [11], note: 'x' }))[0]).toBe(400);
    expect(reply('/api/v1/work/5304/archive-files', 'post', bytes({ expected_revision: 6, case_revision: 41, source_ids: [11] }))[0]).toBe(409);
  });
  it('a lookup then a retry follow the contract’s shapes; a retry before a lookup is refused', () => {
    resetArchiveLive();
    const job = 530300 + 90000;
    const path = `/api/v1/work/5303/archive-files/${job}/recovery`;
    expect(reply(path, 'post', bytes({ revision: 1, action: 'retry' }))[0]).toBe(422);
    const [status, answer] = reply(path, 'post', bytes({ revision: 1, action: 'lookup' }));
    expect(status).toBe(200);
    const validate = ajv.compile({ $ref: schema('/api/v1/work/{work_id}/archive-files/{job_id}/recovery', 'post', 'responses/200') });
    expect(validate(answer), ajv.errorsText(validate.errors)).toBe(true);
    expect(reply(path, 'post', bytes({ revision: 1, action: 'retry' }))[0]).toBe(409);
    expect(reply(path, 'post', bytes({ revision: 2, action: 'retry' }))[0]).toBe(200);
  });
});
