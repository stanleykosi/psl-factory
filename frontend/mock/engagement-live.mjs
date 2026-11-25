// F-97: the engagement and planning panels in the live shapes of contract 1.26.x (GET /work/{id}, GET|POST /work/{id}/engagement,
// GET /work/{id}/planning-owner-requests, and the project's engagement-intake, planning and planning/source-clarifications reads).
// Integer ids 4650 to 4657 only; every other id falls through to work-live.mjs. Sample data; no business rules.
// 4650 engagement open to confirm the PM, 4651 open to record details (and re-check), 4652 open to register, 4653 registered with its
// planning handoff, 4654 held (no step open, a finding), 4655 planning with five departments (changed effort, unknown effort, one waiting)
// and an unassigned owner, 4656 planning whose packet read is not available to the person, 4657 planning with no department asked yet.
// (The server turns a project's UUID into its P-nnnn form before routing, so the project reads are matched in both forms.)
// A scenario that is a status answers every route here with it; 'w409' and 'w422' answer only the engagement write.
import { workLive } from './work-live.mjs';

export const ENGAGEMENT_PATH = /^\/api\/v1\/(?:work\/(465[0-7])(\/engagement|\/planning-owner-requests)?|projects\/(?:00000000-0000-4000-8000-00000000|P-)(465[0-7])\/(engagement-intake|planning|planning\/source-clarifications))$/;

const NOW = '2026-11-25T09:00:00Z';
const caseOf = (id) => `00000000-0000-4000-8000-00000000${id}`;
const BODIES = {
  400: { code: 'bad_request', message: 'We could not read that request.' },
  401: { code: 'not_signed_in', message: 'Sign in to continue.' },
  403: { code: 'forbidden', message: 'Your role does not allow this.' },
  404: { code: 'not_found', message: 'This record is unavailable.' },
  409: { code: 'stale_revision', message: 'Someone changed this since you opened it.' },
  422: { code: 'invalid', message: 'The request was not accepted.', fields: [{ name: 'evidence_id', message: 'Choose a current source.' }] },
  429: { code: 'rate_limited', message: 'Too many requests.' },
  503: { code: 'unavailable', message: 'A dependency is unavailable.' },
};
const CSRF_FAILED = { code: 'csrf_failed', message: 'Your session check failed. Reload and try again.' };

const ROLES = ['PM', 'PMO Lead', 'Head of PMO'];
const PROOFS = [
  { id: 50, version: 2, kind: 'engagement_source' },
  { id: 47, version: 1, kind: 'product_input' },
  { id: 44, version: 1, kind: 'rfp_outcome' },
];
const MANAGERS = [
  { id: 31, name: 'Tunde Bello' },
  { id: 32, name: 'Amaka Obi' },
];

