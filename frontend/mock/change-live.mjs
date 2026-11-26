// F-112: the change request (SCR-31, part 1) in the live shapes of contract 1.26.x: GET|POST /work/{id}/change (assess, decide, authorize)
// and GET|POST /projects/{case_id}/ordinary-changes (capture). Integer ids 4901 to 4912 and 4999 only; every other id falls through.
// (The spec named 4201 to 4208; those are taken, so the fixtures are 4901 to 4912 in the same order.) Sample data; no business rules.
// 4901 Normal, impact, 3 of 4 recorded, Security open; 4902 deciding (Client and Engineering Lead rows open); 4903 a Client rejection;
// 4904 all approved, can authorise with two choices; 4905 read only for the caller; 4906 authorised; 4907 at the notice step; 4908 no
// proof recorded; 4909 conflict (the first decision answers 409 and someone else has decided); 4910 a stage outside the eight codes (and no listed change has its version, so no reference);
// 4911 two deciders only; 4912 no assessment recorded yet; 4999 not found.
// Scenarios (cookie psl_mock_scenario or header x-mock-scenario): a status number answers every route with it; w403, w403csrf, w409,
// w422, w429, w503, w500 answer the writes; wdrop (the write ran, the answer is lost) and wdrop0 (the answer is lost, nothing ran).
import { idOf } from './projects.mjs';
import { workLive } from './work-live.mjs';

export const CHANGE_PATH = /^\/api\/v1\/(?:work\/(49(?:0[1-9]|1[0-2]|99))(\/change)?|projects\/([^/]+)\/ordinary-changes)$/;

const NOW = '2026-11-26T09:00:00Z';
const caseOf = (id) => `00000000-0000-4000-8000-00000000${id}`;
const BODIES = {
  400: { code: 'bad_request', message: 'We could not read that request.' },
  401: { code: 'not_signed_in', message: 'Sign in to continue.' },
  403: { code: 'forbidden', message: 'Your role does not allow this.' },
  404: { code: 'not_found', message: 'This record is unavailable.' },
  409: { code: 'stale_version', message: 'Someone changed this since you opened it.' },
  422: { code: 'invalid', message: 'The request was not accepted.', fields: [{ name: 'note', message: 'A note is needed.' }] },
  429: { code: 'rate_limited', message: 'Too many requests.' },
  503: { code: 'unavailable', message: 'A dependency is unavailable.' },
};
const CSRF_FAILED = { code: 'csrf_failed', message: 'Your session check failed. Reload and try again.' };
const SCENARIO = {
  w403: [403, { code: 'forbidden', message: 'Only the assigned people can record this.' }],
  w403csrf: [403, CSRF_FAILED],
  w409: [409, BODIES[409]],
  w422: [422, BODIES[422]],
  w429: [429, BODIES[429]],
  w503: [503, BODIES[503]],
  w500: [500, { code: 'server_error', message: 'Something broke.' }],
};

const EVIDENCE = [{ id: 7901, version: 1, kind: 'security_assessment' }, { id: 7902, version: 2, kind: 'meeting_minutes' }];
const row = (team, recorded, summary = null, effort = null, id = null) => ({ team, status: recorded ? 'Recorded' : 'Missing', assessment_id: recorded ? id : null, summary, effort });
const IMPACT_3 = [row('Engineering', true, '4 person-days · no impact on go-live', '4', 801), row('QA', true, '1 day of regression testing', '1', 802), row('Infra', true, 'Not needed for this change', null, 803), row('Security', false)];
const IMPACT_4 = IMPACT_3.map((r) => (r.team === 'Security' ? row('Security', true, 'Uses the existing SMS provider.', '0.5', 804) : r));
const decider = (role, status, verdicts = []) => ({ role, status, verdicts });
const FIVE_APPROVED = [decider('Product', 'Approved'), decider('Engineering', 'Approved'), decider('Client', 'Approved'), decider('Engineering Lead', 'Approved'), decider('Security Manager', 'Approved')];

