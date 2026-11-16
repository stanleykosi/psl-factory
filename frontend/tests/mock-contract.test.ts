import { spawnSync } from 'node:child_process';
import { readdirSync, readFileSync } from 'node:fs';
import type { Server } from 'node:http';
import type { AddressInfo } from 'node:net';
import { join } from 'node:path';

import Ajv2020 from 'ajv/dist/2020';
import addFormats from 'ajv-formats';
import { afterAll, beforeAll, describe, expect, it } from 'vitest';

// @ts-expect-error plain ESM module without type declarations
import { M1_OPERATIONS, OPENAPI_PATH, PERSONAS, startMockServer } from '../mock/server.mjs';
// @ts-expect-error plain ESM module without type declarations
import { START_OPERATIONS } from '../mock/start-work.mjs';
// @ts-expect-error plain ESM module without type declarations
import { contractEvidence } from '../mock/evidence.mjs';
// @ts-expect-error plain ESM module without type declarations
import { contractBody as exceptionsBody } from '../mock/exceptions.mjs';
// @ts-expect-error plain ESM module without type declarations
import { contractBody as monthEndBody } from '../mock/finance.mjs';
// @ts-expect-error plain ESM module without type declarations
import { contractRules } from '../mock/setup.mjs';

type Operation = { operationId: string; responses: Record<string, { content: { 'application/json': { schema: object } } }> };
const openapi = JSON.parse(readFileSync(OPENAPI_PATH, 'utf8')) as { paths: Record<string, Record<string, Operation>> };

const ajv = new Ajv2020({ allErrors: true, strict: true });
addFormats(ajv);

const operations = Object.entries(openapi.paths).flatMap(([path, ops]) =>
  Object.entries(ops)
    .filter(([, op]) => op && typeof op === 'object' && 'operationId' in op)
    .map(([method, op]) => ({ path, method: method.toUpperCase(), op })),
);
const byId = (id: string) => operations.find((o) => o.op.operationId === id)!;

const PATH_VALUES: Record<string, string> = { work_id: 'W-1001', task_id: 'T-2001', component: 'documents.client_reviewer', case_id: 'C-SETUP-1', client_id: 'CL-3501', template_id: 'T-01' };
const NOTIFICATION_IDS: Record<string, string> = { finance_lead: 'N-0001', pm: 'N-0101', ceo: 'N-0201', none: 'N-0201', admin: 'N-0201' };
const QUERY: Record<string, string> = { 'E-WORK-LIST': '?queue=needs_me', 'E-WORK-HISTORY': '?kind=all', 'E-MONTH-END': '?period=2026-10' };
const BODY: Record<string, unknown> = {
  'E-ALERT-PREFS': { channel: 'both', frequency: 'immediate' },
  'E-TASK-CLAIM': { expected_revision: 2 },
  'E-TASK-DECIDE': { expected_revision: 2, verdict: 'approve' },
  'E-SETUP-RULE-SAVE': { expected_revision: 2, value: { roles: ['pmo_lead'] } },
  'E-CLIENT-CONTACT': { expected_revision: 3, name: 'Ada Okoye', email: 'ada@example.org' },
  'E-EVIDENCE-UPLOAD': { kind: 'rule_proof', filename: 'minutes.pdf', content_base64: 'JVBERi0xLjQK', case_revision: 1 },
  'E-TEMPLATE-VERSION': { expected_revision: 1, filename: 'invoice.pdf', content_base64: 'JVBERi0xLjQK' },
};
// Operations a persona may not use answer the declared status instead of 200 (Setup is for Leads and Admin; E-EXCEPTIONS is Leads only; E-MONTH-END Finance only).
const PERSONA_STATUS: Record<string, Record<string, number>> = {
  'E-CLIENTS': { none: 403 },
  'E-CLIENT': { none: 403 },
  'E-CLIENT-CONTACT': { none: 403 },
  'E-EXCEPTIONS': { pm: 403 },
  'E-MONTH-END': { pm: 403, none: 403 },
  'E-SETUP-RULES': { pm: 403, none: 403 },
  'E-SETUP-RULE-SAVE': { pm: 403, none: 403 },
  'E-EVIDENCE-UPLOAD': { pm: 403, none: 403 },
  'E-TEMPLATES': { pm: 403, none: 403 },
  'E-TEMPLATE-VERSION': { pm: 403, none: 403 },
};
// Engineering-proposal fields the mock serves ahead of the contract are removed before the schema check (F-06, F-10, F-11).
const CONTRACT_BODY: Record<string, (body: unknown) => unknown> = {
  'E-EXCEPTIONS': exceptionsBody,
  'E-MONTH-END': monthEndBody,
  'E-SETUP-RULES': contractRules,
  'E-EVIDENCE-UPLOAD': contractEvidence,
};
const errorSchema = byId('E-ME').op.responses['401'].content['application/json'].schema;