const engagement = (id, patch) => ({
  expected_revision: 5,
  case_revision: 89,
  capture: { id: 1, route: 'A', reference: 'PSL-DEMO-KORA', evidence_id: 50, rfp_disposition_id: 1 },
  assignment_id: null,
  registration_id: null,
  planning_work_id: null,
  planning_receipt_id: null,
  planning_packet_id: null,
  finding: '',
  actions: [],
  assignment_roles: ROLES,
  registration_roles: ROLES,
  managers: MANAGERS,
  source_proofs: PROOFS,
  project: { label: 'Kora Logistics · fleet tracker', url: `/api/v1/projects/${caseOf(id)}` },
  planning: { label: 'Project planning', url: `/api/v1/projects/${caseOf(id)}/planning` },
  packet_sources: [
    { key: 'scope', label: 'Engagement source', evidence_id: 50, url: null },
    { key: 'price', label: 'Agreed price', evidence_id: null, url: null },
  ],
  details: null,
  project_contact_id: null,
  ...patch,
});
const DETAILS = { id: 9, reference: 'PSL-DEMO-KORA', plan_id: 47, evidence_id: 50, planned_start: '2026-12-01', contact_id: null };
const START = {
  4650: engagement(4650, { actions: ['assign'] }),
  4651: engagement(4651, { assignment_id: 2, actions: ['details', 'reassess'] }),
  4652: engagement(4652, { assignment_id: 2, details: DETAILS, actions: ['register'] }),
  4653: engagement(4653, { assignment_id: 2, details: DETAILS, registration_id: 3, planning_work_id: 4655, planning_receipt_id: 495, planning_packet_id: 55, project_contact_id: 12 }),
  4654: engagement(4654, { assignment_id: 2, finding: 'The prior identity or planning handoff needs current-source review', managers: [], source_proofs: [], assignment_roles: [], registration_roles: [], planning_work_id: 4655, planning_receipt_id: 495, planning_packet_id: 55 }),
};
const WORKS = {
  4650: ['engagement/v1', 'Engagement for Kora Logistics', 'action_needed', 'Action needed'],
  4651: ['engagement/v1', 'Engagement for Kora Logistics', 'action_needed', 'Action needed'],
  4652: ['engagement/v1', 'Engagement for Kora Logistics', 'action_needed', 'Action needed'],
  4653: ['engagement/v1', 'Engagement for Kora Logistics', 'verified', 'Verified'],
  4654: ['engagement/v1', 'Engagement for Kora Logistics', 'verified', 'Verified'],
  4655: ['planning/v1', 'Planning and delivery handoff', 'action_needed', 'Action needed'],
  4656: ['planning/v1', 'Planning and delivery handoff', 'action_needed', 'Action needed'],
  4657: ['planning/v1', 'Planning and delivery handoff', 'waiting', 'Waiting'],
};

const input = (id, version, party, summary, effort_state, person_days, changed_effort = false) => ({ id, version, source_id: 20 + id, source_party: party, received_at: '2026-11-24T10:30:00Z', summary, effort_state, person_days, changed_effort });
const PLANNING = {
  4655: {
    revision: 89,
    packet_id: 55,
    packet: {
      prd_id: 21,
      scope_id: 24,
      engineering_estimate_id: 22,
      security_estimate_id: 23,
      stakeholders: ['Engineering', 'QA', 'Infra', 'Security'].map((team) => ({ team, contact_id: null, evidence_id: null })),
      questions: [{ key: 'data-residency', detail: 'Where the client data must be stored is not yet settled.', state: 'unresolved', action_id: null, evidence_id: null }],
      source_correlations: [{ key: 'scope_id', source_field: 'scope_id', source_id: 24, document_version: 'v2', target_prd_id: 21, target_scope_id: 24, evidence_id: 24, state: 'conflicting', detail: 'The scope source names a different product than the PRD.', resolution_id: null }],
      collect_department_inputs: true,
    },
    finding: 'Two departments have not been asked yet.',
    can_record_input: false,
    review_roles: ['PMO Lead'],
    effort_reviewed: false,
    departments: [
      { department: 'Engineering', input: input(1, 1, 'Ada Okafor', 'Build the tracker API and the driver app.', 'known', '42.5', true) },
      { department: 'QA', input: input(2, 1, 'Ngozi Adeyemi', 'Test plan agreed; effort not yet sized.', 'unknown', null) },
      { department: 'Security', input: input(3, 1, 'Chinedu Okeke', 'Nothing in this scope needs a security review.', 'not_applicable', null) },
      { department: 'Product', input: null },
      { department: 'Infrastructure', input: input(5, 2, 'Folake Bello', 'Two environments and a pipeline.', 'known', '8.0') },
    ],
    readiness: { evidence_id: 65, delivery_dossiers: [{ id: 7, label: 'Kora delivery dossier, version 1' }], source_ids: [22, 23] },
  },
  4657: { revision: 89, packet_id: 55, packet: null, finding: '', can_record_input: false, review_roles: [], effort_reviewed: false, departments: [], readiness: null },
};
const SOURCES = {
  4655: {
    revision: 89,
    packet_id: 55,
    findings: [{ key: 'product-owner', code: 'owner_missing', detail: 'Nobody is set to receive the Product request.', source_ids: [24] }],
    clarifications: [
      { key: 'Product scope question', action_id: 3, action_version: 1, owner_id: null, owner_status: 'unassigned', status: 'open', response_id: null, approval_granted: false },
      { key: 'Security scan access', action_id: 4, action_version: 1, owner_id: 31, owner_status: 'source_access_held', status: 'open', response_id: null, approval_granted: false },
    ],
    reviewed_costing: { disposition: 'new_costing', proposal: 12, previous: 11 },
    can_assign: false,
  },
  4657: { revision: 89, packet_id: 55, findings: [], clarifications: [], reviewed_costing: null, can_assign: false },
};
const REQUESTS = {
  4655: { expected_revision: 9, requests: [{ request_id: 77, receipt_id: 501, role: 'Product', reference: 'REQ-0077', kind: 'scope_breakdown', requested_at: '2026-11-23T08:00:00Z', source_received_at: '2026-11-22T15:00:00Z', proofs: [] }] },
  4656: { expected_revision: 9, requests: [] },
  4657: { expected_revision: 9, requests: [] },
};

