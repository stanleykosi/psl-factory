// F-98: the bid pack and RFP submission (ids 4501 to 4509, and a pack on 4401) are in bid-pack-live.mjs.
// F-96: GET and POST /work/{id}/bid-answers for ids 4401 to 4404 are in bid-answers-live.mjs.
// F-85: the live work item reads and the case file upload, in the live shapes of contract 1.22.0
// (GET /work/{id}, GET /work/{id}/history, GET /work/{id}/weekly-report, POST /cases/{case_id}/files and the file-draft
// routes). Integer work ids only: v7 ids ("W-1003") keep answering from the v7 fixtures. Sample data; no business rules.
// Fixtures: 4101 verified, 4102 processing with a weekly report panel, 4103 a decision waiting, 4104 stuck with null
// revisions, 4105 handoff-only (null revision), 4106 unavailable to everyone, 4107 a weekly report with no parts and
// nothing cited, 4108 history of exactly 30 rows. 2501 to 2505 back the delivery overview rows of project P-0101
// (delivery-overview.mjs): the same line, state, reference and date as the row that links to them.
// A scenario (cookie psl_mock_scenario or header X-Mock-Scenario) answers every route here with that status; csrf_failed
// answers writes with the stale-token 403.
// F-87: the work item's own writes (POST /work/{id}/actions, /control, /background). Fixtures: 4120 awaiting reconciliation
// (reconcile, revision 5), 4121 stopped (resume and cancel, revision 3), 4122 processing with background (revision 7), 4110
// null revision (reconcile and cancel listed), 4111 nothing listed, 4123 lists adopt_profile and release_invoice (never drawn).
// Write scenarios answer only the three write routes, so the re-read still works: w403, w403csrf, w409 (the item moves on to
// a higher revision), w422, w429, w503, w500, wdrop (the connection is cut after the write ran). `ready` makes a reconcile find the item ready.
import { BID_PACK_IDS, packMoved, packReads, packWrite, resetBidPack } from './bid-pack-live.mjs';
import { BID_ANSWERS_IDS, bidAnswersRead, bidAnswersWrite, bidMoved, resetBidAnswers } from './bid-answers-live.mjs';

export const WORK_LIVE_PATH = /^\/api\/v1\/work\/(\d+)(\/history|\/tracking|\/weekly-report|\/bid-answers|\/bid-pack|\/bid-pack\/review-request|\/bid-submission|\/reviews|\/actions|\/control|\/background)?$/;
export const CASE_FILES_PATH = /^\/api\/v1\/cases\/([^/]+)\/(files|files\/(\d+)\/drafts|file-drafts\/(\d+)\/review)$/;

const CASE = '6c2f1d3e-1a4b-4b8e-9d0a-0a1b2c3d4e5f';
const NOW = '2026-11-23T09:00:00Z';
const BODIES = {
  400: { code: 'bad_request', message: 'We could not read that request.' },
  401: { code: 'not_signed_in', message: 'Sign in to continue.' },
  403: { code: 'forbidden', message: 'Your role does not allow this.' },
  404: { code: 'not_found', message: 'This record is unavailable.' },
  409: { code: 'stale_revision', message: 'Someone changed this since you opened it.' },
  413: { code: 'too_large', message: 'The file is too large.' },
  415: { code: 'unsupported_media', message: 'The file type is not accepted.' },
  422: { code: 'invalid', message: 'Check the file and try again.', fields: [{ name: 'file', message: 'The file is empty.' }] },
  429: { code: 'rate_limited', message: 'Too many requests.' },
  503: { code: 'unavailable', message: 'A dependency is unavailable.' },
};
const CSRF_FAILED = { code: 'csrf_failed', message: 'Your session check failed. Reload and try again.' };