let server: Server;
let base: string;

beforeAll(async () => {
  server = await startMockServer({ port: 0 });
  base = `http://127.0.0.1:${(server.address() as AddressInfo).port}`;
});
afterAll(() => new Promise<void>((resolve) => server.close(() => resolve())));

async function request(id: string, init: { persona?: string; scenario?: string; csrf?: string | null } = {}) {
  const { path, method } = byId(id);
  const persona = init.persona ?? 'finance_lead';
  const value = (name: string) => (name === 'notification_id' ? NOTIFICATION_IDS[persona] : PATH_VALUES[name]);
  const url = base + path.replace(/\{(\w+)\}/g, (_, name: string) => value(name) ?? 'X-1') + (QUERY[id] ?? '');
  const headers: Record<string, string> = { Cookie: `psl_mock_persona=${init.persona ?? 'finance_lead'}` };
  if (init.scenario) headers['X-Mock-Scenario'] = init.scenario;
  if (method !== 'GET' && init.csrf !== null) headers['X-CSRFToken'] = init.csrf ?? `mock-csrf-${init.persona ?? 'finance_lead'}`;
  let body: string | undefined;
  if (method !== 'GET') {
    headers['Content-Type'] = 'application/json';
    body = JSON.stringify(BODY[id] ?? {});
  }
  const response = await fetch(url, { method, headers, body });
  expect(response.headers.get('content-type')).toBe('application/json');
  return { status: response.status, body: (await response.json()) as Record<string, unknown> };
}

function expectValid(id: string, status: number, body: unknown) {
  const declared = byId(id).op.responses[String(status)];
  const schema = declared ? declared.content['application/json'].schema : errorSchema;
  const validate = ajv.compile(schema);
  const valid = validate(status === 200 ? (CONTRACT_BODY[id]?.(body) ?? body) : body);
  expect(valid, `${id} ${status}: ${ajv.errorsText(validate.errors)}`).toBe(true);
}

