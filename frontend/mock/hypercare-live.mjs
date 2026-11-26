// F-115: the hypercare page (SCR-46) in the live shapes of contract 1.26.x: GET /work/{id}/stability, GET /work/{id}/stability/events,
// the project's issues register read, and POST /work/{id}/background (the pause and continue the work item's own controls send).
// Integer ids 5201 to 5208 only; every other id falls through. (The spec named 4201 to 4208; those are taken, so each is the same number
// plus 1000.) Sample data; no business rules.
// 5201 setup needed (no criteria), 5202 evaluating (one reading, Pause), 5203 qualified and verified (a resolved issue only),
// 5204 not met (an unmet metric, an unknown confirmation, one open High issue that blocks), 5205 evaluating and paused (Continue),
// 5206 unavailable to everyone, 5207 the events read answers 503, 5208 the issues read answers 503.
// Scenarios (cookie psl_mock_scenario or header x-mock-scenario): a status number answers every route here with it; w403, w403csrf, w409,
// w422, w429, w503, w500 answer only the background write; wdrop (the write ran, the answer is lost) and wdrop0 (nothing ran).
import { workLive } from './work-live.mjs';

export const HYPERCARE_PATH = /^\/api\/v1\/(?:work\/(520[1-8])(\/stability\/events|\/stability|\/background)?|projects\/(?:00000000-0000-4000-8000-00000000|P-)(520[1-8])\/issues)$/;

const NOW = '2026-11-26T09:00:00Z';
const caseOf = (id) => `00000000-0000-4000-8000-00000000${id}`;
const BODIES = {
  400: { code: 'bad_request', message: 'We could not read that request.' },
  401: { code: 'not_signed_in', message: 'Sign in to continue.' },
  403: { code: 'forbidden', message: 'Your role does not allow this.' },
  404: { code: 'not_found', message: 'This record is unavailable.' },
  409: { code: 'stale_revision', message: 'Someone changed this since you opened it.' },
  422: { code: 'invalid', message: 'The request was not accepted.', fields: [{ name: 'enabled', message: 'This cannot be changed now.' }] },
  429: { code: 'rate_limited', message: 'Too many requests.' },
  503: { code: 'unavailable', message: 'A dependency is unavailable.' },
};
const CSRF_FAILED = { code: 'csrf_failed', message: 'Your session check failed. Reload and try again.' };
const SCENARIO = {
  w403: [403, { code: 'forbidden', message: 'Only the PM can change this.' }],
  w403csrf: [403, CSRF_FAILED],
  w409: [409, BODIES[409]],
  w422: [422, BODIES[422]],
  w429: [429, BODIES[429]],
  w503: [503, BODIES[503]],
  w500: [500, { code: 'server_error', message: 'Something broke.' }],
};

const CRITERIA = {
  clock: 'elapsed_hours_since_release',
  minimum_hours: 720,
  confirmation_owners: ['Engineering', 'Infrastructure'],
  metrics: [
    { key: 'error_rate', unit: 'percent', owner: 'Engineering', operator: 'lte', threshold: 2 },
    { key: 'uptime', unit: 'percent', owner: 'Infrastructure', operator: 'gte', threshold: 99.5 },
  ],
  financial_controls: 'independent',
};
const CLEARANCE = { scope: 'project_issue_register', reader_id: 4, blocking_statuses: ['Open', 'In Progress'], blocking_severities: ['Critical', 'High'] };
const results = (status, overrides = {}) =>
  [
    ['Engineering', 'confirmation'],
    ['Infrastructure', 'confirmation'],
    ['Engineering', 'elapsed_hours'],
    ['Infrastructure', 'elapsed_hours'],
    ['Engineering', 'metric:error_rate'],
    ['Infrastructure', 'metric:uptime'],
  ]
    .map(([owner, key]) => ({ owner, key, status: overrides[`${owner}/${key}`] ?? status }))
    .concat([{ owner: null, key: 'issue_clearance', status: overrides['issue_clearance'] ?? (status === 'unknown' ? 'unknown' : status) }]);
