import { readFileSync } from 'node:fs';
import type { Server } from 'node:http';
import type { AddressInfo } from 'node:net';
import { join } from 'node:path';

import Ajv2020 from 'ajv/dist/2020';
import addFormats from 'ajv-formats';
import { afterAll, beforeAll, beforeEach, describe, expect, it } from 'vitest';

// @ts-expect-error plain ESM module without type declarations
import { startMockServer } from '../mock/server.mjs';

// The document-review reads and the decision in the contract mock against the live contract (1.22.0): every fixture and
// every served body, for every scenario, validates; a field the live schema forbids fails.
type Responses = Record<string, { content: { 'application/json': { schema: object } } }>;
type Operation = { responses: Responses; requestBody?: { content: { 'application/json': { schema: object } } } };
const contract = JSON.parse(readFileSync(join(__dirname, '../../contracts/psl-factory.openapi.json'), 'utf8')) as {
  paths: Record<string, Record<string, Operation>>;
  components: { schemas: { Error: object } };
};
const ajv = new Ajv2020({ allErrors: true, strict: true });
addFormats(ajv);
const PATH = '/api/v1/projects/{case_id}/document-reviews/{version_id}';
const validPreview = ajv.compile(contract.paths[PATH].get.responses['200'].content['application/json'].schema);
const validPublication = ajv.compile(contract.paths[`${PATH}/publication`].get.responses['200'].content['application/json'].schema);
const validResult = ajv.compile(contract.paths[PATH].post.responses['200'].content['application/json'].schema);
const validRequest = ajv.compile(contract.paths[PATH].post.requestBody!.content['application/json'].schema);
const validError = ajv.compile(contract.components.schemas.Error);

const fixtures = join(__dirname, '../mock/fixtures/documents');
const readJson = (name: string) => JSON.parse(readFileSync(join(fixtures, name), 'utf8'));
const CASE = '00000000-0000-4000-8000-000000000101';

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

const cookie = (persona: string, scenario?: string) => `psl_mock_persona=${persona}${scenario ? `; psl_mock_docreview=${scenario}` : ''}`;
const get = async (path: string, persona = 'pm', scenario?: string) => {
  const response = await fetch(base + path, { headers: { Cookie: cookie(persona, scenario) } });
  return { status: response.status, body: await response.json() };
};
const token = async (persona = 'pm') => (await (await fetch(`${base}/api/v1/me`, { headers: { Cookie: cookie(persona) } })).json()).csrf_token as string;
const post = async (path: string, body: unknown, persona = 'pm', scenario?: string) => {
  const response = await fetch(base + path, { method: 'POST', headers: { Cookie: cookie(persona, scenario), 'Content-Type': 'application/json', 'X-CSRFToken': await token(persona) }, body: JSON.stringify(body) });
  return { status: response.status, body: await response.json() };
};
const review = (id: number | string) => `/api/v1/projects/${CASE}/document-reviews/${id}`;
const decision = (revision: number, verdict = 'return') => ({ expected_revision: revision, verdict, delegated: false, note: 'Figures match the costing.' });

describe('the fixtures are the live shape', () => {
  it('the preview and the publication fixtures validate', () => {
    expect(validPreview(readJson('review-2901.json')), ajv.errorsText(validPreview.errors)).toBe(true);
    expect(validPublication(readJson('review-2901.publication.json')), ajv.errorsText(validPublication.errors)).toBe(true);
  });

  it('a field the live schema forbids, or a missing one, fails the same check', () => {
    const doc = readJson('review-2901.json');
    expect(validPreview({ ...doc, status: 'Approved' })).toBe(false);
    expect(validPreview({ ...doc, version: '2' })).toBe(false);
    expect(validPreview({ ...doc, audience: undefined })).toBe(false);
    expect(validPreview({ ...doc, preview: [{ field: 'Scope', text: 'x', changed_since: true }] })).toBe(false);
    expect(validPublication({ ...readJson('review-2901.publication.json'), extra: 1 })).toBe(false);
  });
});

