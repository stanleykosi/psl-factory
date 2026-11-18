// Contract mock for F-17's E-WORK-STEP and F-30's E-WORK-ASSIGN (PROPOSAL D-LINE-WORKSPACE). Local use only: nothing is sent to anyone.
//
// E-WORK-ASSIGN (set an owner): scenario, CSRF, the item (404), the body against the v7 request schema, the 2000-character
// note and a person_id outside the served item's `assign.candidates` (422 naming the fields), then cookie psl_mock_assign =
// stale (the item moves on, then 409) | invalid (422 naming person_id) | uncertain (500, nothing written) | uncertain_written
// (written, then 500); then expected_revision (409). A 200 serves <id>.next.json when present, else the item one revision
// higher. There is no idempotency key on this operation (not in the typed body): each request is in the log's `assignments`.
// F-36 (RFP assignment, PROPOSAL overlay mock/proposals/rfp-assign.json): an item without a workspace is checked against its own
// `revision`. An item whose `assign` carries roles or evidence_kind takes the overlay request keys (acting_role, evidence_id,
// case_revision): an acting_role outside `roles` or an evidence_id not uploaded on the item's case is 422, a stale case_revision
// 409. fixtures/work/<id>.assign.json ({status, written}) scripts a failure after the revision check.
//
// Order of checks: scenario (numeric, declared by the operation), CSRF, the item (404), the body against the v7
// request schema and the 2000-character note (422 naming the fields), the step key in the served item's workspace.steps (404), a key seen
// before (the stored reply again, logged as a replay, no second send), expected_revision (409), then the fixture's
// script. fixtures/work/<id>.steps.json (loaded with the other work fixtures) maps a step key to {status, body, next}; the default is 200 `done`.
// A 200 swaps in <id>.next.json when present, else serves the item with its
// revision and workspace.revision one higher; a scripted failure with next: true swaps it in once
// (the step then succeeds on that version). Overrides live in the shared map, cleared by POST /__mock/reset.
// The idempotency map is the mock's only: it proves one send per key on the mock, not the backend's promise.
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

import Ajv2020 from 'ajv/dist/2020.js';
import addFormats from 'ajv-formats';

import { evidenceIssued } from './response.mjs';
import { DEFAULT_PERSONA, OPENAPI_PATH, PERSONAS, SCENARIO_BODIES } from './server.mjs';

export const WORKSPACE_OPERATIONS = ['E-WORK-STEP', 'E-WORK-ASSIGN'];
export const WORKSPACE_LOG_PATH = '/__mock/workspace-log';

const CSRF_FAILED = { code: 'csrf_failed', message: 'Your session check failed. Reload and try again.' };
const NO_STEP = { code: 'not_found', message: 'That step is not offered on this item.' };
const NOTE_MAX = 2000;
const SERVER = { code: 'server_error', message: 'The mock answered with a scripted server error.' };

const overlay = JSON.parse(readFileSync(join(dirname(fileURLToPath(import.meta.url)), 'proposals', 'rfp-assign.json'), 'utf8'));

let compiled;
function validators(operationId = 'E-WORK-STEP') {
  if (!compiled) {
    compiled = {};
    const openapi = JSON.parse(readFileSync(OPENAPI_PATH, 'utf8'));
    const ajv = new Ajv2020({ allErrors: true, strict: true });
    addFormats(ajv);
    for (const ops of Object.values(openapi.paths)) {
      for (const op of Object.values(ops)) {
        if (!WORKSPACE_OPERATIONS.includes(op?.operationId)) continue;
        const replies = {};
        for (const [status, reply] of Object.entries(op.responses)) {
          const schema = reply.content?.['application/json']?.schema;
          if (schema) replies[status] = ajv.compile(schema);
        }
        const schema = op.requestBody.content['application/json'].schema;
        // F-36: the typed request plus the proposed keys, for an item whose `assign` carries the overlay
        const withOverlay = { ...schema, properties: { ...schema.properties, ...overlay.request_extra.properties } };
        compiled[op.operationId] = { request: ajv.compile(schema), overlayRequest: ajv.compile(withOverlay), replies };
      }
    }
  }
  return compiled[operationId];
}

// idempotency_key -> the reply first given; and every request, in order, for GET /__mock/workspace-log.
const replies = new Map();
const log = [];
// E-WORK-ASSIGN: every request that reached the write, in order ({work_id, person_id, expected_revision, status, written}).
const assignments = [];

/** Work ids whose assignment was written (F-36): My work's Unassigned list drops them. */
export const assignedWorkIds = () => new Set(assignments.filter((entry) => entry.written).map((entry) => entry.work_id));

export function resetWorkspace() {
  replies.clear();
  log.length = 0;
  assignments.length = 0;
}

