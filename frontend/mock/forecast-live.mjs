// F-103: the cash forecast reads in the live shapes of contract 1.25.0 (GET /work/{id}, /forecast, /forecast/actuals/{month},
// /forecast/observations/{id}). Integer ids 4301 to 4308 only; every other id falls through to work-live.mjs. Sample data; no business rules.
// Months: 2026-11 is cut (more_actuals), 2026-09 has a reversed match, 2026-12 answers 404, the other forecast months have no rows.
// A scenario 'forecast:<status>' answers only the forecast read.
// 4301 verified management forecast, 4302 in review, 4303 investigating (no result), 4304 group disclosure, 4305 uncertain delivery,
// 4306 delivery with proof on file, 4307 unavailable to everyone, 4308 group disclosure whose lists carry a payroll key and a row with
// a staff name and pay (the page must draw the key text only). Read only: any other method answers 405.
import { workLive } from './work-live.mjs';

export const FORECAST_PATH = /^\/api\/v1\/work\/(430[1-8])(\/forecast(\/actuals\/(\d{4}-\d{2})|\/observations\/(\d+))?)?$/;

const NOW = '2026-11-23T09:00:00Z';
const BODIES = {
  400: { code: 'bad_request', message: 'We could not read that request.' },
  401: { code: 'not_signed_in', message: 'Sign in to continue.' },
  403: { code: 'forbidden', message: 'Your role does not allow this.' },
  404: { code: 'not_found', message: 'This record is unavailable.' },
  409: { code: 'stale_revision', message: 'Someone changed this since you opened it.' },
  422: { code: 'invalid', message: 'Check the month and try again.', fields: [{ name: 'month', message: 'That month is not in the forecast.' }] },
  429: { code: 'rate_limited', message: 'Too many requests.' },
  503: { code: 'unavailable', message: 'A dependency is unavailable.' },
};

const period = (month, opening, inflow, outflow, closing) => ({ month, opening, inflow, outflow, closing, expected_inflow: inflow, expected_outflow: outflow, actual_inflow: null, actual_outflow: null });
const PERIODS = [
  period('2026-07', '48000000.00', '15000000.00', '9000000.00', null),
  period('2026-08', '54000000.00', '12000000.00', '10500000.00', '55500000.00'),
  period('2026-09', '55500000.00', '14000000.00', '11000000.00', '58500000.00'),
  period('2026-10', '58500000.00', '0.00', '12000000.00', '46500000.00'),
  period('2026-11', '46500000.00', '12400000.00', '9800000.00', '49100000.00'),
  period('2026-12', '49100000.00', '16000000.00', '10200000.00', '54900000.00'),
];
const RESULT = (patch = {}) => ({
  status: 'ready',
  entity: 'PSL Technologies Ltd',
  currency: 'NGN',
  basis: 'cash',
  as_of: '2026-11-20',
  findings: ['Rent is due on 28 Nov.'],
  items: [
    { key: 'inv-17', kind: 'invoice', expected_on: '2026-11-15', matched: '12400000.00', residual: '0.00', evidence_id: 31 },
    { key: 'rent', kind: 'commitment', expected_on: '2026-11-28', matched: null, residual: null, evidence_id: 32 },
  ],
  periods: PERIODS,
  actuals: [{ id: 5, direction: 'inflow', amount: '12400000.00', verified: true, unmatched: null }],
  ...patch,
});
const FORECAST = (patch) => ({
  expected_revision: 4,
  case_revision: 9,
  scenario_id: 12,
  run_id: 77,
  version_id: 3,
  stage: 'verified',
  finding: 'The forecast was checked against the ledger.',
  review_roles: [],
  audience: 'management',
  result: RESULT(),
  jobs: [],
  disclosure: null,
  can_restart: false,
  restart_policy_id: null,
  observation: null,
  matches: [{ id: 1, item_key: 'inv-17', actual_id: 5, amount: '12400000.00' }],
  ...patch,
});
const GROUP = (rows, extra = {}) => ({
  audience: 'group',
  stage: 'group_review',
  finding: 'The group version is ready to read.',
  disclosure: {
    configuration_id: 6,
    row_keys: ['rent', 'loan', 'inv-17'],
    recipient_ids: [3, 4],
    oracle_choices: [{ id: 1, version: 2, kind: 'oracle' }],
    decision_choices: [{ id: 2, version: 1, kind: 'decision' }],
    selected_rows: rows,
    selected_fields: ['kind', 'amount', 'expected_on'],
    selected_metadata: ['entity'],
  },
  ...extra,
});
const FORECASTS = {
  4301: FORECAST({ jobs: [{ id: 1, status: 'delivered', receipt_ids: [9], can_retry: false, can_operate: false }] }),
  4302: FORECAST({ stage: 'review', finding: 'Waiting for the finance review.', review_roles: ['Finance'] }),
  4303: FORECAST({ stage: 'investigating', finding: 'Chidi is reading the opening balances.', run_id: null, version_id: null, result: null, matches: [] }),
  4304: FORECAST(GROUP(['rent', 'loan'], { matches: [] })),
  4305: FORECAST({
    stage: 'uncertain',
    finding: 'The send did not confirm.',
    jobs: [{ id: 2, status: 'sent', receipt_ids: [], can_retry: false, can_operate: true }],
    can_restart: true,
    restart_policy_id: 12,
    observation: { id: 7, outcome: 'unknown', has_proof: false },
  }),
  4306: FORECAST({
    jobs: [{ id: 3, status: 'delivered', receipt_ids: [11], can_retry: false, can_operate: false }],
    observation: { id: 8, outcome: 'delivered', has_proof: true },
  }),
  4308: FORECAST(
    GROUP(['rent', 'payroll-run-nov'], {
      result: RESULT({
        items: [{ key: 'payroll-run-nov', kind: 'commitment', expected_on: '2026-11-28', matched: null, residual: null, evidence_id: 40, staff_name: 'Ngozi Okafor', pay: '850000.00' }],
      }),
      matches: [],
    }),
  ),
};