const item = (id, patch) => ({
  id,
  case_id: CASE,
  title: 'Weekly update for Lagoon Health',
  line: 'weekly_report',
  state: 'ready',
  status_label: 'Ready',
  owner: 'Tunde Bello',
  sample: false,
  updated_at: NOW,
  django_url: `/work/${id}/`,
  api_url: `/api/v1/work/${id}`,
  // API 1.26.0 fields: reference, agent and tracking_url feed the header, the agent card and the tracking read (F-91)
  reference: null,
  started_at: '2026-11-20T09:00:00Z',
  verified_at: null,
  queue_output_url: null,
  exception_code: null,
  exception_next_step: null,
  exception_started_at: null,
  action_kind: null,
  station: null,
  agent: null,
  tracking_url: null,
  proofs_url: null,
  revision: 3,
  case_revision: 7,
  next_step: 'No further step is needed yet.',
  blocker: '',
  tasks: [],
  screens: [],
  actions: [],
  progress: null,
  aggregate: null,
  panels: [],
  output_url: null,
  information: [],
  available_control: [],
  ...patch,
});

const delivery = (id, line, title, state, status_label, reference, updated_at) =>
  item(id, { case_id: '00000000-0000-4000-8000-000000000101', title: `${title} for Lagoon Health`, line, state, status_label, reference, updated_at, next_step: state === 'verified' ? 'Nothing more to do.' : 'No further step is needed yet.' });

const WORK = {
  // F-113: the work behind the delivery overview rows of P-0101 (mock/delivery-overview.mjs).
  2501: delivery(2501, 'delivery-release/v1', 'Release gates', 'verified', 'Verified', 'REL-0091', '2026-03-25T10:00:00Z'),
  2502: delivery(2502, 'delivery-go-live/v1', 'Go-live acceptance', 'verified', 'Verified', 'GLV-0104', '2026-04-02T10:00:00Z'),
  2503: delivery(2503, 'delivery-hypercare/v1', 'Hypercare', 'verified', 'Verified', 'HYP-0062', '2026-11-18T10:00:00Z'),
  2504: delivery(2504, 'delivery-handover/v1', 'Handover to Support', 'action_needed', 'Action needed', 'HND-0048', '2026-11-20T10:00:00Z'),
  2505: delivery(2505, 'delivery-archive/v1', 'Archive', 'ready', 'Ready', 'ARC-0130', '2026-11-19T10:00:00Z'),
  4101: item(4101, { title: 'Invoice for Lagoon Health', line: 'invoice', state: 'verified', status_label: 'Verified', next_step: 'Nothing more to do.', output_url: '/api/v1/work/4101/output', reference: 'INV-0412', agent: 'Chidi', verified_at: '2026-11-22T16:40:00Z', tracking_url: '/api/v1/work/4101/tracking' }),
  4102: item(4102, {
    state: 'processing',
    status_label: 'Processing',
    next_step: 'The agent is drafting the update. You will be asked to review it.',
    current_activity: { label: 'Drafting the weekly update', watching: true },
    progress: { status: 'drafting', updated_at: NOW },
    agent: 'Tola',
    tracking_url: '/api/v1/work/4102/tracking',
    panels: [{ key: 'weekly-report', url: '/api/v1/work/4102/weekly-report', contract_path: null }],
  }),
  4103: item(4103, {
    state: 'waiting',
    status_label: 'Waiting for a decision',
    next_step: 'Review the draft and approve or return it.',
    tracking_url: '/api/v1/work/4103/tracking',
    tasks: [
      { id: 9101, kind: 'review', role: 'PMO Lead', status: 'open', revision: 2, claimed_by_you: false, can_claim: false, can_decide: true, verdicts: ['approve', 'return'], url: '/api/v1/tasks/9101' },
      { id: 9102, kind: 'approval', role: 'Finance Lead', status: 'open', revision: 1, claimed_by_you: false, can_claim: false, can_decide: false, verdicts: [], url: '/api/v1/tasks/9102' },
    ],
  }),
  4104: item(4104, { state: 'setup_needed', status_label: 'Setup needed', owner: null, blocker: 'A policy value is missing.', next_step: 'Ask the PMO Lead to set the value.', revision: null, case_revision: null, tracking_url: '/api/v1/work/4104/tracking' }),
  4105: item(4105, { state: 'action_needed', status_label: 'Action needed', revision: null, department_handoff_url: '/handoff/4105' }),
  4107: item(4107, { state: 'waiting', status_label: 'Waiting', tracking_url: '/api/v1/work/4107/tracking', panels: [{ key: 'weekly-report', url: '/api/v1/work/4107/weekly-report', contract_path: null }, { key: 'forecast', url: '/api/v1/work/4107/forecast', contract_path: null }] }),
  4108: item(4108, { state: 'verified', status_label: 'Verified' }),
  4110: item(4110, { state: 'awaiting_reconciliation', status_label: 'Awaiting reconciliation', revision: null, actions: ['reconcile'], available_control: ['cancel'] }),
  4111: item(4111, { state: 'ready', status_label: 'Ready' }),
  4120: item(4120, { title: 'Invoice for Lagoon Health', line: 'invoice', state: 'awaiting_reconciliation', status_label: 'Awaiting reconciliation', revision: 5, actions: ['reconcile'] }),
  4121: item(4121, { state: 'action_needed', status_label: 'Stopped', revision: 3, available_control: ['resume', 'cancel'] }),
  4122: item(4122, { state: 'processing', status_label: 'Processing', revision: 7, actions: ['background'], current_activity: { label: 'Drafting the weekly update', watching: false } }),
  4123: item(4123, { state: 'action_needed', status_label: 'Stopped', revision: 2, actions: ['release_invoice'], available_control: ['adopt_profile'] }),
  // F-96: RFP responses (panel readbacks in bid-answers-live.mjs); item revision 6, case revision 12
  ...Object.fromEntries(
    BID_ANSWERS_IDS.map((id) => [
      id,
      item(id, { title: 'RFP response for Lagoon Health', line: 'rfp-response/v1', state: 'action_needed', status_label: 'Action needed', revision: 6, case_revision: 12, panels: [{ key: 'bid-answers', url: `/api/v1/work/${id}/bid-answers`, contract_path: null }] }),
    ]),
  ),
  // F-98: RFP submissions (readbacks and writes in bid-pack-live.mjs); item revision 9, case revision 89
  ...Object.fromEntries(
    BID_PACK_IDS.map((id) => [
      id,
      item(id, { title: 'RFP submission for Lagoon Health', line: 'rfp-response/v1', revision: 9, case_revision: 89, panels: [{ key: 'bid-submission', url: `/api/v1/work/${id}/bid-submission`, contract_path: null }] }),
    ]),
  ),
  // F-89: weekly reports under review, returned and received (readbacks in REPORTS below); item revision 6, case revision 12
  ...Object.fromEntries(
    [4130, 4131, 4132, 4133, 4134, 4135, 4136, 4137, 4138].map((id) => [
      id,
      item(id, { state: id === 4132 ? 'action_needed' : 'waiting', status_label: id === 4132 ? 'Action needed' : 'Waiting for a decision', revision: 6, case_revision: 12, panels: [{ key: 'weekly-report', url: `/api/v1/work/${id}/weekly-report`, contract_path: null }] }),
    ]),
  ),
};

