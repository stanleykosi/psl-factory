// F-102: the fixed asset schedule reads in the live shapes of contract 1.24.0 (GET /work/{id}, GET /work/{id}/assets,
// GET /work/{id}/assets/date-proofs/{fact_id}). Integer ids 3901 to 3910 only; every other id falls through to work-live.mjs.
// Sample data; no business rules. Read only: any other method answers 405.
// 3901 investigating (64 assets, 4 additions, 1 disposal, 3 assets with no dates, no schedule); 3902 unknown values and a partial
// register; 3903 held schedule; 3904 calculating (processing, no schedule); 3905 verified (ready schedule, proof 701 and 702, note link);
// 3906 ready with no note link; 3907 returned for opening proof; 3908 no register yet; 3909 unavailable to everyone (work item too);
// 3910 the assets read answers 403 forbidden (the work item header still reads).
// A scenario 'assets:<status>' answers only the assets read; the plain scenario 'csrf_failed' also answers only the assets read with
// the stale-token 403; a bare status answers every route here.
import { workLive } from './work-live.mjs';

export const ASSETS_PATH = /^\/api\/v1\/work\/(390[1-9]|3910)(\/assets|\/assets\/date-proofs\/(\d+))?$/;

const NOW = '2026-11-23T09:00:00Z';
const BODIES = {
  400: { code: 'bad_request', message: 'We could not read that request.' },
  401: { code: 'not_signed_in', message: 'Sign in to continue.' },
  403: { code: 'forbidden', message: 'Your role does not allow this.' },
  404: { code: 'not_found', message: 'This record is unavailable.' },
  409: { code: 'stale_revision', message: 'Someone changed this since you opened it.' },
  422: { code: 'invalid', message: 'We could not read that request.' },
  429: { code: 'rate_limited', message: 'Too many requests.' },
  503: { code: 'unavailable', message: 'A dependency is unavailable.' },
};
const CSRF_FAILED = { code: 'csrf_failed', message: 'Your session check failed. Reload and try again.' };

const PDF = Buffer.from('%PDF-1.1\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 100]>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n');

const pad = (n) => String(n).padStart(3, '0');
const asset = (n, patch = {}) => ({
  asset_id: `FA-${pad(n)}`,
  category: n % 3 === 0 ? 'Vehicles' : n % 3 === 1 ? 'Computer-equipment' : 'Plant-machinery',
  capitalisation: 'capitalise',
  classification_evidence_id: 40 + n,
  opening_cost: `${14000000 + n * 1000}.00`,
  opening_accumulated: `${4000000 + n * 100}.00`,
  residual: '0.00',
  life: '5',
  fraction: '1',
  dates: { contract: 'psl/ppe-asset-dates/v1', delivery_date: '2025-02-10', in_service_date: '2025-02-20', fraction_basis: 'explicit_supplied_fraction', support_evidence_id: 300 + n, evidence_id: 700 + n },
  ...patch,
});
const noDates = (n) => {
  const a = asset(n);
  delete a.dates;
  return a;
};
const event = (n, assetId, kind, patch = {}) => ({ event_id: `EV-${pad(n)}`, asset_id: assetId, date: '2025-06-30', kind, cost_delta: '2500000.00', accumulated_delta: '0.00', evidence_id: 500 + n, ...patch });
const register = (patch = {}) => ({
  entity: 'PSL-Technologies',
  provider: 'Sage-200',
  currency: 'NGN',
  unit: 'major_currency',
  period_start: '2025-01-01',
  period_end: '2025-12-31',
  label_as_of: '2025-12-31',
  extracted_at: '2026-11-18T10:00:00Z',
  completeness: 'complete',
  opening_evidence_id: 21,
  assets: [],
  events: [],
  closing_controls: { cost: '1000000000.00', accumulated: '250000000.00', book_value: '750000000.00' },
  ...patch,
});
const row = (n, patch = {}) => ({
  asset_id: `FA-${pad(n)}`,
  category: asset(n).category,
  closing_cost: `${14000000 + n * 1000}.00`,
  charge: '2800000.00',
  closing_accumulated: `${6800000 + n * 100}.00`,
  book_value: `${7200000 + n * 900}.00`,
  event_refs: [],
  findings: [],
  ...patch,
});
const SCOPE = { entity: 'PSL-Technologies', currency: 'NGN', unit: 'major_currency', period_start: '2025-01-01', period_end: '2025-12-31', label_as_of: '2025-12-31' };
const schedule = (patch = {}) => ({
  status: 'ready',
  findings: [],
  rows: [row(1), row(2), row(3, { findings: ['The disposal in June is part-year.'], event_refs: ['EV-001'] })],
  totals: { cost: '42003000.00', accumulated: '20400600.00', book_value: '21602700.00', charge: '8400000.00' },
  scope: SCOPE,
  coverage: 'selected_supplied_population',
  native_source_verified: false,
  ledger_posted: false,
  ...patch,
});
const ASSETS = (patch) => ({
  expected_revision: 4,
  case_revision: 9,
  register_id: 31,
  schedule_id: null,
  accounting_note_id: null,
  stage: 'investigating',
  finding: 'Chidi is reading the register.',
  register: register(),
  schedule: null,
  accounting_note_url: null,
  review_options: [],
  schedule_review_id: null,
  review_evidence: [],
  opening_return: null,
  has_opening_attachment: false,
  date_attachment_ids: [],
  ...patch,
});