/** The log: each request's key, step, item ids and status; `replay` marks an answer from the map (no send). */
export function workspaceLog() {
  const sends = {};
  for (const entry of log) if (!entry.replay) sends[entry.idempotency_key] = (sends[entry.idempotency_key] ?? 0) + 1;
  return { entries: log.map((entry) => ({ ...entry })), sends, assignments: assignments.map((entry) => ({ ...entry })) };
}

function decodeSegment(value) {
  try {
    return decodeURIComponent(value);
  } catch {
    return value;
  }
}

const fieldNames = (errors) => [...new Set(errors.map((e) => e.params.missingProperty ?? e.params.additionalProperty ?? (e.instancePath.split('/')[1] || 'body')))];

/** The item one revision on (its workspace too, when it has one). */
const bumped = (item) => ({ ...structuredClone(item), revision: item.revision + 1, ...(item.workspace ? { workspace: { ...structuredClone(item.workspace), revision: item.workspace.revision + 1 } } : {}) });

/** E-WORK-ASSIGN (F-30, F-36). */
function handleAssign({ req, url, raw, cookies, me, work, overrides }) {
  const persona = PERSONAS.includes(cookies.psl_mock_persona) ? cookies.psl_mock_persona : DEFAULT_PERSONA;
  const { request: typed, overlayRequest, replies: declared } = validators('E-WORK-ASSIGN');
  const scenario = req.headers['x-mock-scenario'] ?? cookies.psl_mock_scenario;
  if (scenario && SCENARIO_BODIES[scenario] && declared[String(scenario)]) return { status: Number(scenario), body: SCENARIO_BODIES[scenario] };
  if (req.headers['x-csrftoken'] !== me[persona].csrf_token) return { status: 403, body: CSRF_FAILED };

  const workId = decodeSegment(url.pathname.split('/')[4] ?? '');
  const item = /^W-\d+$/.test(workId) ? (overrides.get(workId) ?? work[workId]) : undefined;
  if (!item) return { status: 404, body: SCENARIO_BODIES[404] };

  let body;
  try {
    body = JSON.parse(raw);
  } catch {
    return { status: 422, body: { code: 'invalid', message: 'Check these fields: body.', fields: [{ name: 'body', message: 'The request body is not JSON.' }] } };
  }
  const invalid = (names) => ({ status: 422, body: { code: 'invalid', message: `Check these fields: ${names.join(', ')}.`, fields: names.map((name) => ({ name, message: `Check ${name}.` })) } });
  const request = item.assign?.roles !== undefined || item.assign?.evidence_kind !== undefined ? overlayRequest : typed;
  const valid = request(body);
  const tooLong = typeof body?.note === 'string' && body.note.length > NOTE_MAX;
  const candidate = valid ? item.assign?.candidates?.find((c) => c.person_id === body.person_id) : undefined;
  const badRole = valid && body.acting_role !== undefined && !(item.assign?.roles ?? []).some((r) => r.role === body.acting_role);
  const badProof = valid && body.evidence_id !== undefined && !evidenceIssued(item.case_id, body.evidence_id);
  if (!valid || tooLong || !candidate || badRole || badProof) {
    return invalid([...new Set([...(valid ? [] : fieldNames(request.errors)), ...(tooLong ? ['note'] : []), ...(valid && !candidate ? ['person_id'] : []), ...(badRole ? ['acting_role'] : []), ...(badProof ? ['evidence_id'] : [])])]);
  }
  const entry = { work_id: workId, person_id: body.person_id, expected_revision: body.expected_revision, ...(body.acting_role !== undefined ? { acting_role: body.acting_role } : {}), ...(body.evidence_id !== undefined ? { evidence_id: body.evidence_id } : {}) };
  const cookie = cookies.psl_mock_assign;
  if (cookie === 'invalid') return invalid(['person_id']);
  let current = item;
  if (cookie === 'stale') {
    current = bumped(item);
    overrides.set(workId, current);
  }
  if (body.expected_revision !== (current.workspace?.revision ?? current.revision)) {
    assignments.push({ ...entry, status: 409, written: false });
    return { status: 409, body: SCENARIO_BODIES[409] };
  }
  if (body.case_revision !== undefined && body.case_revision !== current.case_revision) {
    assignments.push({ ...entry, status: 409, written: false });
    return { status: 409, body: SCENARIO_BODIES[409] };
  }
  // F-36: a scripted failure; `written` says whether the assignment was recorded before the error
  const script = cookie === 'uncertain_written' ? { status: 500, written: true } : cookie === 'uncertain' ? { status: 500, written: false } : work[`${workId}.assign`];
  if (script && !script.written) {
    assignments.push({ ...entry, status: script.status, written: false });
    return { status: script.status, body: SERVER };
  }
  const next = work[`${workId}.next`];
  const served = next ? structuredClone(next) : bumped(current);
  // the owner is set, so the served item no longer offers an assignment
  delete served.assign;
  overrides.set(workId, served);
  if (script) {
    assignments.push({ ...entry, status: script.status, written: true });
    return { status: script.status, body: SERVER };
  }
  assignments.push({ ...entry, status: 200, written: true });
  return { status: 200, body: { work_id: workId, state: served.state, revision: served.workspace?.revision ?? served.revision, assigned_to: candidate.name } };
}

