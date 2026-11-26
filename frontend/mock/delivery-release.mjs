// F-113B: the release gates page (SCR-44) in the live shapes of contract 1.26.x: GET|POST /work/{id}/planning-exit, GET|POST
// /work/{id}/release-register, the project's client-testing read and the case's decision-appointments read.
// Integer ids 4801 to 4814 and 4890 only; every other id falls through. (The spec named 4201 to 4213; those are taken, so each is
// the same number plus 600: 4801 is the spec's 4201 ... 4813 its 4213, 4814 is new, 4890 its 4290.) Sample data; no business rules.
// 4801 decision, can approve directly, one proof, one blocker; 4802 no proofs, cannot approve directly; 4803 packet not ready;
// 4804 viewer cannot decide; 4805 returned; 4806 returned with a client workaround; 4807 owner needed; 4808 readiness, PM can prepare;
// 4809 readiness, nothing to press; 4810 ready, release not recorded; 4811 release recorded; 4812 the item's version is unknown;
// 4813 no proofs, can approve directly; 4814 one proof, cannot approve directly; 4890 not found.
// Scenarios (cookie psl_mock_scenario or header x-mock-scenario): a status number answers every route with it; w403, w403csrf, w409,
// w422, w429, w503, w500 answer the writes; wdrop (the write ran, the answer is lost) and wdrop0 (the answer is lost, nothing ran);
// uat500 fails only the client-testing read.
import { workLive } from './work-live.mjs';

export const RELEASE_PATH = /^\/api\/v1\/(?:work\/(48(?:0[1-9]|1[0-4]|90))(\/planning-exit|\/release-register)?|projects\/(?:00000000-0000-4000-8000-00000000|P-)(48(?:0[1-9]|1[0-4]))\/delivery\/7\/client-testing|setup\/(?:00000000-0000-4000-8000-00000000|P-)(48(?:0[1-9]|1[0-4]))\/decision-appointments)$/;

const NOW = '2026-11-26T09:00:00Z';
const HEX = 'a'.repeat(64);
const caseOf = (id) => `00000000-0000-4000-8000-00000000${id}`;
const BODIES = {
  400: { code: 'bad_request', message: 'We could not read that request.' },
  401: { code: 'not_signed_in', message: 'Sign in to continue.' },
  403: { code: 'forbidden', message: 'Your role does not allow this.' },
  404: { code: 'not_found', message: 'This record is unavailable.' },
  409: { code: 'stale_version', message: 'Someone changed this since you opened it.' },
  422: { code: 'invalid', message: 'The request was not accepted.', fields: [{ name: 'note', message: 'A note is needed to return a release.' }] },
  429: { code: 'rate_limited', message: 'Too many requests.' },
  503: { code: 'unavailable', message: 'A dependency is unavailable.' },
};
const CSRF_FAILED = { code: 'csrf_failed', message: 'Your session check failed. Reload and try again.' };
const SCENARIO = {
  w403: [403, { code: 'forbidden', message: 'Only the PMO Lead can decide this.' }],
  w403csrf: [403, CSRF_FAILED],
  w409: [409, BODIES[409]],
  w422: [422, BODIES[422]],
  w429: [429, BODIES[429]],
  w503: [503, BODIES[503]],
  w500: [500, { code: 'server_error', message: 'Something broke.' }],
};

