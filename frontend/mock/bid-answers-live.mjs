// F-96: the RFP response panel in the live shapes of contract 1.26.0 (GET and POST /work/{id}/bid-answers). Integer ids 4401 to 4404;
// work-live.mjs serves the work items themselves and routes these two operations here. Sample data; no business rules.
// 4401 a PM who can write: one row per status (current, suggested, reviewed, queued, running, held, stale, clarification with a quote)
// and two reusable earlier answers. 4402 read only, with a returned Engineering review and a row the person cannot see.
// 4403 no requirements. 4404 a suggestion that has no source yet (cannot be reviewed). Item and panel share revision 6, case revision 12.
// Writes follow the live rules: tokens must match (else 409), a decision names the suggestion and the review it follows
// (`predecessor`, 0 for none), a suggestion is asked once per operation key, undo puts the earlier answer back and the suggestion
// can be reviewed again. Write scenarios: w403, w409, w422, w429, w503, w500, wdrop (answer lost after the write ran), wdrop0 (write did not run).

export const BID_ANSWERS_IDS = [4401, 4402, 4403, 4404];
const NOW = '2026-11-24T09:00:00Z';
const BODIES = {
  400: { code: 'bad_request', message: 'We could not read that request.' },
  403: { code: 'forbidden', message: 'Your role does not allow this.' },
  404: { code: 'not_found', message: 'This record is unavailable.' },
  409: { code: 'stale_version', message: 'Someone changed this since you opened it.' },
  429: { code: 'rate_limited', message: 'Too many requests.' },
  500: { code: 'server_error', message: 'Something went wrong.' },
  503: { code: 'unavailable', message: 'A dependency is unavailable.' },
};
const SOURCE = { id: 21, kind: 'requirements', version: 1, reference: 'synthetic:lagoon-rfp' };
const row = (position, key, patch = {}) => ({
  key,
  disposition: 'addressed',
  evidence_id: 21,
  response: null,
  status: 'current',
  suggestion_id: null,
  suggested_answer: null,
  review_id: null,
  review_verdict: null,
  can_review: false,
  can_undo: false,
  position,
  source: SOURCE,
  citation: null,
  ...patch,
});
const FRESH = {
  4401: () => [
    row(1, 'R1', { response: 'We host the service in two regions.' }),
    row(2, 'R2', { response: null, status: 'suggested', suggestion_id: 501, suggested_answer: 'Data is encrypted at rest and in transit.', can_review: true, citation: { wording: 'The supplier shall encrypt client data.', page: 12, evidence_id: 21 } }),
    row(3, 'R3', { response: 'Support is available on every business day.', status: 'reviewed', suggestion_id: 502, suggested_answer: 'Support is available on every business day.', review_id: 7001, review_verdict: 'accept', can_undo: true, previous: null }),
    row(4, 'R4', { status: 'queued', suggestion_id: 503 }),
    row(5, 'R5', { status: 'running', suggestion_id: 504 }),
    row(6, 'R6', { status: 'held', suggestion_id: 505 }),
    row(7, 'R7', { response: 'An older answer.', status: 'stale', suggestion_id: 506, suggested_answer: 'A suggestion for the old source.' }),
    row(8, 'R8', { disposition: 'clarification', citation: { wording: 'Describe how the service meets local data rules.', page: null, evidence_id: 21 } }),
  ],
  4402: () => [row(1, 'R1', { response: 'We host the service in two regions.' }), row(2, 'R2', { disposition: 'clarification', status: 'suggested', suggestion_id: 511, suggested_answer: 'A suggestion you cannot act on.' })],
  4403: () => [],
  4404: () => [row(1, 'R1', { status: 'suggested', suggestion_id: 521, suggested_answer: 'A suggestion with no cited source.' })],
};
const PRIOR = [
  { token: 'won-2025-lagos', label: 'Lagos health RFP, won 2025' },
  { token: 'won-2024-abuja', label: 'Abuja ministry RFP, won 2024' },
];
const REVIEW = { 4402: { response_id: 31, role: 'Engineering Lead', verdict: 'return', reason: 'The hosting answer needs the region names.', reviewed_at: '2026-11-24T08:00:00Z' } };

let state = {};
let nextId = 9000;
let keys = new Set();
export const resetBidAnswers = () => {
  state = {};
  nextId = 9000;
  keys = new Set();
};
const panel = (id) => {
  state[id] ??= { rev: 6, case: 12, rows: FRESH[id]() };
  return state[id];
};

/** F-98: a write on the bid pack (the PM's send for review) moves this item on. */
export const bidBump = (id) => {
  const p = panel(id);
  p.rev += 1;
  p.case += 1;
};

/** What a write moved on the work item (its revision), merged over the item by work-live.mjs. */
export const bidMoved = (id) => (state[id] ? { revision: state[id].rev, case_revision: state[id].case } : undefined);

