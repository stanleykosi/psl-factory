// F-118: closure (SCR-49) in the live shapes of contract 1.26.x: GET /work/{id}, GET /work/{id}/history, POST /work/{id}/reviews
// (kind closure), POST /work/{id}/closure-report, and GET /projects/{case}/delivery/{dossier}/closure-checklist and
// .../finance-confirmation (GET and POST). Integer ids 6201 to 6209 only (the spec named 4301 to 4308; those are taken); the dossier is
// the work id plus 800. Every other id falls through. Sample data; no business rules. The server turns a project's UUID into its P-nnnn
// form before routing, so the project routes are matched in both forms.
// 6201 not yet (retrospective held, finance unknown; the Finance read answers 403); 6202 ready to prepare; 6203 awaiting the Head of
// PMO (the Finance read names a finding); 6204 the viewer may decide (the closure ids are not served, so Close and Return are held; the
// Finance read lists two milestones); 6205 returned (a return row in the history); 6206 closed, debt with an amount, an unknown amount
// and a limited list; 6207 closed, no debt; 6208 closed, debt not visible; 6209 not yours (404 everywhere).
// Scenarios (cookie psl_mock_scenario or header x-mock-scenario): a status number answers every route here with it; w403, w403csrf,
// w409, w413, w422, w429, w503, w500 answer only the writes; wdrop (the write ran, the answer is lost) and wdrop0 (nothing ran).
import { workLive } from './work-live.mjs';

export const CLOSURE_PATH = /^\/api\/v1\/(?:work\/(620[1-9])(\/history|\/reviews|\/closure-report)?|projects\/(?:00000000-0000-4000-8000-00000000|P-)(620[1-9])\/delivery\/(\d+)\/(closure-checklist|finance-confirmation))$/;

const NOW = '2026-11-26T09:00:00Z';
const caseOf = (id) => `00000000-0000-4000-8000-00000000${id}`;
const dossierOf = (id) => id + 800;
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
  w403: [403, { code: 'forbidden', message: 'Only the Head of PMO can do this.' }],
  w403csrf: [403, CSRF_FAILED],
  w409: [409, BODIES[409]],
  w422: [422, BODIES[422]],
  w413: [413, { code: 'too_large', message: 'That is too large.' }],
  w429: [429, BODIES[429]],
  w503: [503, BODIES[503]],
  w500: [500, { code: 'server_error', message: 'Something broke.' }],
};

const TITLES = {
  context: 'Current project scope',
  go_live: 'Go-live acceptance',
  hypercare: 'Release stability',
  archive: 'Project archive',
  handover: 'Support handover',
  retrospective: 'Retrospective',
  finance: 'Finance notification coverage',
  report: 'PM closure report',
};
const OK = 'Current recorded evidence is available';
const check = (key, status = 'current', patch = {}) => ({ key, title: TITLES[key], status, summary: OK, references: status === 'current' ? [100 + Object.keys(TITLES).indexOf(key)] : [], finding: null, ...patch });
const allCurrent = () => Object.keys(TITLES).map((k) => check(k));
const withChecks = (patch) => allCurrent().map((c) => (patch[c.key] ? { ...c, ...patch[c.key] } : c));
const task = (patch = {}) => ({ id: 9301, kind: 'review', role: 'Head of PMO', status: 'open', revision: 2, claimed_by_you: false, can_claim: false, can_decide: false, verdicts: [], url: '/api/v1/tasks/9301', ...patch });
const row = (patch) => ({ entry_id: 9501, station: 'Closure review', actor_kind: 'person', task_id: 9301, actor: 'Ada Okafor', ...patch });
const FINANCE = { revision: 41, confirmation_id: null, finding: null, milestones: [{ milestone_id: 31, receipt_id: 71 }, { milestone_id: 32, receipt_id: 72 }] };
const OPEN = { items: [{ reference: 'INV-0533', currency: 'NGN', basis: 'Milestone invoice', owed: '1250000.00', api_url: '/api/v1/projects/x/billing-invoices/1' }, { reference: 'INV-0540', currency: 'NGN', basis: 'Milestone invoice', owed: null, api_url: '/api/v1/projects/x/billing-invoices/2' }], limited: true, as_of: '2026-11-20' };

