// Contract mock for F-09's writes: E-EVIDENCE-UPLOAD, E-RESPONSE and E-WORK-ACTION, checked against the v7
// proposal (D-RESPONSE-VIEW r2, D-WORK-ACTIONS-VIEW r2) while the base mock stays on v4. Local use only:
// nothing is sent to anyone, and evidence lives in memory until /__mock/reset.
//
// Order of checks: scenario (numeric, or the F-09-only `record-then-fail`: apply the effect, then answer 502),
// CSRF, persona `none` (403), the record (404), the body against the v7 request schema (422), the rules (422),
// revisions (409), the grant from the fixture's flags (403), then success. Every reply is validated against
// its declared v7 schema before it is sent.
// Success: an upload stores the evidence and bumps the served item's case_revision through `overrides`; a
// response swaps in fixtures/response/<work_id>.recorded.json with `recorded` filled from the request; a
// reconcile swaps in fixtures/response/<work_id>.<outcome>.json. A sidecar whose `recorded` has a `summary` is
// board (r2) data and its 200 carries revision, recorded and next; otherwise the 200 is the bare
// {task_id, work_state} and the reloaded item carries only recorded.by and .at.
import { createHash } from 'node:crypto';
import { readdirSync, readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

import Ajv2020 from 'ajv/dist/2020.js';
import addFormats from 'ajv-formats';

import { DEFAULT_PERSONA, OPENAPI_PATH, PERSONAS, SCENARIO_BODIES } from './server.mjs';

const here = dirname(fileURLToPath(import.meta.url));
export const RESPONSE_OPERATIONS = ['E-EVIDENCE-UPLOAD', 'E-RESPONSE', 'E-WORK-ACTION'];

const CSRF_FAILED = { code: 'csrf_failed', message: 'Your session check failed. Reload and try again.' };
const NOT_MOCKED = { code: 'not_mocked', message: 'Not available in the mock yet.' };
const MOCK_LOST = { code: 'mock_lost', message: 'The mock dropped this reply.' };
const RECORD_THEN_FAIL = 'record-then-fail';
const NOTE_MAX = 2000;
const invalid = (fields) => [422, { code: 'invalid', message: `Check these fields: ${[...new Set(fields)].join(', ')}.` }];

let compiled;
/** Request and reply validators for the three operations, compiled once from the v7 file. */
function validators() {
  if (compiled) return compiled;
  const openapi = JSON.parse(readFileSync(OPENAPI_PATH, 'utf8'));
  const ajv = new Ajv2020({ allErrors: true, strict: true });
  addFormats(ajv);
  compiled = {};
  for (const ops of Object.values(openapi.paths)) {
    for (const op of Object.values(ops)) {
      if (!RESPONSE_OPERATIONS.includes(op?.operationId)) continue;
      const replies = {};
      for (const [status, reply] of Object.entries(op.responses)) {
        const schema = reply.content?.['application/json']?.schema;
        if (schema) replies[status] = ajv.compile(schema);
      }
      compiled[op.operationId] = { request: ajv.compile(op.requestBody.content['application/json'].schema), replies };
    }
  }
  return compiled;
}

let sidecars;
/** fixtures/response/*.json by file name without .json, e.g. "W-1601.recorded". */
function readSidecars() {
  if (sidecars) return sidecars;
  const dir = join(here, 'fixtures', 'response');
  const files = readdirSync(dir).filter((name) => name.endsWith('.json'));
  sidecars = Object.fromEntries(files.map((name) => [name.slice(0, -5), JSON.parse(readFileSync(join(dir, name), 'utf8'))]));
  return sidecars;
}

// case_id -> evidence ids this mock issued; cleared by resetResponses().
const evidence = new Map();

export function resetResponses() {
  evidence.clear();
}

/** The items the mock serves now: per-id files, then overrides. */
function servedItems(work, overrides) {
  const items = new Map();
  for (const [name, body] of Object.entries(work)) if (/^W-\d+$/.test(name)) items.set(name, body);
  for (const [workId, body] of overrides) items.set(workId, body);
  return items;
}

function errorFields(errors) {
  return errors.map((e) => e.params.missingProperty ?? e.params.additionalProperty ?? (e.instancePath.split('/')[1] || 'body'));
}

function decodeSegment(value) {
  try {
    return decodeURIComponent(value);
  } catch {
    return value;
  }
}

const issued = (caseId, id) => typeof id === 'string' && (evidence.get(caseId)?.has(id) ?? false);
const responseTasks = (item) => item.tasks.filter((t) => t.response);

/** A case can hold several work items; its revision is theirs, and an upload moves all of them on. */
function upload(body, ctx) {
  const { items, caseId, overrides } = ctx;
  const inCase = [...items].filter(([, item]) => item.case_id === caseId);
  if (inCase.length === 0) return [404, SCENARIO_BODIES[404]];
  const all = inCase.map(([, item]) => item);
  const kinds = all.flatMap((item) => [...responseTasks(item).map((t) => t.response.evidence_kind), item.reconcile?.evidence_kind]).filter(Boolean);
  const fields = [];
  if (!kinds.includes(body.kind)) fields.push('kind');
  const bytes = /^[A-Za-z0-9+/]+={0,2}$/.test(body.content_base64) ? Buffer.from(body.content_base64, 'base64') : Buffer.alloc(0);
  if (bytes.length === 0) fields.push('content_base64');
  if (fields.length) return invalid(fields);
  const current = all[0].case_revision;
  if (body.case_revision !== current) return [409, SCENARIO_BODIES[409]];
  const granted = all.some(
    (item) => responseTasks(item).some((t) => t.you_can_act) || (Boolean(item.reconcile) && (item.allowed_actions ?? []).includes('reconcile')),
  );
  if (!granted) return [403, SCENARIO_BODIES[403]];

  const ids = evidence.get(caseId) ?? new Set();
  const evidenceId = `EV-${caseId}-${ids.size + 1}`;
  ids.add(evidenceId);
  evidence.set(caseId, ids);
  const caseRevision = current + 1;
  for (const [workId, item] of inCase) overrides.set(workId, { ...item, case_revision: caseRevision });
  return [200, { evidence_id: evidenceId, sha256: createHash('sha256').update(bytes).digest('hex'), case_revision: caseRevision }];
}

function respond(body, ctx) {
  const { items, taskId, overrides, me } = ctx;
  const found = [...items].map(([workId, item]) => ({ workId, item, task: item.tasks.find((t) => t.id === taskId) })).find((f) => f.task);
  if (!found) return [404, SCENARIO_BODIES[404]];
  const { workId, item, task } = found;
  const response = task.response;
  if (!response) return [403, SCENARIO_BODIES[403]];
  const fields = [];
  if (body.attested !== true) fields.push('attested');
  if (!issued(item.case_id, body.evidence_id)) fields.push('evidence_id');
  if ((body.evidence_ids ?? []).some((id) => !issued(item.case_id, id))) fields.push('evidence_ids');
  if (!response.responders.some((r) => r.id === body.who)) fields.push('who');
  if (!response.actions.some((a) => a.value === body.action)) fields.push('action');
  if (body.version_id !== undefined && !(response.versions ?? []).some((v) => v.id === body.version_id)) fields.push('version_id');
  if (body.received_via !== undefined && !(response.channels ?? []).some((c) => c.value === body.received_via)) fields.push('received_via');
  if ((body.note?.length ?? 0) > NOTE_MAX) fields.push('note');
  if (fields.length) return invalid(fields);
  if (body.expected_revision !== task.revision) return [409, SCENARIO_BODIES[409]];
  if (body.case_revision !== undefined && body.case_revision !== item.case_revision) return [409, SCENARIO_BODIES[409]];
  if (!task.you_can_act) return [403, SCENARIO_BODIES[403]];

  const sidecar = readSidecars()[`${workId}.recorded`];
  if (!sidecar) return [501, NOT_MOCKED];
  const next = structuredClone(sidecar);
  if (item.case_revision !== undefined) next.case_revision = item.case_revision;
  const done = next.tasks.find((t) => t.id === task.id);
  const board = done.response.recorded?.summary;
  const recorded = { by: { name: me.name, role: me.roles[0], is_you: true }, at: new Date().toISOString() };
  if (board) {
    Object.assign(recorded, { responded_at: body.responded_at, proof_count: 1 + (body.evidence_ids?.length ?? 0), summary: board });
    if (body.received_via) recorded.received_via = body.received_via;
  }
  done.response.recorded = recorded;
  overrides.set(workId, next);
  if (!board) return [200, { task_id: task.id, work_state: next.state }];
  const result = { task_id: task.id, work_state: next.state, revision: done.revision, recorded };
  if (done.response.next) result.next = done.response.next;
  return [200, result];
}

function act(body, ctx) {
  const { items, workId, overrides } = ctx;
  const item = items.get(workId);
  if (!item) return [404, SCENARIO_BODIES[404]];
  if (body.action !== 'reconcile') return [501, NOT_MOCKED];
  const fields = [];
  if (!body.outcome || !(item.reconcile?.outcomes ?? []).includes(body.outcome)) fields.push('outcome');
  if (body.outcome === 'delivered' && !issued(item.case_id, body.evidence_id)) fields.push('evidence_id');
  if (fields.length) return invalid(fields);
  if (body.expected_revision !== item.revision) return [409, SCENARIO_BODIES[409]];
  if (body.case_revision !== undefined && body.case_revision !== item.case_revision) return [409, SCENARIO_BODIES[409]];
  if (!(item.allowed_actions ?? []).includes(body.action)) return [403, SCENARIO_BODIES[403]];
  const sidecar = readSidecars()[`${workId}.${body.outcome}`];
  if (!sidecar) return [501, NOT_MOCKED];
  overrides.set(workId, structuredClone(sidecar));
  return [200, { work_id: workId, state: sidecar.state, revision: sidecar.revision }];
}

function handle(operationId, { req, url, raw, cookies, me, work, overrides }) {
  const persona = PERSONAS.includes(cookies.psl_mock_persona) ? cookies.psl_mock_persona : DEFAULT_PERSONA;
  const { request, replies } = validators()[operationId];
  const scenario = req.headers['x-mock-scenario'] ?? cookies.psl_mock_scenario;
  if (scenario && scenario !== RECORD_THEN_FAIL && SCENARIO_BODIES[scenario] && replies[String(scenario)]) {
    return [Number(scenario), SCENARIO_BODIES[scenario]];
  }
  if (req.headers['x-csrftoken'] !== me[persona].csrf_token) return [403, CSRF_FAILED];
  if (persona === 'none') return [403, SCENARIO_BODIES[403]];

  const segment = decodeSegment(url.pathname.split('/')[4] ?? '');
  const items = servedItems(work, overrides);
  const exists =
    operationId === 'E-EVIDENCE-UPLOAD'
      ? [...items.values()].some((item) => item.case_id === segment)
      : operationId === 'E-RESPONSE'
        ? [...items.values()].some((item) => item.tasks.some((t) => t.id === segment))
        : items.has(segment);
  if (!exists) return [404, SCENARIO_BODIES[404]];

  let body;
  try {
    body = JSON.parse(raw);
  } catch {
    return invalid(['body']);
  }
  if (!request(body)) return invalid(errorFields(request.errors));

  const ctx = { items, overrides, me: me[persona], caseId: segment, taskId: segment, workId: segment };
  const result = operationId === 'E-EVIDENCE-UPLOAD' ? upload(body, ctx) : operationId === 'E-RESPONSE' ? respond(body, ctx) : act(body, ctx);
  if (scenario === RECORD_THEN_FAIL && operationId !== 'E-EVIDENCE-UPLOAD' && result[0] === 200) return [502, MOCK_LOST];
  return result;
}

/** One reply for an F-09 operation, validated against its v7 schema (undeclared 501 and 502 are not). */
export function responseRoute(operationId, args) {
  const [status, body] = handle(operationId, args);
  const validate = validators()[operationId].replies[String(status)];
  if (validate && !validate(body)) {
    return [500, { code: 'mock_invalid_reply', message: `The mock's ${operationId} ${status} reply does not match v7.` }];
  }
  return [status, body];
}
