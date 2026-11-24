// SCR-03 on the live contract (F-64): the decision desk's reads and writes in the live shapes
// (contracts/psl-factory.openapi.json): GET /work/{n}, GET /work/{n}/history, GET /work?queue=decisions,
// GET /tasks/{n} and POST /tasks/{n}/claim, /decision and /comments. Integer ids only; the v7 "W-1201" / "T-1201" ids
// stay with the v7 mock. Sample data only; no business rules.
//
// Tasks: 41 on work 17 is the deciding fixture (claimable by a Finance Lead); 42 on work 18 is not yours (cannot claim,
// cannot decide); 43 on work 19 has no invoice packet (amount unknown). Cookie psl_mock_decide: "stale" answers the
// first decision on task 41 with 409 and serves revision 4 (version 3, 4300000.00) afterwards; "no_evidence" serves
// task 41 with no review evidence. The mock persona "none" cannot claim or decide anything. Scenario cookie or header
// 401, 403, 404, 409, 422 answers every live decide route with that status. State is in memory; /__mock/reset clears it.
const SHA = 'f3a9c1d27b6e4a58c09d1e2f3b4a5968778695a4b3c2d1e0f9a8b7c6d5e4f3a2';
const SHA_B = '0b1c2d3e4f5061728394a5b6c7d8e9f00112233445566778899aabbccddeeff0';
const NOW = '2026-11-23T09:30:00.000Z';

export const LIVE_ERRORS = {
  400: { code: 'bad_request', message: 'We could not read that request.' },
  401: { code: 'not_signed_in', message: 'Sign in to continue.' },
  403: { code: 'forbidden', message: 'Your role does not allow this.' },
  404: { code: 'not_found', message: 'We could not find that record.' },
  409: { code: 'conflict', message: 'This changed while you were reading it. Reload to see the latest version.' },
  422: { code: 'invalid_input', message: 'Check the details and try again.' },
};
const CSRF_FAILED = { code: 'csrf_failed', message: 'Your session check failed. Reload and try again.' };

const WORKS = {
  17: { taskId: 41, title: 'Invoice 3 for the Lekki handover', line: 'finance-ledger/v1' },
  18: { taskId: 42, title: 'Invoice 4 for the Ikeja fit-out', line: 'finance-ledger/v1' },
  19: { taskId: 43, title: 'Invoice 5 for the Yaba office', line: 'finance-ledger/v1' },
};
const TASK_WORK = { 41: 17, 42: 18, 43: 19 };

// task id -> { revision, claimed, decided: { verdict, note, evidenceId, at } | null, redrafted }
const state = new Map();
const comments = [];
let nextComment = 1;
let nextReview = 12;

export function resetLiveDecide() {
  state.clear();
  comments.length = 0;
  nextComment = 1;
  nextReview = 12;
}

const taskState = (taskId) => {
  if (!state.has(taskId)) state.set(taskId, { revision: taskId === 41 ? 3 : 2, claimed: false, decided: null, redrafted: false });
  return state.get(taskId);
};

const OWNED = /^\/api\/v1\/(work\/(\d+)(\/history)?|tasks\/(\d+)(\/(claim|decision|comments))?)$/;

/** True when the live decide mock answers this request. */
export function ownsLiveDecide(method, url) {
  // Work ids 17 to 19 only: the other integer work ids (the F-85 work item fixtures, 41xx) answer from work-live.mjs.
  const match = OWNED.exec(url.pathname);
  if (match) return match[2] === undefined || Boolean(WORKS[Number(match[2])]);
  return method === 'get' && url.pathname === '/api/v1/work' && url.searchParams.get('queue') === 'decisions';
}

function packetOf(taskId, variant, s) {
  if (taskId === 43) return null;
  const redrafted = variant === 'stale' && s.redrafted;
  return {
    invoice_id: 9,
    version: redrafted ? 3 : 2,
    sha256: SHA,
    amount: redrafted ? '4300000.00' : '4250000.00',
    currency: 'NGN',
    recipient: 'Lekki Estates Ltd',
    preparation_id: 5,
    basis: 'Milestone 3 certificate',
    prepared_by: 'Chidi',
    prepared_at: NOW,
    sources: [],
  };
}