describe('mock server matches openapi.json', () => {
  for (const id of M1_OPERATIONS as string[]) {
    // Start work answers per persona and per body; tests/start-work-mock.test.ts covers it.
    for (const persona of (START_OPERATIONS as string[]).includes(id) ? [] : (PERSONAS as string[])) {
      const expected = PERSONA_STATUS[id]?.[persona] ?? 200;
      it(`${id} answers ${expected} for persona ${persona} with a schema-valid body`, async () => {
        const { status, body } = await request(id, { persona });
        expect(status).toBe(expected);
        expectValid(id, expected, body);
      });
    }

    const errorStatuses = Object.keys(byId(id).op.responses).filter((s) => Number(s) >= 400);
    for (const status of errorStatuses) {
      it(`${id} returns declared ${status} via X-Mock-Scenario`, async () => {
        const result = await request(id, { scenario: status });
        expect(result.status).toBe(Number(status));
        expectValid(id, result.status, result.body);
      });
    }
  }

  it('ignores a scenario the operation does not declare', async () => {
    const result = await request('E-ME', { scenario: '409' });
    expect(result.status).toBe(200);
  });

  it('a malformed cookie value falls back to the default persona and the mock keeps serving', async () => {
    const malformed = await fetch(`${base}/api/v1/me`, { headers: { Cookie: 'psl_mock_persona=%' } });
    expect(malformed.status).toBe(200);
    expect(((await malformed.json()) as { name: string }).name).toBe('Ada Okafor');
    expect((await request('E-ME', { persona: 'pm' })).body.name).toBe('Tunde Bello');
  });

  it('E-ME carries each persona fixture', async () => {
    const names = await Promise.all((PERSONAS as string[]).map(async (persona) => (await request('E-ME', { persona })).body));
    expect(names.map((me) => [me.name, me.destinations, me.csrf_token])).toEqual([
      ['Ada Okafor', ['my_work', 'projects', 'overview', 'assistant', 'setup'], 'mock-csrf-finance_lead'],
      ['Tunde Bello', ['my_work', 'projects', 'assistant'], 'mock-csrf-pm'],
      ['Folake Bello', ['my_work', 'projects', 'overview', 'assistant'], 'mock-csrf-ceo'],
      ['Sample Person', [], 'mock-csrf-none'],
      ['Ada Okafor', ['my_work', 'projects', 'overview', 'assistant', 'setup'], 'mock-csrf-admin'],
    ]);
  });

  it('every E-WORK-LIST item and the E-WORK-ITEM record are marked sample', async () => {
    const list = await request('E-WORK-LIST');
    const items = list.body.items as { sample: boolean }[];
    expect(items.length).toBeGreaterThan(0);
    expect(items.every((item) => item.sample === true)).toBe(true);
    expect((await request('E-WORK-ITEM')).body.sample).toBe(true);
  });

  it('a write without X-CSRFToken gets 403 csrf_failed', async () => {
    const result = await request('E-TASK-CLAIM', { csrf: null });
    expect(result).toEqual({ status: 403, body: { code: 'csrf_failed', message: 'Your session check failed. Reload and try again.' } });
    expectValid('E-TASK-CLAIM', 403, result.body);
  });

  it("a write with another persona's token gets 403 csrf_failed", async () => {
    const result = await request('E-TASK-DECIDE', { persona: 'pm', csrf: 'mock-csrf-finance_lead' });
    expect(result.status).toBe(403);
    expect(result.body.code).toBe('csrf_failed');
    expectValid('E-TASK-DECIDE', 403, result.body);
  });

  it('a non-M-1 operation gets 501 not_mocked', async () => {
    const result = await request('E-CONVERSATIONS');
    expect(result).toEqual({ status: 501, body: { code: 'not_mocked', message: 'Not available in the mock yet.' } });
    expectValid('E-CONVERSATIONS', 501, result.body);
  });

  it('refuses to start with NODE_ENV=production', () => {
    const run = spawnSync(process.execPath, [join(__dirname, '../mock/server.mjs')], {
      env: { ...process.env, NODE_ENV: 'production', MOCK_PORT: '0' },
      encoding: 'utf8',
      timeout: 10000,
    });
    expect(run.status).toBe(1);
    expect(run.stderr).toContain('refuses to start');
  });
});

