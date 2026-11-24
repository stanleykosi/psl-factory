import { readFileSync } from 'node:fs';
import type { Server } from 'node:http';
import type { AddressInfo } from 'node:net';
import { join } from 'node:path';

import Ajv2020 from 'ajv/dist/2020';
import addFormats from 'ajv-formats';
import { afterAll, beforeAll, beforeEach, describe, expect, it } from 'vitest';

// @ts-expect-error plain ESM module without type declarations
import { startMockServer } from '../mock/server.mjs';

// F-78: the milestone completion options read, the write and the re-read in the contract mock against the live contract
// (1.24.0 shapes): every body served for every scenario validates; a field the schema forbids fails the same check.
type Responses = Record<string, { content: { 'application/json': { schema: object } } }>;
type Operation = { responses: Responses; requestBody?: { content: { 'application/json': { schema: object } } } };
const contract = JSON.parse(readFileSync(join(__dirname, '../../contracts/psl-factory.openapi.json'), 'utf8')) as {
  paths: Record<string, Record<string, Operation>>;
  components: { schemas: { Error: object } };
};
const ajv = new Ajv2020({ allErrors: true, strict: true });
addFormats(ajv);
const PATH = '/api/v1/projects/{case_id}/milestones/completions';
const validOptions = ajv.compile(contract.paths[PATH].get.responses['200'].content['application/json'].schema);
const validRecorded = ajv.compile(contract.paths[PATH].post.responses['201'].content['application/json'].schema);
const validRequest = ajv.compile(contract.paths[PATH].post.requestBody!.content['application/json'].schema);
const validCompletion = ajv.compile(contract.paths['/api/v1/projects/{case_id}/milestones/{milestone_id}'].get.responses['200'].content['application/json'].schema);
const validError = ajv.compile(contract.components.schemas.Error);

const CASE = '00000000-0000-4000-8000-000000000101';
const NAME = 'UAT sign-off';
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

const cookie = (scenario: string, persona = 'pmo_lead') => `psl_mock_persona=${persona}; psl_mock_complete=${scenario}`;
const get = async (path: string, scenario = 'ok', persona = 'pmo_lead') => {
  const response = await fetch(base + path, { headers: { Cookie: cookie(scenario, persona) } });
  return { status: response.status, body: await response.json() };
};
const token = async (persona: string) => (await (await fetch(`${base}/api/v1/me`, { headers: { Cookie: cookie('ok', persona) } })).json()).csrf_token as string;
const post = async (body: unknown, scenario = 'ok', persona = 'pmo_lead', withToken = true) => {
  const response = await fetch(`${base}/api/v1/projects/${CASE}/milestones/completions`, {
    method: 'POST',
    headers: { Cookie: cookie(scenario, persona), 'Content-Type': 'application/json', ...(withToken ? { 'X-CSRFToken': await token(persona) } : {}) },
    body: JSON.stringify(body),
  });
  return { status: response.status, body: await response.json() };
};
const options = (query = '') => `/api/v1/projects/${CASE}/milestones/completions${query}`;
const proofBody = { revision: 5, name: NAME, evidence_id: 31 };
const pdfBody = { revision: 5, name: NAME, upload_id: 88, checked: true as const };