const change = (patch = {}) => ({
  expected_revision: 6,
  case_revision: 41,
  change_id: 301,
  change_version_id: 1,
  category: 'Normal',
  stage: 'impact',
  finding: '',
  next_action: 'Record the Security assessment.',
  authorization_id: null,
  authorization_choices: [],
  impact: IMPACT_3,
  assessors: [],
  decisions: [],
  documents: [],
  evidence: EVIDENCE,
  can_close: false,
  closure_id: null,
  can_restart: false,
  can_authorize: false,
  deployment_authorized: false,
  jobs: [],
  ...patch,
});

const START = {
  4901: change({ assessors: ['Security'], decisions: [decider('Product', 'Not yet'), decider('Client', 'Not yet'), decider('Engineering Lead', 'Not yet')] }),
  4902: change({
    change_version_id: 2,
    stage: 'authorization',
    impact: IMPACT_4,
    next_action: 'Record the Client and Engineering Lead decisions.',
    decisions: [decider('Product', 'Approved'), decider('Engineering', 'Approved'), decider('Client', 'Waiting', ['approve', 'return', 'reject']), decider('Engineering Lead', 'Waiting', ['approve']), decider('Security Manager', 'Waiting')],
  }),
  4903: change({ change_version_id: 3, stage: 'authorization', impact: IMPACT_4, finding: 'The client did not approve this change.', next_action: 'Log a new change if it is still needed.', decisions: [decider('Product', 'Approved'), decider('Client', 'Rejected')] }),
  4904: change({ change_version_id: 4, stage: 'authorization', impact: IMPACT_4, next_action: 'Record the authorisation.', decisions: FIVE_APPROVED, can_authorize: true, authorization_choices: [11, 12] }),
  4905: change({ change_version_id: 5, decisions: [decider('Product', 'Waiting'), decider('Client', 'Waiting')], next_action: 'Waiting for the assessments.' }),
  4906: change({ change_version_id: 6, stage: 'notice', impact: IMPACT_4, decisions: FIVE_APPROVED, authorization_id: 7001, next_action: 'The change notice is the next step.' }),
  4907: change({ change_version_id: 7, stage: 'notice', impact: IMPACT_4, decisions: [decider('Product', 'Approved'), decider('Engineering', 'Approved')], next_action: 'The change notice is the next step.', can_authorize: false }),
  4908: change({ change_version_id: 8, assessors: ['Security'], evidence: [], decisions: [decider('Product', 'Waiting', ['approve', 'return', 'reject'])] }),
  4909: change({ change_version_id: 9, stage: 'authorization', impact: IMPACT_4, next_action: 'Record the Product decision.', decisions: [decider('Product', 'Waiting', ['approve', 'return'])], conflictOnce: true }),
  4910: change({ change_version_id: 10, stage: 'review_pending', impact: IMPACT_4, decisions: [], next_action: 'Waiting.' }),
  4911: change({ change_version_id: 11, stage: 'authorization', impact: IMPACT_4, decisions: [decider('Product', 'Waiting', ['approve']), decider('Engineering', 'Waiting', ['approve'])], next_action: 'Record the Product and Engineering decisions.' }),
  4912: change({ change_version_id: 12, stage: 'source', impact: [], assessors: ['Engineering', 'QA', 'Infra', 'Security'], next_action: 'Record the four assessments.' }),
};

// per work id: the change as the writes left it; reset with the mock
let live = {};
let nextRecord = 900;
// per case (P-nnnn): the changes logged here and the case revision
let logged = {};
export const resetChangeLive = () => {
  live = {};
  logged = {};
  nextRecord = 900;
};
const current = (id) => live[id] ?? START[id];
const strip = (c) => Object.fromEntries(Object.entries(c).filter(([k]) => k !== 'conflictOnce'));

