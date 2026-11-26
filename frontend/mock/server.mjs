// Local contract mock for /api/v1. Routes come from the v7 openapi.json; M-1
// operations answer with sample fixtures, everything else answers 501. Local use only.
//
// Persona: cookie psl_mock_persona (finance_lead | pm | ceo | none | admin | pmo_lead | hr | hr_lead; default finance_lead). hr is a stand-in (D-142): PSL has not defined what HR staff may see..
// ceo (D-150) has sample data of its own: W-50xx rows and items, alerts, Assistant conversations; and it sees every project.
// Start work: E-LINES, E-LINE-OPTIONS and E-WORK-START are answered by start-work.mjs.
// Scenario: cookie psl_mock_scenario or header X-Mock-Scenario (401 | 403 | 404 | 409 | 422 | csrf_failed),
// applied only when the operation declares that status.
// Work items: E-WORK-ITEM and E-WORK-HISTORY pick fixtures/work/<id>.json and <id>.history.json when
// present (else the default fixture); W-1099 is the reserved no-access id. History honours kind, limit, cursor.
// Tasks: E-TASK-CLAIM and E-TASK-DECIDE validate the body against the openapi request schema, find the task in
// the items the mock serves and check its revision. A decide swaps in <id>.next.json (a redraft: 409) or
// <id>.<verdict>.json (the decided item) as an in-memory override; POST /__mock/reset clears the overrides.
// Projects: E-PROJECTS and E-PROJECT answer from projects.mjs in the live shape (persona rows, status, q, cursor, page; UUID ids, P-nnnn accepted too; P-0099 is the no-access id).
// Project tabs (F-25): E-PROJECT-TAB answers from project-tabs.mjs (milestones, registers, actions; documents 501; money goes to money.mjs, F-26).
// Overview: the live GET /overview and GET /work/counts (overview.mjs) serve a variant when cookie psl_mock_overview names one.
// Alerts (F-12, F-61): the four alert paths go to alerts.mjs, in the live 1.24.0 shapes (not the v7 operations).
// Assistant (F-24): the five assistant operations go to assistant.mjs, which also recognises a draft's E-WORK-START.
// Delegation (F-27): E-DELEGATIONS and E-DELEGATION go to delegations.mjs (scenario and save cookies, overlay proposals).
// Invoices (F-79): the live GET /payments answers from invoices.mjs (variant cookie psl_mock_invoices, q, state, cursor); month-end from finance.mjs.
// Live decision desk (F-64): live-decide.mjs answers the integer-id task and work routes of SCR-03 in the live shapes.
// Document review (F-72): the live document-review reads and decision (documents.mjs, cookie psl_mock_docreview); the v7 E-DOCUMENT stays for the work item's document link.
// Live demo (F-54, D-155): demo.mjs holds the switches and the answer delay; with the demo off nothing changes.
import { readdirSync, readFileSync } from 'node:fs';
import http from 'node:http';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

import Ajv2020 from 'ajv/dist/2020.js';
import addFormats from 'ajv-formats';
import { delayMs, delayReply, demoOn } from './demo.mjs';
import { addDemoProject } from './demo-projects.mjs';
import { caseVisible, idOf, normaliseProjectPath, projects } from './projects.mjs';
import { projectTab } from './project-tabs.mjs';
import { deliveryRead } from './delivery-overview.mjs';
import { documentRead, isLiveDocumentPath, liveDocumentReview, resetDocumentReviews } from './documents.mjs';
import { clients, CLIENT_OPERATIONS, isClientsExtraPath, resetClients } from './clients.mjs';
import { exceptionsList } from './exceptions.mjs';
import { uploadEvidence } from './evidence.mjs';
import { monthEnd } from './finance.mjs';
import { invoices } from './invoices.mjs';
import { COUNTS_PATH, floorRead, OVERVIEW_PATH, ownsFloorCounts } from './overview.mjs';
import { resetResponses, RESPONSE_OPERATIONS, responseRoute } from './response.mjs';
import { resetSetup, saveSetupRule, setupRules } from './setup.mjs';
import { createLineRuns } from './line-runs.mjs';
import { START_OPERATIONS, createStartWorkMock } from './start-work.mjs';
import { RECEIVED_BIDS_PATH, receivedBids, receivedBidsLog, resetReceivedBids } from './received-bids.mjs';
import { resetStartLive, START_LIVE_MINUTES, START_LIVE_PATH, START_LIVE_WORK, startLive, startLiveLog } from './start-live.mjs';
import { resetTemplates, templatesList, templateVersion } from './templates.mjs';
import { delegationsList, resetDelegations, saveDelegation } from './delegations.mjs';
import { isLiveWorkRequest, liveWorkCounts, liveWorkItem, liveWorkList, ownsLiveWorkItem } from './live-work.mjs';
import { workList } from './work-list.mjs';
import { FORECAST_PATH, forecastLive } from './forecast-live.mjs';
import { ASSETS_PATH, assetsLive } from './assets-live.mjs';
import { COMMERCIAL_PATH, commercialLive, resetCommercialLive } from './commercial-live.mjs';
import { ENGAGEMENT_PATH, engagementLive, resetEngagementLive } from './engagement-live.mjs';
import { RELEASE_PATH, releaseLive, resetReleaseLive } from './delivery-release.mjs';
import { COSTING_PATH, costingLive, resetCostingLive } from './costing-live.mjs';
import { INCOME_SCHEDULES_PATH, incomeSchedulesLive, resetIncomeSchedulesLive } from './income-schedules-live.mjs';
import { INVOICE_RELEASE_PATH, invoiceReleaseLive, resetInvoiceRelease } from './invoice-release-live.mjs';
import { issuesLog, issuesRoute, resetIssues } from './issues.mjs';
import { issueRecord, RECORD_PATH, resetIssueRecord } from './issue-record.mjs';
import { liveDecideRoute, ownsLiveDecide, resetLiveDecide } from './live-decide.mjs';
import { CASE_FILES_PATH, resetWorkLive, WORK_LIVE_PATH, workLive, workLiveLog } from './work-live.mjs';
import { INVITATION_PATHS, invitationRoute, resetInvitations } from './invitations.mjs';
import { currentToken, LOGOUT_PATH, logoutRoute, ONBOARDING_PATH, onboardingRoute, ROLE_DASHBOARD_PATH, roleDashboardRoute, SESSION_PATH, SIGNED_OUT_REPLY, signedOut, signInRoute, sessionRoute } from './session.mjs';
import { isMilestoneRequest, isMoneyRequest, moneyRoute } from './money.mjs';
import { isCompletionsPath, milestoneComplete, recordedRead, resetMilestoneComplete } from './milestone-complete.mjs';
import { ALERT_PATH, createAlertsMock } from './alerts.mjs';
import { ASSISTANT_LOG_PATH, ASSISTANT_OPERATIONS, ASSISTANT_UPLOADS_PATH, createAssistantMock } from './assistant.mjs';
import { ownsRetrospective, resetRetrospective, retrospectiveAdmin, retrospectiveRoute } from './retrospective.mjs';
import { resetWorkspace, WORKSPACE_LOG_PATH, WORKSPACE_OPERATIONS, workspaceLog, workspaceRoute } from './workspace.mjs';