describe('mock work items: per-id fixtures, fallback and history parameters', () => {
  const workDir = join(__dirname, '../mock/fixtures/work');
  const get = async (path: string) => {
    const response = await fetch(base + path, { headers: { Cookie: 'psl_mock_persona=finance_lead' } });
    const text = await response.text();
    return { status: response.status, text, body: JSON.parse(text) as Record<string, unknown> };
  };
  const readJson = (path: string) => JSON.parse(readFileSync(path, 'utf8')) as Record<string, unknown>;
  type Row = { _kind?: string; at: string };
  const w1004 = readJson(join(workDir, 'W-1004.history.json')) as { items: Row[] };

  it('serves the per-id item and 404 for the reserved no-access id', async () => {
    const w1003 = await get('/api/v1/work/W-1003');
    expect(w1003.status).toBe(200);
    expect(w1003.body).toEqual(readJson(join(workDir, 'W-1003.json')));
    expectValid('E-WORK-ITEM', 200, w1003.body);
    for (const path of ['/api/v1/work/W-1099', '/api/v1/work/W-1099/history?kind=all']) {
      const denied = await get(path);
      expect(denied).toMatchObject({ status: 404, body: { code: 'not_found', message: 'We could not find that record.' } });
    }
  });

  it('falls back to the unchanged default fixtures for other ids', async () => {
    const other = await get('/api/v1/work/ANY-OTHER');
    expect(other.status).toBe(200);
    expect(other.body).toEqual(readJson(join(__dirname, '../mock/fixtures/E-WORK-ITEM.json')));
    const otherHistory = await get('/api/v1/work/ANY-OTHER/history?kind=all');
    expect(otherHistory.body).toEqual(readJson(join(__dirname, '../mock/fixtures/E-WORK-HISTORY.json')));
  });

  it('never serves a sidecar file such as W-1004.history as an item', async () => {
    const sidecar = await get('/api/v1/work/W-1004.history');
    expect(sidecar.status).toBe(200);
    expect(sidecar.body).toEqual(readJson(join(__dirname, '../mock/fixtures/E-WORK-ITEM.json')));
  });

  it('filters by kind, pages by limit and cursor, and treats other limits as 20', async () => {
    const decisions = await get('/api/v1/work/W-1004/history?kind=decisions');
    const expected = w1004.items.filter((row) => row._kind === 'decision').map((row) => row.at);
    expect((decisions.body.items as Row[]).map((row) => row.at)).toEqual(expected);
    expect(expected.length).toBeGreaterThan(0);
    expectValid('E-WORK-HISTORY', 200, decisions.body);

    const first = await get('/api/v1/work/W-1004/history?kind=all&limit=10');
    expect((first.body.items as Row[]).map((row) => row.at)).toEqual(w1004.items.slice(0, 10).map((row) => row.at));
    expect(typeof first.body.next_cursor).toBe('string');
    const rest = await get(`/api/v1/work/W-1004/history?kind=all&limit=10&cursor=${encodeURIComponent(first.body.next_cursor as string)}`);
    expect((rest.body.items as Row[]).map((row) => row.at)).toEqual(w1004.items.slice(10).map((row) => row.at));
    expect(rest.body).not.toHaveProperty('next_cursor');

    const odd = await get('/api/v1/work/W-1004/history?limit=7');
    expect((odd.body.items as Row[]).length).toBe(12);
    expect(odd.body).not.toHaveProperty('next_cursor');
    const badCursor = await get('/api/v1/work/W-1004/history?limit=10&cursor=nonsense');
    expect((badCursor.body.items as Row[])[0].at).toBe(w1004.items[0].at);
  });

  it('never sends the mock-only _kind', async () => {
    for (const kind of ['all', 'decisions', 'agent_work', 'evidence']) {
      for (const id of ['W-1001', 'W-1004', 'ANY-OTHER']) {
        const { text, body } = await get(`/api/v1/work/${id}/history?kind=${kind}&limit=50`);
        expect(text).not.toContain('"_kind"');
        expectValid('E-WORK-HISTORY', 200, body);
      }
    }
  });

  it('scenarios still win over the per-id fixtures', async () => {
    const response = await fetch(`${base}/api/v1/work/W-1003`, { headers: { 'X-Mock-Scenario': '403' } });
    expect(response.status).toBe(403);
  });

  // PROPOSAL (D-WORKITEM-VIEW): the board fixtures' `presentation` block and history `lines`, as typed in
  // src/features/work-item/presentation.ts. Checked here on their own, then stripped for the contract check.
  const str = { type: 'string', minLength: 1 };
  const strs = { type: 'array', items: str };
  const link = { type: 'object', additionalProperties: false, required: ['label', 'href'], properties: { label: str, href: str, primary: { type: 'boolean' } } };
  const factNames = ['drafted', 'reviewed', 'approved', 'sent', 'receipt_recorded', 'verified'];
  // the fields the phone block may replace are the same shapes as the desktop ones
  const shared = {
      facts: { type: 'object', additionalProperties: false, properties: Object.fromEntries(factNames.map((n) => [n, str])) },
      fact_tones: { type: 'object', additionalProperties: false, properties: Object.fromEntries(factNames.map((n) => [n, { enum: ['waiting', 'signal'] }])) },
      stations: { type: 'array', items: { anyOf: [str, { type: 'null' }] } },
      stations_shown: { type: 'integer', minimum: 0 },
      agent: { type: 'object', additionalProperties: false, properties: { role: str, summary: str, headline: str, limits: str, plain: { type: 'boolean' }, message: strs } },
      panel: {
        type: 'object',
        additionalProperties: false,
        required: ['title', 'body'],
        properties: {
          title: str,
          tone: { enum: ['dark', 'signal', 'waiting', 'verified'] },
          lead: str,
          body: strs,
          quote: str,
          rows: { type: 'array', items: { type: 'object', additionalProperties: false, required: ['label', 'value'], properties: { label: str, value: str } } },
          note: str,
          large_title: { type: 'boolean' },
          note_first: { type: 'boolean' },
          bar_slot: { type: 'boolean' },
          bar_note: str,
          links: { type: 'array', items: link },
          summary: { type: 'object', additionalProperties: false, required: ['text'], properties: { text: str, kind: { enum: ['info', 'warning', 'problem'] } } },
        },
      },
      preview: {
        type: 'object',
        additionalProperties: false,
        required: ['template_label', 'brand', 'bill_to', 'number', 'issue_note', 'lines', 'tax', 'footer', 'version', 'basis'],
        properties: {
          template_label: str,
          brand: str,
          bill_to: { type: 'object', additionalProperties: false, required: ['name', 'email'], properties: { name: str, email: str } },
          number: str,
          issue_note: str,
          lines: { type: 'array', minItems: 1, items: { type: 'object', additionalProperties: false, required: ['description', 'amount'], properties: { description: str, detail: str, amount: str } } },
          tax: str,
          footer: str,
          version: str,
          basis: str,
        },
      },
  };
  const presentationSchema = {
    type: 'object',
    additionalProperties: false,
    properties: {
      back_label: str,
      eyebrow: str,
      ...shared,
      phone: { type: 'object', additionalProperties: false, properties: { title: str, ...shared } },
      task_note: str,
      history_counts: {
        type: 'object',
        additionalProperties: false,
        required: ['all', 'decisions', 'agent_work', 'evidence'],
        properties: Object.fromEntries(['all', 'decisions', 'agent_work', 'evidence'].map((k) => [k, { type: 'integer', minimum: 0 }])),
      },
    },
  };
  const validPresentation = ajv.compile(presentationSchema);
  const boardFixture = (name: string) => /^W-17\d\d(\.history)?\.json$/.test(name);

  // PROPOSAL (F-16 board data): the decision board fixtures' `decide_presentation` block, as typed in
  // src/features/decide/presentation.ts; W-19xx also carry F-14's `presentation.facts` for the facts' details.
  const decideBoardFixture = (name: string) => /^W-19\d\d(\.[a-z]+)?\.json$/.test(name);
  const decidePresentationSchema = {
    type: 'object',
    additionalProperties: false,
    properties: {
      queue: {
        type: 'object',
        additionalProperties: false,
        required: ['position', 'total'],
        properties: {
          position: { type: 'integer', minimum: 1 },
          total: { type: 'integer', minimum: 1 },
          next: { type: 'object', additionalProperties: false, required: ['label', 'href'], properties: { label: str, href: { type: 'string', pattern: '^/(?!/)' } } },
        },
      },
      subject: str,
      client: str,
      waiting: str,
      agent: {
        type: 'object',
        additionalProperties: false,
        properties: { role: str, summary: str, phone_summary: str, link_label: str, note: str, phone_note: str },
      },
      comment: { type: 'object', additionalProperties: false, required: ['label', 'action'], properties: { label: str, action: str } },
    },
  };
  const validDecidePresentation = ajv.compile(decidePresentationSchema);

  it('every fixture in fixtures/work is schema-valid with _kind, presentation and lines removed', () => {
    // Item bodies are W-<digits>.json and histories W-<digits>.history.json; other sidecars (F-04's) are not checked here.
    const files = readdirSync(workDir).filter((name) => /^W-\d+(\.history)?\.json$/.test(name));
    expect(files.length).toBeGreaterThanOrEqual(7);
    for (const name of files) {
      const body = readJson(join(workDir, name));
      if (name.endsWith('.history.json')) {
        const items = (body.items as Record<string, unknown>[]).map((item) => {
          if (!boardFixture(name)) expect(item, name).not.toHaveProperty('lines');
          else if (item.lines !== undefined) expect(ajv.validate(strs, item.lines), name).toBe(true);
          return Object.fromEntries(Object.entries(item).filter(([key]) => key !== '_kind' && key !== 'lines'));
        });
        expectValid('E-WORK-HISTORY', 200, { ...body, items });
      } else {
        const { presentation, decide_presentation: decidePresentation, ...item } = body;
        if (boardFixture(name) || (decideBoardFixture(name) && presentation !== undefined)) {
          expect(validPresentation(presentation), `${name}: ${ajv.errorsText(validPresentation.errors)}`).toBe(true);
        } else {
          expect(presentation, name).toBeUndefined();
        }
        if (decideBoardFixture(name) && decidePresentation !== undefined) {
          expect(validDecidePresentation(decidePresentation), `${name}: ${ajv.errorsText(validDecidePresentation.errors)}`).toBe(true);
        } else {
          expect(decidePresentation, name).toBeUndefined();
        }
        expectValid('E-WORK-ITEM', 200, item);
        expect(body.sample, name).toBe(true);
      }
    }
    expect(files.filter(boardFixture)).toHaveLength(12);
  });

  it('the decision board sidecars (W-19xx decided and redrafted items) are schema-valid with the PROPOSAL blocks removed', () => {
    const files = readdirSync(workDir).filter((name) => /^W-19\d\d\.[a-z]+\.json$/.test(name));
    expect(files.sort()).toEqual(['W-1901.approve.json', 'W-1902.next.json']);
    for (const name of files) {
      const { presentation, decide_presentation: decidePresentation, ...item } = readJson(join(workDir, name));
      if (presentation !== undefined) expect(validPresentation(presentation), name).toBe(true);
      expect(validDecidePresentation(decidePresentation), `${name}: ${ajv.errorsText(validDecidePresentation.errors)}`).toBe(true);
      expectValid('E-WORK-ITEM', 200, item);
    }
    // only the W-19xx files carry the decision board block
    const others = readdirSync(workDir).filter((name) => name.endsWith('.json') && !decideBoardFixture(name));
    for (const name of others) expect(readJson(join(workDir, name)), name).not.toHaveProperty('decide_presentation');
  });

  it('a crafted next-decision href that is not an app path fails the block schema', () => {
    for (const href of ['https://x.example', '//x.example', 'javascript:alert(1)']) {
      expect(validDecidePresentation({ queue: { position: 1, total: 3, next: { label: 'Next', href } } }), href).toBe(false);
    }
  });

  it('the board fixtures leave every existing fixture byte-for-byte unchanged', () => {
    const run = spawnSync('git', ['diff', '--name-only', '--diff-filter=MDR', '8930da1', '--', '.'], { cwd: workDir, encoding: 'utf8' });
    expect(run.status).toBe(0);
    expect(run.stdout.trim()).toBe('');
  });

  it('an unknown W-17xx id still falls back to the default fixture', async () => {
    const other = await get('/api/v1/work/W-1799');
    expect(other.status).toBe(200);
    expect(other.body).toEqual(readJson(join(__dirname, '../mock/fixtures/E-WORK-ITEM.json')));
  });

  it('W-1004 carries the A-WORKITEM given and a 12-row history', () => {
    const item = readJson(join(workDir, 'W-1004.json')) as { facts: { name: string; status: string }[]; agent: { status: string; steps: { text: string; status: string }[] } };
    expect(item.facts.map((f) => `${f.name}:${f.status}`)).toEqual([
      'drafted:earned',
      'reviewed:earned',
      'approved:earned',
      'sent:not_yet',
      'receipt_recorded:unknown',
      'verified:not_yet',
    ]);
    expect(item.agent.status).toBe('done');
    for (const step of item.agent.steps) expect(`${step.text} ${step.status}`).not.toMatch(/approv|send|pay/i);
    const rows = w1004.items as (Row & { actor: string; event: string; restricted: boolean; version?: string; detail?: string })[];
    expect(rows).toHaveLength(12);
    expect([...rows].map((r) => r.at)).toEqual([...rows].map((r) => r.at).sort().reverse());
    const restricted = rows.filter((r) => r.restricted);
    expect(restricted).toHaveLength(1);
    expect(restricted[0]).not.toHaveProperty('version');
    expect(restricted[0]).not.toHaveProperty('detail');
    expect(restricted[0].event).toBe('Restricted');
    expect(rows.filter((r) => !r._kind).map((r) => r.event)).toEqual(['Started the line']);
  });
});

