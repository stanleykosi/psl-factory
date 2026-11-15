// The templates mock (frontend/mock/templates.mjs): scenarios, the upload checks in order, in-memory versions and
// reset, the cursor, and replies and fixtures validated against the generated contract (openapi.json).
import { readdirSync, readFileSync } from 'node:fs';
import type { Server } from 'node:http';
import type { AddressInfo } from 'node:net';
import { join } from 'node:path';

import Ajv2020 from 'ajv/dist/2020';
import addFormats from 'ajv-formats';
import { afterAll, beforeAll, beforeEach, describe, expect, it } from 'vitest';

// @ts-expect-error plain ESM module without type declarations
import { M1_OPERATIONS, OPENAPI_PATH, startMockServer } from '../mock/server.mjs';

type Row = { template_id?: string; name: string; version: string; versions?: number; revision?: number; test_template: boolean; can_upload?: boolean; updated_by?: string; updated_at?: string };
type Page = { items: Row[]; next_cursor?: string; as_of: string };
type Op = { responses: Record<string, { content: { 'application/json': { schema: object } } }> };

const openapi = JSON.parse(readFileSync(OPENAPI_PATH, 'utf8')) as { paths: Record<string, { get?: Op; post?: Op }> };
const ajv = new Ajv2020({ allErrors: true, strict: true });
addFormats(ajv);
const reply = (op: Op, status: number) => ajv.compile(op.responses[String(status)].content['application/json'].schema);
const validList = (status: number) => reply(openapi.paths['/api/v1/setup/templates'].get!, status);
const validUpload = (status: number) => reply(openapi.paths['/api/v1/setup/templates/{template_id}/versions'].post!, status);

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

const cookie = (persona = 'admin', extra = '') => `psl_mock_persona=${persona}${extra ? `; ${extra}` : ''}`;
async function list(query = '', persona = 'admin', extra = '') {
  const res = await fetch(`${base}/api/v1/setup/templates${query}`, { headers: { Cookie: cookie(persona, extra) } });
  return { status: res.status, body: (await res.json()) as Page };
}
const GOOD = { expected_revision: 1, filename: 'invoice.pdf', content_base64: 'JVBERi0xLjQK' };
async function post(id: string, body: unknown, opts: { persona?: string; extra?: string; csrf?: string | null; raw?: string } = {}) {
  const persona = opts.persona ?? 'admin';
  const headers: Record<string, string> = { Cookie: cookie(persona, opts.extra), 'Content-Type': 'application/json' };
  if (opts.csrf !== null) headers['X-CSRFToken'] = opts.csrf ?? `mock-csrf-${persona}`;
  const res = await fetch(`${base}/api/v1/setup/templates/${encodeURIComponent(id)}/versions`, { method: 'POST', headers, body: opts.raw ?? JSON.stringify(body) });
  return { status: res.status, body: (await res.json()) as Record<string, unknown> };
}
const row = (page: Page, id: string) => page.items.find((r) => r.template_id === id)!;

describe('E-TEMPLATES scenarios', () => {
  it('is part of the mock and its fixtures validate against the generated schema with nothing stripped', () => {
    expect(M1_OPERATIONS).toEqual(expect.arrayContaining(['E-TEMPLATES', 'E-TEMPLATE-VERSION']));
    const validate = validList(200);
    const dir = join(__dirname, '../mock/fixtures/templates');
    const files = readdirSync(dir);
    expect(files.sort()).toEqual(['desktop.json', 'empty.json', 'many.json', 'mobile.json', 'readonly.json']);
    for (const file of files) {
      const page = JSON.parse(readFileSync(join(dir, file), 'utf8'));
      expect(validate(page), `${file}: ${ajv.errorsText(validate.errors)}`).toBe(true);
    }
  });

  it('serves the eight desktop templates in order, all test templates, and the same data to admin and finance_lead', async () => {
    const { status, body } = await list();
    expect(status).toBe(200);
    expect(validList(200)(body)).toBe(true);
    expect(body.items.map((r) => r.name)).toEqual(['Invoice', 'Statement of work', 'Weekly client report', 'Minutes', 'RFP response', 'Go-live document', 'Support handover', 'Closure report']);
    expect(body.items.every((r) => r.test_template === true && r.can_upload === true)).toBe(true);
    expect(body.items[0].revision).toBe(1);
    expect((await list('', 'finance_lead')).body).toEqual(body);
    expect((await list('', 'admin', 'psl_mock_templates=mobile')).body.items).toHaveLength(8);
  });

  it('pm and none get 403 on both calls, and the forbidden scenario 403s everyone', async () => {
    for (const persona of ['pm', 'none']) {
      expect((await list('', persona)).status).toBe(403);
      expect((await post('T-01', GOOD, { persona })).status).toBe(403);
    }
    expect((await list('', 'admin', 'psl_mock_templates=forbidden')).status).toBe(403);
    expect((await post('T-01', GOOD, { extra: 'psl_mock_templates=forbidden' })).status).toBe(403);
  });

  it('readonly has no upload right on any row and one row with no template_id; empty has no rows', async () => {
    const { items } = (await list('', 'admin', 'psl_mock_templates=readonly')).body;
    expect(items.every((r) => r.can_upload !== true)).toBe(true);
    expect(items.some((r) => r.template_id === undefined && r.can_upload === undefined)).toBe(true);
    expect((await list('', 'admin', 'psl_mock_templates=empty')).body).toEqual({ items: [], as_of: expect.any(String) });
  });

  it('many serves 60 rows over two pages by cursor', async () => {
    const extra = 'psl_mock_templates=many';
    const first = (await list('', 'admin', extra)).body;
    expect(first.items).toHaveLength(50);
    expect(first.next_cursor).toBeTruthy();
    const second = (await list(`?cursor=${encodeURIComponent(first.next_cursor!)}`, 'admin', extra)).body;
    expect(second.items).toHaveLength(10);
    expect(second.next_cursor).toBeUndefined();
    expect(second.items[0].template_id).toBe('T-51');
  });
});