describe('the options read', () => {
  it.each(['ok', 'baseline', 'proofreq', 'inuse', 'norole', 'paged', 'conflict', 'uncertain'])('%s validates, with and without a name', async (scenario) => {
    for (const query of ['', `?name=${encodeURIComponent(NAME)}`, `?name=${encodeURIComponent(NAME)}&page=2`]) {
      const { status, body } = await get(options(query), scenario);
      expect(status).toBe(200);
      expect(validOptions(body), `${scenario}${query}: ${ajv.errorsText(validOptions.errors)}`).toBe(true);
    }
  });

  it('the scenarios shape can_complete and hold', async () => {
    expect((await get(options(), 'ok')).body).toMatchObject({ can_complete: true, hold: null, can_attach_pdf: true });
    expect((await get(options(), 'baseline')).body).toMatchObject({ can_complete: false, hold: 'baseline_required' });
    expect((await get(options(), 'proofreq')).body).toMatchObject({ can_complete: false, hold: 'proof_required', can_attach_pdf: false });
    expect((await get(options(), 'norole')).body).toMatchObject({ can_complete: false, hold: null });
    expect((await get(options(`?name=${NAME}`), 'inuse')).body).toMatchObject({ can_complete: false, hold: 'name_in_use' });
    expect((await get(options(`?name=${NAME}`), 'paged')).body.next_page).toBe(2);
  });

  it('forbidden, notfound and a project the persona cannot see are error bodies of the live shape', async () => {
    for (const [scenario, status] of [['forbidden', 403], ['notfound', 404]] as const) {
      const r = await get(options(), scenario);
      expect(r.status).toBe(status);
      expect(validError(r.body)).toBe(true);
    }
    expect((await get(options(), 'ok', 'none')).status).toBe(404);
  });
});

describe('the write', () => {
  it('the request bodies are the live shapes; a mixed or unchecked body is not', () => {
    expect(validRequest(proofBody)).toBe(true);
    expect(validRequest(pdfBody)).toBe(true);
    expect(validRequest({ ...pdfBody, checked: false })).toBe(false);
    expect(validRequest({ revision: 5, name: NAME })).toBe(false);
  });

  it('records once; the 201 and the re-read validate, and the name is then in use', async () => {
    const done = await post(proofBody);
    expect(done.status).toBe(201);
    expect(validRecorded(done.body), ajv.errorsText(validRecorded.errors)).toBe(true);
    const again = await get(`/api/v1/projects/${CASE}/milestones/${done.body.id}`, 'ok');
    expect(again.status).toBe(200);
    expect(validCompletion(again.body), ajv.errorsText(validCompletion.errors)).toBe(true);
    expect(again.body).toMatchObject({ id: done.body.id, name: NAME, evidence_id: 31 });
    expect((await get(options(`?name=${NAME}`))).body).toMatchObject({ can_complete: false, hold: 'name_in_use' });
    expect((await post(pdfBody)).status).toBe(409);
  });

  it('a PDF records with upload_id and checked', async () => {
    const done = await post(pdfBody);
    expect(done.status).toBe(201);
    expect(validRecorded(done.body)).toBe(true);
  });

  it('a stale revision, a missing token, both evidence shapes and no authority are refused in the live error shape', async () => {
    for (const [r, status] of [
      [await post({ ...proofBody, revision: 4 }), 409],
      [await post(proofBody, 'ok', 'pmo_lead', false), 403],
      [await post({ ...proofBody, upload_id: 88, checked: true }), 422],
      [await post({ revision: 5, name: '' , evidence_id: 31 }), 422],
      [await post(proofBody, 'norole'), 403],
    ] as const) {
      expect(r.status).toBe(status);
      expect(validError(r.body)).toBe(true);
    }
  });

  it('conflict answers 409 once, then the new revision records', async () => {
    expect((await post(proofBody, 'conflict')).status).toBe(409);
    expect((await get(options(`?name=${NAME}`), 'conflict')).body.revision).toBe(6);
    expect((await post({ ...proofBody, revision: 6 }, 'conflict')).status).toBe(201);
  });

  it('uncertain answers 503 and records nothing; uncertain-saved answers 503 and records', async () => {
    expect((await post(proofBody, 'uncertain')).status).toBe(503);
    expect((await get(options(`?name=${NAME}`), 'uncertain')).body).toMatchObject({ can_complete: true, hold: null });
    expect((await post(proofBody, 'uncertain-saved')).status).toBe(503);
    expect((await get(options(`?name=${NAME}`), 'uncertain-saved')).body).toMatchObject({ hold: 'name_in_use' });
  });

  it('reread-fail answers the re-read 503 once, then the completion', async () => {
    const done = await post(proofBody, 'reread-fail');
    const path = `/api/v1/projects/${CASE}/milestones/${done.body.id}`;
    expect((await get(path, 'reread-fail')).status).toBe(503);
    expect((await get(path, 'reread-fail')).status).toBe(200);
  });
});