describe('F-17 workspace fixtures (W-20xx)', () => {
  const dir = join(__dirname, '../mock/fixtures/work');
  const load = (name: string) => JSON.parse(readFileSync(join(dir, name), 'utf8')) as Record<string, unknown>;
  const items = readdirSync(dir).filter((name) => /^W-20\d\d(\.next)?\.json$/.test(name));

  it('every W-20xx item is schema-valid, marked sample and carries no board presentation block', () => {
    expect(items.length).toBeGreaterThanOrEqual(6);
    for (const name of items) {
      const body = load(name);
      expectValid('E-WORK-ITEM', 200, body);
      expect(body.sample, name).toBe(true);
      expect(body, name).not.toHaveProperty('presentation');
      expect(body, name).not.toHaveProperty('decide_presentation');
    }
  });

  it('W-2001 to W-2009 carry a workspace; W-2010 is W-1002 with its id changed and no workspace', () => {
    for (const id of ['W-2001', 'W-2002', 'W-2003', 'W-2004', 'W-2005', 'W-2006', 'W-2007', 'W-2008', 'W-2009']) expect(load(`${id}.json`), id).toHaveProperty('workspace');
    const copy = load('W-2010.json');
    expect(copy).not.toHaveProperty('workspace');
    expect({ ...copy, id: 'W-1002' }).toEqual(load('W-1002.json'));
  });

  it('the mock serves each W-20xx item as its own fixture', async () => {
    for (const id of ['W-2001', 'W-2002', 'W-2003', 'W-2004', 'W-2005', 'W-2010']) {
      const response = await fetch(`${base}/api/v1/work/${id}`, { headers: { Cookie: 'psl_mock_persona=pm' } });
      expect(response.status, id).toBe(200);
      expect(await response.json(), id).toEqual(load(`${id}.json`));
    }
  });
});