// what a write changed: id -> { state, status_label, revision }; reset with the mock
let moved = {};
let movedReport = {};
const current = (id) => (WORK[id] ? { ...WORK[id], ...moved[id], ...bidMoved(id), ...packMoved(id) } : undefined);
const STATUS_LABEL = { ready: 'Ready', cancelled: 'Cancelled', awaiting_reconciliation: 'Awaiting reconciliation', processing: 'Processing' };
const WRITE_SCENARIOS = {
  w403: [403, BODIES[403]],
  w409: [409, { code: 'stale_version', message: 'Someone changed this since you opened it.' }],
  w422: [422, { code: 'setup_required', message: 'A policy value is missing.', fields: [{ name: 'policy', message: 'Ask the PMO Lead to set it.' }] }],
  w429: [429, BODIES[429]],
  w503: [503, BODIES[503]],
  w500: [500, { code: 'server_error', message: 'Something broke.' }],
};

const REPORT = (patch) => ({
  expected_revision: 3,
  case_revision: 7,
  selection: { start_at: '2026-11-16T00:00:00Z', end_at: '2026-11-22T23:59:59Z', template_id: 5, content_id: 8 },
  editable_parts: null,
  draft: null,
  return_review_id: null,
  can_correct: false,
  document_version_id: null,
  return_note: null,
  preview: null,
  review_notes: [],
  review_verdicts: [],
  recipients: [],
  next_action: 'Nothing to do yet.',
  evidence: [],
  ...patch,
});
const part = (text, ids) => ({ text, evidence_ids: ids });
const EDITABLE = { status: part('Build is on track.', [301]), risks: part('One supplier is late.', [302, 303]), timeline: part('Hand-over on 5 Dec.', []), next_steps: part('Confirm the test date.', [304]) };
const PREVIEW = {
  id: 9101,
  title: 'Weekly update',
  number: 1,
  sections: [
    { key: 'status', text: 'Build is <b>on track</b>.\nTesting starts Monday.' },
    { key: 'risks', text: 'One supplier is late.' },
    { key: 'timeline', text: 'Hand-over on 5 Dec.' },
    { key: 'next_steps', text: 'Confirm the test date.' },
  ],
};
const REVIEW_REPORT = (patch) =>
  REPORT({
    expected_revision: 6,
    case_revision: 12,
    document_version_id: 9101,
    review_verdicts: ['approve', 'return', 'reject'],
    preview: PREVIEW,
    review_notes: [{ section: 'risks', text: 'Agent note: the supplier date is unconfirmed.', recorded_at: '2026-11-22T09:00:00Z' }],
    recipients: [{ name: 'Amaka Eze', status: 'pending', receipt_id: null, recorded_at: null }],
    ...patch,
  });