describe('E-TEMPLATE-VERSION', () => {
  it('bumps version, versions and revision by one, names the persona, and the list shows it until reset', async () => {
    const before = row((await list()).body, 'T-01');
    const result = await post('T-01', GOOD);
    expect(result.status).toBe(200);
    expect(validUpload(200)(result.body)).toBe(true);
    expect(result.body).toEqual({ template_id: 'T-01', version: '2', test_template: true, revision: 2 });
    const after = row((await list()).body, 'T-01');
    expect(after).toMatchObject({ version: '2', versions: (before.versions ?? 0) + 1, revision: 2, updated_by: 'Ada Okafor', test_template: true });
    expect(after.updated_at).toBeTruthy();
    expect(validList(200)((await list()).body)).toBe(true);
    expect((await post('T-01', GOOD)).status).toBe(409);
    expect(row((await list('', 'ceo')).body, 'T-01').version).toBe('1');
    await fetch(`${base}/__mock/reset`, { method: 'POST' });
    expect(row((await list()).body, 'T-01')).toEqual(before);
    expect((await post('T-01', GOOD)).status).toBe(200);
  });

  it('never returns test_template false', async () => {
    const results = [(await list()).body, (await list('', 'admin', 'psl_mock_templates=many')).body, (await post('T-01', GOOD)).body];
    expect(JSON.stringify(results)).not.toContain('"test_template":false');
  });

  it('accepts a note up to 2000 characters and refuses 2001', async () => {
    expect((await post('T-03', { ...GOOD, note: 'é'.repeat(2000) })).status).toBe(200);
    const long = await post('T-05', { ...GOOD, note: 'x'.repeat(2001) });
    expect(long.status).toBe(422);
    expect(validUpload(422)(long.body)).toBe(true);
    expect(long.body.fields).toEqual([{ name: 'note', message: expect.any(String) }]);
  });

  it('422 names the field: empty filename, empty or non-base64 content, unknown key, bad JSON', async () => {
    const names = async (body: unknown, raw?: string) => {
      const r = await post('T-01', body, { raw });
      expect(r.status).toBe(422);
      expect(validUpload(422)(r.body)).toBe(true);
      return (r.body.fields as { name: string }[]).map((f) => f.name);
    };
    expect(await names({ ...GOOD, filename: '' })).toEqual(['filename']);
    expect(await names({ ...GOOD, filename: '   ' })).toEqual(['filename']);
    expect(await names({ ...GOOD, content_base64: '' })).toEqual(['content_base64']);
    expect(await names({ ...GOOD, content_base64: 'not base64!' })).toEqual(['content_base64']);
    expect(await names({ ...GOOD, content_base64: 'abc' })).toEqual(['content_base64']);
    expect(await names({ filename: 'a.pdf', content_base64: 'JVBERi0xLjQK' })).toEqual(['expected_revision']);
    expect(await names({ ...GOOD, extra: 1 })).toEqual(['extra']);
    expect(await names(null, '{not json')).toEqual(['body']);
  });

  it('checks in order: CSRF, persona 403, unknown template 404, schema 422, stale 409, no upload right 403', async () => {
    expect((await post('T-01', GOOD, { csrf: null })).status).toBe(403);
    expect((await post('T-01', GOOD, { csrf: 'wrong' })).status).toBe(403);
    expect((await post('T-99', { nonsense: true }, { persona: 'pm' })).status).toBe(403);
    const missing = await post('T-99', { nonsense: true });
    expect(missing.status).toBe(404);
    expect(validUpload(404)(missing.body)).toBe(true);
    expect((await post('T-01', { ...GOOD, filename: '', expected_revision: 9 })).status).toBe(422);
    const stale = await post('T-01', { ...GOOD, expected_revision: 9 });
    expect(stale.status).toBe(409);
    expect(validUpload(409)(stale.body)).toBe(true);
    const readonly = 'psl_mock_templates=readonly';
    expect((await post('T-01', { ...GOOD, expected_revision: 9 }, { extra: readonly })).status).toBe(409);
    const denied = await post('T-01', GOOD, { extra: readonly });
    expect(denied.status).toBe(403);
    expect(validUpload(403)(denied.body)).toBe(true);
    expect((await post('T-08', GOOD, { extra: readonly })).status).toBe(404);
  });

  it('stale cookie: another person uploads first, then 409 with the template message', async () => {
    const extra = 'psl_mock_templates_save=stale';
    const result = await post('T-01', GOOD, { extra });
    expect(result).toEqual({ status: 409, body: { code: 'stale_revision', message: 'This template changed. Reload to see the newer version.' } });
    expect(row((await list()).body, 'T-01')).toMatchObject({ version: '2', revision: 2 });
  });

  it('invalid cookie: 422 naming filename and note', async () => {
    const result = await post('T-01', GOOD, { extra: 'psl_mock_templates_save=invalid' });
    expect(result.status).toBe(422);
    expect(validUpload(422)(result.body)).toBe(true);
    expect((result.body.fields as { name: string }[]).map((f) => f.name)).toEqual(['filename', 'note']);
    expect(row((await list()).body, 'T-01').version).toBe('1');
  });
});