const item = (id) => {
  const c = current(id);
  const [, template] = workLive({ method: 'get', url: new URL('http://mock/api/v1/work/4101'), scenario: undefined, csrfOk: true, persona: 'finance_lead' });
  return {
    ...template,
    id,
    case_id: caseOf(id),
    title: 'Add SMS appointment reminders',
    line: 'pmo-change/v1',
    state: 'action_needed',
    status_label: 'Action needed',
    reference: 'CHG-0031',
    output_url: null,
    tracking_url: null,
    agent: null,
    verified_at: null,
    updated_at: NOW,
    django_url: `/work/${id}/`,
    api_url: `/api/v1/work/${id}`,
    revision: c.expected_revision,
    case_revision: c.case_revision,
    panels: [{ key: 'change', url: `/api/v1/work/${id}/change`, contract_path: '/api/v1/work/{work_id}/change' }],
  };
};

const int = (v) => Number.isInteger(v) && v >= 1;
const text = (v, max) => typeof v === 'string' && v.trim() !== '' && v.length <= max;
const TEAM = ['Engineering', 'QA', 'Infra', 'Security'];
const ROLE = ['Product', 'Engineering', 'Client', 'Engineering Lead', 'Security Manager'];
const NULL_BOOL = (v) => v === null || typeof v === 'boolean';
const OUTPUTS = ['discipline', 'timeline', 'cost_resource', 'risk', 'dependency'];
const KEYS = {
  assess: ['action', 'expected_revision', 'case_revision', 'change_version_id', 'contributor', 'cost_impact', 'timeline_impact', 'client_facing', 'evidence', 'note', 'production_impact', 'scope_items', 'outputs', 'effort_person_days', 'proof_upload'],
  decide: ['action', 'expected_revision', 'case_revision', 'change_version_id', 'role', 'verdict', 'evidence', 'note'],
  authorize: ['action', 'expected_revision', 'case_revision', 'change_version_id', 'commercial'],
};

/** A problem with the body (a field name), or null. The contract's exact keys and types; every key is required. */
function problem(body) {
  const allowed = KEYS[body.action];
  if (!allowed) return 'action';
  if (Object.keys(body).length !== allowed.length || !allowed.every((k) => k in body)) return Object.keys(body).find((k) => !allowed.includes(k)) ?? allowed.find((k) => !(k in body));
  for (const k of ['expected_revision', 'case_revision', 'change_version_id']) if (!int(body[k])) return k;
  if (body.action === 'assess') {
    if (!TEAM.includes(body.contributor)) return 'contributor';
    for (const k of ['cost_impact', 'timeline_impact', 'client_facing', 'production_impact']) if (!NULL_BOOL(body[k])) return k;
    if (!int(body.evidence)) return 'evidence';
    if (!text(body.note, 4000)) return 'note';
    const s = body.scope_items;
    if (s !== null && !(Array.isArray(s) && s.length <= 100 && s.every((x) => text(x, 240)))) return 'scope_items';
    const o = body.outputs;
    if (o !== null && !(o && typeof o === 'object' && Object.keys(o).length === 5 && OUTPUTS.every((k) => k in o && (o[k] === null || text(o[k], 4000))))) return 'outputs';
    if (body.effort_person_days !== null && !(typeof body.effort_person_days === 'string' && body.effort_person_days.length <= 32)) return 'effort_person_days';
    if (body.proof_upload !== null && !int(body.proof_upload)) return 'proof_upload';
  } else if (body.action === 'decide') {
    if (!ROLE.includes(body.role)) return 'role';
    if (!['approve', 'return', 'reject'].includes(body.verdict)) return 'verdict';
    if (!int(body.evidence)) return 'evidence';
    if (!text(body.note, 4000)) return 'note';
  } else if (body.commercial !== null && !int(body.commercial)) return 'commercial';
  return null;
}