const REPORTS = {
  4102: REPORT({
    editable_parts: { status: part('Build is on track.', [11, 12, 13]), risks: part('One supplier is late.', [14]), timeline: part('Hand-over on 5 Dec.', []), next_steps: part('Confirm the test date.', [15, 16]) },
    can_correct: true,
    recipients: [
      { name: 'Amaka Eze', status: 'sent', receipt_id: 71, recorded_at: '2026-11-22T10:00:00Z' },
      { name: 'Bola Ade', status: 'sent', receipt_id: null, recorded_at: null },
    ],
    next_action: 'Wait for the client to confirm receipt.',
    evidence: [{ id: 11, version: 1, kind: 'status_note' }],
  }),
  4107: REPORT({}),
  ...Object.fromEntries(
    [
      [4130, {}],
      [4131, { review_verdicts: ['approve', 'return'] }],
      [4132, { return_review_id: 7001, return_note: 'Please add the 14 Nov supplier delay to Risks.', can_correct: true, editable_parts: EDITABLE, review_verdicts: [], preview: null, review_notes: [] }],
      [4133, { review_verdicts: [], preview: null, review_notes: [] }],
      [4134, { document_version_id: null }],
      [4135, { return_review_id: 7001, can_correct: true, editable_parts: null, review_verdicts: [], preview: null, review_notes: [] }],
      [4136, { preview: null }],
      [4137, { preview: { ...PREVIEW, id: 9102 } }],
      [4138, { review_notes: [{ section: 'scope', text: 'Agent note: scope is not in this version.', recorded_at: '2026-11-22T09:30:00Z' }] }],
    ].map(([id, patch]) => [id, REVIEW_REPORT(patch)]),
  ),
};