const BIG = Array.from({ length: 64 }, (_, i) => (i === 6 || i === 7 || i === 8 ? noDates(i + 1) : asset(i + 1)));
const SMALL = [asset(1), asset(2), asset(3, { dates: { ...asset(3).dates, fraction_basis: 'reviewed_in_service_date' } }), asset(4), noDates(5)];
const REVIEWS = [{ target_id: 61, purpose: 'register', verdicts: ['approve', 'return', 'reject'] }];

const READS = {
  3901: ASSETS({
    stage: 'investigating',
    finding: 'Chidi is reading the register and checking the dates.',
    register: register({
      assets: BIG,
      events: [event(1, 'FA-001', 'addition'), event(2, 'FA-002', 'addition'), event(3, 'FA-003', 'addition'), event(4, 'FA-004', 'addition', { cost_delta: '1800000.00' }), event(5, 'FA-010', 'disposal', { cost_delta: '-900000.00', accumulated_delta: '-300000.00' })],
    }),
    review_options: REVIEWS,
  }),
  3902: ASSETS({
    stage: 'investigating',
    finding: 'Some values in the register are not supplied.',
    register: register({
      completeness: 'partial',
      assets: [asset(1, { opening_cost: null }), asset(2, { life: null, fraction: null }), asset(3)],
      events: [event(1, 'FA-001', 'addition', { cost_delta: null })],
      closing_controls: { cost: '1000000000.00', accumulated: null, book_value: null },
    }),
  }),
  3903: ASSETS({
    stage: 'held',
    finding: 'The schedule is held.',
    schedule_id: 51,
    register: register({ assets: SMALL, events: [] }),
    schedule: schedule({
      status: 'held',
      findings: ['The in-service date of one asset is unclear, so the charge is held.'],
      rows: [row(1, { charge: null }), row(5, { charge: null, book_value: null })],
      totals: { cost: null, accumulated: null, book_value: null, charge: null },
    }),
  }),
  3904: ASSETS({ stage: 'calculating', finding: 'The depreciation is being calculated.', schedule_id: 51, register: register({ assets: SMALL.slice(0, 4), events: [] }), review_options: [] }),
  3905: ASSETS({
    stage: 'verified',
    finding: 'The schedule was checked against the register.',
    schedule_id: 51,
    accounting_note_id: 8,
    accounting_note_url: 'https://notes.example.test/accounting-note/8',
    register: register({ assets: SMALL.slice(0, 4), events: [event(1, 'FA-001', 'addition'), event(2, 'FA-002', 'reclassification', { cost_delta: null, accumulated_delta: null })] }),
    schedule: schedule(),
    review_evidence: [{ id: 61, version: 1, kind: 'register' }],
    has_opening_attachment: true,
    date_attachment_ids: [701, 702, 703],
    review_options: [{ target_id: 62, purpose: 'schedule', verdicts: ['approve', 'return'] }],
    schedule_review_id: 62,
  }),
  3906: ASSETS({ stage: 'verified', finding: 'The schedule was checked against the register.', schedule_id: 51, register: register({ assets: SMALL.slice(0, 4), events: [] }), schedule: schedule(), has_opening_attachment: true, date_attachment_ids: [701] }),
  3907: ASSETS({ stage: 'returned', finding: 'Returned: the opening balances need their proof.', register: register({ assets: SMALL.slice(0, 4), events: [] }), opening_return: { target_id: 61, review_id: 70 }, has_opening_attachment: false }),
  3908: ASSETS({ stage: 'investigating', finding: 'Waiting for the first register.', register: null }),
};

const item = (id) => {
  const [, template] = workLive({ method: 'get', url: new URL('http://mock/api/v1/work/4101'), scenario: undefined, csrfOk: true, persona: 'finance_lead' });
  const processing = id === 3904;
  return {
    ...template,
    id,
    title: 'Fixed asset schedule for PSL Technologies',
    line: 'finance-ppe/v1',
    state: processing ? 'processing' : id === 3905 || id === 3906 ? 'verified' : 'action_needed',
    status_label: processing ? 'Processing' : id === 3905 || id === 3906 ? 'Verified' : 'Action needed',
    output_url: null,
    tracking_url: null,
    updated_at: NOW,
    django_url: `/work/${id}/`,
    api_url: `/api/v1/work/${id}`,
    ...(processing ? { current_activity: { label: 'Calculating the depreciation', watching: false } } : {}),
    panels: [{ key: 'assets', url: `/api/v1/work/${id}/assets`, contract_path: null }],
  };
};

/** One assets read. `scenario` is the cookie or header value. Returns [status, body, headers?]. */
export function assetsLive({ method, url, scenario, persona }) {
  const found = ASSETS_PATH.exec(url.pathname);
  const route = found[2];
  const only = /^assets:(\d+)$/.exec(scenario ?? '');
  const onAssets = route !== undefined;
  const status = Number(only ? (onAssets ? only[1] : 0) : scenario);
  if (BODIES[status]) return [status, BODIES[status]];
  if (method !== 'get') return [405, { code: 'method_not_allowed', message: 'Read only.' }];
  const id = Number(found[1]);
  if (persona === 'none' || id === 3909) return [404, BODIES[404]];
  if (!route) return [200, item(id)];
  if (scenario === 'csrf_failed') return [403, CSRF_FAILED];
  if (id === 3910) return [403, BODIES[403]];
  const read = READS[id];
  if (!read) return [404, BODIES[404]];
  if (found[3] !== undefined) {
    // a proof opens only for a fact id the read lists
    return read.date_attachment_ids.includes(Number(found[3])) ? [200, PDF, { 'Content-Type': 'application/pdf', 'Content-Disposition': 'attachment; filename="date-proof.pdf"' }] : [404, BODIES[404]];
  }
  return [200, read];
}