const START = {
  6201: {
    state: 'waiting',
    ready: false,
    checks: withChecks({ retrospective: { status: 'held', references: [], summary: 'Select the current record of an actual post-release retrospective', finding: 'No retrospective saved' }, finance: { status: 'unknown', references: [], summary: 'Ask an authorised Finance person to confirm the exact milestone notification inventory' }, report: { status: 'unknown', references: [] } }),
    tasks: [],
    finance: 403,
  },
  6202: { state: 'ready', ready: true, checks: allCurrent(), tasks: [] },
  6203: {
    state: 'waiting',
    ready: false,
    checks: withChecks({ finance: { status: 'unknown', references: [], summary: 'Ask an authorised Finance person to confirm the exact milestone notification inventory' } }),
    tasks: [task()],
    finance: { ...FINANCE, finding: 'Receipt missing for milestone 3', milestones: [] },
  },
  6204: {
    state: 'action_needed',
    ready: false,
    checks: withChecks({ finance: { status: 'unknown', references: [], summary: 'Ask an authorised Finance person to confirm the exact milestone notification inventory' } }),
    tasks: [task({ can_decide: true, verdicts: ['approve', 'return'] })],
    finance: FINANCE,
  },
  6205: {
    state: 'action_needed',
    ready: true,
    checks: allCurrent(),
    tasks: [],
    history: [row({ status: 'return', at: '2026-11-24T14:30:00Z', reason: 'Add the client’s sign-off on the hypercare summary to the report.' })],
  },
  6206: { state: 'verified', closed: 7, checks: [{ ...check('context', 'closed'), summary: 'Project closure is recorded.' }, ...allCurrent().slice(1)], tasks: [], debt: OPEN },
  6207: { state: 'verified', closed: 7, checks: [{ ...check('context', 'closed'), summary: 'Project closure is recorded.' }, ...allCurrent().slice(1)], tasks: [], debt: { items: [], limited: false, as_of: '2026-11-20' } },
  6208: { state: 'verified', closed: 7, checks: [{ ...check('context', 'closed'), summary: 'Project closure is recorded.' }, ...allCurrent().slice(1)], tasks: [], debt: null },
};

// what the writes changed: id -> the same parts; reset with the mock
let live = {};
export const resetClosureLive = () => {
  live = {};
};
const current = (id) => live[id] ?? { ...START[id], revision: 8, caseRevision: 41, history: START[id].history ?? [] };

const item = (id) => {
  const c = current(id);
  const [, template] = workLive({ method: 'get', url: new URL('http://mock/api/v1/work/4101'), scenario: undefined, csrfOk: true, persona: 'finance_lead' });
  const labels = { ready: 'Ready', waiting: 'Waiting', action_needed: 'Action needed', verified: 'Verified' };
  return {
    ...template,
    id,
    case_id: caseOf(id),
    title: 'Project closure for Kora Logistics',
    line: 'delivery-closure/v1',
    state: c.state,
    status_label: labels[c.state],
    reference: 'CLS-0021',
    output_url: null,
    tracking_url: null,
    agent: null,
    verified_at: c.state === 'verified' ? '2026-11-25T12:00:00Z' : null,
    updated_at: `${NOW.slice(0, 17)}${String(c.revision).padStart(2, '0')}Z`,
    django_url: `/work/${id}/`,
    api_url: `/api/v1/work/${id}`,
    revision: c.revision,
    case_revision: c.caseRevision,
    actions: [],
    available_control: [],
    current_activity: null,
    tasks: c.tasks,
    panels: [{ key: 'closure-checklist', url: `/api/v1/projects/${caseOf(id)}/delivery/${dossierOf(id)}/closure-checklist`, contract_path: '/api/v1/projects/{case_id}/delivery/{dossier_id}/closure-checklist' }],
  };
};