function taskBody(taskId, me, variant) {
  const s = taskState(taskId);
  const yours = taskId !== 42 && me.persona !== 'none';
  const open = s.decided === null;
  const task = {
    id: taskId,
    kind: 'invoice_review',
    role: 'finance_reviewer',
    status: open ? 'open' : 'closed',
    revision: variant === 'stale' && s.redrafted ? 4 : s.revision,
    claimed_by_you: yours && open && s.claimed,
    can_claim: yours && open && !s.claimed,
    can_decide: yours && open && s.claimed,
    verdicts: open ? ['approve', 'return', 'reject'] : [],
    url: `/work/${TASK_WORK[taskId]}/decide?task=${taskId}`,
  };
  return { task, work: TASK_WORK[taskId] };
}

function workItem(workId, me, variant) {
  const meta = WORKS[workId];
  const { task } = taskBody(meta.taskId, me, variant);
  const s = taskState(meta.taskId);
  return {
    id: workId,
    case_id: `00000000-0000-4000-8000-0000000000${workId}`,
    title: meta.title,
    line: meta.line,
    state: s.decided ? 'waiting' : 'action_needed',
    status_label: s.decided ? 'Waiting on others' : 'Needs your decision',
    owner: null,
    sample: true,
    updated_at: NOW,
    django_url: `/work/${workId}/`,
    api_url: `/api/v1/work/${workId}`,
    revision: 1,
    case_revision: 1,
    next_step: s.decided ? 'The decision is recorded.' : 'A reviewer decides the invoice.',
    blocker: '',
    tasks: [task],
    screens: [{ key: 'decision', django_url: `/work/${workId}/decision/` }],
    actions: [],
    progress: null,
    aggregate: null,
    panels: [],
    output_url: null,
    information: [],
    available_control: [],
    reference: null,
    started_at: NOW,
    verified_at: null,
    queue_output_url: null,
    exception_code: null,
    exception_next_step: null,
    exception_started_at: null,
    action_kind: s.decided ? null : 'decide',
    station: null,
    agent: null,
    tracking_url: null,
    proofs_url: null,
  };
}

function listItem(workId, me, variant) {
  const { id, case_id, title, line, state, status_label, owner, sample, updated_at, django_url, api_url, reference, started_at, verified_at, queue_output_url, exception_code, exception_next_step, exception_started_at, action_kind, station, agent } = workItem(workId, me, variant);
  return { id, case_id, title, line, state, status_label, owner, sample, updated_at, django_url, api_url, reference, started_at, verified_at, queue_output_url, exception_code, exception_next_step, exception_started_at, action_kind, station, agent };
}

function readBody(taskId, me, variant) {
  const s = taskState(taskId);
  const { task, work } = taskBody(taskId, me, variant);
  const evidence = variant === 'no_evidence' ? [] : [
    { id: 88, version: 2, source: 'signed milestone certificate', sha256: SHA_B },
    { id: 91, version: 2, source: 'client email', sha256: SHA },
  ];
  return {
    task,
    work_id: work,
    label: WORKS[work].title,
    invoice_packet: packetOf(taskId, variant, s),
    decision_hold_code: null,
    review_stations_url: null,
    changes_from_previous: null,
    review_evidence: evidence,
    recipient_change: { earlier: null, current: taskId === 43 ? null : 'Lekki Estates Ltd' },
  };
}

const invalid = (fields) => [422, { ...LIVE_ERRORS[422], fields: fields.map(([name, message]) => ({ name, message })) }];
const isInt = (value) => Number.isInteger(value);

function validBody(op, body) {
  const spec = { claim: { expected_revision: 'int' }, decision: { expected_revision: 'int', verdict: 'str', evidence_id: 'int', note: 'str' }, comments: { revision: 'int', body: 'str' } }[op];
  if (typeof body !== 'object' || body === null || Array.isArray(body)) return [['body', 'Send a JSON object.']];
  const problems = [];
  for (const [key, type] of Object.entries(spec)) {
    if (!(key in body)) problems.push([key, 'This field is required.']);
    else if (type === 'int' ? !isInt(body[key]) : typeof body[key] !== 'string') problems.push([key, 'Check this field.']);
  }
  for (const key of Object.keys(body)) if (!(key in spec)) problems.push([key, 'This field is not accepted.']);
  return problems;
}

