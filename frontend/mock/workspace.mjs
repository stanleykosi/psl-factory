// Contract mock for F-17's E-WORK-STEP (PROPOSAL D-LINE-WORKSPACE). Local use only: nothing is sent to anyone.
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

import Ajv2020 from 'ajv/dist/2020.js';
import addFormats from 'ajv-formats';

import { DEFAULT_PERSONA, OPENAPI_PATH, PERSONAS, SCENARIO_BODIES } from './server.mjs';

export const WORKSPACE_OPERATIONS = ['E-WORK-STEP'];
export const WORKSPACE_LOG_PATH = '/__mock/workspace-log';

const CSRF_FAILED = { code: 'csrf_failed', message: 'Your session check failed. Reload and try again.' };
const NO_STEP = { code: 'not_found', message: 'That step is not offered on this item.' };
const NOTE_MAX = 2000;
const SERVER = { code: 'server_error', message: 'The mock answered with a scripted server error.' };

let compiled;
function validators() {
  if (compiled) return compiled;
  const openapi = JSON.parse(readFileSync(OPENAPI_PATH, 'utf8'));
  const ajv = new Ajv2020({ allErrors: true, strict: true });
  addFormats(ajv);
  for (const ops of Object.values(openapi.paths)) {
    for (const op of Object.values(ops)) {
      if (op?.operationId !== 'E-WORK-STEP') continue;
      const replies = {};
      for (const [status, reply] of Object.entries(op.responses)) {
        const schema = reply.content?.['application/json']?.schema;
        if (schema) replies[status] = ajv.compile(schema);
      }
      compiled = { request: ajv.compile(op.requestBody.content['application/json'].schema), replies };
    }
  }
  return compiled;
}

// idempotency_key -> the reply first given; and every request, in order, for GET /__mock/workspace-log.
const replies = new Map();
const log = [];

export function resetWorkspace() {
  replies.clear();
  log.length = 0;
}

/** The log: each request's key, step, item ids and status; `replay` marks an answer from the map (no send). */
export function workspaceLog() {
  const sends = {};
  for (const entry of log) if (!entry.replay) sends[entry.idempotency_key] = (sends[entry.idempotency_key] ?? 0) + 1;
  return { entries: log.map((entry) => ({ ...entry })), sends };
}

function decodeSegment(value) {
  try {
    return decodeURIComponent(value);
  } catch {
    return value;
  }
}

const fieldNames = (errors) => [...new Set(errors.map((e) => e.params.missingProperty ?? e.params.additionalProperty ?? (e.instancePath.split('/')[1] || 'body')))];

function handle({ req, url, raw, cookies, me, work, overrides }) {
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

  const next = work[`${workId}.next`];
  const scripted = work[`${workId}.steps`]?.[body.step];
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

/** One E-WORK-STEP reply, validated against its v7 schema (an undeclared 5xx is not). */
export function workspaceRoute(args) {
  const { status, body } = handle(args);
  const validate = validators().replies[String(status)];
  if (validate && !validate(body)) {
    return [500, { code: 'mock_invalid_reply', message: `The mock's E-WORK-STEP ${status} reply does not match v7.` }];
  }
  return [status, body];
}