const phases = () => [
  { name: 'Initiation', checks: [
    { key: 'engagement', title: 'Engagement registered', authority: 'PMO Lead', status: 'current', records: [{ id: 1, type: 'engagement' }, { id: 2, type: 'plan' }] },
    { key: 'identity', title: 'Client identity confirmed', authority: 'Client', status: 'current', records: [{ id: 3, type: 'identity' }] },
  ] },
  { name: 'Planning', checks: [
    { key: 'exit', title: 'Planning exit decided', authority: 'PMO Lead', status: 'unknown_or_stale', records: [] },
    { key: 'sources', title: 'Planning sources current', authority: 'Engineering', status: 'stale_scope', records: [{ id: 4, type: 'source' }] },
  ] },
  { name: 'Execution', checks: [
    { key: 'stages', title: 'Stages built', authority: 'PM', status: 'restricted_or_authority_changed', records: [] },
    { key: 'issues', title: 'Issue register reviewed', authority: 'PM', status: 'unknown', records: [] },
  ] },
  { name: 'Closure', checks: [
    { key: 'closure', title: 'Closure checklist', authority: 'PMO Lead', status: 'unknown_or_stale', records: [] },
    { key: 'handover', title: 'Handover accepted', authority: 'Support', status: 'brand_new_status', records: [] },
  ] },
];
const PROOF = [{ id: 61, version: 1, kind: 'signed_pdf' }];
const register = (patch = {}) => ({ expected_revision: 6, case_revision: 41, dossier_id: 7, candidate_id: 8, as_of: NOW, current_scope: true, synthetic: true, actions: [], phases: phases(), proofs: PROOF, readiness_ids: [], release: null, ...patch });
const exit = (patch = {}) => ({ expected_revision: 6, case_revision: 41, packet: HEX, verdicts: ['approve', 'return', 'reject'], proofs: PROOF, blockers: [{ id: 301, reference: 'ISS-0301' }], checklist: [{ name: 'planning_sources', status: 'current' }, { name: 'planning_decision', status: 'held' }], workaround: null, can_approve_directly: true, latest_decision: null, ...patch });
const decision = (verdict, direct = false) => ({ id: 91, verdict, role: 'PMO Lead', by: 'Kemi Adebayo', at: '2026-11-25T14:30:00Z', direct });
const RELEASED = { reference: 'REL-2026-044', released_at: '2026-11-25T16:00:00Z', environment: 'Production', evidence_id: 9001 };

const START = {
  4801: { register: register(), exit: exit() },
  4802: { register: register(), exit: exit({ proofs: [], can_approve_directly: false }) },
  4803: { register: register(), exit: exit({ packet: null }) },
  4804: { register: register(), exit: exit({ verdicts: [], proofs: [], can_approve_directly: false }) },
  4805: { register: register(), exit: exit({ verdicts: [], latest_decision: decision('return'), can_approve_directly: false }) },
  4806: { register: register(), exit: exit({ verdicts: [], latest_decision: decision('return'), can_approve_directly: false, workaround: { return_id: 91, issue_state_id: 12, response_id: 13, review_id: 14 } }) },
  4807: { register: register(), exit: exit({ verdicts: [], proofs: [], can_approve_directly: false }), state: 'owner_needed' },
  4808: { register: register({ actions: ['prepare_readiness'] }), exit: exit({ verdicts: [], latest_decision: decision('approve', true), can_approve_directly: false }) },
  4809: { register: register(), exit: exit({ verdicts: [], latest_decision: decision('approve'), can_approve_directly: false }) },
  4810: { register: register({ actions: ['observe_release'], readiness_ids: [71] }), exit: exit({ verdicts: [], latest_decision: decision('approve'), can_approve_directly: false }) },
  4811: { register: register({ readiness_ids: [71], release: RELEASED }), exit: exit({ verdicts: [], latest_decision: decision('approve'), can_approve_directly: false }) },
  4812: { register: register(), exit: exit(), unknownRevision: true },
  4813: { register: register(), exit: exit({ proofs: [] }) },
  4814: { register: register(), exit: exit({ can_approve_directly: false }) },
};

// what the writes changed: id -> { register, exit, item }; reset with the mock
let live = {};
export const resetReleaseLive = () => {
  live = {};
};
const current = (id) => live[id] ?? START[id];