const here = dirname(fileURLToPath(import.meta.url));
export const OPENAPI_PATH = join(here, '..', '..', 'architecture', 'packages', 'v7', 'openapi.json');

export const M1_OPERATIONS = ['E-ME', 'E-WORK-LIST', 'E-WORK-ITEM', 'E-WORK-HISTORY', 'E-TASK-CLAIM', 'E-TASK-DECIDE', 'E-EXCEPTIONS', 'E-SETUP-RULES', 'E-SETUP-RULE-SAVE', 'E-EVIDENCE-UPLOAD', 'E-PROJECTS', 'E-PROJECT', 'E-PROJECT-TAB', 'E-TEMPLATES', 'E-TEMPLATE-VERSION', 'E-DELEGATIONS', 'E-DELEGATION', ...CLIENT_OPERATIONS, ...START_OPERATIONS, ...ASSISTANT_OPERATIONS, 'E-DOCUMENT'];
export const PERSONAS = ['finance_lead', 'pm', 'ceo', 'none', 'admin', 'pmo_lead', 'hr', 'hr_lead'];
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
  // F-09: the v7 response items (fixtures/response/work/) are served from the same map; v4 checks read only fixtures/work/.
  const responseDir = join(here, 'fixtures', 'response', 'work');
  const responseFiles = readdirSync(responseDir).filter((name) => name.endsWith('.json'));
  return Object.fromEntries([
    ...files.map((name) => [name.slice(0, -5), JSON.parse(readFileSync(join(dir, name), 'utf8'))]),
    ...responseFiles.map((name) => [name.slice(0, -5), JSON.parse(readFileSync(join(responseDir, name), 'utf8'))]),
  ]);
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

