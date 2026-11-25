// F-101: the income schedule on the live work item, in the live shapes of contract 1.24.0: GET /work/{id}, GET /work/{id}/finance-schedule
// and POST /work/{id}/reviews (kind schedule). Integer ids 4201 to 4207 and 4299 only; every other id falls through to work-live.mjs.
// 4201 investigating (no result, one amount unknown); 4202 held (missing_required, a possible duplicate); 4203 in review (Approve,
// Return, Reject); 4204 returned (rows, no note on the read); 4205 verified (only Withdraw approval); 4206 reviewer not set; 4207 an
// inventory; 4299 unavailable to every caller. Sample data; no business rules, no real amounts.
// A scenario applies to the review write only: w409 (answers 409 once), w422, w429, w503, wcsrf (403 csrf_failed), wdrop (no answer),
// wstale (200 but the schedule is unchanged on the re-read).
import { workLive } from './work-live.mjs';

export const INCOME_SCHEDULES_PATH = /^\/api\/v1\/work\/(420[1-7]|4299)(\/finance-schedule|\/reviews)?$/;

const NOW = '2026-11-25T09:00:00Z';
const caseOf = (id) => `00000000-0000-4000-8000-00000000${id}`;
const BODIES = {
  400: { code: 'bad_request', message: 'We could not read that request.' },
  404: { code: 'not_found', message: 'This record is unavailable.' },
  409: { code: 'stale_revision', message: 'Someone changed this since you opened it.' },
  422: { code: 'invalid', message: 'The request was not accepted.', fields: [{ name: 'note', message: 'The note is needed.' }] },
  429: { code: 'rate_limited', message: 'Too many requests.' },
  503: { code: 'unavailable', message: 'A dependency is unavailable.' },
};
const CSRF_FAILED = { code: 'csrf_failed', message: 'Your session check failed. Reload and try again.' };

const ROWS = [
  { key: 'row-3', relationship: 'disaggregation', amount: '1500000.00', unit: 'NGN', source_accounts: ['4100', '4110'], evidence_id: 61, duplicate_state: 'not_assessed', duplicate_resolution_evidence_id: null, adjustment_lines: [] },
  { key: 'row-7', relationship: 'additive', amount: null, unit: 'NGN', source_accounts: ['4200'], evidence_id: 61, duplicate_state: 'already_represented', duplicate_resolution_evidence_id: null, adjustment_lines: [] },
  { key: 'row-12', relationship: 'reclassification', amount: '250000.50', unit: 'NGN', source_accounts: ['4300'], evidence_id: 61, duplicate_state: 'separately_justified', duplicate_resolution_evidence_id: 62, adjustment_lines: [] },
];
const INCOME = { entity: 'kora-logistics', period: '2026-09', currency: 'NGN', report_line: 'service_income', source_unit: 'NGN', target_unit: 'NGN', rows: ROWS };
const READY = { status: 'ready', findings: [], adjusted_total: '1750000.50', parent_amount: '1750000.50', additive_total: null, reclassification_total: '250000.50', target_unit: 'NGN', coverage: null, complete_inventory: null, missing_required: [], included_schedules: [] };

const schedule = (patch) => ({
  expected_revision: 5,
  case_revision: 12,
  schedule_id: 9,
  kind: 'income',
  stage: 'Chidi is checking the income rows.',
  finding: 'Three income rows were read from the September ledger.',
  duplicates: [],
  returned: null,
  review_id: null,
  review_verdicts: [],
  can_export: false,
  review_hold_code: null,
  evidence: [{ id: 61, version: 1, kind: 'document' }],
  exports: [],
  income: INCOME,
  inventory: null,
  result: null,
  ...patch,
});
const START = {
  4201: schedule({}),
  4202: schedule({
    stage: 'The schedule is held.',
    finding: 'A required part is missing and one row may repeat another.',
    duplicates: ['row-7'],
    result: { ...READY, status: 'held', findings: ['rows_unassessed'], missing_required: ['report_line'], adjusted_total: null, parent_amount: null, reclassification_total: null },
  }),
  4203: schedule({ stage: 'The schedule is ready for review.', finding: 'The rows add up to the parent amount.', review_id: 41, review_verdicts: ['approve', 'return', 'reject'], result: READY }),
  4204: schedule({ stage: 'The schedule was returned.', finding: 'One row needs its relationship corrected.', returned: { review_id: 40, rows: [{ key: 'row-12', relationship: 'disaggregation' }] }, result: READY }),
  4205: schedule({ stage: 'The schedule is approved.', finding: 'The review is recorded.', review_verdicts: ['revoke'], result: READY }),
  4206: schedule({ stage: 'The schedule is ready for review.', finding: 'The rows add up to the parent amount.', review_hold_code: 'reviewer_missing', result: READY }),
  4207: schedule({
    kind: 'inventory',
    stage: 'The workbook inventory is being read.',
    finding: 'Two schedules were found in the workbook.',
    income: null,
    inventory: {
      workbook_evidence_id: 61,
      coverage: 'partial',
      schedules: [
        { key: 'income-detail', purpose: 'Income by customer', owner_id: null, dependencies: [], source_evidence_ids: [61], formula_evidence_ids: [], manual_cell_evidence_ids: [], consumer_refs: [], restricted: false, validation_package_id: null, gaps: ['No formula evidence'] },
        { key: 'restricted-detail', purpose: 'Hidden purpose', owner_id: null, dependencies: [], source_evidence_ids: [], formula_evidence_ids: [], manual_cell_evidence_ids: [], consumer_refs: [], restricted: true, validation_package_id: null, gaps: ['Hidden gap'] },
      ],
    },
  }),
};