const refused = (field) => [400, { code: 'bad_request', message: 'We could not read that request.', fields: [{ name: field, message: 'This field is missing or not accepted.' }] }];
const invalid = (field, message) => [422, { code: 'invalid', message, fields: [{ name: field, message }] }];

function write(id, scenario, csrfOk, rawBytes) {
  const c = current(id);
  if (!c) return [404, BODIES[404]];
  if (!csrfOk) return [403, CSRF_FAILED];
  let body;
  try {
    body = JSON.parse(Buffer.from(rawBytes ?? []).toString('utf8') || '{}');
  } catch {
    return [400, BODIES[400]];
  }
  const bad = problem(body);
  if (bad) return refused(bad);
  if (scenario === 'wdrop0') return ['drop'];
  if (SCENARIO[scenario]) return SCENARIO[scenario];
  if (c.conflictOnce && body.action === 'decide') {
    // someone else decided: the revisions move on, the row has no verdicts, and the next read shows it
    live[id] = { ...c, conflictOnce: false, expected_revision: c.expected_revision + 1, case_revision: c.case_revision + 1, decisions: c.decisions.map((d) => ({ ...d, status: 'Approved', verdicts: [] })), next_action: 'Record the authorisation.' };
    return [409, BODIES[409]];
  }
  if (body.expected_revision !== c.expected_revision || body.case_revision !== c.case_revision || body.change_version_id !== c.change_version_id || scenario === 'w409') return [409, BODIES[409]];
  const next = { ...c };
  if (body.action === 'assess') {
    if (!c.assessors.includes(body.contributor)) return invalid('contributor', 'This team’s assessment isn’t open to you.');
    if (!c.evidence.some((e) => e.id === body.evidence)) return invalid('evidence', 'Choose a listed proof.');
    nextRecord += 1;
    const rows = TEAM.map((team) => (team === body.contributor ? row(team, true, body.note, body.effort_person_days, nextRecord) : (c.impact.find((r) => r.team === team) ?? row(team, false))));
    next.impact = rows;
    next.assessors = c.assessors.filter((t) => t !== body.contributor);
    if (rows.every((r) => r.assessment_id !== null) && c.stage !== 'authorization') next.stage = 'authorization';
  } else if (body.action === 'decide') {
    const d = c.decisions.find((x) => x.role === body.role);
    if (!d || !d.verdicts.includes(body.verdict)) return invalid('verdict', 'This decision isn’t open to you.');
    if (!c.evidence.some((e) => e.id === body.evidence)) return invalid('evidence', 'Choose a listed proof.');
    const status = { approve: 'Approved', return: 'Returned', reject: 'Rejected' }[body.verdict];
    // a rejection closes the change: no other decision stays open
    next.decisions = c.decisions.map((x) => (x.role === body.role ? { ...x, status, verdicts: [] } : body.verdict === 'reject' ? { ...x, verdicts: [] } : x));
    if (next.decisions.every((x) => x.status === 'Approved')) {
      next.can_authorize = true;
      next.authorization_choices = [11, 12];
    }
  } else {
    if (!c.can_authorize || c.authorization_id !== null) return invalid('commercial', 'The authorisation isn’t open to you.');
    if (body.commercial !== null && !c.authorization_choices.includes(body.commercial)) return invalid('commercial', 'Choose a listed commercial item.');
    next.authorization_id = 7100 + id - 4900;
    next.can_authorize = false;
    next.stage = 'notice';
    next.next_action = 'The change notice is the next step.';
  }
  next.expected_revision = c.expected_revision + 1;
  next.case_revision = c.case_revision + 1;
  live[id] = next;
  if (scenario === 'wdrop') return ['drop'];
  return [201, { work_id: id, state: 'action_needed', revision: next.expected_revision, record_id: nextRecord + 1 }];
}

// ---- the project's change list: GET and POST /projects/{case_id}/ordinary-changes ----

