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
import { ASSISTANT_OPERATIONS } from '../mock/assistant.mjs';
// @ts-expect-error plain ESM module without type declarations
import { contractEvidence } from '../mock/evidence.mjs';
// @ts-expect-error plain ESM module without type declarations
import { contractBody as exceptionsBody } from '../mock/exceptions.mjs';
// @ts-expect-error plain ESM module without type declarations
import { contractBody as monthEndBody } from '../mock/finance.mjs';
// @ts-expect-error plain ESM module without type declarations
import { contractBody as invoicesBody } from '../mock/invoices.mjs';
// @ts-expect-error plain ESM module without type declarations
import { contractRules } from '../mock/setup.mjs';
// @ts-expect-error plain ESM module without type declarations
import { contractDelegation, contractDelegations } from '../mock/delegations.mjs';

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

const PATH_VALUES: Record<string, string> = { work_id: 'W-1001', task_id: 'T-2001', component: 'documents.client_reviewer', case_id: 'C-SETUP-1', client_id: 'CL-3501', template_id: 'T-01', tab: 'milestones', document_id: 'D-2304', version: '1' };
const NOTIFICATION_IDS: Record<string, string> = { finance_lead: 'N-0001', pm: 'N-0101', ceo: 'N-0201', none: 'N-0201', admin: 'N-0201', pmo_lead: 'N-0201' };
const QUERY: Record<string, string> = { 'E-WORK-LIST': '?queue=needs_me', 'E-WORK-HISTORY': '?kind=all', 'E-MONTH-END': '?period=2026-10' };
const BODY: Record<string, unknown> = {
  'E-ALERT-PREFS': { channel: 'both', frequency: 'immediate' },
  'E-TASK-CLAIM': { expected_revision: 2 },
  'E-TASK-DECIDE': { expected_revision: 2, verdict: 'approve' },
  'E-SETUP-RULE-SAVE': { expected_revision: 2, value: { roles: ['pmo_lead'] } },
  'E-CLIENT-CONTACT': { expected_revision: 3, name: 'Ada Okoye', email: 'ada@example.org' },
  'E-EVIDENCE-UPLOAD': { kind: 'rule_proof', filename: 'minutes.pdf', content_base64: 'JVBERi0xLjQK', case_revision: 1 },
  'E-TEMPLATE-VERSION': { expected_revision: 1, filename: 'invoice.pdf', content_base64: 'JVBERi0xLjQK' },
  'E-DELEGATION': { expected_revision: 2, from_person_id: 'P-KEMI', delegate: 'P-FEMI', starts: '2026-11-18', ends: '2026-11-25' },
};
// Operations a persona may not use answer the declared status instead of 200 (Setup is for Leads and Admin; E-EXCEPTIONS is Leads only; E-MONTH-END Finance only).
const PERSONA_STATUS: Record<string, Record<string, number>> = {
  'E-CLIENTS': { none: 403 },
  'E-CLIENT': { none: 403 },
  'E-CLIENT-CONTACT': { none: 403 },
  'E-EXCEPTIONS': { pm: 403 },
  'E-MONTH-END': { pm: 403, none: 403 },
  'E-INVOICES': { pm: 403, none: 403 },
  'E-SETUP-RULES': { pm: 403, none: 403 },
  'E-SETUP-RULE-SAVE': { pm: 403, none: 403 },
  'E-EVIDENCE-UPLOAD': { pm: 403, none: 403 },
  'E-TEMPLATES': { pm: 403, none: 403 },
  'E-TEMPLATE-VERSION': { pm: 403, none: 403 },
  'E-DELEGATIONS': { pm: 403, none: 403 },
  'E-DELEGATION': { pm: 403, none: 403 },
};
// Engineering-proposal fields the mock serves ahead of the contract are removed before the schema check (F-06, F-10, F-11).
// PROPOSAL (BACKEND-HANDOFF 2, F-22): a records step field carries its saved records as a list of {value, label} in `value`;
// the generated type says string, so the list's shape is checked here and it is removed before the schema check.
function savedRecordsStripped(body: unknown): unknown {
  const copy = structuredClone(body) as { workspace?: { steps?: { fields?: { type: string; value?: unknown }[] }[] } };
  for (const step of copy.workspace?.steps ?? []) {
    for (const f of step.fields ?? []) {
      if (f.type !== 'records' || f.value === undefined) continue;
      const list = f.value as { value?: unknown; label?: unknown }[];
      expect(Array.isArray(list) && list.length > 0 && list.every((o) => typeof o.value === 'string' && typeof o.label === 'string' && Object.keys(o).length === 2)).toBe(true);
      delete f.value;
    }
  }
  return copy;
}
// PROPOSAL (D-LINE-WORKSPACE, F-23): `steps[].items_default` ("checked" or absent) and `workspace.links[]`
// ({key, label, target: {kind: assistant | document | project_tab (F-28) | work (F-32) | setup_rules (F-34), document_id?, version?, tab?, case_id?}}). Each is checked on its own, then removed
// before the schema check; the generated types and openapi.json do not carry them.
const linkSchema = {
  type: 'array',
  minItems: 1,
  items: {
    oneOf: [
      { type: 'object', additionalProperties: false, required: ['key', 'label', 'target'], properties: { key: { type: 'string', minLength: 1 }, label: { type: 'string', minLength: 1 }, target: { type: 'object', additionalProperties: false, required: ['kind'], properties: { kind: { const: 'assistant' } } } } },
      { type: 'object', additionalProperties: false, required: ['key', 'label', 'target'], properties: { key: { type: 'string', minLength: 1 }, label: { type: 'string', minLength: 1 }, target: { type: 'object', additionalProperties: false, required: ['kind', 'tab', 'case_id'], properties: { kind: { const: 'project_tab' }, tab: { enum: ['journey', 'delivery', 'milestones', 'documents', 'money', 'registers', 'actions'] }, case_id: { type: 'string', pattern: '^[A-Za-z0-9][A-Za-z0-9._-]*$' } } } } },
      { type: 'object', additionalProperties: false, required: ['key', 'label', 'target'], properties: { key: { type: 'string', minLength: 1 }, label: { type: 'string', minLength: 1 }, target: { type: 'object', additionalProperties: false, required: ['kind', 'work_id'], properties: { kind: { const: 'work' }, work_id: { type: 'string', pattern: '^[A-Za-z0-9][A-Za-z0-9._-]*$' } } } } },
      { type: 'object', additionalProperties: false, required: ['key', 'label', 'target'], properties: { key: { type: 'string', minLength: 1 }, label: { type: 'string', minLength: 1 }, target: { type: 'object', additionalProperties: false, required: ['kind', 'area'], properties: { kind: { const: 'setup_rules' }, area: { enum: ['finance', 'delivery'] } } } } },
      { type: 'object', additionalProperties: false, required: ['key', 'label', 'target'], properties: { key: { type: 'string', minLength: 1 }, label: { type: 'string', minLength: 1 }, target: { type: 'object', additionalProperties: false, required: ['kind', 'document_id', 'version'], properties: { kind: { const: 'document' }, document_id: { type: 'string', minLength: 1 }, version: { anyOf: [{ type: 'string' }, { type: 'integer' }] } } } } },
    ],
  },
};
const validLinks = ajv.compile(linkSchema);
function minutesProposalsStripped(body: unknown): unknown {
  const copy = structuredClone(savedRecordsStripped(body)) as { workspace?: { links?: unknown; sections?: { columns?: { date_format?: unknown }[]; items: { id: string; values?: Record<string, unknown> }[] }[]; steps?: { key?: string; task_id?: string; items_default?: unknown; starts_line?: unknown; verdict?: unknown }[] } };
  const w = copy.workspace;
  if (w?.links !== undefined) {
    expect(validLinks(w.links), ajv.errorsText(validLinks.errors)).toBe(true);
    delete w.links;
  }
  const note = (copy.workspace as { agent_note?: { lines: string[]; warn_lines?: unknown } } | undefined)?.agent_note;
  if (note?.warn_lines !== undefined) {
    expect(Array.isArray(note.warn_lines) && note.warn_lines.every((n) => Number.isInteger(n) && n >= 0 && n < note.lines.length)).toBe(true);
    delete note.warn_lines;
  }
  // PROPOSAL (item `values`): each value is a string, or a record {value, label}
  for (const section of w?.sections ?? []) {
    for (const column of section.columns ?? []) {
      if (column.date_format === undefined) continue;
      expect(column.date_format).toBe('day_month');
      delete column.date_format;
    }
    for (const row of section.items) {
      if (row.values === undefined) continue;
      for (const [name, v] of Object.entries(row.values)) {
        const ok = typeof v === 'string' ? v.trim() !== '' : typeof v === 'object' && v !== null && typeof (v as { value?: unknown }).value === 'string' && typeof (v as { label?: unknown }).label === 'string';
        expect(ok, `${row.id}.${name}`).toBe(true);
      }
      delete row.values;
    }
    // PROPOSAL (F-41 G-SCR32-3): an item's `attachment` {label, size_bytes, document_id?}
    for (const row of section.items as { id: string; attachment?: { label?: unknown; size_bytes?: unknown; document_id?: unknown } }[]) {
      if (row.attachment === undefined) continue;
      const { label, size_bytes: size, document_id: documentId, ...rest } = row.attachment;
      expect(typeof label === 'string' && label !== '' && Number.isInteger(size) && (documentId === undefined || typeof documentId === 'string') && Object.keys(rest).length === 0, row.id).toBe(true);
      delete row.attachment;
    }
  }
  // PROPOSAL (F-31, mock/proposals/engagement-planning.json): `assign.default_person_id` (one of the candidates) and `default_hint`,
  // `items[].team_key` and `tasks[].response.teams[].disabled_reason` / `asked_at`; each is checked on its own, then removed.
  const offered = (copy as { assign?: { candidates: { person_id: string }[]; default_person_id?: unknown; default_hint?: unknown } }).assign;
  if (offered?.default_person_id !== undefined) {
    expect(offered.candidates.some((c) => c.person_id === offered.default_person_id)).toBe(true);
    delete offered.default_person_id;
  }
  if (offered?.default_hint !== undefined) {
    expect(typeof offered.default_hint === 'string' && offered.default_hint !== '').toBe(true);
    delete offered.default_hint;
  }
  // PROPOSAL (F-36, mock/proposals/rfp-assign.json): `assign.roles`, `evidence_kind` and `next`; tests/rfp-assign-mock.test.ts checks each against the overlay.
  const rfpAssign = (copy as { assign?: Record<string, unknown> }).assign;
  if (rfpAssign) for (const key of ['roles', 'evidence_kind', 'next']) delete rfpAssign[key];
  for (const section of w?.sections ?? []) {
    for (const row of section.items as { team_key?: unknown }[]) {
      if (row.team_key === undefined) continue;
      expect(typeof row.team_key === 'string' && row.team_key !== '').toBe(true);
      delete row.team_key;
    }
  }
  for (const task of (copy as { tasks?: { response?: { teams?: { disabled_reason?: unknown; asked_at?: unknown }[] } }[] }).tasks ?? []) {
    for (const team of task.response?.teams ?? []) {
      delete team.disabled_reason;
      delete team.asked_at;
    }
  }
  // PROPOSAL (F-30): `steps[].starts_line` {line_key, prefill} and `assign.candidates[].kind`
  const candidates = (copy as { assign?: { candidates: { kind?: unknown }[] } }).assign?.candidates ?? [];
  for (const candidate of candidates) {
    if (candidate.kind === undefined) continue;
    expect(['person', 'team', 'outside_party']).toContain(candidate.kind);
    delete candidate.kind;
  }
  for (const step of w?.steps ?? []) {
    // PROPOSAL (F-41 UX-2-3): `steps[].submit_label`, the words on a step form's submit button
    const submit = (step as { submit_label?: unknown }).submit_label;
    if (submit !== undefined) {
      expect(typeof submit === 'string' && submit.trim() !== '', step.key).toBe(true);
      delete (step as { submit_label?: unknown }).submit_label;
    }
    if (step.starts_line !== undefined) {
      const { line_key: line, prefill } = step.starts_line as { line_key?: unknown; prefill?: unknown };
      expect(typeof line === 'string' && line !== '' && typeof prefill === 'object' && prefill !== null, step.key).toBe(true);
      delete step.starts_line;
    }
    // PROPOSAL (F-33 G-C-1): `steps[].verdict`, a decision step decided in place; only on a step that carries a task id
    if (step.verdict !== undefined) {
      expect(typeof step.task_id === 'string' && typeof step.verdict === 'string', step.key).toBe(true);
      delete step.verdict;
    }
    if (step.items_default === undefined) continue;
    expect(step.items_default, step.key).toBe('checked');
    delete step.items_default;
  }
  return copy;
}
const CONTRACT_BODY: Record<string, (body: unknown) => unknown> = {
  'E-WORK-ITEM': minutesProposalsStripped,
  'E-EXCEPTIONS': exceptionsBody,
  'E-MONTH-END': monthEndBody,
  'E-INVOICES': invoicesBody,
  'E-SETUP-RULES': contractRules,
  'E-EVIDENCE-UPLOAD': contractEvidence,
  'E-DELEGATIONS': contractDelegations,
  'E-DELEGATION': contractDelegation,
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
    // Start work and the assistant answer per persona, per body and per conversation; tests/start-work-mock.test.ts and
    // tests/assistant-mock.test.ts cover them.
    const ownTests = [...(START_OPERATIONS as string[]), ...(ASSISTANT_OPERATIONS as string[])];
    for (const persona of ownTests.includes(id) ? [] : (PERSONAS as string[])) {
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
      ['Kemi Adebayo', ['my_work', 'projects', 'assistant'], 'mock-csrf-pmo_lead'],
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
    const result = await request('E-PAYROLL-MATCH');
    expect(result).toEqual({ status: 501, body: { code: 'not_mocked', message: 'Not available in the mock yet.' } });
    expectValid('E-PAYROLL-MATCH', 501, result.body);
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
        expectValid('E-WORK-ITEM', 200, minutesProposalsStripped(item));
        // F-41: W-3813 is the one item served with sample: false, to prove the label follows the record
        expect(body.sample, name).toBe(name !== 'W-3813.json');
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

describe('F-23 minutes fixtures (W-2301 to W-2308)', () => {
  const dir = join(__dirname, '../mock/fixtures/work');
  const all = readdirSync(dir).filter((name) => /^W-230[1-8](\.[a-z]+)?\.json$/.test(name) && !name.includes('.steps'));

  it('every minutes item and sidecar is schema-valid and marked sample once the two proposal keys are removed', () => {
    expect(all.filter((name) => /^W-230[1-8]\.json$/.test(name))).toHaveLength(8);
    for (const name of all) {
      const body = JSON.parse(readFileSync(join(dir, name), 'utf8'));
      expectValid('E-WORK-ITEM', 200, minutesProposalsStripped(body));
      expect(body.sample, name).toBe(true);
    }
  });

  it('the proposal keys exist on their own: items_default only on W-2301, W-2306 and W-2307 confirm steps, links only on the four boards that draw them', () => {
    const withKey = (key: 'items_default' | 'links') =>
      readdirSync(dir)
        .filter((name) => /^W-\d+(\.[a-z]+)?\.json$/.test(name))
        .filter((name) => (key === 'links' ? 'links' in (JSON.parse(readFileSync(join(dir, name), 'utf8')).workspace ?? {}) : JSON.stringify(JSON.parse(readFileSync(join(dir, name), 'utf8')).workspace ?? {}).includes('"items_default"')));
    expect(withKey('items_default').every((name) => /^W-23/.test(name))).toBe(true);
    // F-31 (W-26xx), F-32 release boards (W-2501, W-2503: Ask Tola, Open go-live) and F-34 hypercare (W-31xx) carry links too; F-33's investigating board (W-2701) and F-42's (W-3901) F-43's (W-4001) and F-45's (W-4201, W-4211) draw Ask Chidi;
    // F-35's drafting board (W-3201) draws Ask Tola; F-39's escalation boards (W-36xx) and F-38's submission boards (W-35xx: Ask Tola, Open the full pack) draw their links too; F-40's handover (W-37xx) too
    expect(withKey('links').every((name) => /^W-(23|25|26|31|35|36|37)/.test(name) || name === 'W-2701.json' || name === 'W-3201.json' || name === 'W-3901.json' || name === 'W-4001.json' || name === 'W-4201.json' || name === 'W-4211.json')).toBe(true);
    expect(withKey('links')).toEqual(expect.arrayContaining(['W-2302.json', 'W-2303.json', 'W-2304.json', 'W-2305.json']));
  });

  it('items[].values, columns[].date_format and agent_note.warn_lines appear only in W-23xx fixtures (TECH-2-1)', () => {
    type Section = { items?: { values?: unknown }[]; columns?: { date_format?: unknown }[] };
    const files = readdirSync(dir).filter((name) => /^W-\d+(\.[a-z]+)?\.json$/.test(name));
    const carrying = (pick: (section: Section) => boolean) =>
      files.filter((name) => ((JSON.parse(readFileSync(join(dir, name), 'utf8')).workspace?.sections ?? []) as Section[]).some(pick));
    const values = carrying((sec) => (sec.items ?? []).some((i) => i.values !== undefined));
    const formats = carrying((sec) => (sec.columns ?? []).some((c) => c.date_format !== undefined));
    expect(values.length).toBeGreaterThan(0);
    expect(formats.length).toBeGreaterThan(0);
    const warns = files.filter((name) => JSON.parse(readFileSync(join(dir, name), 'utf8')).workspace?.agent_note?.warn_lines !== undefined);
    expect([...values, ...formats, ...warns].every((name) => /^W-23/.test(name))).toBe(true);
  });

  it('the E-DOCUMENT fixture is a test template for D-2304 version 1', () => {
    const body = JSON.parse(readFileSync(join(__dirname, '../mock/fixtures/E-DOCUMENT.json'), 'utf8'));
    expect(body).toMatchObject({ document_id: 'D-2304', version: '1', test_template: true });
  });
});

describe('F-28 minutes end-state fixtures (W-2309 to W-2314)', () => {
  const dir = join(__dirname, '../mock/fixtures/work');
  const names = readdirSync(dir).filter((name) => /^W-(2309|231[0-4])(\.[a-z]+)?\.json$/.test(name) || name === 'W-2301.next.internal.json');

  it('every end-state item and sidecar is schema-valid and marked sample once the proposal keys are removed', () => {
    expect(names.filter((name) => /^W-\d+\.json$/.test(name))).toHaveLength(6);
    for (const name of names.filter((n) => !n.includes('.steps'))) {
      const body = JSON.parse(readFileSync(join(dir, name), 'utf8'));
      expectValid('E-WORK-ITEM', 200, minutesProposalsStripped(body));
      expect(body.sample, name).toBe(true);
    }
  });

  it('the project_tab link kind is checked on its own: it names a known project tab and a valid case id, and only W-231x and the W-2309 sidecar carry it', () => {
    const carrying: string[] = [];
    for (const name of names) {
      const links = (JSON.parse(readFileSync(join(dir, name), 'utf8')).workspace?.links ?? []) as { target: { kind: string } }[];
      if (links.some((l) => l.target.kind === 'project_tab')) carrying.push(name);
    }
    expect(carrying.sort()).toEqual(['W-2309.approve.json', 'W-2310.json', 'W-2311.json', 'W-2312.json', 'W-2313.json', 'W-2301.next.internal.json'].sort());
    expect(validLinks([{ key: 'k', label: 'Open', target: { kind: 'project_tab', tab: 'nowhere', case_id: 'C-0211' } }])).toBe(false);
    expect(validLinks([{ key: 'k', label: 'Open', target: { kind: 'project_tab', tab: 'actions', case_id: '../x' } }])).toBe(false);
  });
});

describe('F-42 fixed asset schedule fixtures (W-3901 to W-3912)', () => {
  const dir = join(__dirname, '../mock/fixtures/work');
  const names = readdirSync(dir).filter((name) => /^W-39\d\d(\.[a-z]+)?\.json$/.test(name));

  it('every item and decide sidecar is schema-valid and marked sample once steps[].verdict is removed', () => {
    expect(names.filter((name) => /^W-\d+\.json$/.test(name))).toHaveLength(12);
    expect(names).toHaveLength(21);
    for (const name of names) {
      const body = JSON.parse(readFileSync(join(dir, name), 'utf8'));
      expectValid('E-WORK-ITEM', 200, minutesProposalsStripped(body));
      expect(body.sample, name).toBe(true);
      expect(body.workspace.line_key, name).toBe('fixed_assets');
    }
  });
});

describe('F-45 ledger source fixtures (W-4201 to W-4213)', () => {
  const dir = join(__dirname, '../mock/fixtures/work');
  const names = readdirSync(dir).filter((name) => /^W-42\d\d(\.[a-z]+)?\.json$/.test(name) && !name.includes('.steps'));

  it('every item and sidecar is schema-valid and marked sample once steps[].verdict and the links are removed', () => {
    expect(names.filter((name) => /^W-\d+\.json$/.test(name))).toHaveLength(13);
    expect(names).toHaveLength(20);
    for (const name of names) {
      const body = JSON.parse(readFileSync(join(dir, name), 'utf8'));
      expectValid('E-WORK-ITEM', 200, minutesProposalsStripped(body));
      expect(body.sample, name).toBe(true);
      expect(body.workspace.line_key, name).toBe('ledger_sources');
    }
  });
});

describe('F-43 cash forecast fixtures (W-4001 to W-4013)', () => {
  const dir = join(__dirname, '../mock/fixtures/work');
  const names = readdirSync(dir).filter((name) => /^W-40\d\d(\.[a-z]+)?\.json$/.test(name));

  it('every item and decide sidecar is schema-valid and marked sample once steps[].verdict is removed', () => {
    expect(names.filter((name) => /^W-\d+\.json$/.test(name))).toHaveLength(13);
    expect(names).toHaveLength(19);
    for (const name of names) {
      const body = JSON.parse(readFileSync(join(dir, name), 'utf8'));
      expectValid('E-WORK-ITEM', 200, minutesProposalsStripped(body));
      expect(body.sample, name).toBe(true);
      expect(body.workspace.line_key, name).toBe('cash_forecast');
    }
  });
});
