// Local contract mock for /api/v1. Routes come from the v7 openapi.json; M-1
// operations answer with sample fixtures, everything else answers 501. Local use only.
//
// Persona: cookie psl_mock_persona (finance_lead | pm | none; default finance_lead).
// Scenario: cookie psl_mock_scenario or header X-Mock-Scenario (401 | 403 | 404 | 409 | 422),
// applied only when the operation declares that status.
// Work items: E-WORK-ITEM and E-WORK-HISTORY pick fixtures/work/<id>.json and <id>.history.json when
// present (else the default fixture); W-1099 is the reserved no-access id. History honours kind, limit, cursor.
// Tasks: E-TASK-CLAIM and E-TASK-DECIDE validate the body against the openapi request schema, find the task in
// the items the mock serves and check its revision. A decide swaps in <id>.next.json (a redraft: 409) or
// <id>.<verdict>.json (the decided item) as an in-memory override; POST /__mock/reset clears the overrides.
// Alerts (F-12): the four alert operations go to alerts.mjs; as typed by the v7 contract.
import { readdirSync, readFileSync } from 'node:fs';
import http from 'node:http';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

import Ajv2020 from 'ajv/dist/2020.js';
import addFormats from 'ajv-formats';
import { exceptionsList } from './exceptions.mjs';
import { uploadEvidence } from './evidence.mjs';
import { monthEnd } from './finance.mjs';
import { resetSetup, saveSetupRule, setupRules } from './setup.mjs';
import { workList } from './work-list.mjs';
import { ALERT_OPERATIONS, createAlertsMock } from './alerts.mjs';

const here = dirname(fileURLToPath(import.meta.url));
export const OPENAPI_PATH = join(here, '..', '..', 'architecture', 'packages', 'v7', 'openapi.json');

export const M1_OPERATIONS = ['E-ME', 'E-WORK-LIST', 'E-WORK-ITEM', 'E-WORK-HISTORY', 'E-TASK-CLAIM', 'E-TASK-DECIDE', 'E-EXCEPTIONS', 'E-MONTH-END', 'E-NOTIFICATIONS', 'E-NOTIFICATION-READ', 'E-ALERT-PREFS-READ', 'E-ALERT-PREFS', 'E-SETUP-RULES', 'E-SETUP-RULE-SAVE', 'E-EVIDENCE-UPLOAD'];
export const PERSONAS = ['finance_lead', 'pm', 'none', 'admin'];
export const DEFAULT_PERSONA = 'finance_lead';
const WRITE_METHODS = new Set(['post', 'put', 'patch', 'delete']);

export const SCENARIO_BODIES = {
  401: { code: 'not_signed_in', message: 'Sign in to continue.' },
  403: { code: 'forbidden', message: 'Your role does not allow this.' },
  404: { code: 'not_found', message: 'We could not find that record.' },
  409: { code: 'stale_revision', message: 'Someone changed this since you opened it. Reload to see the latest version.' },
  422: { code: 'invalid', message: 'Check the highlighted fields and try again.' },
};
const CSRF_FAILED = { code: 'csrf_failed', message: 'Your session check failed. Reload and try again.' };
const NOT_MOCKED = { code: 'not_mocked', message: 'Not available in the mock yet.' };
const NO_ROUTE = { code: 'not_found', message: 'We could not find that record.' };

function readFixture(name) {
  return JSON.parse(readFileSync(join(here, 'fixtures', `${name}.json`), 'utf8'));
}

export const NO_ACCESS_WORK_ID = 'W-1099';
const HISTORY_KINDS = { decisions: 'decision', agent_work: 'agent_work', evidence: 'evidence' };
const HISTORY_LIMITS = [10, 20, 50];

/** fixtures/work/*.json by file name without .json, e.g. "W-1003" and "W-1004.history". */
function readWorkFixtures() {
  const dir = join(here, 'fixtures', 'work');
  const files = readdirSync(dir).filter((name) => name.endsWith('.json'));
  return Object.fromEntries(files.map((name) => [name.slice(0, -5), JSON.parse(readFileSync(join(dir, name), 'utf8'))]));
}

/** One history page: filter by the mock-only `_kind`, page by an "o:<offset>" cursor, strip `_kind`. */
function historyPage(history, query) {
  const kind = HISTORY_KINDS[query.get('kind')];
  const rows = kind ? history.items.filter((item) => item._kind === kind) : history.items;
  const limit = HISTORY_LIMITS.includes(Number(query.get('limit'))) ? Number(query.get('limit')) : 20;
  const match = /^o:(\d+)$/.exec(query.get('cursor') ?? '');
  const offset = match && Number(match[1]) < rows.length ? Number(match[1]) : 0;
  const items = rows
    .slice(offset, offset + limit)
    .map((item) => Object.fromEntries(Object.entries(item).filter(([key]) => key !== '_kind')));
  const page = { items, as_of: history.as_of };
  if (offset + limit < rows.length) page.next_cursor = `o:${offset + limit}`;
  return page;
}