const MONTHS = {
  '2026-11': {
    rows: [
      { key: 'inv-17', expected: '12400000.00', actual: '12400000.00', status: 'matched', notes: [] },
      { key: 'rent', expected: '9800000.00', actual: null, status: 'open', notes: [{ id: 1, actual_id: 6, reason: 'Waiting for the landlord’s receipt.' }] },
    ],
    actuals: [
      { id: 5, direction: 'inflow', amount: '12400000.00', verified: true },
      { id: 6, direction: 'outflow', amount: null, verified: false },
    ],
    history: [{ id: 1, item_key: 'inv-17', actual_id: 5, amount: '12400000.00', reversed: false }],
    more_actuals: true,
    more_history: false,
    more_notes: false,
  },
  '2026-09': {
    rows: [{ key: 'inv-12', expected: '14000000.00', actual: '14000000.00', status: 'matched', notes: [] }],
    actuals: [{ id: 3, direction: 'inflow', amount: '14000000.00', verified: true }],
    history: [{ id: 2, item_key: 'inv-12', actual_id: 3, amount: '14000000.00', reversed: true }],
    more_actuals: false,
    more_history: false,
    more_notes: false,
  },
};
const EMPTY_MONTH = { rows: [], actuals: [], history: [], more_actuals: false, more_history: false, more_notes: false };

const item = (id) => {
  const [, template] = workLive({ method: 'get', url: new URL('http://mock/api/v1/work/4101'), scenario: undefined, csrfOk: true, persona: 'finance_lead' });
  return {
    ...template,
    id,
    title: 'Cash forecast for PSL Technologies',
    line: 'cash_forecast',
    state: 'waiting',
    status_label: 'Waiting',
    output_url: null,
    updated_at: NOW,
    django_url: `/work/${id}/`,
    api_url: `/api/v1/work/${id}`,
    panels: [{ key: 'forecast', url: `/api/v1/work/${id}/forecast`, contract_path: null }],
  };
};

/** One forecast read. `scenario` is the cookie or header value; it answers every route here with that status. */
export function forecastLive({ method, url, scenario, persona }) {
  const found = FORECAST_PATH.exec(url.pathname);
  // 'forecast:409' answers only the forecast read with that status, so the work item header stays; a bare status answers every route.
  const forecastOnly = /^forecast:(\d+)$/.exec(scenario ?? '');
  const status = Number(forecastOnly ? (url.pathname.endsWith('/forecast') ? forecastOnly[1] : 0) : scenario);
  if (BODIES[status]) return [status, BODIES[status]];
  if (method !== 'get') return [405, { code: 'method_not_allowed', message: 'Read only.' }];
  const id = Number(found[1]);
  if (persona === 'none' || id === 4307) return [404, BODIES[404]];
  if (!found[2]) return [200, item(id)];
  if (found[5]) return [200, Buffer.from('proof'), { 'Content-Type': 'application/octet-stream' }];
  if (found[4]) {
    const data = MONTHS[found[4]] ?? (found[4] !== '2026-12' && PERIODS.some((p) => p.month === found[4]) ? EMPTY_MONTH : null);
    return data ? [200, { expected_revision: 4, case_revision: 9, scenario_id: 12, month: found[4], ...data }] : [404, BODIES[404]];
  }
  return [200, FORECASTS[id]];
}
