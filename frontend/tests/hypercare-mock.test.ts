// F-115: the hypercare mock (mock/hypercare-live.mjs) answers the contract's shapes, and refuses the background bodies the contract refuses.
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import Ajv2020 from 'ajv/dist/2020';
import addFormats from 'ajv-formats';
import { describe, expect, it } from 'vitest';

// @ts-expect-error plain ESM module without type declarations
import { HYPERCARE_PATH, hypercareLive, resetHypercareLive } from '../mock/hypercare-live.mjs';

const spec = JSON.parse(readFileSync(join(__dirname, '../../contracts/psl-factory.openapi.json'), 'utf8')) as object;
const ajv = new Ajv2020({ allErrors: true, strict: false });
addFormats(ajv);
ajv.addSchema({ $id: 'spec', ...spec });
const ptr = (path: string) => path.replaceAll('/', '~1');
const schema = (path: string, method: string, tail: string) => `spec#/paths/${ptr(path)}/${method}/${tail}/content/application~1json/schema`;
const reply = (path: string, method = 'get', extra: object = {}) => hypercareLive({ method, url: new URL(path, 'http://m.local'), scenario: undefined, csrfOk: true, persona: 'finance_lead', ...extra }) as [number, unknown];
const IDS = [5201, 5202, 5203, 5204, 5205, 5207, 5208];

describe('the reads are the contract’s shapes', () => {
  it('the work item, stability and the issues register', () => {
    for (const id of IDS) {
      for (const [path, op] of [
        [`/api/v1/work/${id}`, '/api/v1/work/{work_id}'],
        [`/api/v1/work/${id}/stability`, '/api/v1/work/{work_id}/stability'],
        ...(id === 5208 ? [] : [[`/api/v1/projects/00000000-0000-4000-8000-00000000${id}/issues`, '/api/v1/projects/{case_id}/issues']]),
        ...(id === 5207 ? [] : [[`/api/v1/work/${id}/stability/events`, '/api/v1/work/{work_id}/stability/events']]),
      ] as const) {
        const [status, body] = reply(path);
        expect(status, path).toBe(200);
        const validate = ajv.compile({ $ref: schema(op, 'get', 'responses/200') });
        expect(validate(body), `${path}: ${ajv.errorsText(validate.errors)}`).toBe(true);
      }
    }
  });
  it('5206 is unavailable to everyone; 5207 and 5208 fail one read each', () => {
    expect(reply('/api/v1/work/5206')[0]).toBe(404);
    expect(reply('/api/v1/work/5206/stability')[0]).toBe(404);
    expect(reply('/api/v1/work/5207/stability/events')[0]).toBe(503);
    expect(reply('/api/v1/work/5207/stability')[0]).toBe(200);
    expect(reply('/api/v1/projects/P-5208/issues')[0]).toBe(503);
  });
  it('owns only its ids', () => {
    expect(HYPERCARE_PATH.test('/api/v1/work/5201/stability')).toBe(true);
    expect(HYPERCARE_PATH.test('/api/v1/work/4201/stability')).toBe(false);
    expect(HYPERCARE_PATH.test('/api/v1/work/5209/stability')).toBe(false);
  });
});

describe('the background write', () => {
  const post = (id: number, body: object, extra: object = {}) => reply(`/api/v1/work/${id}/background`, 'post', { rawBytes: Buffer.from(JSON.stringify(body)), ...extra });
  const bodyOk = ajv.compile({ $ref: schema('/api/v1/work/{work_id}/background', 'post', 'requestBody') });
  it('a body valid for the contract is accepted with the contract’s 202; the item then reads paused', () => {
    resetHypercareLive();
    const body = { expected_revision: 8, enabled: false };
    expect(bodyOk(body)).toBe(true);
    const [status, answer] = post(5202, body);
    expect(status).toBe(202);
    const validate = ajv.compile({ $ref: schema('/api/v1/work/{work_id}/background', 'post', 'responses/202') });
    expect(validate(answer), ajv.errorsText(validate.errors)).toBe(true);
    const item = reply('/api/v1/work/5202')[1] as { revision: number; available_control: string[] };
    expect(item.revision).toBe(9);
    expect(item.available_control).toEqual(['resume']);
  });
  it('refuses a body the contract refuses (case_revision, a missing or non-boolean enabled)', () => {
    resetHypercareLive();
    for (const bad of [{ expected_revision: 8, enabled: false, case_revision: 41 }, { expected_revision: 8 }, { expected_revision: 8, enabled: 'no' }, { enabled: true }]) {
      expect(bodyOk(bad), JSON.stringify(bad)).toBe(false);
      expect(post(5202, bad)[0], JSON.stringify(bad)).toBe(400);
    }
  });
  it('a stale revision is 409, a bad session check 403, and no write is allowed on the reads', () => {
    resetHypercareLive();
    expect(post(5202, { expected_revision: 7, enabled: false })[0]).toBe(409);
    expect(post(5202, { expected_revision: 8, enabled: false }, { csrfOk: false })[0]).toBe(403);
    expect(reply('/api/v1/work/5202/stability', 'post')[0]).toBe(405);
  });
});