const readOf = (id) => {
  const p = panel(id);
  const visible = p.rows.filter((r) => r.source !== null);
  return {
    expected_revision: p.rev,
    case_revision: p.case,
    can_write: id !== 4402,
    rows: p.rows.map((r) => Object.fromEntries(Object.entries(r).filter(([name]) => name !== 'previous' && name !== 'prior_answer'))),
    next_page: null,
    response_review: REVIEW[id] ?? null,
    counts: { total: id === 4402 ? 3 : p.rows.length, visible: id === 4402 ? 2 : visible.length, answered: visible.filter((r) => r.response).length, clarification: visible.filter((r) => r.disposition === 'clarification').length, reviewed: visible.filter((r) => r.status === 'reviewed').length },
    prior_options: id === 4402 || id === 4403 ? [] : PRIOR,
  };
};

export function bidAnswersRead(id, persona) {
  if (persona === 'none' || !BID_ANSWERS_IDS.includes(id)) return [404, BODIES[404]];
  return [200, readOf(id)];
}

const bad = (message, name) => [422, { code: 'invalid', message, fields: [{ name, message }] }];

export function bidAnswersWrite(id, scenario, csrfOk, rawBytes) {
  if (!BID_ANSWERS_IDS.includes(id)) return [404, BODIES[404]];
  if (scenario === 'w403csrf' || !csrfOk) return [403, { code: 'csrf_failed', message: 'Your session check failed. Reload and try again.' }];
  let body;
  try {
    body = JSON.parse(Buffer.from(rawBytes ?? []).toString('utf8') || '{}');
  } catch {
    return [400, BODIES[400]];
  }
  const p = panel(id);
  if (id === 4402 || scenario === 'w403') return [403, { code: 'forbidden', message: 'You can’t change these answers.' }];
  if (body.expected_revision !== p.rev || body.case_revision !== p.case) return [409, BODIES[409]];
  if (scenario === 'w409') {
    p.rev += 2;
    return [409, BODIES[409]];
  }
  if (scenario === 'w422') return bad('The answer was not accepted.', 'answer');
  const status = Number(scenario);
  if (BODIES[status]) return [status, BODIES[status]];
  if (scenario === 'wdrop0') return ['drop'];
  const ids = [];
  const find = (match) => p.rows.find(match);
  if (body.action === 'suggest') {
    if (typeof body.key !== 'string' || !/^[0-9a-f-]{36}$/.test(body.operation_key ?? '')) return bad('Use the current form.', 'key');
    const target = find((r) => r.key === body.key);
    if (!target) return bad('Choose a requirement on this response.', 'key');
    if (!keys.has(body.operation_key)) {
      if (['queued', 'running'].includes(target.status)) return bad('Tola is already working on this requirement.', 'key');
      keys.add(body.operation_key);
      target.status = 'queued';
      target.suggestion_id = ++nextId;
      target.suggested_answer = null;
      target.can_review = false;
      target.prior_answer = body.prior_answer ?? null;
    }
    ids.push(target.suggestion_id);
  } else if (body.action === 'review') {
    if (!Array.isArray(body.decisions) || body.decisions.length < 1) return bad('Select one or more suggestions.', 'decisions');
    for (const d of body.decisions) {
      const target = find((r) => r.suggestion_id === d.suggestion);
      if (!target || !target.can_review) return bad('Choose each current suggestion once.', 'decisions');
      if (d.predecessor !== (target.review_id ?? 0)) return bad('A newer answer review exists. Reload it before continuing.', 'decisions');
      if (!['accept', 'edit', 'replace'].includes(d.verdict) || !['addressed', 'clarification', 'out_of_scope'].includes(d.disposition)) return bad('Choose how this requirement is covered.', 'decisions');
      const answer = d.verdict === 'accept' ? target.suggested_answer : d.answer;
      if (typeof answer !== 'string' || answer.trim() === '') return bad('Write the answer to save for this requirement.', 'answer');
      target.previous = { response: target.response, disposition: target.disposition };
      Object.assign(target, { response: answer.trim(), disposition: d.disposition, status: 'reviewed', review_id: ++nextId, review_verdict: d.verdict, can_review: false, can_undo: true });
      ids.push(target.review_id);
    }
  } else if (body.action === 'undo') {
    const target = find((r) => r.review_id === body.review_id && r.can_undo);
    if (!target) return bad('Choose the current accepted answer to undo.', 'review_id');
    Object.assign(target, { ...(target.previous ?? { response: null }), status: 'suggested', review_id: ++nextId, review_verdict: 'undo', can_review: !!target.suggested_answer, can_undo: false });
    ids.push(target.review_id);
  } else return [400, BODIES[400]];
  p.rev += 1;
  p.case += 1;
  if (scenario === 'wdrop') return ['drop'];
  return [201, { work_id: id, state: 'waiting', revision: p.rev, record_ids: ids }];
}

export { NOW };
