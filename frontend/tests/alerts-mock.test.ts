import { readFileSync } from 'node:fs';
import type { Server } from 'node:http';
import type { AddressInfo } from 'node:net';
import { join } from 'node:path';

import Ajv2020 from 'ajv/dist/2020';
import addFormats from 'ajv-formats';
import { afterAll, beforeAll, beforeEach, describe, expect, it } from 'vitest';

// @ts-expect-error plain ESM module without type declarations
import { PERSONAS, startMockServer } from '../mock/server.mjs';

// The alerts mock against the live contract (1.24.0): every served body validates, for every persona and scenario.
type Op = { requestBody?: { content: { 'application/json': { schema: object } } }; responses: Record<string, { content: { 'application/json': { schema: object } } }> };
const contract = JSON.parse(readFileSync(join(__dirname, '../../contracts/psl-factory.openapi.json'), 'utf8')) as { paths: Record<string, Record<string, Op>> };
const ajv = new Ajv2020({ allErrors: true, strict: true });
addFormats(ajv);
const ok = (path: string, method: string) => ajv.compile(contract.paths[path][method].responses['200'].content['application/json'].schema);
const validList = ok('/api/v1/notifications', 'get');
const validRead = ok('/api/v1/notifications/{notification_id}/read', 'post');
const validPrefs = ok('/api/v1/me/alert-preferences', 'get');
const validSaved = ok('/api/v1/me/alert-preferences', 'post');
const validSave = ajv.compile(contract.paths['/api/v1/me/alert-preferences'].post.requestBody!.content['application/json'].schema);

type Item = { id: string; read: boolean; group: string; at: string | null; agent: string | null; api_url: string | null };
type List = { items: Item[]; as_of: string; page: number; next_page: number | null; unread: number; daily_summary: Record<string, unknown> };

let server: Server;
let origin: string;
beforeAll(async () => {
  server = await startMockServer({ port: 0 });
  origin = `http://127.0.0.1:${(server.address() as AddressInfo).port}`;
});
afterAll(() => new Promise<void>((resolve) => server.close(() => resolve())));
beforeEach(async () => {
  await fetch(`${origin}/__mock/reset`, { method: 'POST' });
});

type Init = { persona?: string; scenario?: string; method?: string; body?: unknown; csrf?: string | null };
async function api(path: string, init: Init = {}) {
  const persona = init.persona ?? 'finance_lead';
  const headers: Record<string, string> = { Cookie: `psl_mock_persona=${persona}${init.scenario ? `; psl_mock_alerts=${init.scenario}` : ''}` };
  const method = init.method ?? 'GET';
  if (method !== 'GET' && init.csrf !== null) headers['X-CSRFToken'] = init.csrf ?? `mock-csrf-${persona}`;
  if (init.body !== undefined) headers['Content-Type'] = 'application/json';
  const res = await fetch(origin + path, { method, headers, body: init.body === undefined ? undefined : JSON.stringify(init.body) });
  // eslint-disable-next-line @typescript-eslint/no-explicit-any -- the served bodies are checked against the contract schemas below
  return { status: res.status, body: (await res.json()) as any };
}
const list = (init: Init = {}, page = '') => api(`/api/v1/notifications${page}`, init);
const save = (body: unknown, init: Init = {}) => api('/api/v1/me/alert-preferences', { ...init, method: 'POST', body });
const read = (id: string, init: Init = {}) => api(`/api/v1/notifications/${encodeURIComponent(id)}/read`, { ...init, method: 'POST', body: {} });

describe('GET /notifications', () => {
  it('validates for every persona and scenario, with a count that matches the items', async () => {
    for (const persona of PERSONAS as string[]) {
      for (const scenario of [undefined, 'empty', 'many']) {
        const res = await list({ persona, scenario });
        expect(res.status).toBe(200);
        const valid = validList(res.body);
        expect(valid, `${persona}/${scenario}: ${ajv.errorsText(validList.errors)}`).toBe(true);
        const body = res.body as List;
        if (body.next_page === null) expect(body.unread).toBe(body.items.filter((item) => !item.read).length);
      }
    }
  });

  it('the board has needs-you and information, with and without agent, time and link', async () => {
    const { items, daily_summary } = (await list()).body as List;
    expect(new Set(items.map((i) => i.group))).toEqual(new Set(['action', 'update']));
    expect(items.some((i) => i.agent === null && i.at === null && i.api_url === null)).toBe(true);
    expect(items.some((i) => i.agent && i.at && i.api_url)).toBe(true);
    expect(daily_summary).toMatchObject({ scope: 'current_inbox', actions_open: items.filter((i) => i.group === 'action' && !i.read).length });
  });

  it('pages 25 at a time: three pages for 60, next_page null on the last, unread for all pages', async () => {
    const pages = [await list({ scenario: 'many' }), await list({ scenario: 'many' }, '?page=2'), await list({ scenario: 'many' }, '?page=3')];
    expect(pages.map((p) => [p.body.page, p.body.items.length, p.body.next_page])).toEqual([[1, 25, 2], [2, 25, 3], [3, 10, null]]);
    expect(new Set(pages.flatMap((p) => p.body.items.map((i: Item) => i.id))).size).toBe(60);
    expect(pages.map((p) => p.body.unread)).toEqual([40, 40, 40]);
  });

  it('refuses page 0, a non-number and 10001 with 422; a page past the last is an empty 200; unknown parameters are ignored', async () => {
    for (const bad of ['?page=abc', '?page=0', '?page=10001']) expect((await list({}, bad)).status, bad).toBe(422);
    const past = await list({}, '?page=9');
    expect([past.status, past.body.items, past.body.next_page]).toEqual([200, [], null]);
    expect(validList(past.body), ajv.errorsText(validList.errors)).toBe(true);
    expect((await list({}, '?q=lagoon&agent=tola&unread=true')).body.items.length).toBe(6);
  });

  it('a scenario status answers every alert path', async () => {
    const res = await fetch(`${origin}/api/v1/notifications`, { headers: { Cookie: 'psl_mock_persona=finance_lead; psl_mock_scenario=401' } });
    expect(res.status).toBe(401);
  });
});