const item = (id) => {
  const c = current(id);
  const [, template] = workLive({ method: 'get', url: new URL('http://mock/api/v1/work/4101'), scenario: undefined, csrfOk: true, persona: 'finance_lead' });
  const [state, label] = c.moved ?? ['action_needed', 'Action needed'];
  return {
    ...template,
    id,
    case_id: caseOf(id),
    title: 'Release gates for Kora Logistics',
    line: 'delivery-release/v1',
    state: c.state ?? state,
    status_label: c.state === 'owner_needed' ? 'Needs an owner' : label,
    reference: 'REL-0091',
    output_url: null,
    tracking_url: null,
    agent: null,
    verified_at: null,
    updated_at: NOW,
    django_url: `/work/${id}/`,
    api_url: `/api/v1/work/${id}`,
    revision: c.unknownRevision ? null : c.register.expected_revision,
    case_revision: c.register.case_revision,
    panels: [
      { key: 'release-register', url: `/api/v1/work/${id}/release-register`, contract_path: '/api/v1/work/{work_id}/release-register' },
      { key: 'planning-exit', url: `/api/v1/work/${id}/planning-exit`, contract_path: '/api/v1/work/{work_id}/planning-exit' },
      { key: 'client-testing', url: `/api/v1/projects/${caseOf(id)}/delivery/7/client-testing`, contract_path: '/api/v1/projects/{case_id}/delivery/{dossier_id}/client-testing' },
    ],
  };
};

const UAT = (id) => ({
  case_revision: 41,
  target_id: 5,
  response_id: id === 4801 ? 6 : null,
  outcome: id === 4801 ? 'approved_with_workaround' : null,
  inspection_id: null,
  review_id: null,
  binding_id: null,
  gate_id: null,
  proof_current: id !== 4801,
  binding_current: id !== 4801,
  contact_choices: [],
  owned_files: [],
  proof_files: [],
});
const APPOINTMENTS = { case_revision: 41, latest_id: null, active_id: null, people: [{ id: 31, label: 'Tunde Bello' }, { id: 32, label: 'Amaka Obi' }], proofs: [], can_draft: false, appointments: [], next_page: null };

const WRITE_KEYS = {
  decide: ['expected_revision', 'case_revision', 'packet', 'verdict', 'evidence_id', 'note', 'issue_id'],
  prepare_readiness: ['action', 'expected_revision', 'case_revision'],
  observe_release: ['action', 'expected_revision', 'case_revision', 'readiness_id', 'released_at', 'reference', 'upload_id', 'checked', 'note', 'environment', 'private_log_id'],
};
const int = (v) => Number.isInteger(v) && v >= 1;

/** A problem with the body (a field name), or null. The contract's exact keys and types; required keys must be present. */
function problem(kind, body) {
  const allowed = WRITE_KEYS[kind];
  const names = Object.keys(body);
  const odd = names.find((k) => !allowed.includes(k));
  if (odd) return odd;
  const optional = kind === 'decide' ? ['evidence_id', 'note', 'issue_id'] : [];
  const missing = allowed.find((k) => !optional.includes(k) && !(k in body));
  if (missing) return missing;
  if (!int(body.expected_revision)) return 'expected_revision';
  if (!int(body.case_revision)) return 'case_revision';
  if (kind === 'decide') {
    if (typeof body.packet !== 'string' || !/^[0-9a-f]{64}$/.test(body.packet)) return 'packet';
    if (!['approve', 'return', 'reject'].includes(body.verdict)) return 'verdict';
    if ('evidence_id' in body && !int(body.evidence_id)) return 'evidence_id';
    if ('note' in body && (typeof body.note !== 'string' || body.note.length > 4000)) return 'note';
    if ('issue_id' in body && !int(body.issue_id)) return 'issue_id';
  }
  if (kind === 'observe_release') {
    if (body.readiness_id !== null && !int(body.readiness_id)) return 'readiness_id';
    if (typeof body.released_at !== 'string' || Number.isNaN(Date.parse(body.released_at))) return 'released_at';
    if (typeof body.reference !== 'string' || body.reference.trim() === '' || body.reference.length > 240) return 'reference';
    if (!int(body.upload_id)) return 'upload_id';
    if (body.checked !== true) return 'checked';
    if (typeof body.note !== 'string' || body.note.trim() === '' || body.note.length > 4000) return 'note';
    if (body.environment !== null && (typeof body.environment !== 'string' || body.environment.length > 160)) return 'environment';
    if (body.private_log_id !== null && !int(body.private_log_id)) return 'private_log_id';
  }
  return null;
}

const refused = (field, message = 'This field is missing or not accepted.') => [400, { code: 'bad_request', message: 'We could not read that request.', fields: [{ name: field, message }] }];