function workResponse(operationId, url, fixtures, work, overrides) {
  const workId = decodeCookie(url.pathname.split('/')[4] ?? '');
  if (workId === NO_ACCESS_WORK_ID) return [404, SCENARIO_BODIES[404]];
  // Only plain ids ("W-1003") pick a per-id file, so "W-1004.history" or other sidecar names never answer as an item.
  const own = (name) => (/^W-\d+$/.test(workId) && Object.hasOwn(work, name) ? work[name] : undefined);
  if (operationId === 'E-WORK-ITEM') return [200, overrides.get(workId) ?? own(workId) ?? fixtures['E-WORK-ITEM']];
  return [200, historyPage(own(`${workId}.history`) ?? fixtures['E-WORK-HISTORY'], url.searchParams)];
}

const TASK_OPERATIONS = ['E-TASK-CLAIM', 'E-TASK-DECIDE'];
const NOTE_REQUIRED = new Set(['return', 'reject', 'revoke']);
const NOTE_MAX = 2000;
const invalid = (fields) => [422, { code: 'invalid', message: `Check these fields: ${[...new Set(fields)].join(', ')}.` }];

/** One request-body validator per task operation, compiled once from the loaded openapi. */
function bodyValidators(openapi) {
  const ajv = new Ajv2020({ allErrors: true, strict: true });
  addFormats(ajv);
  const validators = {};
  for (const ops of Object.values(openapi.paths)) {
    for (const op of Object.values(ops)) {
      if (TASK_OPERATIONS.includes(op?.operationId)) {
        validators[op.operationId] = ajv.compile(op.requestBody.content['application/json'].schema);
      }
    }
  }
  return validators;
}

/** Field names from Ajv errors: the missing or extra property, else the failing path; "body" for the whole body. */
function errorFields(errors) {
  return errors.map(
    (e) => e.params.missingProperty ?? e.params.additionalProperty ?? (e.instancePath.split('/')[1] || 'body'),
  );
}

/** The task with this id in the items the mock currently serves: default, per-id files, then overrides. */
function findTask(taskId, fixtures, work, overrides) {
  const items = new Map([[fixtures['E-WORK-ITEM'].id, fixtures['E-WORK-ITEM']]]);
  for (const [name, body] of Object.entries(work)) if (/^W-\d+$/.test(name)) items.set(name, body);
  for (const [workId, body] of overrides) items.set(workId, body);
  for (const [workId, item] of items) {
    const task = item.tasks.find((t) => t.id === taskId);
    if (task) return { workId, item, task };
  }
  return undefined;
}

function taskResponse(operationId, url, raw, ctx) {
  const { fixtures, work, overrides, validators, me } = ctx;
  const taskId = decodeCookie(url.pathname.split('/')[4] ?? '');
  const found = findTask(taskId, fixtures, work, overrides);
  if (!found) return [404, SCENARIO_BODIES[404]];
  let body;
  try {
    body = JSON.parse(raw);
  } catch {
    return invalid(['body']);
  }
  const validate = validators[operationId];
  if (!validate(body)) return invalid(errorFields(validate.errors));
  const decide = operationId === 'E-TASK-DECIDE';
  if (decide) {
    const blank = typeof body.note !== 'string' || body.note.trim() === '';
    if ((NOTE_REQUIRED.has(body.verdict) && blank) || (body.note?.length ?? 0) > NOTE_MAX) return invalid(['note']);
    if (body.verdict === 'revoke') return [501, NOT_MOCKED];
  }
  const { workId, item, task } = found;
  // Revision before eligibility, so a decided task (now you_can_act: false) answers a repeat decide with 409.
  if (body.expected_revision !== task.revision) return [409, SCENARIO_BODIES[409]];
  if (!task.you_can_act) return [403, SCENARIO_BODIES[403]];
  if (!decide) return [200, { task_id: task.id, revision: task.revision, claimed_by: me.name }];

  const next = work[`${workId}.next`];
  if (next && !overrides.has(workId)) {
    overrides.set(workId, next);
    return [409, SCENARIO_BODIES[409]];
  }
  const decided = work[`${workId}.${body.verdict}`];
  if (decided) overrides.set(workId, decided);
  const result = { task_id: task.id, verdict: body.verdict, decided_by: me.name, decided_at: new Date().toISOString() };
  return [200, { ...result, work_state: (decided ?? item).state }];
}

export function loadRoutes(openapi) {
  const routes = [];
  for (const [template, ops] of Object.entries(openapi.paths)) {
    const pattern = new RegExp(
      '^' + template.replace(/[.*+?^$()|[\]\\]/g, '\\$&').replace(/\{[^}]+\}/g, '[^/]+') + '$',
    );
    for (const [method, op] of Object.entries(ops)) {
      if (!op || typeof op !== 'object' || !op.operationId) continue;
      routes.push({ method, template, pattern, operationId: op.operationId, statuses: Object.keys(op.responses) });
    }
  }
  return routes;
}