describe('POST /notifications/{id}/read', () => {
  it('marks one read, answers {id, read} and lowers the unread total by one', async () => {
    const before = (await list()).body as List;
    const target = before.items.find((i) => !i.read)!;
    const res = await read(target.id);
    expect(res.status).toBe(200);
    expect(validRead(res.body), ajv.errorsText(validRead.errors)).toBe(true);
    expect(res.body).toEqual({ id: target.id, read: true });
    expect(((await list()).body as List).unread).toBe(before.unread - 1);
    expect((await read(target.id)).status).toBe(200);
  });

  it('refuses a request without the CSRF token, an unknown id, a body that is not {}, and keeps personas apart', async () => {
    const target = ((await list()).body as List).items[0];
    expect((await read(target.id, { csrf: null })).status).toBe(403);
    expect((await read('nope')).status).toBe(404);
    expect((await api(`/api/v1/notifications/${target.id}/read`, { method: 'POST', body: { x: 1 } })).status).toBe(422);
    expect((await read(target.id, { persona: 'pm' })).status).toBe(404);
  });

  it('readfail answers 500 and gone answers 404 and nothing changes', async () => {
    const target = ((await list({ scenario: 'readfail' })).body as List).items[0];
    expect((await read(target.id, { scenario: 'readfail' })).status).toBe(500);
    expect((await read(target.id, { scenario: 'gone' })).status).toBe(404);
    expect(((await list({ scenario: 'readfail' })).body as List).items[0].read).toBe(false);
  });
});

describe('alert preferences', () => {
  it('reads and saves in the live shapes; the save answers without receipts and bumps the revision', async () => {
    const held = await api('/api/v1/me/alert-preferences');
    expect(validPrefs(held.body), ajv.errorsText(validPrefs.errors)).toBe(true);
    expect(held.body.recent_deliveries.map((d: { state: string }) => d.state)).toEqual(['delivered', 'uncertain', 'queued', 'held']);
    const body = { revision: held.body.revision, email_requested: false, whatsapp_requested: true };
    expect(validSave(body)).toBe(true);
    const saved = await save(body);
    expect(saved.status).toBe(200);
    expect(validSaved(saved.body), ajv.errorsText(validSaved.errors)).toBe(true);
    expect(saved.body).toMatchObject({ revision: held.body.revision + 1, email_requested: false, whatsapp_requested: true });
    expect(saved.body.recent_deliveries).toBeUndefined();
    expect((await save(body)).status).toBe(409);
  });

  it('refuses extra or missing fields with 422, a missing token with 403', async () => {
    expect((await save({ revision: 3, email_requested: true })).status).toBe(422);
    expect((await save({ revision: 3, email_requested: true, whatsapp_requested: true, channel: 'both' })).status).toBe(422);
    expect((await save({ revision: 3, email_requested: 'yes', whatsapp_requested: true })).status).toBe(422);
    expect((await save({ revision: 3, email_requested: true, whatsapp_requested: true }, { csrf: null })).status).toBe(403);
  });

  it('scenario stale answers the first save with 409 after another person saved; invalid answers 422', async () => {
    const body = { revision: 3, email_requested: true, whatsapp_requested: true };
    expect((await save(body, { scenario: 'stale' })).status).toBe(409);
    const held = (await api('/api/v1/me/alert-preferences', { scenario: 'stale' })).body;
    expect([held.revision, held.email_requested]).toEqual([4, false]);
    expect((await save({ ...body, revision: 4 }, { scenario: 'stale' })).status).toBe(200);
    expect((await save(body, { scenario: 'invalid' })).status).toBe(422);
  });
});