// F-91: GET /work/{id}/tracking. 4102 processing, 4101 verified, 4103 a decision waiting (reviewed unknown), 4104 stuck with one
// station unknown; 4107 answers 503 and 4105 has no tracking_url.
const STATION_NAMES = { intake: 'Intake', execution: 'Execution', decision: 'Decision', delivery: 'Delivery', verified: 'Verified' };
const stationsOf = (rows) => rows.map(([key, status, owner], i) => ({ key, name: STATION_NAMES[key], position: i + 1, status, owner }));
const FACTS_NONE = { drafted: false, reviewed: false, approved: false, sent: false, receipt: false, verified: false };
const trackingOf = (id, stations, facts, patch = {}) => {
  const list = stationsOf(stations);
  return {
    work_id: id,
    as_of: NOW,
    next_step: WORK[id].next_step,
    blocker: WORK[id].blocker,
    owner: WORK[id].owner,
    station: list.find((s) => s.status === 'current') ?? list[list.length - 1],
    stations: list,
    started_at: '2026-11-20T09:00:00Z',
    started_by: 'Tunde Bello',
    verified_at: null,
    facts: { ...FACTS_NONE, ...facts },
    worker_history_url: `/api/v1/work/${id}/history?kind=worker`,
    decision_history_url: `/api/v1/work/${id}/history?kind=decision`,
    evidence_history_url: `/api/v1/work/${id}/history?kind=evidence`,
    can_record_delivery_observation: false,
    delivery_observation_url: null,
    uncertain_effects: [],
    last_activity: null,
    ...patch,
  };
};
const TRACKING = {
  4101: () =>
    trackingOf(4101, [['intake', 'recorded', 'Tunde Bello'], ['execution', 'recorded', 'Chidi'], ['decision', 'recorded', 'Ada Okafor'], ['delivery', 'recorded', null], ['verified', 'recorded', null]], { drafted: true, reviewed: true, approved: true, sent: true, receipt: true, verified: true }, { verified_at: '2026-11-22T16:40:00Z' }),
  4102: () =>
    trackingOf(4102, [['intake', 'recorded', 'Tunde Bello'], ['execution', 'current', 'Tola'], ['decision', 'pending', null], ['delivery', 'pending', null], ['verified', 'pending', null]], { drafted: null }, { last_activity: { kind: 'worker', status: 'drafting', at: NOW, agent_process: 'weekly report draft', evidence_id: null } }),
  4103: () =>
    trackingOf(4103, [['intake', 'recorded', 'Tunde Bello'], ['execution', 'recorded', 'Tola'], ['decision', 'current', 'Ada Okafor'], ['delivery', 'pending', null], ['verified', 'pending', null]], { drafted: true, reviewed: null }),
  4104: () =>
    trackingOf(4104, [['intake', 'recorded', null], ['execution', 'current', null], ['decision', 'unknown', null], ['delivery', 'pending', null], ['verified', 'pending', null]], {}, { owner: null }),
};

const HISTORY_ROWS = [
  { at: '2026-11-23T08:00:00Z', station: 'draft', status: 'completed', actor_kind: 'worker', entry_id: 301, actor: 'Chidi', evidence_id: 11 },
  { at: '2026-11-23T07:30:00Z', station: 'review', status: 'approved', task_id: 9101, actor_kind: 'person', entry_id: 302, actor: 'Kemi Adebayo', reason: 'Figures agree with the ledger.', evidence_id: null },
  { at: '2026-11-23T07:00:00Z', station: 'odd_station', status: 'odd_status', actor_kind: 'worker', entry_id: 303, evidence_id: null },
];
const kindOf = { worker: (r) => r.station === 'draft', decision: (r) => r.station === 'review', evidence: (r) => r.evidence_id != null };
// 4101 with no filter has 60 changes in two pages of 30; `before` is the entry id of the last row of the page before.
const MORE_ROWS = Array.from({ length: 57 }, (_, i) => ({ at: new Date(Date.parse(NOW) - (i + 2) * 3600000).toISOString(), station: 'draft', status: 'completed', actor_kind: 'worker', entry_id: 299 - i, actor: 'Chidi', evidence_id: null }));
function historyOf(id, kind, before) {
  if (id === 4108) return { items: Array.from({ length: 30 }, (_, i) => ({ at: new Date(Date.parse(NOW) - i * 60000).toISOString(), station: 'draft', status: 'completed', actor_kind: 'worker', entry_id: 400 + i })), next_before: null };
  if (kind && kindOf[kind]) return { items: HISTORY_ROWS.filter(kindOf[kind]), next_before: null };
  if (id !== 4101) return { items: HISTORY_ROWS, next_before: null };
  const all = [...HISTORY_ROWS, ...MORE_ROWS];
  const rest = before === null ? all : all.filter((r) => r.entry_id < before);
  const items = rest.slice(0, 30);
  return { items, next_before: rest.length > 30 ? items[items.length - 1].entry_id : null };
}

let uploads = 0;
let log = [];
export const resetWorkLive = () => {
  uploads = 0;
  log = [];
  moved = {};
  movedReport = {};
  resetBidAnswers();
  resetBidPack();
};
/** The uploads, drafts and reviews the mock accepted: tests read it to count what was sent. */
export const workLiveLog = () => log;

const send = (status, body) => [status, body];