function write(id, route, scenario, csrfOk, rawBytes) {
  const c = current(id);
  if (!c) return [404, BODIES[404]];
  if (!csrfOk) return [403, CSRF_FAILED];
  let body;
  try {
    body = JSON.parse(Buffer.from(rawBytes ?? []).toString('utf8') || '{}');
  } catch {
    return [400, BODIES[400]];
  }
  const kind = route === '/planning-exit' ? 'decide' : body.action;
  if (!WRITE_KEYS[kind] || (route === '/planning-exit' && 'action' in body)) return refused('action');
  const bad = problem(kind, body);
  if (bad) return refused(bad);
  if (scenario === 'wdrop0') return ['drop'];
  if (SCENARIO[scenario]) return SCENARIO[scenario];
  const exp = route === '/planning-exit' ? c.exit : c.register;
  if (body.expected_revision !== exp.expected_revision || body.case_revision !== exp.case_revision || scenario === 'w409') return [409, BODIES[409]];
  const next = { ...c, register: { ...c.register }, exit: { ...c.exit } };
  const bump = () => {
    for (const part of [next.register, next.exit]) part.expected_revision += 1;
  };
  if (kind === 'decide') {
    if (!c.exit.verdicts.includes(body.verdict) || c.exit.packet !== body.packet) return [409, BODIES[409]];
    const direct = body.verdict === 'approve' && c.exit.can_approve_directly;
    if (!direct && !('evidence_id' in body)) return [422, { code: 'invalid', message: 'Choose the evidence for this decision.', fields: [{ name: 'evidence_id', message: 'Evidence is needed.' }] }];
    if ('evidence_id' in body && !c.exit.proofs.some((p) => p.id === body.evidence_id)) return [422, { code: 'invalid', message: 'That evidence is not current.', fields: [{ name: 'evidence_id', message: 'Choose a listed record.' }] }];
    if (body.verdict === 'return' && (body.note ?? '').trim() === '') return [422, BODIES[422]];
    next.exit.latest_decision = { id: 92, verdict: body.verdict, role: 'PMO Lead', by: 'Kemi Adebayo', at: NOW, direct };
    next.exit.verdicts = [];
    if (body.verdict === 'approve') next.register.actions = ['prepare_readiness'];
  } else if (kind === 'prepare_readiness') {
    if (!c.register.actions.includes('prepare_readiness')) return [409, BODIES[409]];
    next.register.readiness_ids = [71];
    next.register.actions = ['observe_release'];
  } else {
    if (!c.register.actions.includes('observe_release') || c.register.release !== null) return [409, BODIES[409]];
    if (body.readiness_id !== null && !c.register.readiness_ids.includes(body.readiness_id)) return [422, BODIES[422]];
    next.register.release = { reference: body.reference, released_at: body.released_at, environment: body.environment, evidence_id: 9001 };
    next.register.actions = [];
  }
  bump();
  next.exit.case_revision += 1;
  next.register.case_revision += 1;
  next.moved = ['waiting', 'Waiting'];
  live[id] = next;
  if (scenario === 'wdrop') return ['drop'];
  return [200, { work_id: id, state: 'waiting', revision: next.register.expected_revision, record_id: 100 + next.register.expected_revision }];
}

/** One release read or write. `scenario` is the cookie or header value. */
export function releaseLive({ method, url, scenario, csrfOk, persona, rawBytes }) {
  const found = RELEASE_PATH.exec(url.pathname);
  const status = Number(scenario);
  if (BODIES[status]) return [status, BODIES[status]];
  if (persona === 'none') return [404, BODIES[404]];
  const id = Number(found[1] ?? found[3] ?? found[4]);
  const part = found[2];
  if (id === 4890) return [404, BODIES[404]];
  if (method === 'post') return part ? write(id, part, scenario, csrfOk, rawBytes) : [405, { code: 'method_not_allowed', message: 'Read only.' }];
  if (method !== 'get') return [405, { code: 'method_not_allowed', message: 'Read only.' }];
  if (found[3]) return scenario === 'uat500' ? [500, SCENARIO.w500[1]] : [200, UAT(id)];
  if (found[4]) return [200, APPOINTMENTS];
  if (!part) return [200, item(id)];
  return [200, part === '/planning-exit' ? current(id).exit : current(id).register];
}
