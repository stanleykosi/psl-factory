// F-111: the issue follow-up reads (SCR-30 part 1) in the live shapes of contract 1.25.0: GET /work/{id}, /work/{id}/issue-followup,
// /projects/{case}/issues/{id} and /projects/{case}/issues/{id}/messages. Sample data; no business rules. Reads only.
// Fixtures: 5101 In Progress, 5102 overdue, 5103 no owner, 5104 verified, 5105 messages 403, 5106 unavailable, 5107 detail 503.
export const ISSUES_PATH = /^\/api\/v1\/(?:work\/(51\d\d)(\/issue-followup)?|projects\/([^/]+)\/issues\/(\d+)(\/messages)?)$/;

const CASE = '6c2f1d3e-1a4b-4b8e-9d0a-0a1b2c3d4e5f';
const NOW = '2026-11-23T09:00:00Z';
const BODY = {
  401: { code: 'not_signed_in', message: 'Sign in to continue.' },
  403: { code: 'forbidden', message: 'Your role does not allow this.' },
  404: { code: 'not_found', message: 'This record is unavailable.' },
  429: { code: 'rate_limited', message: 'Too many requests.' },
  503: { code: 'unavailable', message: 'A dependency is unavailable.' },
};

const work = (id, patch) => ({
  id, case_id: CASE, title: 'Login fails on older Android phones', line: 'pmo_issues', state: 'waiting', status_label: 'Waiting', owner: 'Tunde Bello', sample: false,
  updated_at: NOW, api_url: `/api/v1/work/${id}`, reference: null, started_at: '2026-11-20T09:00:00Z', verified_at: null,
  queue_output_url: null, exception_code: null, exception_next_step: null, exception_started_at: null, action_kind: null, station: null, agent: null,
  tracking_url: null, proofs_url: null, revision: 3, case_revision: 7, next_step: 'Wait for the owner to update the issue.', blocker: '', tasks: [], screens: [], actions: [],
  progress: null, aggregate: null, panels: [{ key: 'issue-followup', url: `/api/v1/work/${id}/issue-followup`, contract_path: null }], output_url: null,
  information: [], available_control: [], ...patch,
});

const issue = (n, patch) => ({
  id: n, state_id: 900 + n, reference: 'ISS-0233', title: 'Login fails on older Android phones', kind: 'defect', status: 'In Progress', severity: 'High', owner_id: 4,
  next_action: 'Wait for Engineering to update the issue.', opened_at: '2026-11-20T08:30:00Z', age_days: 3, acknowledged_at: '2026-11-20T10:00:00Z', resolved_at: null, ...patch,
});
const team = (patch) => ({ mode: 'team', status: 'acknowledged', assignment_id: 7, label: 'Engineering', can_record: true, can_resolve: false, finding: '', ...patch });
const milestone = { id: 31, name: 'Go-live', url: '/api/v1/projects/x/milestones/31' };

