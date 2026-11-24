// F-85: the live work item reads and the case file upload, in the live shapes of contract 1.22.0
// (GET /work/{id}, GET /work/{id}/history, GET /work/{id}/weekly-report, POST /cases/{case_id}/files and the file-draft
// routes). Integer work ids only: v7 ids ("W-1003") keep answering from the v7 fixtures. Sample data; no business rules.
// Fixtures: 4101 verified, 4102 processing with a weekly report panel, 4103 a decision waiting, 4104 stuck with null
// revisions, 4105 handoff-only (null revision), 4106 unavailable to everyone, 4107 a weekly report with no parts and
// nothing cited, 4108 history of exactly 30 rows. 2501 to 2505 back the delivery overview rows of project P-0101
// (delivery-overview.mjs): the same line, state, reference and date as the row that links to them.
// A scenario (cookie psl_mock_scenario or header X-Mock-Scenario) answers every route here with that status; csrf_failed
// answers writes with the stale-token 403.
export const WORK_LIVE_PATH = /^\/api\/v1\/work\/(\d+)(\/history|\/weekly-report)?$/;
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
  // API 1.24.0 fields; the page draws none of them yet (tracking, facts and reference are a later feature)
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
  4101: item(4101, { title: 'Invoice for Lagoon Health', line: 'invoice', state: 'verified', status_label: 'Verified', next_step: 'Nothing more to do.', output_url: '/api/v1/work/4101/output' }),
  4102: item(4102, {
    state: 'processing',
    status_label: 'Processing',
    next_step: 'The agent is drafting the update. You will be asked to review it.',
    current_activity: { label: 'Drafting the weekly update', watching: true },
    progress: { status: 'drafting', updated_at: NOW },
    panels: [{ key: 'weekly-report', url: '/api/v1/work/4102/weekly-report', contract_path: null }],
  }),
  4103: item(4103, {
    state: 'waiting',
    status_label: 'Waiting for a decision',
    next_step: 'Review the draft and approve or return it.',
    tasks: [
      { id: 9101, kind: 'review', role: 'PMO Lead', status: 'open', revision: 2, claimed_by_you: false, can_claim: false, can_decide: true, verdicts: ['approve', 'return'], url: '/api/v1/tasks/9101' },
      { id: 9102, kind: 'approval', role: 'Finance Lead', status: 'open', revision: 1, claimed_by_you: false, can_claim: false, can_decide: false, verdicts: [], url: '/api/v1/tasks/9102' },
    ],
  }),
  4104: item(4104, { state: 'setup_needed', status_label: 'Setup needed', owner: null, blocker: 'A policy value is missing.', next_step: 'Ask the PMO Lead to set the value.', revision: null, case_revision: null }),
  4105: item(4105, { state: 'action_needed', status_label: 'Action needed', revision: null, department_handoff_url: '/handoff/4105' }),
  4107: item(4107, { state: 'waiting', status_label: 'Waiting', panels: [{ key: 'weekly-report', url: '/api/v1/work/4107/weekly-report', contract_path: null }, { key: 'forecast', url: '/api/v1/work/4107/forecast', contract_path: null }] }),
  4108: item(4108, { state: 'verified', status_label: 'Verified' }),
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
};

const HISTORY_ROWS = [
  { at: '2026-11-23T08:00:00Z', station: 'draft', status: 'completed', actor_kind: 'worker', entry_id: 301, actor: 'Chidi', evidence_id: 11 },
  { at: '2026-11-23T07:30:00Z', station: 'review', status: 'approved', task_id: 9101, actor_kind: 'person', entry_id: 302, actor: 'Kemi Adebayo', reason: 'Figures agree with the ledger.', evidence_id: null },
  { at: '2026-11-23T07:00:00Z', station: 'odd_station', status: 'odd_status', actor_kind: 'worker', entry_id: 303, evidence_id: null },
];
const kindOf = { worker: (r) => r.station === 'draft', decision: (r) => r.station === 'review', evidence: (r) => r.evidence_id != null };
function historyOf(id, kind) {
  if (id === 4108) return Array.from({ length: 30 }, (_, i) => ({ at: new Date(Date.parse(NOW) - i * 60000).toISOString(), station: 'draft', status: 'completed', actor_kind: 'worker', entry_id: 400 + i }));
  if (id === 4101) return kind ? HISTORY_ROWS.filter(kindOf[kind] ?? (() => true)) : HISTORY_ROWS;
  return kind && kindOf[kind] ? HISTORY_ROWS.filter(kindOf[kind]) : HISTORY_ROWS;
}

let uploads = 0;
let log = [];
export const resetWorkLive = () => {
  uploads = 0;
  log = [];
};
/** The uploads, drafts and reviews the mock accepted: tests read it to count what was sent. */
export const workLiveLog = () => log;

const send = (status, body) => [status, body];

/** One live read or upload. `scenario` is the cookie or header value; `csrfOk` is whether the write carried the persona's token. */
export function workLive({ method, url, scenario, csrfOk, persona, rawBytes }) {
  const read = WORK_LIVE_PATH.exec(url.pathname);
  const write = CASE_FILES_PATH.exec(url.pathname);
  const status = Number(scenario);
  if (BODIES[status]) return send(status, BODIES[status]);
  if (read && method === 'get') {
    if (scenario === 'csrf_failed') return send(403, CSRF_FAILED);
    const id = Number(read[1]);
    if (persona === 'none' || id === 4106 || (!WORK[id] && !REPORTS[id] && id !== 4108)) return send(404, BODIES[404]);
    if (!read[2]) return send(200, WORK[id]);
    if (read[2] === '/history') {
      const kind = url.searchParams.get('kind');
      if (kind && !['worker', 'decision', 'evidence'].includes(kind)) return send(400, BODIES[400]);
      return send(200, { items: historyOf(id, kind), as_of: NOW, next_before: null });
    }
    return REPORTS[id] ? send(200, REPORTS[id]) : send(404, BODIES[404]);
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