function workResponse(operationId, url, fixtures, work, overrides, persona) {
  const workId = decodeCookie(url.pathname.split('/')[4] ?? '');
  if (workId === NO_ACCESS_WORK_ID) return [404, SCENARIO_BODIES[404]];
  // Only plain ids ("W-1003") pick a per-id file, so "W-1004.history" or other sidecar names never answer as an item.
  const own = (name) => (/^W-\d+$/.test(workId) && Object.hasOwn(work, name) ? work[name] : undefined);
  // F-55: <id>.<persona>.json is that persona's own copy of an item (W-4605 reads differently for hr and hr_lead)
  const forPersona = /^W-\d+$/.test(workId) && Object.hasOwn(work, `${workId}.${persona}`) ? work[`${workId}.${persona}`] : undefined;
  if (operationId === 'E-WORK-ITEM') return [200, overrides.get(workId) ?? forPersona ?? own(workId) ?? fixtures['E-WORK-ITEM']];
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
  const { fixtures, work, overrides, validators, me, runs, persona } = ctx;
  const taskId = decodeCookie(url.pathname.split('/')[4] ?? '');
  // D-155: a task of a demo line run (line-runs.mjs) is decided there; every other task is a fixture's.
  const run = runs.findTask(taskId, persona);
  const found = run ?? findTask(taskId, fixtures, work, overrides);
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

  if (run) return [200, { task_id: task.id, verdict: body.verdict, decided_by: me.name, decided_at: new Date().toISOString(), work_state: runs.decide(task.id, body.verdict, body.note, persona) }];
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

/** D-155: a start made with the demo on creates a line run, and the 201 names its work item; any other reply stands. */
function demoStart(runs, reply, raw, persona, client) {
  if (reply[0] !== 201) return reply;
  const body = JSON.parse(raw);
  const run = runs.start({ key: body.idempotency_key, lineKey: body.line, persona, client: body.line === 'rfp_intake' ? client(body.intake, persona) : undefined });
  return [201, { work_id: run.id, state: 'processing' }];
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

function send(res, status, body, headers = {}) {
  const text = JSON.stringify(body);
  res.writeHead(status, { 'Content-Type': 'application/json', 'Cache-Control': 'no-store', ...headers });
  res.end(text);
}

// `liveStart`: answer Start work's reads and the weekly start in the live shapes (start-live.mjs). The mock run from the command line sets it; the
// v7 contract tests start the server without it and keep the v7 start (start-work.mjs).
export function createMockServer(openapi = JSON.parse(readFileSync(OPENAPI_PATH, 'utf8')), { liveStart = false } = {}) {
  const routes = loadRoutes(openapi);
  const me = Object.fromEntries(PERSONAS.map((p) => [p, readFixture(`me.${p}`)]));
  const fixtures = Object.fromEntries(M1_OPERATIONS.filter((id) => id !== 'E-ME' && id !== 'E-PROJECT-TAB' && !START_OPERATIONS.includes(id) && !ASSISTANT_OPERATIONS.includes(id)).map((id) => [id, readFixture(id)]));
  const work = readWorkFixtures();
  const validators = bodyValidators(openapi);
  const startWork = createStartWorkMock(openapi);
  // work_id -> the item served instead of its fixture; in memory only, cleared on restart and by /__mock/reset.
  const overrides = new Map();
  const alerts = createAlertsMock();
  const assistant = createAssistantMock({ openapi });
  // D-155: the live demo's line runs; they exist only after a start made with the demo on.
  // D-164: a demo RFP that is verified (won) creates the client's project and tells whoever started it.
  const runs = createLineRuns({
    work,
    me,
    raise: (persona, alert) => alerts.raise(persona, alert),
    onVerified: (run) => {
      if (run.lineKey !== 'rfp_intake' || !run.client) return;
      const project = addDemoProject({ client: run.client, run });
      alerts.raise(run.starter, { id: `N-P${project.case_id.slice(2)}`, work_id: run.id, case_id: project.case_id, agent: run.agent, text: `${project.title} is ready to plan`, at: new Date().toISOString(), read: false, reference: run.reference, delivered_via: ['in_app'] });
    },
  });

  return http.createServer((req, res) => {
    const chunks = [];
    req.on('data', (chunk) => chunks.push(chunk));
    req.on('end', () => {
      const rawBytes = Buffer.concat(chunks);
      const raw = rawBytes.toString('utf8');
      const url = new URL(req.url ?? '/', 'http://mock.local');
      // a project may be named by its UUID or its P-nnnn id; the tab and money fixtures are keyed by the P-nnnn form
      url.pathname = normaliseProjectPath(url.pathname);
      const method = (req.method ?? 'GET').toLowerCase();
      // D-155: in the live demo every answer to the API waits a realistic time (demo.mjs); off, there is no wait.
      if (url.pathname.startsWith('/api/')) delayReply(res, delayMs(method, parseCookies(req.headers.cookie)));
      if (method === 'post' && url.pathname === '/__mock/reset') {
        overrides.clear();
        startWork.reset();
        resetStartLive();
        resetReceivedBids();
        resetResponses();
        resetSetup();
        resetTemplates();
        resetDelegations();
        alerts.reset();
        resetWorkspace();
        resetRetrospective();
        resetWorkLive();
        resetEngagementLive();
        resetReleaseLive();
        resetCommercialLive();
        resetCostingLive();
        resetIncomeSchedulesLive();
        resetInvoiceRelease();
        resetInvitations();
        resetIssues();
        resetClients();
        resetDocumentReviews();
        resetMilestoneComplete();
        resetIssueRecord();
        assistant.reset();
        runs.reset();
        resetLiveDecide();
        res.writeHead(204, { 'Cache-Control': 'no-store' });
        return res.end();
      }
      // F-58: after a logout (cookie psl_mock_session=out) every other read and write answers 401, as a signed-out session does.
      if (url.pathname.startsWith('/api/') && url.pathname !== SESSION_PATH && url.pathname !== LOGOUT_PATH && !INVITATION_PATHS.includes(url.pathname) && parseCookies(req.headers.cookie).psl_mock_session === 'out') return send(res, ...SIGNED_OUT_REPLY);
      // F-97: the engagement and planning panels (ids 4650 to 4657, engagement-live.mjs); every other id falls through.
      if (ENGAGEMENT_PATH.test(url.pathname)) {
        const cookies = parseCookies(req.headers.cookie);
        const persona = PERSONAS.includes(cookies.psl_mock_persona) ? cookies.psl_mock_persona : DEFAULT_PERSONA;
        const scenario = req.headers['x-mock-scenario'] ?? cookies.psl_mock_scenario;
        return send(res, ...engagementLive({ method, url, scenario, csrfOk: req.headers['x-csrftoken'] === me[persona].csrf_token, persona, rawBytes }));
      }
      // F-113B: the release gates page (ids 4801 to 4814 and 4890, delivery-release.mjs); every other id falls through to F-113's reads.
      if (RELEASE_PATH.test(url.pathname)) {
        const cookies = parseCookies(req.headers.cookie);
        const persona = PERSONAS.includes(cookies.psl_mock_persona) ? cookies.psl_mock_persona : DEFAULT_PERSONA;
        const scenario = req.headers['x-mock-scenario'] ?? cookies.psl_mock_scenario;
        const reply = releaseLive({ method, url, scenario, csrfOk: req.headers['x-csrftoken'] === me[persona].csrf_token, persona, rawBytes });
        // a dropped connection: the answer never arrives
        if (reply[0] === 'drop') return req.socket.destroy();
        return send(res, ...reply);
      }
      // F-136: the client's response and SOW signature (ids 4660 to 4666, commercial-live.mjs); every other id falls through.
      if (COMMERCIAL_PATH.test(url.pathname)) {
        const cookies = parseCookies(req.headers.cookie);
        const persona = PERSONAS.includes(cookies.psl_mock_persona) ? cookies.psl_mock_persona : DEFAULT_PERSONA;
        const scenario = req.headers['x-mock-scenario'] ?? cookies.psl_mock_scenario;
        return send(res, ...commercialLive({ method, url, scenario, csrfOk: req.headers['x-csrftoken'] === me[persona].csrf_token, persona, rawBytes }));
      }
      // F-90: releasing an invoice (ids 4140 to 4144, invoice-release-live.mjs); every other id falls through.
      if (INVOICE_RELEASE_PATH.test(url.pathname)) {
        const cookies = parseCookies(req.headers.cookie);
        const persona = PERSONAS.includes(cookies.psl_mock_persona) ? cookies.psl_mock_persona : DEFAULT_PERSONA;
        const scenario = req.headers['x-mock-scenario'] ?? cookies.psl_mock_scenario;
        const reply = invoiceReleaseLive({ method, url, scenario, csrfOk: req.headers['x-csrftoken'] === me[persona].csrf_token, persona, rawBytes });
        // a dropped connection: the answer never arrives
        if (reply[0] === 'drop') return req.socket.destroy();
        return send(res, ...reply);
      }
      // F-101: income schedules (ids 4201 to 4207 and 4299, income-schedules-live.mjs); every other id falls through.
      if (INCOME_SCHEDULES_PATH.test(url.pathname)) {
        const cookies = parseCookies(req.headers.cookie);
        const persona = PERSONAS.includes(cookies.psl_mock_persona) ? cookies.psl_mock_persona : DEFAULT_PERSONA;
        const scenario = req.headers['x-mock-scenario'] ?? cookies.psl_mock_scenario;
        const reply = incomeSchedulesLive({ method, url, scenario, csrfOk: req.headers['x-csrftoken'] === me[persona].csrf_token, persona, rawBytes });
        // a dropped connection: the answer never arrives
        if (reply[0] === 'drop') return req.socket.destroy();
        return send(res, ...reply);
      }
      // F-99: the costing sheet (ids 4700 to 4705, costing-live.mjs); every other id falls through.
      if (COSTING_PATH.test(url.pathname)) {
        const cookies = parseCookies(req.headers.cookie);
        const persona = PERSONAS.includes(cookies.psl_mock_persona) ? cookies.psl_mock_persona : DEFAULT_PERSONA;
        const scenario = req.headers['x-mock-scenario'] ?? cookies.psl_mock_scenario;
        return send(res, ...costingLive({ method, url, scenario, csrfOk: req.headers['x-csrftoken'] === me[persona].csrf_token, persona, rawBytes }));
      }
      // F-102: the fixed asset schedule reads (ids 3901 to 3910, assets-live.mjs); every other id falls through.
      if (ASSETS_PATH.test(url.pathname)) {
        const cookies = parseCookies(req.headers.cookie);
        const persona = PERSONAS.includes(cookies.psl_mock_persona) ? cookies.psl_mock_persona : DEFAULT_PERSONA;
        const scenario = req.headers['x-mock-scenario'] ?? cookies.psl_mock_scenario;
        const [status, body, headers] = assetsLive({ method, url, scenario, persona });
        if (Buffer.isBuffer(body)) {
          res.writeHead(status, { 'Cache-Control': 'no-store', ...headers });
          return res.end(body);
        }
        return send(res, status, body);
      }
      // F-103: the cash forecast reads (ids 4301 to 4308); every other id falls through to work-live.mjs.
      if (FORECAST_PATH.test(url.pathname)) {
        const cookies = parseCookies(req.headers.cookie);
        const persona = PERSONAS.includes(cookies.psl_mock_persona) ? cookies.psl_mock_persona : DEFAULT_PERSONA;
        const scenario = req.headers['x-mock-scenario'] ?? cookies.psl_mock_scenario;
        const [status, body, headers] = forecastLive({ method, url, scenario, persona });
        if (Buffer.isBuffer(body)) {
          res.writeHead(status, { 'Cache-Control': 'no-store', ...headers });
          return res.end(body);
        }
        return send(res, status, body);
      }
      // F-119: the project retrospective's meetings, options, actions and closure checklist (retrospective.mjs).
      if (url.pathname.startsWith('/__mock/retrospective/')) {
        const r = retrospectiveAdmin({ method, url, raw });
        if (r) return r[1] === null ? (res.writeHead(r[0]), res.end()) : send(res, ...r);
      }
      if (ownsRetrospective(url.pathname)) {
        const cookies = parseCookies(req.headers.cookie);
        const persona = PERSONAS.includes(cookies.psl_mock_persona) ? cookies.psl_mock_persona : DEFAULT_PERSONA;
        return send(res, ...retrospectiveRoute({ method, url, raw, token: req.headers['x-csrftoken'], expected: me[persona].csrf_token }));
      }
      // F-137 (not in v7): the register read with the owner and proof choices, and the write that records an issue (issue-record.mjs).
      if ((method === 'get' || method === 'post') && RECORD_PATH.test(url.pathname)) {
        const cookies = parseCookies(req.headers.cookie);
        const persona = PERSONAS.includes(cookies.psl_mock_persona) ? cookies.psl_mock_persona : DEFAULT_PERSONA;
        const scenario = req.headers['x-mock-scenario'] ?? cookies.psl_mock_scenario;
        if (scenario && SCENARIO_BODIES[scenario] && (method === 'post' || ['401', '403', '404'].includes(String(scenario)))) return send(res, Number(scenario), SCENARIO_BODIES[scenario]);
        if (method === 'post' && req.headers['x-csrftoken'] !== me[persona].csrf_token) return send(res, 403, CSRF_FAILED);
        const r = issueRecord({ method, url, raw, persona, cookies, canSee: caseVisible });
        return send(res, r.status, r.body);
      }
      // F-111: the issue follow-up reads (work 51xx and the project's issue reads); anything else falls through.
      if (method === 'get') {
        const cookies = parseCookies(req.headers.cookie);
        const reply = issuesRoute({ method, url, scenario: req.headers['x-mock-scenario'] ?? cookies.psl_mock_scenario, persona: PERSONAS.includes(cookies.psl_mock_persona) ? cookies.psl_mock_persona : DEFAULT_PERSONA });
        if (reply) return send(res, ...reply);
      }
      if (method === 'get' && url.pathname === '/__mock/issues-log') return send(res, 200, issuesLog());
      // F-64: the live decision desk (live-decide.mjs): integer work and task ids, the live shapes. Not in v7.
      if (ownsLiveDecide(method, url)) {
        const cookies = parseCookies(req.headers.cookie);
        const persona = PERSONAS.includes(cookies.psl_mock_persona) ? cookies.psl_mock_persona : DEFAULT_PERSONA;
        return send(res, ...liveDecideRoute({ method, url, raw, cookies, scenario: req.headers['x-mock-scenario'] ?? cookies.psl_mock_scenario, token: req.headers['x-csrftoken'], me: me[persona], persona }));
      }
      // F-62: the work list's own rows (live-work.mjs) answer their item read before F-85's handler, which owns every other integer id.
      if (method === 'get' && /^\/api\/v1\/work\/\d+$/.test(url.pathname) && ownsLiveWorkItem(Number(url.pathname.split('/')[4]))) { const r = liveWorkItem({ id: Number(url.pathname.split('/')[4]) }); return send(res, r.status, r.body); }
      // F-63: the live queue counts (live-work.mjs). The scenario cookie answers 401, 403 or 500 here as it does on the list.
      // The factory floor (F-65, overview.mjs) answers the same path for the ceo persona and whenever a psl_mock_overview variant is named.
      if (method === 'get' && url.pathname === '/api/v1/work/counts' && !ownsFloorCounts(parseCookies(req.headers.cookie))) {
        const cookies = parseCookies(req.headers.cookie);
        const persona = PERSONAS.includes(cookies.psl_mock_persona) ? cookies.psl_mock_persona : DEFAULT_PERSONA;
        const scenario = req.headers['x-mock-scenario'] ?? cookies.psl_mock_scenario;
        if (scenario === 'counts_500') return send(res, 500, { code: 'server_error', message: 'Something went wrong on our side.' });
        if (scenario && SCENARIO_BODIES[scenario]) return send(res, Number(scenario), SCENARIO_BODIES[scenario]);
        const r = liveWorkCounts({ persona, dataset: cookies.psl_mock_worklist });
        return send(res, r.status, r.body);
      }
      // F-85: live work item reads (integer ids only) and the case file upload (work-live.mjs); not in v7. v7 ids and v7 case routes fall through.
      if (WORK_LIVE_PATH.test(url.pathname) || CASE_FILES_PATH.test(url.pathname)) {
        const cookies = parseCookies(req.headers.cookie);
        const persona = PERSONAS.includes(cookies.psl_mock_persona) ? cookies.psl_mock_persona : DEFAULT_PERSONA;
        const scenario = req.headers['x-mock-scenario'] ?? cookies.psl_mock_scenario;
        const reply = workLive({ method, url, scenario, csrfOk: req.headers['x-csrftoken'] === me[persona].csrf_token, persona, rawBytes });
        // a dropped connection: the write ran, the answer never arrives
        if (reply[0] === 'drop') return req.socket.destroy();
        return send(res, ...reply);
      }
      // F-61: the alert reads and writes in the live shapes. A scenario status answers every one of them; a write needs the persona's CSRF token.
      if (ALERT_PATH.test(url.pathname)) {
        const cookies = parseCookies(req.headers.cookie);
        const persona = PERSONAS.includes(cookies.psl_mock_persona) ? cookies.psl_mock_persona : DEFAULT_PERSONA;
        const scenario = req.headers['x-mock-scenario'] ?? cookies.psl_mock_scenario;
        if (scenario && SCENARIO_BODIES[scenario]) return send(res, Number(scenario), SCENARIO_BODIES[scenario]);
        if (scenario === 'csrf_failed' && WRITE_METHODS.has(method)) return send(res, 403, CSRF_FAILED);
        if (WRITE_METHODS.has(method) && req.headers['x-csrftoken'] !== me[persona].csrf_token) return send(res, 403, CSRF_FAILED);
        if (demoOn(cookies)) runs.tick();
        const [status, body] = alerts.handle({ method, url, raw, persona, cookies });
        return send(res, status, body);
      }
      // F-86: the live Start work reads and the weekly start (start-live.mjs). The v7 routes of the same paths stay for the v7 contract tests (start without liveStart).
      if (method === 'get' && url.pathname === '/__mock/start-live-log') return send(res, 200, startLiveLog());
      if ((START_LIVE_PATH.test(url.pathname) && method === 'get') || ((url.pathname === START_LIVE_WORK || START_LIVE_MINUTES.test(url.pathname)) && method === 'post')) {
        const cookies = parseCookies(req.headers.cookie);
        if (liveStart) {
          const persona = PERSONAS.includes(cookies.psl_mock_persona) ? cookies.psl_mock_persona : DEFAULT_PERSONA;
          const scenario = req.headers['x-mock-scenario'] ?? cookies.psl_mock_scenario;
          return send(res, ...startLive({ method, url, raw, rawBytes, contentType: req.headers['content-type'], scenario, csrfOk: req.headers['x-csrftoken'] === me[persona].csrf_token, persona }));
        }
      }
      // F-88: the live received RFP (received-bids.mjs); the v7 contract has none of these routes.
      if (method === 'get' && url.pathname === '/__mock/received-bids-log') return send(res, 200, receivedBidsLog());
      if (liveStart && RECEIVED_BIDS_PATH.test(url.pathname)) {
        const cookies = parseCookies(req.headers.cookie);
        const persona = PERSONAS.includes(cookies.psl_mock_persona) ? cookies.psl_mock_persona : DEFAULT_PERSONA;
        const scenario = req.headers['x-mock-scenario'] ?? cookies.psl_mock_scenario;
        return send(res, ...receivedBids({ method, url, raw, rawBytes, contentType: req.headers['content-type'], scenario, csrfOk: req.headers['x-csrftoken'] === me[persona].csrf_token, persona }));
      }
      if (method === 'get' && url.pathname === '/__mock/work-live-log') return send(res, 200, workLiveLog());
      if (method === 'get' && url.pathname === WORKSPACE_LOG_PATH) return send(res, 200, workspaceLog());
      if (method === 'get' && url.pathname === ASSISTANT_LOG_PATH) return send(res, 200, assistant.log());
      // D-161 (proposal, not in v7): the assistant's image upload and its read-back.
      if (url.pathname === ASSISTANT_UPLOADS_PATH || url.pathname.startsWith(`${ASSISTANT_UPLOADS_PATH}/`)) {
        const cookies = parseCookies(req.headers.cookie);
        const persona = PERSONAS.includes(cookies.psl_mock_persona) ? cookies.psl_mock_persona : DEFAULT_PERSONA;
        if (method === 'post' && url.pathname === ASSISTANT_UPLOADS_PATH) {
          if (req.headers['x-csrftoken'] !== me[persona].csrf_token) return send(res, 403, CSRF_FAILED);
          return send(res, ...assistant.upload(rawBytes, req.headers['content-type'], persona, me[persona].assistant_agents ?? []));
        }
        const file = method === 'get' ? assistant.uploadRead(url.pathname.slice(ASSISTANT_UPLOADS_PATH.length + 1), persona) : null;
        if (!file) return send(res, 404, NO_ROUTE);
        res.writeHead(200, { 'Content-Type': file.type, 'Cache-Control': 'no-store' });
        return res.end(file.bytes);
      }
      // F-65 (API 1.24.0, not in v7): the factory floor's two reads (overview.mjs).
      if (method === 'get' && (url.pathname === OVERVIEW_PATH || url.pathname === COUNTS_PATH)) {
        const cookies = parseCookies(req.headers.cookie);
        const scenario = req.headers['x-mock-scenario'] ?? cookies.psl_mock_scenario;
        if (scenario && SCENARIO_BODIES[scenario]) return send(res, Number(scenario), SCENARIO_BODIES[scenario]);
        return send(res, ...floorRead({ pathname: url.pathname, cookies }));
      }
      // F-60: invitation preview and accept (invitations.mjs); unauthenticated, but the current token is required.
      if (method === 'post' && INVITATION_PATHS.includes(url.pathname)) {
        const cookies = parseCookies(req.headers.cookie);
        const persona = PERSONAS.includes(cookies.psl_mock_persona) ? cookies.psl_mock_persona : DEFAULT_PERSONA;
        const scenario = req.headers['x-mock-scenario'] ?? cookies.psl_mock_scenario;
        return send(res, ...invitationRoute({ path: url.pathname, raw, scenario, token: req.headers['x-csrftoken'], expectedToken: currentToken({ cookies, scenario, me: me[persona] }) }));
      }
      // Live session reads and writes (session.mjs): not in v7. Reads need no token; sign-in and sign-out check it.
      if (url.pathname === SESSION_PATH || url.pathname === LOGOUT_PATH || url.pathname === ROLE_DASHBOARD_PATH || url.pathname === ONBOARDING_PATH) {
        const cookies = parseCookies(req.headers.cookie);
        const persona = PERSONAS.includes(cookies.psl_mock_persona) ? cookies.psl_mock_persona : DEFAULT_PERSONA;
        const scenario = req.headers['x-mock-scenario'] ?? cookies.psl_mock_scenario;
        const ctx = { cookies, scenario, me: me[persona], persona, raw, token: req.headers['x-csrftoken'] };
        if (method === 'get' && url.pathname === SESSION_PATH) return send(res, ...sessionRoute(ctx));
        if (method === 'post' && url.pathname === SESSION_PATH) return send(res, ...signInRoute(ctx));
        if (method === 'post' && url.pathname === LOGOUT_PATH) return send(res, ...logoutRoute(ctx));
        if (method === 'get' && url.pathname === ONBOARDING_PATH) {
          if (signedOut(ctx)) return send(res, ...SIGNED_OUT_REPLY);
          return send(res, ...onboardingRoute(ctx));
        }
        if (method === 'get' && url.pathname === ROLE_DASHBOARD_PATH) {
          if (scenario && SCENARIO_BODIES[scenario]) return send(res, Number(scenario), SCENARIO_BODIES[scenario]);
          return send(res, ...roleDashboardRoute({ persona }));
        }
      }
      // F-78 (SCR-19, not in v7): the completion options read and the write (milestone-complete.mjs), and a completion recorded there.
      if ((method === 'get' || method === 'post') && isCompletionsPath(url.pathname)) {
        const cookies = parseCookies(req.headers.cookie);
        const persona = PERSONAS.includes(cookies.psl_mock_persona) ? cookies.psl_mock_persona : DEFAULT_PERSONA;
        const scenario = req.headers['x-mock-scenario'] ?? cookies.psl_mock_scenario;
        if (scenario && SCENARIO_BODIES[scenario] && (method === 'post' || ['401', '403', '404'].includes(String(scenario)))) return send(res, Number(scenario), SCENARIO_BODIES[scenario]);
        if (method === 'post' && req.headers['x-csrftoken'] !== me[persona].csrf_token) return send(res, 403, CSRF_FAILED);
        const r = milestoneComplete({ method, url, raw, persona, cookies, canSee: caseVisible });
        return send(res, r.status, r.body);
      }
      const recordedHere = method === 'get' ? recordedRead(url.pathname, parseCookies(req.headers.cookie)) : undefined;
      if (recordedHere) return send(res, recordedHere.status, recordedHere.body);
      // F-71: one recorded completion of a project (live, not in v7); money.mjs answers it.
      if (method === 'get' && isMilestoneRequest(url)) return send(res, ...moneyRoute({ route: { statuses: ['401', '403', '404'] }, url, req, cookies: parseCookies(req.headers.cookie) }));
      // F-113 (not in v7): the delivery overview and the two reads behind the closure reason (delivery-overview.mjs).
      const delivery = method === 'get' ? deliveryRead({ pathname: url.pathname, idOf }) : null;
      if (delivery) return send(res, ...delivery);
      // F-72 (SCR-08): the live document-review reads and decision (documents.mjs); not in v7.
      if ((method === 'get' || method === 'post') && isLiveDocumentPath(url.pathname)) {
        const cookies = parseCookies(req.headers.cookie);
        const persona = PERSONAS.includes(cookies.psl_mock_persona) ? cookies.psl_mock_persona : DEFAULT_PERSONA;
        const scenario = req.headers['x-mock-scenario'] ?? cookies.psl_mock_scenario;
        if (scenario && SCENARIO_BODIES[scenario] && (method === 'post' || ['401', '403', '404'].includes(String(scenario)))) return send(res, Number(scenario), SCENARIO_BODIES[scenario]);
        if (scenario === 'csrf_failed' && method === 'post') return send(res, 403, CSRF_FAILED);
        if (method === 'post' && req.headers['x-csrftoken'] !== me[persona].csrf_token) return send(res, 403, CSRF_FAILED);
        const r = liveDocumentReview({ method, url, raw, persona, cookies, canSee: caseVisible });
        return send(res, r.status, r.body);
      }
      // F-73 (SCR-35, not in v7): the client group page and the contact history, in the live shape (clients.mjs).
      if (method === 'get' && isClientsExtraPath(url.pathname)) {
        const cookies = parseCookies(req.headers.cookie);
        const persona = PERSONAS.includes(cookies.psl_mock_persona) ? cookies.psl_mock_persona : DEFAULT_PERSONA;
        const scenario = req.headers['x-mock-scenario'] ?? cookies.psl_mock_scenario;
        if (scenario && SCENARIO_BODIES[scenario] && ['401', '403', '404'].includes(String(scenario))) return send(res, Number(scenario), SCENARIO_BODIES[scenario]);
        const r = clients({ url, persona, cookies });
        return send(res, r.status, r.body);
      }
      // F-79 (SCR-36, SCR-20): the live month-end and payments reads (finance.mjs, invoices.mjs); the v7 routes of the same data are retired.
      if (method === 'get' && (url.pathname === '/api/v1/month-end' || url.pathname === '/api/v1/payments')) {
        const cookies = parseCookies(req.headers.cookie);
        const persona = PERSONAS.includes(cookies.psl_mock_persona) ? cookies.psl_mock_persona : DEFAULT_PERSONA;
        const scenario = req.headers['x-mock-scenario'] ?? cookies.psl_mock_scenario;
        if (scenario && SCENARIO_BODIES[scenario] && ['401', '403', '404'].includes(String(scenario))) return send(res, Number(scenario), SCENARIO_BODIES[scenario]);
        const r = (url.pathname === '/api/v1/month-end' ? monthEnd : invoices)({ url, persona, cookies });
        return send(res, r.status, r.body);
      }
      const route = routes.find((r) => r.method === method && r.pattern.test(url.pathname));
      if (!route) return send(res, 404, NO_ROUTE);
      // F-17, F-30: E-WORK-STEP and E-WORK-ASSIGN go to workspace.mjs (fixture scripts, the mock's idempotency map and log).
      if (WORKSPACE_OPERATIONS.includes(route.operationId)) return send(res, ...workspaceRoute({ req, url, raw, cookies: parseCookies(req.headers.cookie), me, work, overrides, operationId: route.operationId }));
      // E-EVIDENCE-UPLOAD has two mock owners: Setup proof cases (C-SETUP-*, F-11, evidence.mjs) and work-item cases (F-09, response.mjs).
      const setupProof = route.operationId === 'E-EVIDENCE-UPLOAD' && decodeURIComponent(url.pathname.split('/')[4] ?? '').startsWith('C-SETUP-');
      // F-47: a third owner, start work (start-work.mjs), for an upload whose kind is a Start work line's evidence_kind for this persona, on a case that line starts on.
      if (route.operationId === 'E-EVIDENCE-UPLOAD' && !setupProof) {
        const cookies = parseCookies(req.headers.cookie);
        const persona = PERSONAS.includes(cookies.psl_mock_persona) ? cookies.psl_mock_persona : DEFAULT_PERSONA;
        if (startWork.ownsUpload(url, raw, persona)) {
          const scenario = req.headers['x-mock-scenario'] ?? cookies.psl_mock_scenario;
          if (scenario && SCENARIO_BODIES[scenario] && route.statuses.includes(String(scenario))) return send(res, Number(scenario), SCENARIO_BODIES[scenario]);
          if (req.headers['x-csrftoken'] !== me[persona].csrf_token) return send(res, 403, CSRF_FAILED);
          return send(res, ...startWork.handle(route.operationId, { url, raw, persona, cookies }));
        }
      }
      if (RESPONSE_OPERATIONS.includes(route.operationId) && !setupProof) {
        return send(res, ...responseRoute(route.operationId, { req, url, raw, cookies: parseCookies(req.headers.cookie), me, work, overrides }));
      }
      // F-26, F-71: the money tab of E-PROJECT-TAB goes to money.mjs (its own persona and scenario check); other tabs stay 501.
      if (isMoneyRequest(route.operationId, url)) return send(res, ...moneyRoute({ route, url, req, cookies: parseCookies(req.headers.cookie) }));
      if (!M1_OPERATIONS.includes(route.operationId)) return send(res, 501, NOT_MOCKED);

      const cookies = parseCookies(req.headers.cookie);
      const persona = PERSONAS.includes(cookies.psl_mock_persona) ? cookies.psl_mock_persona : DEFAULT_PERSONA;
      const scenario = req.headers['x-mock-scenario'] ?? cookies.psl_mock_scenario;
      if (scenario && SCENARIO_BODIES[scenario] && route.statuses.includes(String(scenario))) {
        return send(res, Number(scenario), SCENARIO_BODIES[scenario]);
      }
      // Scenario csrf_failed: the live 403 for a stale token, on /me and on writes (the app must say "press again").
      if (scenario === 'csrf_failed' && (WRITE_METHODS.has(method) || route.operationId === 'E-ME')) return send(res, 403, CSRF_FAILED);
      if (WRITE_METHODS.has(method) && req.headers['x-csrftoken'] !== me[persona].csrf_token) {
        return send(res, 403, CSRF_FAILED);
      }
      const demo = demoOn(cookies);
      if (demo) runs.tick();
      if (ASSISTANT_OPERATIONS.includes(route.operationId)) return send(res, ...assistant.handle({ operationId: route.operationId, url, raw, persona, agents: me[persona].assistant_agents ?? [], demo }));
      if (route.operationId === 'E-ME') return send(res, 200, me[persona]);
      if (route.operationId === 'E-WORK-LIST' && isLiveWorkRequest(url)) { const r = liveWorkList({ url, persona, dataset: cookies.psl_mock_worklist }); return send(res, r.status, r.body); }
      if (route.operationId === 'E-WORK-LIST') { const r = workList({ url, persona, dataset: cookies.psl_mock_worklist, extra: runs.rows(persona) }); return send(res, r.status, r.body); }
      if (CLIENT_OPERATIONS.includes(route.operationId)) { const r = clients({ url, persona, cookies }); return send(res, r.status, r.body); }
      if (route.operationId === 'E-PROJECTS' || route.operationId === 'E-PROJECT') { const r = projects({ operationId: route.operationId, url, persona }); return send(res, r.status, r.body); }
      if (route.operationId === 'E-PROJECT-TAB') { const r = projectTab({ url, persona, cookies }); return send(res, r.status, r.body); }
      if (route.operationId === 'E-EXCEPTIONS') { const r = exceptionsList({ url, persona, cookies }); return send(res, r.status, r.body); }
      if (route.operationId === 'E-SETUP-RULES' || route.operationId === 'E-SETUP-RULE-SAVE') { const r = (route.operationId === 'E-SETUP-RULES' ? setupRules : saveSetupRule)({ url, raw, persona, cookies }); return send(res, r.status, r.body); }
      if (route.operationId === 'E-TEMPLATES' || route.operationId === 'E-TEMPLATE-VERSION') { const r = (route.operationId === 'E-TEMPLATES' ? templatesList : templateVersion)({ url, raw, persona, cookies }); return send(res, r.status, r.body); }
      if (route.operationId === 'E-DELEGATIONS' || route.operationId === 'E-DELEGATION') { const r = (route.operationId === 'E-DELEGATIONS' ? delegationsList : saveDelegation)({ url, raw, persona, cookies }); return send(res, r.status, r.body); }
      if (route.operationId === 'E-EVIDENCE-UPLOAD') { const r = uploadEvidence({ url, raw, persona, cookies }); return send(res, r.status, r.body); }
      if (route.operationId === 'E-WORK-ITEM' && /^\/api\/v1\/work\/\d+$/.test(url.pathname)) { const r = liveWorkItem({ id: Number(url.pathname.split('/')[4]) }); return send(res, r.status, r.body); }
      if (route.operationId === 'E-WORK-ITEM' || route.operationId === 'E-WORK-HISTORY') {
        // F-40 (UX-1-3): a handover item (W-37xx) answers only a persona who can see its project, as the Delivery tab does
        if (/^\/api\/v1\/work\/W-37\d\d(\/|$)/.test(url.pathname) && !caseVisible('P-0101', persona)) return send(res, 404, { code: 'not_found', message: 'We could not find that record.' });
        // D-155: the item and history of a demo line run
        const runId = decodeCookie(url.pathname.split('/')[4] ?? '');
        if (runs.owns(runId)) return send(res, 200, route.operationId === 'E-WORK-ITEM' ? runs.item(runId, persona) : historyPage(runs.history(runId), url.searchParams));
        return send(res, ...workResponse(route.operationId, url, fixtures, work, overrides, persona));
      }
      if (TASK_OPERATIONS.includes(route.operationId)) {
        return send(res, ...taskResponse(route.operationId, url, raw, { fixtures, work, overrides, validators, me: me[persona], runs, persona }));
      }
      if (route.operationId === 'E-WORK-START') {
        const fromDraft = assistant.draftStart(raw, persona);
        if (fromDraft) return send(res, ...fromDraft);
      }
      if (START_OPERATIONS.includes(route.operationId)) {
        const reply = startWork.handle(route.operationId, { url, raw, persona, cookies });
        return send(res, ...(demo && route.operationId === 'E-WORK-START' ? demoStart(runs, reply, raw, persona, startWork.clientLabel) : reply));
      }
      // F-29: the statement of work D-2901 (documents.mjs); every other document falls through to F-23's rule below.
      if (route.operationId === 'E-DOCUMENT') { const r = documentRead({ url, persona, cookies, work, overrides }); if (r) return send(res, r.status, r.body); }
      // F-23: the one document the minutes fixtures name (D-2304 v1); any other document stays unmocked, as before.
      if (route.operationId === 'E-DOCUMENT' && url.pathname !== '/api/v1/documents/D-2304/versions/1') return send(res, 501, NOT_MOCKED);
      return send(res, 200, fixtures[route.operationId]);
    });
  });
}

export function startMockServer({ port = Number(process.env.MOCK_PORT ?? 4010), liveStart = false } = {}) {
  if (process.env.NODE_ENV === 'production') {
    throw new Error('The mock API refuses to start with NODE_ENV=production.');
  }
  const server = createMockServer(undefined, { liveStart });
  return new Promise((resolve, reject) => {
    server.once('error', reject);
    server.listen(port, '127.0.0.1', () => resolve(server));
  });
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  try {
    // The running mock serves the live Start work (F-86); the v7 contract tests start it without.
    const server = await startMockServer({ liveStart: true });
    const { port } = server.address();
    console.log(`Mock API (sample data) on http://127.0.0.1:${port}/api/v1`);
  } catch (error) {
    console.error(error.message);
    process.exit(1);
  }
}