describe('every served body validates', () => {
  it.each(['decidable', 'return-only', 'with-reject', 'blocked', 'returned', 'empty-sections', 'hostile', 'no-publication'])('%s', async (scenario) => {
    const doc = await get(review(2901), 'pm', scenario);
    expect(doc.status).toBe(200);
    expect(validPreview(doc.body), ajv.errorsText(validPreview.errors)).toBe(true);
    const pub = await get(`${review(2901)}/publication`, 'pm', scenario);
    if (scenario === 'no-publication') {
      expect(pub.status).toBe(500);
      expect(validError(pub.body)).toBe(true);
    } else {
      expect(pub.status).toBe(200);
      expect(validPublication(pub.body), ajv.errorsText(validPublication.errors)).toBe(true);
    }
  });

  it('the older version is not current and offers no decision', async () => {
    const { body } = await get(review(2900));
    expect(validPreview(body)).toBe(true);
    expect(body).toMatchObject({ version: 1, current: false, decisions: [] });
  });

  it('the scenarios shape decisions, findings and status', async () => {
    expect((await get(review(2901), 'pm', 'return-only')).body.decisions).toEqual(['return']);
    expect((await get(review(2901), 'pm', 'blocked')).body.decisions).toEqual([]);
    expect((await get(`${review(2901)}/publication`, 'pm', 'blocked')).body.findings).toEqual(['Section Fees is empty.']);
    expect((await get(`${review(2901)}/publication`, 'pm', 'returned')).body.review_status).toBe('Returned to PM');
  });
});

describe('access', () => {
  it('a missing version, another project and a persona who cannot see the project answer the same 404', async () => {
    for (const path of [review(2999), review('abc'), `/api/v1/projects/${CASE.replace('101', '102')}/document-reviews/2901`, `/api/v1/projects/00000000-0000-4000-8000-000000000099/document-reviews/2901`]) {
      const { status, body } = await get(path);
      expect(status, path).toBe(404);
      expect(validError(body), path).toBe(true);
    }
    expect((await get(review(2901), 'none')).status).toBe(404);
  });
});

describe('the decision', () => {
  it('records once, answers the live result and the next read shows it', async () => {
    const before = (await get(review(2901))).body;
    const request = decision(before.revision, 'approve');
    expect(validRequest(request)).toBe(true);
    const done = await post(review(2901), request);
    expect(done.status).toBe(200);
    expect(validResult(done.body), ajv.errorsText(validResult.errors)).toBe(true);
    const after = await get(review(2901));
    expect(validPreview(after.body)).toBe(true);
    expect(after.body.decisions).toEqual([]);
    expect(after.body.revision).toBeGreaterThan(before.revision);
    const pub = await get(`${review(2901)}/publication`);
    expect(validPublication(pub.body)).toBe(true);
    expect(pub.body.review_status).toBe('Approved');
    expect((await post(review(2901), request)).status).toBe(409);
  });

  it('a wrong revision is 409, a blank or long note is 422 on the note, a body with an extra key is 422', async () => {
    const stale = await post(review(2901), decision(1));
    expect(stale.status).toBe(409);
    expect(validError(stale.body)).toBe(true);
    for (const note of ['', '   ', 'x'.repeat(4001)]) {
      const r = await post(review(2901), { ...decision(7), note });
      expect(r.status).toBe(422);
      expect(validError(r.body)).toBe(true);
      expect(r.body.fields[0].name).toBe('note');
    }
    expect((await post(review(2901), { ...decision(7), extra: true })).status).toBe(422);
    expect((await post(review(2901), { ...decision(7), delegated: undefined })).status).toBe(422);
  });

  it('a write without the token is the csrf 403', async () => {
    const response = await fetch(base + review(2901), { method: 'POST', headers: { Cookie: cookie('pm'), 'Content-Type': 'application/json' }, body: JSON.stringify(decision(7)) });
    expect(response.status).toBe(403);
    expect(validError(await response.json())).toBe(true);
  });

  it.each([
    ['stale', 409, 'stale_revision'],
    ['unavailable', 422, 'action_unavailable'],
    ['note-refused', 422, 'invalid'],
    ['forbidden', 403, 'forbidden'],
    ['server-error', 500, 'server_error'],
  ])('scenario %s answers %i with a contract error body', async (scenario, status, code) => {
    const r = await post(review(2901), decision(7), 'pm', scenario);
    expect(r.status).toBe(status);
    expect(r.body.code).toBe(code);
    expect(validError(r.body)).toBe(true);
  });

  it('stale moves the revision on once; unavailable makes the next read blocked', async () => {
    await post(review(2901), decision(7), 'pm', 'stale');
    expect((await get(review(2901), 'pm', 'stale')).body.revision).toBe(8);
    expect((await post(review(2901), decision(8), 'pm', 'stale')).status).toBe(200);
    await fetch(`${base}/__mock/reset`, { method: 'POST' });
    await post(review(2901), decision(7), 'pm', 'unavailable');
    expect((await get(review(2901))).body.decisions).toEqual([]);
    expect((await get(`${review(2901)}/publication`)).body.findings).toEqual(['Section Fees is empty.']);
  });
});
