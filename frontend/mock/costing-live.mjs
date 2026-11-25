// F-99: the costing sheet in the live shapes of contract 1.26.x: GET /work/{id} (line rfp-response/v1, panel bid-pricing),
// GET|POST /work/{id}/bid-pricing, POST /work/{id}/reviews, and the project's costing read (the rule used).
// Integer ids 4700 to 4705 only; every other id falls through to work-live.mjs. Sample data; no business rules, no real amounts.
// 4700 the PM's approval is waiting, with a price change open to propose; 4701 the CEO's step is waiting (PM and Head approved);
// 4702 all three approved; 4703 held (estimates missing, no amounts, replaced); 4704 a price change waiting for a decision;
// 4705 a figure the calculation does not give (unknown).
// (The server turns a project's UUID into its P-nnnn form before routing, so the project read is matched in both forms.)
// A scenario that is a status answers every route here with it; 'w409' and 'w422' answer only the writes.
import { workLive } from './work-live.mjs';

export const COSTING_PATH = /^\/api\/v1\/(?:work\/(470[0-5])(\/bid-pricing|\/reviews)?|projects\/(?:00000000-0000-4000-8000-00000000|P-)(470[0-5])\/costing)$/;

const NOW = '2026-11-25T09:00:00Z';
const caseOf = (id) => `00000000-0000-4000-8000-00000000${id}`;
const BODIES = {
  400: { code: 'bad_request', message: 'We could not read that request.' },
  401: { code: 'not_signed_in', message: 'Sign in to continue.' },
  403: { code: 'forbidden', message: 'Your role does not allow this.' },
  404: { code: 'not_found', message: 'This record is unavailable.' },
  409: { code: 'stale_revision', message: 'Someone changed this since you opened it.' },
  422: { code: 'invalid', message: 'The request was not accepted.', fields: [{ name: 'amount', message: 'That amount is outside the limit.' }] },
  429: { code: 'rate_limited', message: 'Too many requests.' },
  503: { code: 'unavailable', message: 'A dependency is unavailable.' },
};
const CSRF_FAILED = { code: 'csrf_failed', message: 'Your session check failed. Reload and try again.' };

const INPUTS = [
  { label: 'Requirements', version: 1 },
  { label: 'Delivery plan', version: 2 },
  { label: 'Engineering estimate', version: 1 },
  { label: 'Security estimate', version: 1 },
  { label: 'Costing source', version: null },
];
const AMOUNTS = [
  { key: 'engineering', unit: 'NGN', value: '25000000.00' },
  { key: 'security', unit: 'NGN', value: '6000000.00' },
  { key: 'project_management', unit: 'NGN', value: '3500000.00' },
  { key: 'total', unit: 'NGN', value: '34500000.00' },
];
const step = (label, role, status_code, recorded_at = null) => ({ label, role, status: { approved: 'Approved', pending: 'Waiting', returned: 'Returned', rejected: 'Refused' }[status_code], status_code, recorded_at });
const PM = (code, at) => step('Project manager', 'PM', code, at);
const HEAD = (code, at) => step('Head of project management', 'Head of PMO', code, at);
const CEO = (code, at) => step('Chief executive', 'CEO', code, at);
const DONE = '2026-11-24T10:00:00Z';