// what the writes changed: id -> schedule, and the state the work item carries; reset with the mock
let live = {};
let states = {};
let staled = new Set();
let conflicted = new Set();
export const resetIncomeSchedulesLive = () => {
  live = {};
  states = {};
  staled = new Set();
  conflicted = new Set();
};
const current = (id) => live[id] ?? START[id];

const item = (id, p) => {
  const [, template] = workLive({ method: 'get', url: new URL('http://mock/api/v1/work/4101'), scenario: undefined, csrfOk: true, persona: 'finance_lead' });
  const state = states[id] ?? (id === 4205 ? 'verified' : 'waiting');
  return {
    ...template,
    id,
    case_id: caseOf(id),
    title: 'Income schedule for Kora Logistics',
    line: 'finance-schedules/v1',
    state,
    status_label: state === 'verified' ? 'Verified' : 'Waiting',
    reference: 'Income schedule: Kora Logistics · September 2026',
    output_url: null,
    tracking_url: null,
    agent: null,
    verified_at: null,
    updated_at: NOW,
    api_url: `/api/v1/work/${id}`,
    revision: p.expected_revision,
    case_revision: p.case_revision,
    panels: [{ key: 'finance-schedule', url: `/api/v1/work/${id}/finance-schedule`, contract_path: '/api/v1/work/{work_id}/finance-schedule' }],
  };
};

const KEYS = ['kind', 'expected_revision', 'case_revision', 'target_id', 'verdict', 'evidence_id', 'note'];
const int = (v) => Number.isInteger(v) && v >= 1;
const fieldError = (name, message) => [422, { code: 'invalid', message: 'The request was not accepted.', fields: [{ name, message }] }];

function write(id, scenario, csrfOk, rawBytes) {
  const p = current(id);
  if (!p) return [404, BODIES[404]];
  if (!csrfOk || scenario === 'wcsrf') return [403, CSRF_FAILED];
  let body;
  try {
    body = JSON.parse(Buffer.from(rawBytes ?? []).toString('utf8') || '{}');
  } catch {
    return [400, BODIES[400]];
  }
  if (typeof body !== 'object' || body === null || Object.keys(body).some((k) => !KEYS.includes(k))) return [400, BODIES[400]];
  const wrong = ['kind', 'expected_revision', 'case_revision', 'target_id', 'verdict'].find((k) => !(k in body));
  if (wrong || body.kind !== 'schedule' || !int(body.expected_revision) || !int(body.case_revision) || !int(body.target_id) || !['approve', 'return', 'reject', 'revoke'].includes(body.verdict)) return [400, BODIES[400]];
  if (!int(body.evidence_id)) return fieldError('evidence_id', 'Choose the evidence this decision rests on.');
  if (typeof body.note !== 'string' || body.note.trim() === '' || body.note.length > 4000) return fieldError('note', 'The note is needed.');
  if (scenario === 'w422') return [422, BODIES[422]];
  if (scenario === 'w429') return [429, BODIES[429]];
  if (scenario === 'w503') return [503, BODIES[503]];
  if (scenario === 'wdrop') return ['drop', null];
  if (scenario === 'w409' && !conflicted.has(id)) {
    conflicted.add(id);
    live[id] = { ...p, expected_revision: p.expected_revision + 1 };
    return [409, BODIES[409]];
  }
  if (body.expected_revision !== p.expected_revision || body.case_revision !== p.case_revision) return [409, BODIES[409]];
  if (body.target_id !== p.schedule_id || !p.evidence.some((e) => e.id === body.evidence_id) || !p.review_verdicts.includes(body.verdict)) return [422, BODIES[422]];
  const next = { ...p, expected_revision: p.expected_revision + 1, case_revision: p.case_revision + 1 };
  if (scenario === 'wstale') {
    // the write is answered but the re-read still shows the old schedule
    staled.add(id);
  } else {
    Object.assign(next, { review_id: null, review_verdicts: body.verdict === 'approve' ? ['revoke'] : [] });
    if (body.verdict === 'return') next.returned = { review_id: p.review_id, rows: [{ key: 'row-12', relationship: 'disaggregation' }] };
    states[id] = body.verdict === 'approve' ? 'verified' : 'waiting';
  }
  live[id] = next;
  return [200, { work_id: id, state: states[id] ?? 'waiting', revision: next.expected_revision, review_id: p.review_id }];
}

/** One income schedule read or write. `scenario` is the cookie or header value. */
export function incomeSchedulesLive({ method, url, scenario, csrfOk, persona, rawBytes }) {
  const found = INCOME_SCHEDULES_PATH.exec(url.pathname);
  const id = Number(found[1]);
  const part = found[2] ?? '';
  if (persona === 'none' || id === 4299) return [404, BODIES[404]];
  if (method === 'post') return part === '/reviews' ? write(id, scenario, csrfOk, rawBytes) : [405, { code: 'method_not_allowed', message: 'Not offered here.' }];
  if (method !== 'get') return [405, { code: 'method_not_allowed', message: 'Read only.' }];
  if (part === '') return [200, item(id, current(id))];
  if (staled.has(id)) return [200, { ...START[id], expected_revision: current(id).expected_revision, case_revision: current(id).case_revision }];
  return [200, current(id)];
}