describe('F-17 step scripts and sidecars', () => {
  const dir = join(__dirname, '../mock/fixtures/work');
  const load = (name: string) => JSON.parse(readFileSync(join(dir, name), 'utf8')) as Record<string, { status: number; body?: unknown; next?: boolean }>;

  it('each W-20xx.steps.json names only steps the item offers, with a declared status', () => {
    const scripts = readdirSync(dir).filter((name) => /^W-20\d\d\.steps\.json$/.test(name));
    expect(scripts.sort()).toEqual(['W-2001.steps.json', 'W-2006.steps.json', 'W-2007.steps.json', 'W-2008.steps.json']);
    for (const name of scripts) {
      const item = JSON.parse(readFileSync(join(dir, name.replace('.steps', '')), 'utf8')) as { workspace: { steps: { key: string }[] } };
      const keys = item.workspace.steps.map((s) => s.key);
      for (const [step, script] of Object.entries(load(name))) {
        expect(keys, `${name} ${step}`).toContain(step);
        expect([200, 409, 422, 500], `${name} ${step}`).toContain(script.status);
        if (script.status === 422) expectValid('E-WORK-STEP', 422, script.body);
      }
    }
  });

  it('W-2009 is W-1901’s decision with its own ids and no board blocks', () => {
    const w2009 = JSON.parse(readFileSync(join(dir, 'W-2009.json'), 'utf8'));
    const { presentation, decide_presentation: board, ...w1901 } = JSON.parse(readFileSync(join(dir, 'W-1901.json'), 'utf8'));
    expect(presentation).toBeDefined();
    expect(board).toBeDefined();
    const { workspace, ...rest } = w2009;
    expect(workspace.steps[0].task_id).toBe('T-2009');
    expect(rest).toEqual({ ...w1901, id: 'W-2009', tasks: [{ ...w1901.tasks[0], id: 'T-2009' }] });
  });
});