// what the writes changed: id -> engagement; reset with the mock
let live = {};
export const resetEngagementLive = () => {
  live = {};
};
const current = (id) => live[id] ?? START[id];

const item = (id, e) => {
  const [, template] = workLive({ method: 'get', url: new URL('http://mock/api/v1/work/4101'), scenario: undefined, csrfOk: true, persona: 'finance_lead' });
  const [line, title, state, status_label] = WORKS[id];
  const settled = e && e.registration_id !== null && id !== 4653 ? ['verified', 'Verified'] : [state, status_label];
  return {
    ...template,
    id,
    case_id: caseOf(id),
    title,
    line,
    state: settled[0],
    status_label: settled[1],
    reference: 'PSL-DEMO-KORA',
    output_url: null,
    tracking_url: null,
    agent: null,
    verified_at: null,
    updated_at: NOW,
    django_url: `/work/${id}/`,
    api_url: `/api/v1/work/${id}`,
    revision: e ? e.expected_revision : 9,
    case_revision: e ? e.case_revision : 89,
    panels: line === 'engagement/v1' ? [{ key: 'engagement', url: `/api/v1/work/${id}/engagement`, contract_path: null }] : [{ key: 'planning-owner-requests', url: `/api/v1/work/${id}/planning-owner-requests`, contract_path: null }],
  };
};

const BODY_KEYS = {
  assign: ['action', 'expected_revision', 'case_revision', 'key', 'evidence_id', 'role', 'pm_id'],
  details: ['action', 'expected_revision', 'case_revision', 'key', 'evidence_id', 'capture_id', 'reference', 'plan_id', 'checked', 'planned_start', 'contact_id'],
  register: ['action', 'expected_revision', 'case_revision', 'key', 'evidence_id', 'role', 'value', 'plan_id', 'details_id'],
  reassess: ['action', 'expected_revision', 'case_revision', 'capture_id', 'reason'],
};
const int = (v) => Number.isInteger(v) && v >= 1;

/** A problem with the body, as a 400 field message, or null. Exact keys and types of the contract's four bodies. */
function problem(body) {
  const keys = BODY_KEYS[body.action];
  if (!keys) return 'action';
  const names = Object.keys(body);
  const odd = names.find((k) => !keys.includes(k)) ?? keys.find((k) => !(k in body));
  if (odd) return odd;
  if (!int(body.expected_revision)) return 'expected_revision';
  if (!int(body.case_revision)) return 'case_revision';
  if ('key' in body && !(typeof body.key === 'string' && /^[ -~]{1,100}$/.test(body.key))) return 'key';
  if ('evidence_id' in body && !int(body.evidence_id)) return 'evidence_id';
  if ('role' in body && !ROLES.includes(body.role)) return 'role';
  if (body.action === 'assign' && !int(body.pm_id)) return 'pm_id';
  if (body.action === 'details') {
    if (!int(body.capture_id)) return 'capture_id';
    if (typeof body.reference !== 'string' || body.reference.trim() === '' || body.reference.length > 120) return 'reference';
    if (!int(body.plan_id)) return 'plan_id';
    if (body.checked !== true) return 'checked';
    if (body.planned_start !== null && !/^\d{4}-\d{2}-\d{2}$/.test(String(body.planned_start))) return 'planned_start';
    if (body.contact_id !== null && !int(body.contact_id)) return 'contact_id';
  }
  if (body.action === 'register') {
    if (typeof body.value !== 'string' || body.value.trim() === '' || body.value.length > 120) return 'value';
    if (!int(body.plan_id)) return 'plan_id';
    if (body.details_id !== null && !int(body.details_id)) return 'details_id';
  }
  if (body.action === 'reassess') {
    if (body.capture_id !== null && !int(body.capture_id)) return 'capture_id';
    if (typeof body.reason !== 'string' || body.reason.trim() === '' || body.reason.length > 2000) return 'reason';
  }
  return null;
}