function parseCookies(header = '') {
  const cookies = {};
  for (const part of header.split(';')) {
    const eq = part.indexOf('=');
    if (eq > 0) cookies[part.slice(0, eq).trim()] = decodeCookie(part.slice(eq + 1).trim());
  }
  return cookies;
}

// A malformed value such as `%` keeps its raw text instead of crashing the mock.
function decodeCookie(value) {
  try {
    return decodeURIComponent(value);
  } catch {
    return value;
  }
}

function send(res, status, body) {
  const text = JSON.stringify(body);
  res.writeHead(status, { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' });
  res.end(text);
}

export function createMockServer(openapi = JSON.parse(readFileSync(OPENAPI_PATH, 'utf8'))) {
  const routes = loadRoutes(openapi);
  const me = Object.fromEntries(PERSONAS.map((p) => [p, readFixture(`me.${p}`)]));
  const fixtures = Object.fromEntries(M1_OPERATIONS.filter((id) => id !== 'E-ME').map((id) => [id, readFixture(id)]));
  const work = readWorkFixtures();
  const validators = bodyValidators(openapi);
  // work_id -> the item served instead of its fixture; in memory only, cleared on restart and by /__mock/reset.
  const overrides = new Map();
  const alerts = createAlertsMock({ openapi });

  return http.createServer((req, res) => {
    const chunks = [];
    req.on('data', (chunk) => chunks.push(chunk));
    req.on('end', () => {
      const raw = Buffer.concat(chunks).toString('utf8');
      const url = new URL(req.url ?? '/', 'http://mock.local');
      const method = (req.method ?? 'GET').toLowerCase();
      if (method === 'post' && url.pathname === '/__mock/reset') {
        overrides.clear();
        resetSetup();
        alerts.reset();
        res.writeHead(204, { 'Cache-Control': 'no-store' });
        return res.end();
      }
      const route = routes.find((r) => r.method === method && r.pattern.test(url.pathname));
      if (!route) return send(res, 404, NO_ROUTE);
      if (!M1_OPERATIONS.includes(route.operationId)) return send(res, 501, NOT_MOCKED);

      const cookies = parseCookies(req.headers.cookie);
      const persona = PERSONAS.includes(cookies.psl_mock_persona) ? cookies.psl_mock_persona : DEFAULT_PERSONA;
      const scenario = req.headers['x-mock-scenario'] ?? cookies.psl_mock_scenario;
      if (scenario && SCENARIO_BODIES[scenario] && route.statuses.includes(String(scenario))) {
        return send(res, Number(scenario), SCENARIO_BODIES[scenario]);
      }
      if (WRITE_METHODS.has(method) && req.headers['x-csrftoken'] !== me[persona].csrf_token) {
        return send(res, 403, CSRF_FAILED);
      }
      if (ALERT_OPERATIONS.includes(route.operationId)) { const r = alerts.handle({ operationId: route.operationId, url, raw, persona, cookies }); return send(res, r.status, r.body); }
      if (route.operationId === 'E-ME') return send(res, 200, me[persona]);
      if (route.operationId === 'E-WORK-LIST') { const r = workList({ url, persona, dataset: cookies.psl_mock_worklist }); return send(res, r.status, r.body); }
      if (route.operationId === 'E-EXCEPTIONS') { const r = exceptionsList({ url, persona, cookies }); return send(res, r.status, r.body); }
      if (route.operationId === 'E-MONTH-END') { const r = monthEnd({ url, persona, cookies }); return send(res, r.status, r.body); }
      if (route.operationId === 'E-SETUP-RULES' || route.operationId === 'E-SETUP-RULE-SAVE') { const r = (route.operationId === 'E-SETUP-RULES' ? setupRules : saveSetupRule)({ url, raw, persona, cookies }); return send(res, r.status, r.body); }
      if (route.operationId === 'E-EVIDENCE-UPLOAD') { const r = uploadEvidence({ url, raw, persona, cookies }); return send(res, r.status, r.body); }
      if (route.operationId === 'E-WORK-ITEM' || route.operationId === 'E-WORK-HISTORY') {
        return send(res, ...workResponse(route.operationId, url, fixtures, work, overrides));
      }
      if (TASK_OPERATIONS.includes(route.operationId)) {
        return send(res, ...taskResponse(route.operationId, url, raw, { fixtures, work, overrides, validators, me: me[persona] }));
      }
      return send(res, 200, fixtures[route.operationId]);
    });
  });
}

export function startMockServer({ port = Number(process.env.MOCK_PORT ?? 4010) } = {}) {
  if (process.env.NODE_ENV === 'production') {
    throw new Error('The mock API refuses to start with NODE_ENV=production.');
  }
  const server = createMockServer();
  return new Promise((resolve, reject) => {
    server.once('error', reject);
    server.listen(port, '127.0.0.1', () => resolve(server));
  });
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  try {
    const server = await startMockServer();
    const { port } = server.address();
    console.log(`Mock API (sample data) on http://127.0.0.1:${port}/api/v1`);
  } catch (error) {
    console.error(error.message);
    process.exit(1);
  }
}
