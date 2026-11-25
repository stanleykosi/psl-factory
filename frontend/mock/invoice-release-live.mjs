// F-90: releasing an invoice from the live work item, in the live shapes of contract 1.24.0: GET /work/{id},
// POST /work/{id}/actions (release_invoice and reconcile) and GET /projects/{case_id}/billing-invoices/{invoice_id}.
// Integer ids 4140 to 4144 only (4120 to 4123 are F-87's); every other id falls through to work-live.mjs. Sample data; no business rules.
// 4140 ready to release (revision 9): a release answers 202 and the item is processing at revision 10 for two reads, then verified
//   at revision 11 with the invoice issued and delivered; 4141 the release answers 202 but the item still lists the action at
//   revision 9; 4142 a null revision with the action listed; 4143 the action is not listed, paid and owed unknown; 4144 awaiting
//   reconciliation with reconcile and release_invoice listed (a reconcile moves it on to revision 10, ready, nothing listed).
// A scenario that is a status answers every route here with it. Release-only scenarios (the reconcile is not touched): w403, w403csrf
// (an expired token), w404, w409 (stale_version; the item moves on to revision 10 without the action), w422 (setup_required with a field),
// w429, w503, w500 and wdrop (the connection is cut and the release did not run: the item still shows revision 9).
import { workLive } from './work-live.mjs';

export const INVOICE_RELEASE_PATH = /^\/api\/v1\/(?:work\/(414[0-4])(\/actions)?|projects\/(?:00000000-0000-4000-8000-00000000|P-)(414[0-4])\/billing-invoices\/(81[2-6]))$/;

const NOW = '2026-11-25T09:00:00Z';
const caseOf = (id) => `00000000-0000-4000-8000-00000000${id}`;
const INVOICE_OF = { 4140: 812, 4141: 813, 4142: 814, 4143: 815, 4144: 816 };
const BODIES = {
  400: { code: 'bad_request', message: 'We could not read that request.' },
  401: { code: 'not_signed_in', message: 'Sign in to continue.' },
  403: { code: 'forbidden', message: 'Your role does not allow this.' },
  404: { code: 'not_found', message: 'This record is unavailable.' },
  409: { code: 'stale_version', message: 'Someone changed this since you opened it.' },
  429: { code: 'rate_limited', message: 'Too many requests.' },
  503: { code: 'unavailable', message: 'A dependency is unavailable.' },
};
const CSRF_FAILED = { code: 'csrf_failed', message: 'Your session check failed. Reload and try again.' };
const RELEASE_SCENARIOS = {
  w403: [403, { code: 'forbidden', message: 'Your role does not allow releasing this invoice.' }],
  w404: [404, BODIES[404]],
  w409: [409, BODIES[409]],
  w422: [422, { code: 'setup_required', message: 'A release setting is missing.', fields: [{ name: 'policy', message: 'Ask the Finance Lead to set it.' }] }],
  w429: [429, BODIES[429]],
  w503: [503, BODIES[503]],
  w500: [500, { code: 'server_error', message: 'Something broke.' }],
};

const START = {
  4140: { state: 'ready', status_label: 'Ready', revision: 9, actions: ['release_invoice'] },
  4141: { state: 'ready', status_label: 'Ready', revision: 9, actions: ['release_invoice'] },
  4142: { state: 'ready', status_label: 'Ready', revision: null, actions: ['release_invoice'] },
  4143: { state: 'ready', status_label: 'Ready', revision: 9, actions: [] },
  4144: { state: 'awaiting_reconciliation', status_label: 'Awaiting reconciliation', revision: 9, actions: ['reconcile', 'release_invoice'] },
};

// what the writes changed, and how many reads of the item followed a release on 4140; reset with the mock
let live = {};
let reads = {};
let log = [];
export const resetInvoiceRelease = () => {
  live = {};
  reads = {};
  log = [];
};
/** Every write the mock accepted to read (route, work id, parsed body), for tests that count what was sent. */
export const invoiceReleaseLog = () => log;

/** The item as the next read shows it: 4140 moves processing, processing, then verified after the release. */
function stateOf(id, counts = true) {
  const base = { ...START[id], ...live[id] };
  if (id !== 4140 || !live[id]?.released) return base;
  if (counts) reads[id] = (reads[id] ?? 0) + 1;
  return reads[id] >= 3
    ? { state: 'verified', status_label: 'Verified', revision: 11, actions: [], released: true }
    : { state: 'processing', status_label: 'Processing', revision: 10, actions: [], released: true };
}