const pricing = (patch) => ({
  expected_revision: 9,
  case_revision: 89,
  commercial_revision_id: 5,
  commercial_revision: 2,
  inputs: INPUTS,
  amounts: AMOUNTS,
  approvals: [PM('pending'), HEAD('pending'), CEO('pending')],
  costing_note: 'This costing uses the template rule, not PSL’s final rule. The engineering lead is a placeholder.',
  current: true,
  estimate_missing: false,
  security_estimate_missing: false,
  can_open_calculator: true,
  adjustment_run_id: null,
  adjustment_targets: [],
  adjustment_currency: null,
  can_configure: false,
  finance_targets: [],
  finance_pending: null,
  finance_last_decision: null,
  can_propose: false,
  can_decide: false,
  ...patch,
});
const TARGETS = [
  { key: 'engineering', label: 'Engineering', max_absolute_value: '2000000.00' },
  { key: 'security', label: 'Security', max_absolute_value: '500000.00' },
];
const START = {
  4700: pricing({ adjustment_targets: TARGETS, adjustment_currency: 'NGN', can_propose: true }),
  4701: pricing({ approvals: [PM('approved', DONE), HEAD('approved', DONE), CEO('pending')] }),
  4702: pricing({ approvals: [PM('approved', DONE), HEAD('approved', DONE), CEO('approved', DONE)] }),
  4703: pricing({ amounts: [], estimate_missing: true, security_estimate_missing: true, current: false, commercial_revision_id: null, commercial_revision: null, costing_note: 'A costing reference was supplied. Its calculated amounts are unavailable here.' }),
  4704: pricing({
    approvals: [PM('approved', DONE), HEAD('pending'), CEO('pending')],
    can_decide: true,
    finance_pending: { id: 8, by: 31, at: '2026-11-25T08:00:00Z', target: 'engineering', before: '25000000.00', after: '24500000.00', reason: 'The delivery plan shortened.' },
  }),
  4705: pricing({ amounts: [AMOUNTS[0], { key: 'security', unit: 'NGN', value: null }, AMOUNTS[2], { key: 'total', unit: 'NGN', value: null }] }),
};

// what the writes changed: id -> pricing; reset with the mock
let live = {};
export const resetCostingLive = () => {
  live = {};
};
const current = (id) => live[id] ?? START[id];

const item = (id, p) => {
  const [, template] = workLive({ method: 'get', url: new URL('http://mock/api/v1/work/4101'), scenario: undefined, csrfOk: true, persona: 'finance_lead' });
  const waiting = p.approvals.some((a) => a.status_code !== 'approved');
  return {
    ...template,
    id,
    case_id: caseOf(id),
    title: 'RFP response and project handoff',
    line: 'rfp-response/v1',
    state: waiting ? 'waiting' : 'verified',
    status_label: waiting ? 'Waiting' : 'Verified',
    reference: 'Costing: Kora Logistics · fleet tracker',
    output_url: null,
    tracking_url: null,
    agent: null,
    verified_at: null,
    updated_at: NOW,
    api_url: `/api/v1/work/${id}`,
    revision: p.expected_revision,
    case_revision: p.case_revision,
    panels: [{ key: 'bid-pricing', url: `/api/v1/work/${id}/bid-pricing`, contract_path: '/api/v1/work/{work_id}/bid-pricing' }],
  };
};

const REVIEW_KEYS = ['kind', 'expected_revision', 'case_revision', 'subject', 'target_id', 'role', 'verdict', 'evidence_id', 'note'];
const int = (v) => Number.isInteger(v) && v >= 1;
const MONEY = /^-?\d+(\.\d{1,2})?$/;

/** A problem with a review body, or null: the contract's exact keys and types. */
function reviewProblem(body, p) {
  const odd = Object.keys(body).find((k) => !REVIEW_KEYS.includes(k)) ?? REVIEW_KEYS.find((k) => !(k in body));
  if (odd) return odd;
  if (body.kind !== 'bid') return 'kind';
  if (body.subject !== 'commercial') return 'subject';
  if (!int(body.expected_revision)) return 'expected_revision';
  if (!int(body.case_revision)) return 'case_revision';
  if (body.target_id !== p.commercial_revision_id) return 'target_id';
  if (!['PM', 'Head of PMO', 'CEO'].includes(body.role)) return 'role';
  if (!['approve', 'return', 'reject'].includes(body.verdict)) return 'verdict';
  if (body.evidence_id !== null && !int(body.evidence_id)) return 'evidence_id';
  if (typeof body.note !== 'string' || body.note.length > 4000) return 'note';
  return null;
}
/** A problem with a bid-pricing body (a proposal, or the decision on one), or null. */
function pricingProblem(body) {
  const base = ['expected_revision', 'case_revision'];
  const keys = body.action === undefined ? [...base, 'target', 'amount', 'reason'] : [...base, 'action', 'proposal_id', 'reason'];
  const odd = Object.keys(body).find((k) => !keys.includes(k)) ?? keys.find((k) => !(k in body));
  if (odd) return odd;
  if (!int(body.expected_revision)) return 'expected_revision';
  if (!int(body.case_revision)) return 'case_revision';
  if (typeof body.reason !== 'string' || body.reason.trim() === '' || body.reason.length > 2000) return 'reason';
  if (body.action === undefined) {
    if (typeof body.target !== 'string' || body.target === '') return 'target';
    if (typeof body.amount !== 'string' || !MONEY.test(body.amount)) return 'amount';
  } else {
    if (!['approve', 'return'].includes(body.action)) return 'action';
    if (!int(body.proposal_id)) return 'proposal_id';
  }
  return null;
}