const checks = (held = null) => [
  { name: 'release', status: 'ready', finding: null },
  { name: 'acceptance', status: 'ready', finding: null },
  { name: 'stability', status: held ? 'held' : 'ready', finding: held },
];
const obs = (owner, n) => ({ owner, source_id: 700 + n, verification_id: 800 + n });
const stability = (patch = {}) => ({
  expected_revision: 8,
  case_revision: 41,
  dossier_id: 7,
  checks: checks(),
  proofs: [],
  configuration_id: 21,
  criteria: { ...CRITERIA, issue_clearance: CLEARANCE },
  can_draft_criteria: false,
  observation_owners: ['Engineering', 'Infrastructure'],
  assessment_id: null,
  qualified: null,
  observations: [],
  criterion_results: [],
  findings: [],
  due_at: '2026-12-26T09:00:00Z',
  verified: false,
  ...patch,
});
const EVIDENCE = { id: 61, version: 1, kind: 'release_record' };
const SIGNED = [{ id: 71, version: 1, kind: 'pm_signature' }, { id: 72, version: 1, kind: 'client_signature' }];
const events = (patch = {}) => ({
  expected_revision: 8,
  case_revision: 41,
  can_record_release: false,
  readiness_ids: [51],
  release_evidence: [EVIDENCE],
  signatures: SIGNED,
  private_logs: [],
  acceptance_packet: 'c'.repeat(64),
  receipts: [{ id: 91, version_id: 2, at: '2026-11-25T16:00:00Z' }],
  ...patch,
});
const issue = (id, status, severity) => ({
  id, state_id: id, reference: `ISS-0${id}`, title: id === 315 ? 'Checkout fails under load' : 'Login is slow', kind: 'defect', status, severity, owner_id: 4,
  next_action: 'Fix the timeout', opened_at: '2026-11-20T09:00:00Z', age_days: 6, acknowledged_at: null, resolved_at: status === 'Resolved' ? '2026-11-24T09:00:00Z' : null,
});

const START = {
  5201: {
    stab: stability({ criteria: null, configuration_id: null, can_draft_criteria: true, due_at: null, observation_owners: [], checks: checks('Hypercare criteria are not set.') }),
    events: events({ can_record_release: true, release_evidence: [], signatures: [], acceptance_packet: null, receipts: [], readiness_ids: [] }),
    issues: [],
  },
  5202: { stab: stability({ observations: [obs('Engineering', 1)], criterion_results: results('unknown', { 'Engineering/metric:error_rate': 'met' }) }), events: events({ acceptance_packet: null, signatures: [], receipts: [] }), issues: [] },
  5203: {
    stab: stability({ assessment_id: 33, qualified: true, verified: true, observations: [obs('Engineering', 1), obs('Infrastructure', 2)], criterion_results: results('met') }),
    events: events(),
    issues: [issue(310, 'Resolved', 'High')],
  },
  5204: {
    stab: stability({
      assessment_id: 34,
      qualified: false,
      observations: [obs('Engineering', 1)],
      criterion_results: results('met', { 'Engineering/metric:error_rate': 'not_met', 'Infrastructure/confirmation': 'unknown', 'Infrastructure/elapsed_hours': 'unknown', 'Infrastructure/metric:uptime': 'unknown', issue_clearance: 'not_met' }),
      findings: ['Engineering/error_rate fails the configured criterion', 'Infrastructure has not confirmed stability'],
      checks: checks('Hypercare is not yet qualified.'),
    }),
    events: events(),
    issues: [issue(315, 'Open', 'High'), issue(310, 'Resolved', 'High')],
  },
  5205: { stab: stability({ observations: [obs('Engineering', 1)], criterion_results: results('unknown') }), events: events(), issues: [], paused: true },
  5207: { stab: stability({ observations: [obs('Engineering', 1)], criterion_results: results('unknown') }), events: events(), issues: [] },
  5208: { stab: stability({ observations: [obs('Engineering', 1)], criterion_results: results('unknown') }), events: events(), issues: [] },
};

// what the writes changed: id -> { paused, revision }; reset with the mock
let live = {};
export const resetHypercareLive = () => {
  live = {};
};
const revisionOf = (id) => live[id]?.revision ?? 8;
const pausedOf = (id) => live[id]?.paused ?? START[id].paused === true;

