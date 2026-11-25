// F-137: "Record an issue" in the contract mock (live shapes of GET and POST /projects/{case_id}/issues, contract 1.26+): the register read
// with the exact owner and proof choices, and the write. A recorded issue is kept per project, answered by the next read, and added to the top
// of the Registers tab's issues section (recordedItems). Cookie psl_mock_record picks the case: ok (default) | forbidden | conflict | invalid |
// uncertain (503, not saved) | uncertain-saved (503, saved) | reread-fail (201, then the next read answers 503 once) | empty-proofs.
// The mock checks the contract's limits and ids, and invents no rule. A project the persona cannot see answers 404. Sample data only.
import { idOf, uuidOf } from './projects.mjs';

export const RECORD_PATH = /^\/api\/v1\/projects\/([^/]+)\/issues$/;
const NOT_FOUND = { code: 'not_found', message: 'We could not find that record.' };
const FORBIDDEN = { code: 'forbidden', message: 'Your role does not allow recording issues here.' };
const STALE = { code: 'stale_revision', message: 'This project changed. Reload and try again.' };
const SERVER_ERROR = { code: 'server_error', message: 'Something went wrong on our side.' };
const OWNERS = [
  { id: 4, name: 'Tunde Bello' },
  { id: 5, name: 'Kemi Adebayo' },
  { id: 6, name: 'Engineering' },
];
const PROOFS = [
  { id: 7901, version: 1, kind: 'meeting_minutes' },
  { id: 7902, version: 2, kind: 'test_report' },
];
const LIMITS = { reference: 160, title: 240, kind: 100, next_action: 1000, note: 4000 };
const SEVERITIES = ['Critical', 'High', 'Medium', 'Low'];
const BASE_REVISION = 7;

let recorded = new Map(); // caseId -> issues, newest first
let conflicted = false;
let rereadFailed = false;
let nextId = 900;

export function resetIssueRecord() {
  recorded = new Map();
  conflicted = false;
  rereadFailed = false;
  nextId = 900;
}

const heldOf = (caseId) => recorded.get(caseId) ?? [];
const revisionOf = (caseId) => BASE_REVISION + heldOf(caseId).length;
const fail = (name, message) => ({ status: 422, body: { code: 'invalid', message: 'Check the fields.', fields: [{ name, message }] } });

/** The Registers tab's rows for the issues recorded here, newest first (the tab's live item shape). */
export function recordedItems(caseId) {
  const uuid = uuidOf(caseId);
  return heldOf(caseId).map((i) => ({
    title: i.reference,
    state: 'Open',
    state_code: 'open',
    detail: i.title,
    at: null,
    due: null,
    severity: i.severity,
    owner: OWNERS.find((o) => o.id === i.owner_id)?.name ?? null,
    django_url: `/projects/${uuid}/issues/#${i.id}`,
    record_id: i.id,
    api_url: `/api/v1/projects/${uuid}/issues/${i.id}`,
    reference: i.reference,
    age_days: 0,
    origin_meeting: null,
  }));
}

/** { status, body } for the read or the write; the caller has checked the CSRF token on a write. */
export function issueRecord({ method, url, raw, persona, cookies = {}, canSee }) {
  const caseId = idOf(decodeURIComponent(RECORD_PATH.exec(url.pathname)[1]));
  const scenario = cookies.psl_mock_record ?? 'ok';
  if (!canSee(caseId, persona)) return { status: 404, body: NOT_FOUND };
  if (scenario === 'forbidden') return { status: 403, body: FORBIDDEN };
  if (method === 'get') {
    if (scenario === 'reread-fail' && heldOf(caseId).length > 0 && !rereadFailed) {
      rereadFailed = true;
      return { status: 503, body: SERVER_ERROR };
    }
    return {
      status: 200,
      body: { case_revision: revisionOf(caseId), issues: heldOf(caseId).map(toIssue), next_before: null, owners: OWNERS, proofs: scenario === 'empty-proofs' ? [] : PROOFS },
    };
  }
  let body;
  try {
    body = JSON.parse(raw);
  } catch {
    return { status: 400, body: { code: 'bad_request', message: 'Not JSON.' } };
  }
  for (const name of Object.keys(LIMITS)) {
    const value = body?.[name];
    if (typeof value !== 'string' || value.length < 1 || value.length > LIMITS[name]) return fail(name, `Enter ${name.replace('_', ' ')} (up to ${LIMITS[name]} characters).`);
  }
  if (!OWNERS.some((o) => o.id === body.owner_id)) return fail('owner_id', 'Choose one of the listed owners.');
  if (!PROOFS.some((p) => p.id === body.evidence_id)) return fail('evidence_id', 'Choose one of the listed evidence.');
  if (body.severity !== null && !SEVERITIES.includes(body.severity)) return fail('severity', 'Choose a listed severity.');
  if (!Array.isArray(body.external_links) || !Number.isInteger(body.case_revision)) return { status: 400, body: { code: 'bad_request', message: 'Check the request.' } };
  if (scenario === 'invalid') return fail('reference', 'This reference is already used on this project.');
  if (scenario === 'conflict' && !conflicted) {
    conflicted = true;
    return { status: 409, body: STALE };
  }
  if (body.case_revision !== revisionOf(caseId)) return { status: 409, body: STALE };
  if (scenario === 'uncertain') return { status: 503, body: SERVER_ERROR };
  const issue = { id: nextId++, reference: body.reference, title: body.title, kind: body.kind, owner_id: body.owner_id, next_action: body.next_action, severity: body.severity };
  recorded.set(caseId, [issue, ...heldOf(caseId)]);
  if (scenario === 'uncertain-saved') return { status: 503, body: SERVER_ERROR };
  return { status: 201, body: { issue_id: issue.id, state_id: issue.id + 1000, case_revision: revisionOf(caseId) } };
}

const toIssue = (i) => ({
  id: i.id, state_id: i.id + 1000, reference: i.reference, title: i.title, kind: i.kind, status: 'Open', severity: i.severity, owner_id: i.owner_id, next_action: i.next_action,
  opened_at: '2026-11-25T09:00:00Z', age_days: 0, acknowledged_at: null, resolved_at: null,
});