/** Reply [status, body] for an owned request. */
export function liveDecideRoute({ method, url, raw, cookies, scenario, token, me: person, persona }) {
  const me = { ...person, persona };
  if (LIVE_ERRORS[scenario]) {
    return [Number(scenario), scenario === '422' ? { ...LIVE_ERRORS[422], fields: [{ name: 'note', message: 'Add a note to return or reject.' }] } : LIVE_ERRORS[scenario]];
  }
  const variant = cookies.psl_mock_decide;
  const { pathname } = url;
  if (method === 'get' && pathname === '/api/v1/work') {
    const items = [17, 18, 19].filter((id) => taskState(WORKS[id].taskId).decided === null).map((id) => listItem(id, me, variant));
    return [200, { items, page: 1, next_page: null, as_of: NOW, page_size: 20, total: items.length, limited: false, total_coverage: 'complete', lines: [], evaluated: items.length, deferred: [], payroll_questions: [] }];
  }
  const workMatch = /^\/api\/v1\/work\/(\d+)(\/history)?$/.exec(pathname);
  if (workMatch) {
    const workId = Number(workMatch[1]);
    if (!WORKS[workId]) return [404, LIVE_ERRORS[404]];
    if (!workMatch[2]) return [200, workItem(workId, me, variant)];
    const s = taskState(WORKS[workId].taskId);
    const items = s.decided
      ? [{ at: s.decided.at, station: 'Finance review', status: s.decided.verdict, task_id: WORKS[workId].taskId, actor: me.name, actor_kind: 'person', entry_id: 1, reason: s.decided.note, evidence_id: s.decided.evidenceId }]
      : [];
    return [200, { items, as_of: NOW, next_before: null }];
  }
  const taskMatch = /^\/api\/v1\/tasks\/(\d+)(?:\/(claim|decision|comments))?$/.exec(pathname);
  const taskId = Number(taskMatch[1]);
  if (!TASK_WORK[taskId]) return [404, LIVE_ERRORS[404]];
  if (method === 'get' && !taskMatch[2]) return [200, readBody(taskId, me, variant)];
  if (method !== 'post' || !taskMatch[2]) return [404, LIVE_ERRORS[404]];
  if (token !== me.csrf_token) return [403, CSRF_FAILED];
  const op = taskMatch[2];
  let body;
  try {
    body = JSON.parse(raw);
  } catch {
    return [400, LIVE_ERRORS[400]];
  }
  const problems = validBody(op, body);
  if (problems.length > 0) return invalid(problems);
  const s = taskState(taskId);
  const current = readBody(taskId, me, variant).task;
  const revision = op === 'comments' ? body.revision : body.expected_revision;
  if (op === 'decision') {
    if (!['approve', 'return', 'reject'].includes(body.verdict)) return invalid([['verdict', 'Choose approve, return or reject.']]);
    if (!readBody(taskId, me, variant).review_evidence.some((e) => e.id === body.evidence_id)) return invalid([['evidence_id', 'Choose evidence recorded on this review.']]);
    if (body.verdict !== 'approve' && body.note.trim() === '') return invalid([['note', 'Add a note to return or reject.']]);
    if (body.note.length > 2000) return invalid([['note', 'Keep the note to 2000 characters or fewer.']]);
  }
  if (op === 'comments' && (body.body.trim() === '' || body.body.length > 2000)) return invalid([['body', 'Write a comment of 1 to 2000 characters.']]);
  // A redraft arrives before the first decision on task 41 is accepted (variant "stale").
  if (op === 'decision' && variant === 'stale' && taskId === 41 && !s.redrafted) {
    s.redrafted = true;
    return [409, LIVE_ERRORS[409]];
  }
  if (revision !== current.revision) return [409, LIVE_ERRORS[409]];
  if (op === 'claim') {
    if (!current.can_claim && !current.claimed_by_you) return [403, LIVE_ERRORS[403]];
    s.claimed = true;
    return [200, { task_id: taskId, revision: current.revision, claimed_by: me.name }];
  }
  if (op === 'decision') {
    if (!current.can_decide) return [403, LIVE_ERRORS[403]];
    s.decided = { verdict: body.verdict, note: body.note, evidenceId: body.evidence_id, at: new Date().toISOString() };
    return [200, { task_id: taskId, review_id: nextReview++, verdict: body.verdict, work_state: 'waiting' }];
  }
  // comments: a person who can decide has no use for the box; the not-yours task takes comments from a signed-in reviewer
  if (current.can_decide || current.can_claim) return [403, LIVE_ERRORS[403]];
  comments.push({ id: nextComment, taskId, body: body.body });
  return [200, { comment_id: nextComment++ }];
}