/** One of the three work item writes. The body is the raw bytes; the result is moved only when the scenario lets the write through. */
function workWrite(id, route, scenario, csrfOk, rawBytes) {
  const item = current(id);
  if (!item) return send(404, BODIES[404]);
  if (scenario === 'w403csrf' || !csrfOk) return send(403, CSRF_FAILED);
  let body = {};
  try {
    body = JSON.parse(Buffer.from(rawBytes ?? []).toString('utf8') || '{}');
  } catch {
    return send(400, BODIES[400]);
  }
  log.push({ route, work_id: id, body });
  const action = route === 'background' ? 'background' : body.action;
  const listed = route === 'control' ? item.available_control.includes(action) : item.actions.includes(action);
  if (!listed) return send(409, { code: 'action_unavailable', message: 'That is not available for this item now.' });
  if (scenario === 'w409') {
    moved[id] = { ...moved[id], revision: (item.revision ?? 0) + 2 };
    return send(409, WRITE_SCENARIOS.w409[1]);
  }
  if (WRITE_SCENARIOS[scenario]) return send(...WRITE_SCENARIOS[scenario]);
  const state =
    route === 'actions' ? (scenario === 'ready' ? 'ready' : 'awaiting_reconciliation') : action === 'cancel' ? 'cancelled' : action === 'resume' ? 'ready' : item.state;
  // as the live API does, a background change leaves the revision as it was; the others move it on
  const revision = route === 'background' ? item.revision : item.revision + 1;
  moved[id] = { state, status_label: STATUS_LABEL[state] ?? item.status_label, revision };
  // the connection is cut after the write ran: the page cannot know, and the re-read shows the item moved
  if (scenario === 'wdrop') return ['drop'];
  return send(route === 'control' ? 200 : 202, { work_id: id, state, revision });
}

/** F-89: POST /work/{id}/reviews and /weekly-report. Scenarios: w403, w403csrf, w409 (the report moves on), w422 (a note or reason field), w429, w503, w500 and wdrop (the write ran, the answer is lost) or wdrop0 (the answer is lost, the write did not run). */
function reportWrite(id, route, scenario, csrfOk, rawBytes) {
  const report = REPORTS[id] && { ...REPORTS[id], ...movedReport[id] };
  const item = current(id);
  if (!report || !item) return send(404, BODIES[404]);
  if (scenario === 'w403csrf' || !csrfOk) return send(403, CSRF_FAILED);
  let body = {};
  try {
    body = JSON.parse(Buffer.from(rawBytes ?? []).toString('utf8') || '{}');
  } catch {
    return send(400, BODIES[400]);
  }
  const review = route === 'reviews';
  log.push({ route, work_id: id, body });
  const listed = review ? report.review_verdicts.includes(body.verdict) && body.version_id === report.document_version_id : report.can_correct;
  if (!listed || body.expected_revision !== report.expected_revision) return send(409, { code: 'stale_version', message: 'Someone changed this since you opened it.' });
  const move = (state) => {
    movedReport[id] = { expected_revision: report.expected_revision + 1, review_verdicts: [], can_correct: false };
    moved[id] = { state, status_label: STATUS_LABEL[state] ?? item.status_label, revision: item.revision + 1 };
  };
  if (scenario === 'w409') {
    movedReport[id] = { expected_revision: report.expected_revision + 2 };
    return send(409, WRITE_SCENARIOS.w409[1]);
  }
  if (scenario === 'w403') return send(403, { code: 'forbidden', message: 'You wrote this report, so you can’t review it.' });
  if (scenario === 'w422') return send(422, { code: 'invalid', message: review ? 'The review was not accepted.' : 'The update was not accepted.', fields: [review ? { name: 'note', message: 'A note is needed to return a report.' } : { name: 'reason', message: 'Say why the report changed.' }] });
  if (WRITE_SCENARIOS[scenario]) return send(...WRITE_SCENARIOS[scenario]);
  const state = review ? 'waiting' : 'processing';
  if (scenario === 'wdrop0') return ['drop'];
  move(state);
  if (scenario === 'wdrop') return ['drop'];
  return review ? send(200, { work_id: id, state, revision: moved[id].revision, review_id: 8001 }) : send(201, { work_id: id, state, revision: moved[id].revision });
}