const CAPTURE = ['action', 'case_revision', 'reference', 'category', 'module', 'description', 'reason', 'evidence_id'];
const caseState = (caseId) => {
  const worked = /^P-49(\d\d)$/.exec(caseId);
  if (!logged[caseId]) {
    const wid = worked ? 4900 + Number(worked[1]) : null;
    const seeded = wid && START[wid] ? [{ id: 301, version_id: wid === 4910 ? 999 : START[wid].change_version_id, reference: 'CR-0031', category: START[wid].category, module: 'Appointments', description: 'Add SMS appointment reminders' }] : [];
    logged[caseId] = { case_revision: 12, records: seeded };
  }
  return logged[caseId];
};
const register = (caseId) => {
  const s = caseState(caseId);
  return { case_revision: s.case_revision, records: s.records, evidence: EVIDENCE, catalogue: [], catalogue_finding: '' };
};
function capture(caseId, scenario, csrfOk, rawBytes) {
  if (!csrfOk) return [403, CSRF_FAILED];
  let body;
  try {
    body = JSON.parse(Buffer.from(rawBytes ?? []).toString('utf8') || '{}');
  } catch {
    return [400, BODIES[400]];
  }
  if (body.action !== 'capture') return refused('action');
  if (Object.keys(body).length !== CAPTURE.length || !CAPTURE.every((k) => k in body)) return refused(Object.keys(body).find((k) => !CAPTURE.includes(k)) ?? CAPTURE.find((k) => !(k in body)));
  if (!int(body.case_revision)) return refused('case_revision');
  if (!text(body.reference, 160)) return refused('reference');
  if (!['Standard', 'Normal'].includes(body.category)) return refused('category');
  if (!text(body.module, 160)) return refused('module');
  for (const k of ['description', 'reason']) if (!text(body[k], 4000)) return refused(k);
  if (!int(body.evidence_id)) return refused('evidence_id');
  if (scenario === 'wdrop0') return ['drop'];
  if (SCENARIO[scenario]) return SCENARIO[scenario];
  const s = caseState(caseId);
  if (body.case_revision !== s.case_revision) return [409, BODIES[409]];
  if (!EVIDENCE.some((e) => e.id === body.evidence_id)) return invalid('evidence_id', 'Choose a listed proof.');
  if (s.records.some((r) => r.reference === body.reference)) return invalid('reference', 'This reference is already used.');
  nextRecord += 1;
  s.records = [{ id: nextRecord, version_id: nextRecord, reference: body.reference, category: body.category, module: body.module, description: body.description }, ...s.records];
  s.case_revision += 1;
  if (scenario === 'wdrop') return ['drop'];
  return [201, { id: nextRecord, case_revision: s.case_revision }];
}

/** One change read or write. `scenario` is the cookie or header value. */
export function changeLive({ method, url, scenario, csrfOk, persona, rawBytes }) {
  const found = CHANGE_PATH.exec(url.pathname);
  const status = Number(scenario);
  if (BODIES[status]) return [status, BODIES[status]];
  if (persona === 'none') return [404, BODIES[404]];
  if (found[3] !== undefined) {
    // a project may be named by its UUID or its P-nnnn id
    const caseId = idOf(decodeURIComponent(found[3]));
    if (method === 'post') return capture(caseId, scenario, csrfOk, rawBytes);
    return method === 'get' ? [200, register(caseId)] : [405, { code: 'method_not_allowed', message: 'Not allowed.' }];
  }
  const id = Number(found[1]);
  if (id === 4999) return [404, BODIES[404]];
  if (method === 'post') return found[2] ? write(id, scenario, csrfOk, rawBytes) : [405, { code: 'method_not_allowed', message: 'Read only.' }];
  if (method !== 'get') return [405, { code: 'method_not_allowed', message: 'Read only.' }];
  if (!found[2]) return [200, item(id)];
  return [200, strip(current(id))];
}
