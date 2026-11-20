// Contract mock for F-09's writes: E-EVIDENCE-UPLOAD, E-RESPONSE and E-WORK-ACTION, checked against the v7
// proposal (D-RESPONSE-VIEW r2, D-WORK-ACTIONS-VIEW r2) while the base mock stays on v4; and F-18's
// E-RFP-OUTCOME (D-RFP-OUTCOME r2, proposed) with team input on E-RESPONSE. Local use only: nothing is sent to
// anyone, and evidence lives in memory until /__mock/reset.
//
// Order of checks: scenario (numeric, or `record-then-fail` on a write: apply the effect, then answer 502),
// CSRF, persona `none` (403), the record (404), the body against the v7 request schema (422), the rules (422),
// revisions (409), the grant from the fixture's flags (403), then success. Every reply is validated against
// its declared v7 schema before it is sent.
// Success: an upload stores the evidence and bumps the served item's case_revision through `overrides`; a
// response swaps in fixtures/response/<work_id>.recorded.json with `recorded` filled from the request; a
// reconcile swaps in fixtures/response/<work_id>.<outcome>.json; an RFP outcome swaps in the recorded item of
// its result (W-2105 won, W-2106 lost, W-2107 pending, W-2108 unknown) under the item's own id, case and next
// revision, with recorded.at and .by from the request. A follow-up send (E-RFP-FOLLOWUP) answers sent and serves
// <work_id>.sent.json when present (else the draft marked sent); W-2111 answers effect_uncertain and serves its
// draft in that state; W-2112's first send answers 409 and serves W-2112.next.json. A repeated idempotency_key
// returns the stored reply with no second effect. Nothing is emailed: the mock only changes what it serves. A sidecar whose `recorded` has a `summary` is
// board (r2) data and its 200 carries revision, recorded and next; otherwise the 200 is the bare
// {task_id, work_state} and the reloaded item carries only recorded.by and .at.
// F-40: a support-handover task takes `gaps` (PROPOSAL G-48-1, mock only: required and non-empty with changes_requested, refused with any
// other action, else 422 `gaps`), and a 200 swaps in <work_id>.recorded.<action> when present, else <work_id>.recorded.
import { createHash } from 'node:crypto';
import { readdirSync, readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

import Ajv2020 from 'ajv/dist/2020.js';
import addFormats from 'ajv-formats';

import { DEFAULT_PERSONA, OPENAPI_PATH, PERSONAS, SCENARIO_BODIES } from './server.mjs';

const here = dirname(fileURLToPath(import.meta.url));
export const RESPONSE_OPERATIONS = ['E-EVIDENCE-UPLOAD', 'E-RESPONSE', 'E-WORK-ACTION', 'E-RFP-OUTCOME', 'E-RFP-FOLLOWUP'];

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
// "<work_id> <idempotency_key>" -> the stored E-RFP-FOLLOWUP reply; work ids whose one-time 409 was served.
const sends = new Map();
const stalled = new Set();

export function resetResponses() {
  evidence.clear();
  sends.clear();
  stalled.clear();
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
/** F-36: whether this evidence id was uploaded on that case (the assignment's proof). */
export const evidenceIssued = issued;
const responseTasks = (item) => item.tasks.filter((t) => t.response);

/** A case can hold several work items; its revision is theirs, and an upload moves all of them on. */
function upload(body, ctx) {
  const { items, caseId, overrides } = ctx;
  const inCase = [...items].filter(([, item]) => item.case_id === caseId);
  if (inCase.length === 0) return [404, SCENARIO_BODIES[404]];
  const all = inCase.map(([, item]) => item);
  // F-31: a workspace step's evidence field (plan evidence on the engagement) takes uploads of its kind on the item's case
  const stepEvidence = (item) => (item.workspace?.steps ?? []).flatMap((s) => (s.fields ?? []).filter((f) => f.type === 'evidence' && f.evidence_kind));
  const kinds = all
    .flatMap((item) => [...responseTasks(item).map((t) => t.response.evidence_kind), item.reconcile?.evidence_kind, item.rfp_outcome?.evidence_kind, ...stepEvidence(item).map((f) => f.evidence_kind), item.assign?.evidence_kind])
    .filter(Boolean);
  const fields = [];
  if (!kinds.includes(body.kind)) fields.push('kind');
  const bytes = /^[A-Za-z0-9+/]+={0,2}$/.test(body.content_base64) ? Buffer.from(body.content_base64, 'base64') : Buffer.alloc(0);
  if (bytes.length === 0) fields.push('content_base64');
  if (fields.length) return invalid(fields);
  const current = all[0].case_revision;
  if (body.case_revision !== current) return [409, SCENARIO_BODIES[409]];
  const granted = all.some(
    (item) =>
      responseTasks(item).some((t) => t.you_can_act) ||
      (Boolean(item.reconcile) && (item.allowed_actions ?? []).includes('reconcile')) ||
      Boolean(item.rfp_outcome) ||
      stepEvidence(item).length > 0 ||
      Boolean(item.assign?.evidence_kind),
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
  if (response.variant === 'team_input') {
    const team = (response.teams ?? []).find((t) => t.key === body.team);
    if (!team) fields.push('team');
    if (team?.estimate_needed && body.estimate_person_days === undefined) fields.push('estimate_person_days');
    if (typeof body.what !== 'string' || body.what.trim() === '') fields.push('what');
  }
  if (fields.length) return invalid(fields);
  if (body.expected_revision !== task.revision) return [409, SCENARIO_BODIES[409]];
  if (body.case_revision !== undefined && body.case_revision !== item.case_revision) return [409, SCENARIO_BODIES[409]];
  if (!task.you_can_act) return [403, SCENARIO_BODIES[403]];

  // F-40 (G-F40-1): a state per action (<work_id>.recorded.<action>) when present, else <work_id>.recorded
  const sidecars = readSidecars();
  const sidecar = sidecars[`${workId}.recorded.${body.action}`] ?? sidecars[`${workId}.recorded`];
  if (!sidecar) return [501, NOT_MOCKED];
  const next = structuredClone(sidecar);
  if (item.case_revision !== undefined) next.case_revision = item.case_revision;
  // F-40: a recorded state that no longer lists the task (the handover's gaps and acknowledged states) has nothing to mark recorded: the 200 is the bare form
  const done = next.tasks.find((t) => t.id === task.id) ?? { response: {}, revision: task.revision };
  // F-31: one team's input on a task that stays open for the other teams (the sidecar carries no `recorded`): the 200 says who recorded it and the task is not marked recorded
  const staysOpen = done.response.variant === 'team_input' && !done.response.recorded;
  const board = staysOpen ? `${response.teams.find((t) => t.key === body.team).name}\u2019s input` : done.response.recorded?.summary;
  const recorded = { by: { name: me.name, role: me.roles[0], is_you: true }, at: new Date().toISOString() };
  if (board) {
    Object.assign(recorded, { responded_at: body.responded_at, proof_count: 1 + (body.evidence_ids?.length ?? 0), summary: board });
    if (body.received_via) recorded.received_via = body.received_via;
  }
  if (!staysOpen) done.response.recorded = recorded;
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

const OUTCOME_ITEMS = { won: 'W-2105', lost: 'W-2106', pending: 'W-2107', unknown: 'W-2108' };

function recordOutcome(body, ctx) {
  const { items, workId, overrides, work, me } = ctx;
  const item = items.get(workId);
  if (!item) return [404, SCENARIO_BODIES[404]];
  const outcome = item.rfp_outcome;
  // The rules read the block; an item without one (no grant) falls through to the 403 below.
  if (outcome) {
    const fields = [];
    if (body.submission_id !== outcome.submission.id) fields.push('submission_id');
    if (!outcome.results.includes(body.result)) fields.push('result');
    if (!outcome.record_as.some((r) => r.value === body.record_as)) fields.push('record_as');
    if (body.reason !== undefined && !(outcome.reasons ?? []).some((r) => r.value === body.reason)) fields.push('reason');
    if ((body.note?.length ?? 0) > NOTE_MAX) fields.push('note');
    if (body.awarded_amount?.unknown === true && body.awarded_amount.amount !== undefined) fields.push('awarded_amount');
    if (body.awarded_amount?.unknown === false && body.awarded_amount.amount === undefined) fields.push('awarded_amount');
    if (!issued(item.case_id, body.evidence_id)) fields.push('evidence_id');
    if (fields.length) return invalid(fields);
  }
  if (body.expected_revision !== item.revision || body.case_revision !== item.case_revision) return [409, SCENARIO_BODIES[409]];
  if (!outcome) return [403, SCENARIO_BODIES[403]];

  const source = work[OUTCOME_ITEMS[body.result]];
  if (!source) return [501, NOT_MOCKED];
  const next = structuredClone(source);
  Object.assign(next, { id: workId, case_id: item.case_id, case_revision: item.case_revision, revision: item.revision + 1 });
  next.rfp_outcome.submission = outcome.submission;
  next.rfp_outcome.recorded.at = new Date().toISOString();
  next.rfp_outcome.recorded.by = me.name;
  overrides.set(workId, next);
  const result = { work_id: workId, result: body.result, state: next.state, revision: next.revision };
  const engagement = next.rfp_outcome.recorded.engagement?.work_id;
  if (body.result === 'won' && engagement) result.engagement_work_id = engagement;
  return [200, result];
}

const UNCERTAIN_SEND = 'W-2111';
const STALE_ONCE = 'W-2112';

function sendFollowup(body, ctx) {
  const { items, workId, overrides, work } = ctx;
  const item = items.get(workId);
  if (!item) return [404, SCENARIO_BODIES[404]];
  const stored = sends.get(`${workId} ${body.idempotency_key}`);
  if (stored) return structuredClone(stored);
  const followup = item.rfp_outcome?.followup;
  if (body.body !== undefined && body.body.trim() === '') return invalid(['body']);
  if (body.expected_revision !== item.revision || (followup && body.version !== followup.version)) return [409, SCENARIO_BODIES[409]];
  if (workId === STALE_ONCE && !stalled.has(workId) && work[`${workId}.next`]) {
    stalled.add(workId);
    overrides.set(workId, structuredClone(work[`${workId}.next`]));
    return [409, SCENARIO_BODIES[409]];
  }
  if (!followup || followup.can_send !== true || followup.status !== 'drafted') return [403, SCENARIO_BODIES[403]];

  const status = workId === UNCERTAIN_SEND ? 'effect_uncertain' : 'sent';
  const sent = work[`${workId}.sent`];
  const next = structuredClone(status === 'sent' && sent ? sent : item);
  next.revision = item.revision + 1;
  const draft = next.rfp_outcome.followup;
  Object.assign(draft, { status, can_send: false, can_edit: false });
  if (body.body !== undefined) draft.body = body.body;
  if (status === 'sent') draft.sent_at = new Date().toISOString();
  overrides.set(workId, next);
  const reply = [200, { work_id: workId, status, revision: next.revision }];
  sends.set(`${workId} ${body.idempotency_key}`, reply);
  return structuredClone(reply);
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
  // F-40 (PROPOSAL G-48-1): `gaps` is checked on its own for a support-handover task, then taken out before the v7 body check
  let gapFields = [];
  if (operationId === 'E-RESPONSE' && body !== null && typeof body === 'object') {
    const handover = [...items.values()].flatMap((item) => item.tasks).find((t) => t.id === segment)?.response?.variant === 'support_handover';
    if (handover && Object.hasOwn(body, 'gaps')) {
      const { gaps, ...rest } = body;
      const listed = Array.isArray(gaps) && gaps.length > 0 && gaps.every((g) => typeof g === 'string' && g.trim() !== '');
      if (body.action !== 'changes_requested' || !listed) gapFields = ['gaps'];
      body = rest;
    } else if (handover && body.action === 'changes_requested') gapFields = ['gaps'];
  }
  if (!request(body)) return invalid([...errorFields(request.errors), ...gapFields]);
  if (gapFields.length) return invalid(gapFields);

  const ctx = { items, overrides, work, me: me[persona], caseId: segment, taskId: segment, workId: segment };
  const writes = { 'E-EVIDENCE-UPLOAD': upload, 'E-RESPONSE': respond, 'E-WORK-ACTION': act, 'E-RFP-OUTCOME': recordOutcome, 'E-RFP-FOLLOWUP': sendFollowup };
  const result = writes[operationId](body, ctx);
  if (scenario === RECORD_THEN_FAIL && operationId !== 'E-EVIDENCE-UPLOAD' && result[0] === 200) return [502, MOCK_LOST];
  return result;
}

/** One reply for an F-09 or F-18 operation, validated against its v7 schema (undeclared 501 and 502 are not). */
export function responseRoute(operationId, args) {
  const [status, body] = handle(operationId, args);
  const validate = validators()[operationId].replies[String(status)];
  if (validate && !validate(body)) {
    return [500, { code: 'mock_invalid_reply', message: `The mock's ${operationId} ${status} reply does not match v7.` }];
  }
  return [status, body];
}
