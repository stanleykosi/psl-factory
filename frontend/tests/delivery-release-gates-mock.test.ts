// F-113B: the release mock (mock/delivery-release.mjs) answers the contract's shapes, and refuses the bodies the contract refuses.
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import Ajv2020 from 'ajv/dist/2020';
import addFormats from 'ajv-formats';
import { describe, expect, it } from 'vitest';

// @ts-expect-error plain ESM module without type declarations
import { RELEASE_PATH, releaseLive, resetReleaseLive } from '../mock/delivery-release.mjs';

const spec = JSON.parse(readFileSync(join(__dirname, '../../contracts/psl-factory.openapi.json'), 'utf8')) as object;
const ajv = new Ajv2020({ allErrors: true, strict: false });
addFormats(ajv);
ajv.addSchema({ $id: 'spec', ...spec });
const ptr = (path: string) => path.replaceAll('/', '~1');
const schema = (path: string, method: string, tail: string) => `spec#/paths/${ptr(path)}/${method}/${tail}/content/application~1json/schema`;
const reply = (path: string, method = 'get', extra: object = {}) => releaseLive({ method, url: new URL(path, 'http://m.local'), scenario: undefined, csrfOk: true, persona: 'finance_lead', ...extra }) as [number, unknown];
const GATE_IDS = [4801, 4802, 4803, 4804, 4805, 4806, 4807, 4808, 4809, 4810, 4811, 4812, 4813, 4814];

describe('the reads are the contract’s shapes', () => {
  it('release-register, planning-exit and the work item, for every fixture', () => {
    for (const id of GATE_IDS) {
      for (const [path, op] of [
        [`/api/v1/work/${id}/release-register`, '/api/v1/work/{work_id}/release-register'],
        [`/api/v1/work/${id}/planning-exit`, '/api/v1/work/{work_id}/planning-exit'],
        [`/api/v1/work/${id}`, '/api/v1/work/{work_id}'],
      ] as const) {
        const [status, body] = reply(path);
        expect(status, path).toBe(200);
        const validate = ajv.compile({ $ref: schema(op, 'get', 'responses/200') });
        expect(validate(body), `${path}: ${ajv.errorsText(validate.errors)}`).toBe(true);
      }
    }
  });
  it('client-testing and decision-appointments', () => {
    for (const [path, op] of [
      ['/api/v1/projects/P-4801/delivery/7/client-testing', '/api/v1/projects/{case_id}/delivery/{dossier_id}/client-testing'],
      ['/api/v1/setup/00000000-0000-4000-8000-000000004807/decision-appointments', '/api/v1/setup/{case_id}/decision-appointments'],
    ] as const) {
      const [status, body] = reply(path);
      expect(status, path).toBe(200);
      const validate = ajv.compile({ $ref: schema(op, 'get', 'responses/200') });
      expect(validate(body), `${path}: ${ajv.errorsText(validate.errors)}`).toBe(true);
    }
  });
  it('owns only its ids; 4890 is unavailable', () => {
    expect(RELEASE_PATH.test('/api/v1/work/4801/release-register')).toBe(true);
    expect(RELEASE_PATH.test('/api/v1/work/4201/release-register')).toBe(false);
    expect(RELEASE_PATH.test('/api/v1/work/2501/release-register')).toBe(false);
    expect(reply('/api/v1/work/4890')[0]).toBe(404);
  });
});

describe('the writes', () => {
  const post = (path: string, body: object, extra: object = {}) => reply(path, 'post', { rawBytes: Buffer.from(JSON.stringify(body)), ...extra });
  const decide = { expected_revision: 6, case_revision: 41, packet: 'a'.repeat(64), verdict: 'approve' };

  it('a decision body valid for the contract is accepted; the 200 is the contract’s', () => {
    resetReleaseLive();
    const bodyOk = ajv.compile({ $ref: schema('/api/v1/work/{work_id}/planning-exit', 'post', 'requestBody') });
    expect(bodyOk(decide)).toBe(true);
    const [status, body] = post('/api/v1/work/4801/planning-exit', decide);
    expect(status).toBe(200);
    const validate = ajv.compile({ $ref: schema('/api/v1/work/{work_id}/planning-exit', 'post', 'responses/200') });
    expect(validate(body), ajv.errorsText(validate.errors)).toBe(true);
  });
  it('refuses a body the contract refuses', () => {
    resetReleaseLive();
    const bodyOk = ajv.compile({ $ref: schema('/api/v1/work/{work_id}/planning-exit', 'post', 'requestBody') });
    for (const bad of [{ ...decide, packet: undefined }, { ...decide, verdict: 'maybe' }, { ...decide, extra: 1 }, { ...decide, expected_revision: undefined }]) {
      expect(bodyOk(bad), JSON.stringify(bad)).toBe(false);
      expect(post('/api/v1/work/4801/planning-exit', bad)[0], JSON.stringify(bad)).toBe(400);
    }
  });
  it('the server-side rules the page does not repeat: evidence unless direct, a note to return, a stale token', () => {
    resetReleaseLive();
    expect(post('/api/v1/work/4814/planning-exit', decide)[0]).toBe(422);
    expect(post('/api/v1/work/4801/planning-exit', { ...decide, verdict: 'return' })[0]).toBe(422);
    expect(post('/api/v1/work/4801/planning-exit', { ...decide, expected_revision: 5 })[0]).toBe(409);
    expect(post('/api/v1/work/4801/planning-exit', decide, { csrfOk: false })[0]).toBe(403);
  });
  it('prepare_readiness and observe_release bodies are the contract’s', () => {
    resetReleaseLive();
    const bodyOk = ajv.compile({ $ref: schema('/api/v1/work/{work_id}/release-register', 'post', 'requestBody') });
    const prepare = { action: 'prepare_readiness', expected_revision: 6, case_revision: 41 };
    const observe = { action: 'observe_release', expected_revision: 6, case_revision: 41, readiness_id: 71, released_at: '2026-11-26T10:00:00.000Z', reference: 'R', upload_id: 8001, checked: true, note: 'n', environment: null, private_log_id: null };
    expect(bodyOk(prepare)).toBe(true);
    expect(bodyOk(observe)).toBe(true);
    expect(post('/api/v1/work/4808/release-register', prepare)[0]).toBe(200);
    expect(post('/api/v1/work/4810/release-register', observe)[0]).toBe(200);
    expect(post('/api/v1/work/4810/release-register', { ...observe, checked: false })[0]).toBe(400);
    expect(post('/api/v1/work/4810/release-register', { ...observe, evidence_id: 5 })[0]).toBe(400);
  });
});