function write(id, scenario, csrfOk, rawBytes) {
  const e = current(id);
  if (!e) return [404, BODIES[404]];
  if (!csrfOk) return [403, CSRF_FAILED];
  let body;
  try {
    body = JSON.parse(Buffer.from(rawBytes ?? []).toString('utf8') || '{}');
  } catch {
    return [400, BODIES[400]];
  }
  const bad = problem(body);
  if (bad) return [400, { code: 'bad_request', message: 'We could not read that request.', fields: [{ name: bad, message: 'This field is missing or not accepted.' }] }];
  if (scenario === 'w422') return [422, BODIES[422]];
  if (scenario === 'w409' || body.expected_revision !== e.expected_revision || body.case_revision !== e.case_revision || !e.actions.includes(body.action)) {
    live[id] = { ...e, expected_revision: e.expected_revision + 1 };
    return [409, BODIES[409]];
  }
  const next = { ...e, expected_revision: e.expected_revision + 1, case_revision: e.case_revision + 1 };
  if (body.action === 'assign') Object.assign(next, { assignment_id: 2, actions: ['details', 'reassess'] });
  if (body.action === 'details') Object.assign(next, { details: { ...DETAILS, reference: body.reference, plan_id: body.plan_id, evidence_id: body.evidence_id, planned_start: body.planned_start, contact_id: body.contact_id }, actions: ['register', 'reassess'] });
  if (body.action === 'register') Object.assign(next, { registration_id: 3, planning_work_id: 4655, planning_receipt_id: 495, planning_packet_id: 55, actions: [] });
  if (body.action === 'reassess') Object.assign(next, { finding: 'Checked again; nothing changed.' });
  live[id] = next;
  return [201, { work_id: id, state: next.registration_id !== null ? 'verified' : 'action_needed', revision: next.expected_revision, record_id: 100 + next.expected_revision }];
}

/** One engagement or planning read or write. `scenario` is the cookie or header value. */
export function engagementLive({ method, url, scenario, csrfOk, persona, rawBytes }) {
  const found = ENGAGEMENT_PATH.exec(url.pathname);
  const status = Number(scenario);
  if (BODIES[status]) return [status, BODIES[status]];
  const id = Number(found[1] ?? found[3]);
  if (persona === 'none') return [404, BODIES[404]];
  const part = found[2] ?? (found[4] ? `/${found[4]}` : '');
  if (method === 'post') return part === '/engagement' ? write(id, scenario, csrfOk, rawBytes) : [405, { code: 'method_not_allowed', message: 'Read only.' }];
  if (method !== 'get') return [405, { code: 'method_not_allowed', message: 'Read only.' }];
  if (part === '') return [200, item(id, current(id))];
  if (part === '/engagement') return current(id) ? [200, current(id)] : [404, BODIES[404]];
  if (part === '/engagement-intake') return [200, { revision: 89, capture: START[4650].capture, sources: PROOFS, won_dispositions: [1], next_before: null }];
  if (part === '/planning-owner-requests') return REQUESTS[id] ? [200, REQUESTS[id]] : [404, BODIES[404]];
  if (id === 4656) return [404, BODIES[404]];
  if (part === '/planning') return PLANNING[id] ? [200, PLANNING[id]] : [404, BODIES[404]];
  return SOURCES[id] ? [200, SOURCES[id]] : [404, BODIES[404]];
}