function write(id, part, scenario, csrfOk, rawBytes) {
  const p = current(id);
  if (!p) return [404, BODIES[404]];
  if (!csrfOk) return [403, CSRF_FAILED];
  let body;
  try {
    body = JSON.parse(Buffer.from(rawBytes ?? []).toString('utf8') || '{}');
  } catch {
    return [400, BODIES[400]];
  }
  const bad = part === '/reviews' ? reviewProblem(body, p) : pricingProblem(body);
  if (bad) return [400, { code: 'bad_request', message: 'We could not read that request.', fields: [{ name: bad, message: 'This field is missing or not accepted.' }] }];
  if (scenario === 'w422') return [422, BODIES[422]];
  if (scenario === 'w409' || body.expected_revision !== p.expected_revision || body.case_revision !== p.case_revision) {
    live[id] = { ...p, expected_revision: p.expected_revision + 1 };
    return [409, BODIES[409]];
  }
  const next = { ...p, expected_revision: p.expected_revision + 1, case_revision: p.case_revision + 1 };
  if (part === '/reviews') {
    const at = next.approvals.findIndex((a) => a.role === body.role);
    const code = { approve: 'approved', return: 'returned', reject: 'rejected' }[body.verdict];
    if (at === -1 || next.approvals[at].status_code !== 'pending') return [409, BODIES[409]];
    next.approvals = next.approvals.map((a, i) => (i === at ? step(a.label, a.role, code, NOW) : a));
  } else if (body.action === undefined) {
    if (!p.can_propose || !p.adjustment_targets.some((t) => t.key === body.target)) return [422, BODIES[422]];
    Object.assign(next, {
      can_propose: false,
      finance_pending: { id: 9, by: 31, at: NOW, target: body.target, before: '25000000.00', after: body.amount, reason: body.reason },
    });
  } else {
    if (!p.can_decide || !p.finance_pending || p.finance_pending.id !== body.proposal_id) return [422, BODIES[422]];
    Object.assign(next, { can_decide: false, finance_pending: null, finance_last_decision: { id: 3, proposal_id: body.proposal_id, by: 32, at: NOW, status: body.action === 'approve' ? 'approved' : 'returned', reason: body.reason } });
  }
  live[id] = next;
  return [200, part === '/reviews' ? { work_id: id, state: 'waiting', revision: next.expected_revision, review_id: 40 + next.expected_revision } : { work_id: id, state: 'waiting', revision: next.expected_revision }];
}

/** One costing read or write. `scenario` is the cookie or header value. */
export function costingLive({ method, url, scenario, csrfOk, persona, rawBytes }) {
  const found = COSTING_PATH.exec(url.pathname);
  const status = Number(scenario);
  if (BODIES[status]) return [status, BODIES[status]];
  const id = Number(found[1] ?? found[3]);
  if (persona === 'none') return [404, BODIES[404]];
  const part = found[2] ?? (found[3] ? '/costing' : '');
  if (method === 'post') return part === '/bid-pricing' || part === '/reviews' ? write(id, part, scenario, csrfOk, rawBytes) : [405, { code: 'method_not_allowed', message: 'Read only.' }];
  if (method !== 'get') return [405, { code: 'method_not_allowed', message: 'Read only.' }];
  if (part === '') return [200, item(id, current(id))];
  if (part === '/bid-pricing') return [200, current(id)];
  if (part === '/costing') {
    // 4701 has no readable rule, so the panel draws without it
    if (id === 4701) return [403, BODIES[403]];
    return [200, { revision: 89, policy_status: 'VALID', actions: [], rules: [{ id: 1, version: 1, reference: 'Template rule (placeholder)', sha256: 'a'.repeat(64) }], oracles: [], runs: [{ id: 1, status: 'known' }], proposal_ids: [], evidence: [], next_page: null }];
  }
  return [404, BODIES[404]];
}