const checklist = (id) => {
  const c = current(id);
  return {
    revision: c.caseRevision,
    as_of: NOW,
    ready_to_prepare: c.ready ?? false,
    recorded_closure_id: c.closed ?? null,
    checks: c.checks,
    debt: c.debt ?? null,
    retrospective_url: null,
  };
};

const int = (v) => Number.isInteger(v) && v >= 1;
const refused = (field) => [400, { code: 'bad_request', message: 'We could not read that request.', fields: [{ name: field, message: 'This field is missing or not accepted.' }] }];
const invalid = (field, message) => [422, { code: 'invalid', message, fields: [{ name: field, message }] }];
const KEYS = {
  review: ['kind', 'expected_revision', 'case_revision', 'version_id', 'evidence_id', 'verdict', 'note'],
  report: ['expected_revision', 'case_revision', 'previous_evidence_id', 'report_text', 'source_reference', 'reason'],
  finance: ['revision', 'milestone_ids', 'inventory_complete', 'evidence_id', 'note'],
};
const text = (v, max) => typeof v === 'string' && v.trim() !== '' && v.length <= max;

/** A problem with the body (a field name), or null: the contract's exact keys and types. */
function problem(kind, b) {
  const keys = Object.keys(b);
  if (keys.length !== KEYS[kind].length || !KEYS[kind].every((k) => k in b)) return keys.find((k) => !KEYS[kind].includes(k)) ?? KEYS[kind].find((k) => !(k in b));
  if (kind === 'finance') {
    if (!int(b.revision)) return 'revision';
    if (!Array.isArray(b.milestone_ids) || !b.milestone_ids.every(int)) return 'milestone_ids';
    if (b.inventory_complete !== true) return 'inventory_complete';
    if (!int(b.evidence_id)) return 'evidence_id';
    return text(b.note, 4000) ? null : 'note';
  }
  if (!int(b.expected_revision)) return 'expected_revision';
  if (!int(b.case_revision)) return 'case_revision';
  if (kind === 'review') {
    if (b.kind !== 'closure') return 'kind';
    if (!int(b.version_id)) return 'version_id';
    if (!int(b.evidence_id)) return 'evidence_id';
    if (!['approve', 'return', 'reject'].includes(b.verdict)) return 'verdict';
    return typeof b.note === 'string' && b.note.length <= 4000 ? null : 'note';
  }
  if (!(b.previous_evidence_id === null || int(b.previous_evidence_id))) return 'previous_evidence_id';
  if (!text(b.report_text, 16000)) return 'report_text';
  if (!text(b.source_reference, 160)) return 'source_reference';
  return text(b.reason, 2000) ? null : 'reason';
}