/** One live read or upload. `scenario` is the cookie or header value; `csrfOk` is whether the write carried the persona's token. */
export function workLive({ method, url, scenario, csrfOk, persona, rawBytes }) {
  const read = WORK_LIVE_PATH.exec(url.pathname);
  const write = CASE_FILES_PATH.exec(url.pathname);
  const status = Number(scenario);
  const packId = Number(read?.[1]);
  const packRoute = read?.[2];
  // F-98: the bid pack's writes, and the RFP review (kind bid), come before the weekly report's reviews
  if (read && method === 'post' && (packRoute === '/bid-pack/review-request' || packRoute === '/bid-submission' || (packRoute === '/reviews' && (BID_PACK_IDS.includes(packId) || packId === 4401)))) return packWrite(packId, packRoute, scenario, csrfOk, rawBytes, current(packId));
  if (read && method === 'post' && read[2] === '/bid-answers') return bidAnswersWrite(Number(read[1]), scenario, csrfOk, rawBytes);
  if (read && method === 'post' && read[2] && /^\/(reviews|weekly-report)$/.test(read[2])) return reportWrite(Number(read[1]), read[2].slice(1), scenario, csrfOk, rawBytes);
  if (read && method === 'post' && read[2] && /^\/(actions|control|background)$/.test(read[2])) return workWrite(Number(read[1]), read[2].slice(1), scenario, csrfOk, rawBytes);
  if (BODIES[status]) return send(status, BODIES[status]);
  if (read && method === 'get') {
    if (scenario === 'csrf_failed') return send(403, CSRF_FAILED);
    const id = Number(read[1]);
    if (persona === 'none' || id === 4106 || (!WORK[id] && !REPORTS[id] && id !== 4108)) return send(404, BODIES[404]);
    if (!read[2]) return send(200, current(id));
    if (read[2] === '/history') {
      const kind = url.searchParams.get('kind');
      if (kind && !['worker', 'decision', 'evidence'].includes(kind)) return send(400, BODIES[400]);
      const before = url.searchParams.get('before');
      if (before !== null && !/^\d+$/.test(before)) return send(400, BODIES[400]);
      return send(200, { ...historyOf(id, kind, before === null ? null : Number.parseInt(before, 10)), as_of: NOW });
    }
    if (read[2] === '/tracking') {
      if (id === 4107) return send(503, BODIES[503]);
      return TRACKING[id] ? send(200, TRACKING[id]()) : send(404, BODIES[404]);
    }
    if (read[2] === '/bid-answers') return bidAnswersRead(id, persona);
    if (read[2] === '/bid-pack' || read[2] === '/bid-submission') return packReads(id, read[2], persona);
    return REPORTS[id] ? send(200, { ...REPORTS[id], ...movedReport[id] }) : send(404, BODIES[404]);
  }
  if (write && method === 'post') {
    if (scenario === 'csrf_failed' || !csrfOk) return send(403, CSRF_FAILED);
    if (write[2] === 'files') {
      uploads += 1;
      log.push({ route: 'files', case_id: write[1], bytes: rawBytes?.length ?? 0 });
      return send(200, { upload_id: 8000 + uploads, name: 'upload.pdf', size: rawBytes?.length ?? 0, sha256: 'a'.repeat(64), download_url: `/api/v1/cases/${write[1]}/files/${8000 + uploads}/download` });
    }
    if (write[4] === undefined) {
      log.push({ route: 'drafts', upload_id: Number(write[3]) });
      return send(202, { job_id: 6001, upload_id: Number(write[3]), role: 'A01', status: 'draft', label: 'Draft ready', attempt: 1, draft: { pin: 'p1', summary: 'A short summary.', excerpts: [], questions: [] }, recovery_pin: null, reviewed_evidence_id: null, workflow_record_id: null });
    }
    log.push({ route: 'review', job_id: Number(write[4]) });
    return send(200, { job_id: Number(write[4]), upload_id: 8001, role: 'A01', status: 'reviewed', label: 'Reviewed', attempt: 1, draft: null, recovery_pin: null, reviewed_evidence_id: 5001, workflow_record_id: null });
  }
  return send(404, BODIES[404]);
}