function itemOf(id) {
  const [, template] = workLive({ method: 'get', url: new URL('http://mock/api/v1/work/4101'), scenario: undefined, csrfOk: true, persona: 'finance_lead' });
  const s = stateOf(id);
  return {
    ...template,
    id,
    case_id: caseOf(id),
    title: 'Invoice for Lagoon Health',
    line: 'invoice',
    state: s.state,
    status_label: s.status_label,
    reference: 'INV-0412',
    output_url: null,
    tracking_url: null,
    agent: null,
    verified_at: s.state === 'verified' ? NOW : null,
    updated_at: NOW,
    api_url: `/api/v1/work/${id}`,
    revision: s.revision,
    case_revision: null,
    actions: s.actions,
    available_control: [],
    panels: [{ key: 'invoice', url: `/api/v1/projects/${caseOf(id)}/billing-invoices/${INVOICE_OF[id]}`, contract_path: '/api/v1/projects/{case_id}/billing-invoices/{invoice_id}' }],
  };
}

function invoiceOf(id) {
  const done = id === 4140 && live[id]?.released && (reads[id] ?? 0) >= 3;
  return {
    id: INVOICE_OF[id],
    reference: `INV-04${12 + (id - 4140)}`,
    version: 2,
    issued_at: done ? '2026-11-25T09:00:00Z' : null,
    delivered_at: done ? '2026-11-25T09:01:00Z' : null,
    currency: 'NGN',
    amount: '1250000.00',
    paid: done ? '0.00' : null,
    owed: done ? '1250000.00' : null,
    preparation_id: 77,
    issue_id: done ? 91 : null,
    delivery_id: done ? 92 : null,
    payments_url: null,
    corrections_url: `/api/v1/work/${id}/corrections`,
  };
}

function write(id, scenario, csrfOk, rawBytes) {
  if (!csrfOk) return [403, CSRF_FAILED];
  let body;
  try {
    body = JSON.parse(Buffer.from(rawBytes ?? []).toString('utf8') || '{}');
  } catch {
    return [400, BODIES[400]];
  }
  log.push({ route: 'actions', work_id: id, body });
  // the contract's exact body: two keys, a positive integer revision, one of two actions
  const keys = Object.keys(body).sort().join(',');
  if (keys !== 'action,expected_revision' || !Number.isInteger(body.expected_revision) || body.expected_revision < 1 || !['reconcile', 'release_invoice'].includes(body.action)) {
    return [400, { code: 'bad_request', message: 'We could not read that request.', fields: [{ name: 'body', message: 'This field is missing or not accepted.' }] }];
  }
  const now = stateOf(id, false);
  const release = body.action === 'release_invoice';
  if (release && scenario === 'w403csrf') return [403, CSRF_FAILED];
  if (release && RELEASE_SCENARIOS[scenario]) {
    if (scenario === 'w409') live[id] = { ...live[id], revision: (now.revision ?? 9) + 1, actions: [] };
    return RELEASE_SCENARIOS[scenario];
  }
  if (release && scenario === 'wdrop') return ['drop'];
  if (!now.actions.includes(body.action)) return [409, { code: 'action_unavailable', message: 'That is not available for this item now.' }];
  if (body.expected_revision !== now.revision) return [409, BODIES[409]];
  if (!release) {
    live[id] = { state: 'ready', status_label: 'Ready', revision: now.revision + 1, actions: [] };
    return [202, { work_id: id, state: 'ready', revision: now.revision + 1 }];
  }
  // 4141 answers 202 and changes nothing the page can see: the server has not caught up
  if (id === 4141) return [202, { work_id: id, state: 'processing', revision: now.revision + 1 }];
  live[id] = { released: true, state: 'processing', status_label: 'Processing', revision: 10, actions: [] };
  return [202, { work_id: id, state: 'processing', revision: 10 }];
}

/** One read or write. `scenario` is the cookie or header value; `csrfOk` is whether a write carried the persona's token. */
export function invoiceReleaseLive({ method, url, scenario, csrfOk, persona, rawBytes }) {
  const found = INVOICE_RELEASE_PATH.exec(url.pathname);
  const status = Number(scenario);
  if (BODIES[status]) return [status, BODIES[status]];
  if (persona === 'none') return [404, BODIES[404]];
  if (found[2]) return method === 'post' ? write(Number(found[1]), scenario, csrfOk, rawBytes) : [405, { code: 'method_not_allowed', message: 'Write only.' }];
  if (method !== 'get') return [405, { code: 'method_not_allowed', message: 'Read only.' }];
  if (found[1]) return [200, itemOf(Number(found[1]))];
  const id = Number(found[3]);
  return INVOICE_OF[id] === Number(found[4]) ? [200, invoiceOf(id)] : [404, BODIES[404]];
}