describe('F-21 weekly fixtures (W-2201 to W-2208)', () => {
  const dir = join(__dirname, '../mock/fixtures/work');
  const files = readdirSync(dir).filter((name) => /^W-22(0\d|\d\d)(\.next)?\.json$/.test(name) && name.slice(0, 6) <= 'W-2208');

  it('every weekly item and sidecar is schema-valid and marked sample, with no stripping', () => {
    expect(files.filter((name) => !name.includes('.next'))).toHaveLength(8);
    for (const name of files) {
      const body = JSON.parse(readFileSync(join(dir, name), 'utf8'));
      expectValid('E-WORK-ITEM', 200, body);
      expect(body.sample, name).toBe(true);
    }
  });
});

describe('F-22 weekly fixtures (W-2209 to W-2214)', () => {
  const dir = join(__dirname, '../mock/fixtures/work');
  const files = readdirSync(dir).filter((name) => /^W-22(09|1[0-4])(\.next)?\.json$/.test(name));

  it('every returned or received item and sidecar is schema-valid and marked sample, with no stripping', () => {
    expect(files.filter((name) => !name.includes('.next'))).toHaveLength(6);
    for (const name of files) {
      const body = JSON.parse(readFileSync(join(dir, name), 'utf8'));
      expectValid('E-WORK-ITEM', 200, body);
      expect(body.sample, name).toBe(true);
    }
  });
});