const item = (id) => {
  const [, template] = workLive({ method: 'get', url: new URL('http://mock/api/v1/work/4101'), scenario: undefined, csrfOk: true, persona: 'finance_lead' });
  const paused = pausedOf(id);
  return {
    ...template,
    id,
    case_id: caseOf(id),
    title: 'Hypercare for Kora Logistics',
    line: 'delivery-hypercare/v1',
    state: paused ? 'waiting' : 'processing',
    status_label: paused ? 'Waiting' : 'Processing',
    reference: 'HYP-0091',
    output_url: null,
    tracking_url: null,
    agent: null,
    verified_at: null,
    updated_at: `${NOW.slice(0, 17)}${String(revisionOf(id)).padStart(2, '0')}Z`,
    django_url: `/work/${id}/`,
    api_url: `/api/v1/work/${id}`,
    revision: revisionOf(id),
    case_revision: 41,
    actions: ['background'],
    available_control: paused ? ['resume'] : [],
    current_activity: { label: paused ? 'Paused' : 'Evaluating hypercare', watching: !paused },
    panels: [
      { key: 'stability', url: `/api/v1/work/${id}/stability`, contract_path: '/api/v1/work/{work_id}/stability' },
      { key: 'stability/events', url: `/api/v1/work/${id}/stability/events`, contract_path: '/api/v1/work/{work_id}/stability/events' },
    ],
  };
};

const refused = (field) => [400, { code: 'bad_request', message: 'We could not read that request.', fields: [{ name: field, message: 'This field is missing or not accepted.' }] }];

function background(id, scenario, csrfOk, rawBytes) {
  if (!csrfOk) return [403, CSRF_FAILED];
  let body;
  try {
    body = JSON.parse(Buffer.from(rawBytes ?? []).toString('utf8') || '{}');
  } catch {
    return [400, BODIES[400]];
  }
  const odd = Object.keys(body).find((k) => !['expected_revision', 'enabled'].includes(k));
  if (odd) return refused(odd);
  if (!Number.isInteger(body.expected_revision) || body.expected_revision < 1) return refused('expected_revision');
  if (typeof body.enabled !== 'boolean') return refused('enabled');
  if (scenario === 'wdrop0') return ['drop'];
  if (SCENARIO[scenario]) return SCENARIO[scenario];
  if (body.expected_revision !== revisionOf(id)) return [409, BODIES[409]];
  live[id] = { paused: !body.enabled, revision: revisionOf(id) + 1 };
  if (scenario === 'wdrop') return ['drop'];
  return [202, { work_id: id, state: body.enabled ? 'processing' : 'waiting', revision: live[id].revision }];
}

/** One hypercare read or write. `scenario` is the cookie or header value. */
export function hypercareLive({ method, url, scenario, csrfOk, persona, rawBytes }) {
  const found = HYPERCARE_PATH.exec(url.pathname);
  const status = Number(scenario);
  if (BODIES[status]) return [status, BODIES[status]];
  const id = Number(found[1] ?? found[3]);
  if (persona === 'none' || id === 5206) return [404, BODIES[404]];
  const part = found[2];
  if (method === 'post') return part === '/background' ? background(id, scenario, csrfOk, rawBytes) : [405, { code: 'method_not_allowed', message: 'Read only.' }];
  if (method !== 'get' || part === '/background') return [405, { code: 'method_not_allowed', message: 'Read only.' }];
  const data = START[id];
  if (found[3]) {
    if (id === 5208) return [503, BODIES[503]];
    const before = url.searchParams.get('before');
    if (before !== null && !/^\d+$/.test(before)) return [400, BODIES[400]];
    return [200, { case_revision: 41, issues: data.issues, next_before: null, owners: [{ id: 4, name: 'Tunde Bello' }], proofs: [] }];
  }
  if (!part) return [200, item(id)];
  if (part === '/stability/events') return id === 5207 ? [503, BODIES[503]] : [200, { ...data.events, expected_revision: revisionOf(id) }];
  return [200, { ...data.stab, expected_revision: revisionOf(id) }];
}