function write(id, kind, scenario, csrfOk, rawBytes) {
  if (!csrfOk) return [403, CSRF_FAILED];
  const c = current(id);
  let body;
  try {
    body = JSON.parse(Buffer.from(rawBytes ?? []).toString('utf8') || '{}');
  } catch {
    return [400, BODIES[400]];
  }
  const mayDecide = c.tasks.some((t) => t.can_decide);
  // a stale copy is answered 409 before anything else, so a second reviewer on an old page learns it changed
  if (kind === 'review' && Number.isInteger(body.expected_revision) && body.expected_revision !== c.revision) return [409, BODIES[409]];
  if (kind === 'review' && !mayDecide) return [403, BODIES[403]];
  if (kind === 'finance' && (c.finance === undefined || c.finance === 403)) return [403, BODIES[403]];
  const bad = problem(kind, body);
  if (bad) return refused(bad);
  if (scenario === 'wdrop0') return ['drop'];
  if (SCENARIO[scenario]) return SCENARIO[scenario];
  const after = { ...c, revision: c.revision + 1, caseRevision: c.caseRevision + 1 };
  if (kind === 'finance') {
    if (body.revision !== c.caseRevision) return [409, BODIES[409]];
    if (c.finance.finding || body.milestone_ids.join() !== c.finance.milestones.map((m) => m.milestone_id).join()) return invalid('milestone_ids', 'Confirm the exact listed milestones.');
    if (c.finance.confirmation_id !== null) return [409, BODIES[409]];
    after.finance = { ...c.finance, revision: after.caseRevision, confirmation_id: 9701 };
    after.checks = c.checks.map((k) => (k.key === 'finance' ? { ...k, status: 'current', references: [9701], summary: OK } : k));
    live[id] = after;
    if (scenario === 'wdrop') return ['drop'];
    return [201, { confirmation_id: 9701, revision: after.caseRevision }];
  }
  if (body.expected_revision !== c.revision || body.case_revision !== c.caseRevision) return [409, BODIES[409]];
  if (kind === 'review') {
    if (body.version_id !== 9601 || body.evidence_id !== 9602) return invalid('version_id', 'Decide the exact current closure report.');
    if (body.verdict === 'return' && body.note.trim() === '') return invalid('note', 'A note is needed to return.');
    if (body.verdict === 'reject') return invalid('verdict', 'Choose a listed verdict.');
    const decided = row({ entry_id: 9600 + after.revision, status: body.verdict, at: NOW, actor: 'Tunde Bello', ...(body.verdict === 'return' ? { reason: body.note } : {}) });
    after.history = [decided, ...c.history];
    after.tasks = [];
    if (body.verdict === 'approve') Object.assign(after, { state: 'verified', closed: 7, ready: true, debt: null });
    else after.state = 'action_needed';
    live[id] = after;
    if (scenario === 'wdrop') return ['drop'];
    return [200, { work_id: id, state: after.state, revision: after.revision, review_id: 9600 + after.revision }];
  }
  const previous = c.checks.find((k) => k.key === 'report')?.references[0] ?? null;
  if (body.previous_evidence_id !== previous) return [409, BODIES[409]];
  after.state = 'waiting';
  after.tasks = [task()];
  after.checks = c.checks.map((k) => (k.key === 'report' ? { ...k, status: 'current', references: [9800 + after.revision] } : k));
  live[id] = after;
  if (scenario === 'wdrop') return ['drop'];
  return [201, { work_id: id, state: after.state, revision: after.revision, report_evidence_id: 9800 + after.revision }];
}

/** One closure read or write. `scenario` is the cookie or header value. */
export function closureLive({ method, url, scenario, csrfOk, persona, rawBytes }) {
  const found = CLOSURE_PATH.exec(url.pathname);
  const status = Number(scenario);
  if (BODIES[status]) return [status, BODIES[status]];
  const id = Number(found[1] ?? found[3]);
  if (persona === 'none' || id === 6209) return [404, BODIES[404]];
  const part = found[2] ?? (found[5] ? `/${found[5]}` : '');
  if (found[4] !== undefined && Number(found[4]) !== dossierOf(id)) return [404, BODIES[404]];
  const c = current(id);
  if (method === 'post') {
    const kind = { '/reviews': 'review', '/closure-report': 'report', '/finance-confirmation': 'finance' }[part];
    return kind ? write(id, kind, scenario, csrfOk, rawBytes) : [405, { code: 'method_not_allowed', message: 'Read only.' }];
  }
  if (method !== 'get') return [405, { code: 'method_not_allowed', message: 'Read only.' }];
  if (part === '') return [200, item(id)];
  if (part === '/history') return [200, { items: c.history, as_of: NOW, next_before: null }];
  if (part === '/closure-checklist') return [200, checklist(id)];
  if (c.finance === undefined || c.finance === 403) return [403, BODIES[403]];
  return [200, c.finance];
}