// id -> { work, issue, team, followup extras, timeline, ack, messages }
const request = (n, kind, status, at) => ({ id: n, kind, status, at });
const ITEMS = {
  5101: {
    work: work(5101),
    issue: issue(233, {}),
    team: team({}),
    followup: { can_request_update: true, blocked_milestone: milestone, blocked_planned_milestone: null, response_task: { id: 61, revision: 2 }, next_action: 'Wait for Engineering to update the issue.', finding: '' },
    timeline: [request(1, 'state', 'Open', '2026-11-20T08:30:00Z'), request(2, 'request', 'Sent', '2026-11-20T09:00:00Z'), request(3, 'acknowledgement', 'Acknowledged', '2026-11-20T10:00:00Z'), request(4, 'state', 'In Progress', '2026-11-20T10:05:00Z')],
    ack: { status: 'Acknowledged', at: '2026-11-20T10:00:00Z', basis: 'Owner replied by email', reply_id: 5 },
    messages: { items: [{ draft_id: 41, version: 1, kind: 'request', body: 'Please update this issue.', status: 'Sent', review_id: 3, verdict: 'approve', dispatch_id: 8, receipt: { id: 9, delivered: true, delivered_at: '2026-11-20T09:01:00Z', recorded_at: '2026-11-20T09:02:00Z', source_evidence_id: null, reference: 'R-9' }, finding: '' }], timing: { last_receipt_id: 9, reminder_due_at: '2026-11-25T09:00:00Z', escalation_due_at: '2026-11-27T09:00:00Z', reminder_overdue: false, escalation_overdue: false, escalation_target: null, finding: '' } },
  },
  5102: {
    work: work(5102),
    issue: issue(234, { status: 'Open', acknowledged_at: null }),
    team: team({ status: 'asked' }),
    followup: { can_request_update: true, blocked_milestone: milestone, blocked_planned_milestone: null, response_task: { id: 62, revision: 1 }, next_action: 'Chase the owner for an update.', finding: '' },
    timeline: [request(1, 'state', 'Open', '2026-11-09T08:30:00Z'), request(2, 'request', 'Sent', '2026-11-09T09:00:00Z'), request(3, 'reminder', 'Sent', '2026-11-16T09:00:00Z')],
    ack: { status: 'Not acknowledged', at: null, basis: null, reply_id: null },
    messages: { items: [
      { draft_id: 42, version: 1, kind: 'request', body: 'Please update this issue.', status: 'Sent', review_id: 3, verdict: 'approve', dispatch_id: 8, receipt: { id: 9, delivered: true, delivered_at: '2026-11-09T09:01:00Z', recorded_at: '2026-11-09T09:02:00Z', source_evidence_id: null, reference: 'R-9' }, finding: '' },
      { draft_id: 43, version: 1, kind: 'reminder', body: 'Reminder.', status: 'Sent', review_id: 4, verdict: 'approve', dispatch_id: 10, receipt: null, finding: '' },
    ], timing: { last_receipt_id: null, reminder_due_at: '2026-11-16T09:00:00Z', escalation_due_at: '2026-11-18T09:00:00Z', reminder_overdue: true, escalation_overdue: true, escalation_target: 'PMO lead', finding: 'No response since 09 Nov' } },
  },
  5103: {
    work: work(5103, { owner: null }),
    issue: issue(235, { status: 'Open', severity: null, opened_at: null, age_days: null, acknowledged_at: null }),
    team: team({ status: 'unassigned', assignment_id: null, label: '', can_record: false, finding: 'This issue has no owner.' }),
    followup: { can_request_update: false, blocked_milestone: milestone, blocked_planned_milestone: null, response_task: null, next_action: 'Choose an owner for this issue.', finding: '' },
    timeline: [request(1, 'state', 'Open', '2026-11-20T08:30:00Z')],
    ack: { status: 'Not acknowledged', at: null, basis: null, reply_id: null },
    messages: { items: [], timing: null },
  },
  5104: {
    work: work(5104, { state: 'verified', status_label: 'Verified', verified_at: NOW, next_step: 'Nothing more to do.' }),
    issue: issue(236, { status: 'Resolved', resolved_at: '2026-11-22T10:00:00Z', age_days: 5 }),
    team: team({ status: 'resolved' }),
    followup: { can_request_update: false, blocked_milestone: null, blocked_planned_milestone: { stage: 'uat', name: 'UAT', policy_id: 3 }, response_task: null, next_action: 'No further step is needed.', finding: 'The fix was confirmed by Engineering on 22 Nov.' },
    timeline: [request(1, 'state', 'Open', '2026-11-18T08:30:00Z'), request(2, 'state', 'Resolved', '2026-11-22T10:00:00Z')],
    ack: { status: 'Acknowledged', at: '2026-11-19T10:00:00Z', basis: null, reply_id: 5 },
    messages: { items: [], timing: null },
  },
};
ITEMS[5105] = { ...ITEMS[5101], work: work(5105), issue: issue(237, {}), messagesStatus: 403 };
ITEMS[5107] = { ...ITEMS[5101], work: work(5107), issue: issue(239, {}), detailStatus: 503 };
const BY_ISSUE = Object.fromEntries(Object.entries(ITEMS).map(([id, it]) => [it.issue.id, { id: Number(id), ...it }]));

const send = (status, body) => [status, body];
let log = [];
export const resetIssues = () => {
  log = [];
};
export const issuesLog = () => log;

/** One issue read; null when the path is not an issue route, so the caller falls through. */
export function issuesRoute({ method, url, scenario, persona }) {
  const m = ISSUES_PATH.exec(url.pathname);
  if (!m || method !== 'get') return null;
  log.push(`${method.toUpperCase()} ${url.pathname}`);
  const forced = Number(scenario);
  if (BODY[forced]) return send(forced, BODY[forced]);
  if (persona === 'none') return send(404, BODY[404]);
  if (m[1]) {
    const it = ITEMS[m[1]];
    if (!it || m[1] === '5106') return send(404, BODY[404]);
    if (!m[2]) return send(200, it.work);
    const { issue: i, team: t, followup, work: w } = it;
    return send(200, { expected_revision: w.revision, case_revision: w.case_revision, issue: i, team: t, source_id: 700 + i.id, ...followup });
  }
  const it = BY_ISSUE[Number(m[4])];
  if (!it || m[3] !== it.work.case_id) return send(404, BODY[404]);
  const caseRevision = it.work.case_revision;
  if (m[5]) {
    if (it.messagesStatus) return send(it.messagesStatus, BODY[it.messagesStatus]);
    return send(200, { case_revision: caseRevision, state_id: it.issue.state_id, items: it.messages.items, evidence: [], timing: it.messages.timing });
  }
  if (it.detailStatus) return send(it.detailStatus, BODY[it.detailStatus]);
  return send(200, {
    case_revision: caseRevision, issue: it.issue, team: it.team, blocked_milestone: it.followup.blocked_milestone, blocked_planned_milestone: it.followup.blocked_planned_milestone,
    history: [], messages_url: `/api/v1/projects/${m[3]}/issues/${it.issue.id}/messages`, timeline: it.timeline, acknowledgement: it.ack,
  });
}