function handle({ req, url, raw, cookies, me, work, overrides, operationId }) {
  if (operationId === 'E-WORK-ASSIGN') return handleAssign({ req, url, raw, cookies, me, work, overrides });
  const persona = PERSONAS.includes(cookies.psl_mock_persona) ? cookies.psl_mock_persona : DEFAULT_PERSONA;
  const { request } = validators();
  const scenario = req.headers['x-mock-scenario'] ?? cookies.psl_mock_scenario;
  if (scenario && SCENARIO_BODIES[scenario] && validators().replies[String(scenario)]) return { status: Number(scenario), body: SCENARIO_BODIES[scenario] };
  if (req.headers['x-csrftoken'] !== me[persona].csrf_token) return { status: 403, body: CSRF_FAILED };

  const workId = decodeSegment(url.pathname.split('/')[4] ?? '');
  const item = /^W-\d+$/.test(workId) ? (overrides.get(workId) ?? work[workId]) : undefined;
  if (!item) return { status: 404, body: SCENARIO_BODIES[404] };

  let body;
  try {
    body = JSON.parse(raw);
  } catch {
    return { status: 422, body: { code: 'invalid', message: 'Check these fields: body.', fields: [{ name: 'body', message: 'The request body is not JSON.' }] } };
  }
  const valid = request(body);
  const tooLong = typeof body?.note === 'string' && body.note.length > NOTE_MAX;
  if (!valid || tooLong) {
    const names = [...new Set([...(valid ? [] : fieldNames(request.errors)), ...(tooLong ? ['note'] : [])])];
    return { status: 422, body: { code: 'invalid', message: `Check these fields: ${names.join(', ')}.`, fields: names.map((name) => ({ name, message: `Check ${name}.` })) } };
  }
  const entry = { work_id: workId, step: body.step, idempotency_key: body.idempotency_key, item_ids: body.item_ids, expected_revision: body.expected_revision };
  const stored = replies.get(body.idempotency_key);
  if (stored) {
    log.push({ ...entry, status: stored.status, replay: true });
    return stored;
  }
  const workspace = item.workspace;
  if (!workspace?.steps?.some((s) => s.key === body.step)) {
    log.push({ ...entry, status: 404, replay: false });
    return { status: 404, body: NO_STEP };
  }
  if (body.expected_revision !== workspace.revision) {
    log.push({ ...entry, status: 409, replay: false });
    return { status: 409, body: SCENARIO_BODIES[409] };
  }

  // F-28: a step that carries inputs.audience takes <id>.next.<audience> when one exists (internal minutes end filed); else <id>.next.
  const audience = typeof body.inputs?.audience === 'string' ? work[`${workId}.next.${body.inputs.audience}`] : undefined;
  const scripted = work[`${workId}.steps`]?.[body.step];
  // F-31: a script's `serve` names another fixture to serve under this id (the registered engagement is served under the id that was registered).
  const servedAs = scripted?.serve ? { ...structuredClone(work[scripted.serve]), id: workId } : undefined;
  const next = servedAs ?? audience ?? work[`${workId}.next`];
  // A scripted failure that swaps in the next version (a redraft: 409) happens once; the step then succeeds on it.
  const replayed = scripted?.next === true && scripted.status !== 200 && next !== undefined && item.revision === next.revision;
  const script = !scripted || replayed ? { status: 200, body: { outcome: 'done' }, next: false } : scripted;
  let reply;
  if (script.status === 200) {
    const served = next && script.next !== false ? structuredClone(next) : { ...structuredClone(item), revision: item.revision + 1, workspace: { ...structuredClone(workspace), revision: workspace.revision + 1 } };
    overrides.set(workId, served);
    reply = { status: 200, body: { work_id: workId, state: served.state, revision: served.workspace?.revision ?? served.revision, ...script.body } };
  } else {
    if (next && script.next) overrides.set(workId, structuredClone(next));
    reply = { status: script.status, body: script.body ?? (script.status >= 500 ? SERVER : SCENARIO_BODIES[script.status]) };
  }
  log.push({ ...entry, status: reply.status, replay: false });
  replies.set(body.idempotency_key, reply);
  return reply;
}

/** One E-WORK-STEP or E-WORK-ASSIGN reply, validated against its v7 schema (an undeclared 5xx is not). */
export function workspaceRoute(args) {
  const { status, body } = handle(args);
  const operationId = args.operationId ?? 'E-WORK-STEP';
  const validate = validators(operationId).replies[String(status)];
  if (validate && !validate(body)) {
    return [500, { code: 'mock_invalid_reply', message: `The mock's ${operationId} ${status} reply does not match v7.` }];
  }
  return [status, body];
}
