// F-88: the received RFP in the live shapes of contract 1.26.0: SCR-23 (organisations, POST /received-bids as multipart, the receipt)
// and SCR-24 (the Unassigned list, the assignment read, the assign POST). Sample data; no business rules. server.mjs hands these
// routes here when it runs with `liveStart`.
// Scenarios (cookie psl_mock_scenario or header X-Mock-Scenario). A status number answers every route here with that status.
// Log: rb_uncertain (503 on the first send of a start_key, 200 on the same key), rb_duplicate (422 action_unavailable), rb_invalid (422
// with fields), rb_denied (403 on the POST), rb_orgs_denied (403 on the organisations), rb_too_large (413), rb_unsupported (415),
// rb_receipt_down (500 on the receipt read). Assign: assign_stale (409 once, the revision moves on), assign_lost_reply (503 but the
// assignment is stored), assign_uncertain (503, nothing stored), assign_invalid (422 with fields), assign_denied (403),
// assign_missing (404). Reads: rb_setup, rb_no_nominees, rb_no_proofs, rb_no_steps, rb_one_role, rb_assigned.
export const RECEIVED_BIDS_PATH = /^\/api\/v1\/received-bids(\/.*)?$/;

const BODIES = {
  400: { code: 'bad_request', message: 'We could not read that request.' },
  401: { code: 'not_signed_in', message: 'Sign in to continue.' },
  403: { code: 'forbidden', message: 'Your role does not allow this.' },
  404: { code: 'not_found', message: 'This record is unavailable.' },
  409: { code: 'stale_revision', message: 'The RFP has a newer revision.' },
  413: { code: 'too_large', message: 'The request is too large.' },
  415: { code: 'unsupported_media', message: 'The request type is not accepted.' },
  422: { code: 'invalid', message: 'Check the form and try again.' },
  429: { code: 'rate_limited', message: 'Too many requests.' },
  500: { code: 'server_error', message: 'Something went wrong.' },
  503: { code: 'unavailable', message: 'A dependency is unavailable.' },
};
const CSRF_FAILED = { code: 'csrf_failed', message: 'Your session check failed. Reload and try again.' };
const ORGS = [
  { id: 11, organisation: 'Northwind Bank' },
  { id: 12, organisation: 'Harbour Insurance' },
];
const FIRST = '2f0c8a54-6b0e-4f7a-9d1a-0c5b2f6f1a11';
const uuid = (n) => `2f0c8a54-6b0e-4f7a-9d1a-${String(n).padStart(12, '0')}`;
// 13 RFPs: two pages of 12 and 1. The third needs owner access first.
const BIDS = Array.from({ length: 13 }, (_, i) => ({
  case_id: i === 0 ? FIRST : uuid(i + 1),
  intake_id: 77 + i,
  revision: 3,
  reference: i === 0 ? 'RFP-2026-041' : `RFP-2026-${String(42 + i).padStart(3, '0')}`,
  received_at: '2026-11-20T09:30:00Z',
  deadline_status: i % 3 === 0 ? 'stated' : 'unknown',
  deadline: i % 3 === 0 ? '2026-12-05T17:00:00Z' : null,
  owner_access_required: i === 2,
}));
const PAGE = 12;
const NOMINEES = [{ id: 301, label: 'Amara Okoye' }, { id: 302, label: 'Tunde Bello' }];
const PROOFS = [{ id: 901, label: 'Delegation email, 18 Nov' }];
const STEPS = [{ key: 'prepare_rfp', label: 'The PM prepares the RFP response', api_url: null }];

let logged = [];
let receipts = new Map();
let keys = new Map();
let tried = new Set();
let assigned = new Map();
let revisions = new Map();
let staleSpent = false;
let log = [];
export const resetReceivedBids = () => {
  logged = [];
  receipts = new Map();
  keys = new Map();
  tried = new Set();
  assigned = new Map();
  revisions = new Map();
  staleSpent = false;
  log = [];
};
/** Every write this mock received (the multipart as its fields and file, the assign body) with the status it answered. */
export const receivedBidsLog = () => ({ requests: log, logged });

const send = (status, body) => [status, body];
const isInt = (v) => Number.isSafeInteger(v) && v > 0;
const revisionOf = (bid) => revisions.get(bid.case_id) ?? bid.revision;

/** A multipart body as `{fields, files}`; a file is `{filename, bytes}`. */
export function parseMultipart(rawBytes, contentType) {
  const boundary = /boundary=([^;]+)/.exec(contentType ?? '')?.[1]?.replace(/^"|"$/g, '');
  const out = { fields: {}, files: {} };
  if (!boundary) return null;
  const text = Buffer.from(rawBytes).toString('latin1');
  for (const part of text.split(`--${boundary}`).slice(1)) {
    if (part.startsWith('--')) break;
    const cut = part.indexOf('\r\n\r\n');
    if (cut < 0) continue;
    const head = part.slice(0, cut);
    const value = part.slice(cut + 4).replace(/\r\n$/, '');
    const name = /name="([^"]*)"/.exec(head)?.[1];
    const filename = /filename="([^"]*)"/.exec(head)?.[1];
    if (name === undefined) continue;
    if (filename !== undefined) out.files[name] = { filename, bytes: value.length };
    else out.fields[name] = Buffer.from(value, 'latin1').toString('utf8');
  }
  return out;
}

const FIELD_KEYS = ['authority', 'start_key', 'reference', 'note', 'received_at', 'deadline_status', 'deadline_at', 'prospect_name', 'submission_method', 'submission_target', 'context_attested'];
const DATE_TIME = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2}(\.\d+)?)?(Z|[+-]\d{2}:?\d{2})$/;
const WORD_OR_PDF = /\.(pdf|doc|docx)$/i;

function logProblems({ fields, files }) {
  const out = [];
  const problem = (name, message) => out.push({ name, message });
  for (const k of Object.keys(fields)) if (!FIELD_KEYS.includes(k)) problem(k, 'This field is not accepted.');
  if (!ORGS.some((o) => String(o.id) === fields.authority)) problem('authority', 'Choose a client from the list.');
  if (!/^[0-9a-f-]{36}$/i.test(fields.start_key ?? '')) problem('start_key', 'This must be a UUID.');
  if (!fields.reference || fields.reference.length > 160) problem('reference', 'Use 1 to 160 characters.');
  if (!DATE_TIME.test(fields.received_at ?? '')) problem('received_at', 'Use a date and time with an offset.');
  if (!['unknown', 'stated', 'not_stated'].includes(fields.deadline_status)) problem('deadline_status', 'Choose one.');
  if (fields.deadline_status === 'stated' && !DATE_TIME.test(fields.deadline_at ?? '')) problem('deadline_at', 'A stated deadline needs a date and time.');
  if (fields.deadline_status !== 'stated' && fields.deadline_at) problem('deadline_at', 'Only a stated deadline has a date.');
  if ((fields.note ?? '').length > 4000) problem('note', 'Use 4000 characters or fewer.');
  if (!files.document) problem('document', 'This field is required.');
  return out;
}

function logBid({ rawBytes, contentType, scenario, csrfOk }) {
  const form = parseMultipart(rawBytes, contentType);
  const entry = { form, status: 0 };
  log.push(entry);
  const reply = (status, body) => {
    entry.status = status;
    return send(status, body);
  };
  if (!form) return reply(415, BODIES[415]);
  if (scenario === 'csrf_failed' || !csrfOk) return reply(403, CSRF_FAILED);
  if (scenario === 'rb_denied') return reply(403, BODIES[403]);
  if (scenario === 'rb_too_large') return reply(413, BODIES[413]);
  if (scenario === 'rb_unsupported') return reply(415, BODIES[415]);
  const problems = logProblems(form);
  if (problems.length > 0) return reply(422, { ...BODIES[422], fields: problems });
  if (!WORD_OR_PDF.test(form.files.document.filename)) return reply(415, BODIES[415]);
  if (form.files.document.bytes > 5 * 1024 * 1024) return reply(413, BODIES[413]);
  if (scenario === 'rb_invalid') return reply(422, { ...BODIES[422], fields: [{ name: 'submission_target', message: 'Give an email address for an email submission.' }] });
  const { fields } = form;
  const same = keys.get(fields.start_key);
  if (same) return reply(200, same);
  if (scenario === 'rb_uncertain' && !tried.has(fields.start_key)) {
    tried.add(fields.start_key);
    return reply(503, BODIES[503]);
  }
  if (scenario === 'rb_duplicate' || logged.some((r) => r.authority === fields.authority && r.reference === fields.reference)) {
    return reply(422, { code: 'action_unavailable', message: 'This reference has already been logged for this organisation.' });
  }
  const id = 501 + logged.length;
  const caseId = id === 501 ? FIRST : uuid(500 + id);
  const answer = { receipt_id: id, case_id: caseId, django_url: `/received-bids/${id}/` };
  logged.push({ authority: fields.authority, reference: fields.reference, start_key: fields.start_key, receipt_id: id });
  keys.set(fields.start_key, answer);
  const named = fields.prospect_name || fields.submission_method || fields.submission_target;
  receipts.set(id, {
    id,
    case_id: caseId,
    reference: fields.reference,
    number: 1,
    current: true,
    received_at: fields.received_at,
    deadline_status: fields.deadline_status,
    deadline_at: fields.deadline_status === 'stated' ? fields.deadline_at : null,
    customer_instructions: named ? { prospect_name: fields.prospect_name ?? null, submission_method: fields.submission_method ?? null, submission_target: fields.submission_target ?? null, source_version: 1 } : null,
    note: fields.note || null,
    original: { filename: form.files.document.filename, bytes: Math.max(form.files.document.bytes, 1), download_url: `/api/v1/received-bids/${caseId}/receipts/${id}/original` },
  });
  return reply(200, answer);
}

const FIXTURE_RECEIPT = {
  id: 501,
  case_id: FIRST,
  reference: 'RFP-2026-041',
  number: 1,
  current: true,
  received_at: '2026-11-20T09:30:00Z',
  deadline_status: 'stated',
  deadline_at: '2026-12-05T17:00:00Z',
  customer_instructions: { prospect_name: 'Northwind Bank plc', submission_method: 'email', submission_target: 'bids@northwind.example', source_version: 1 },
  note: 'Client wants a draft by Friday.',
  original: { filename: 'rfp.pdf', bytes: 482113, download_url: '/api/v1/received-bids/original' },
};

function detail(bid, scenario) {
  const person = assigned.get(bid.case_id);
  const existing = person ?? (scenario === 'rb_assigned' ? { id: 1, person_id: 301, role: 'Head of PMO', intake_id: bid.intake_id } : null);
  return {
    bid: { ...bid, revision: revisionOf(bid) },
    setup_required: scenario === 'rb_setup',
    assignment: existing,
    roles: scenario === 'rb_one_role' ? ['Head of PMO'] : ['Head of PMO', 'PMO Lead'],
    nominees: scenario === 'rb_no_nominees' ? [] : NOMINEES,
    proofs: scenario === 'rb_no_proofs' ? [] : PROOFS,
    next_steps: scenario === 'rb_no_steps' ? [] : STEPS,
  };
}

function assign({ bid, raw, scenario, csrfOk }) {
  let body;
  try {
    body = JSON.parse(raw);
  } catch {
    return send(400, BODIES[400]);
  }
  const entry = { case_id: bid.case_id, body, status: 0 };
  log.push(entry);
  const reply = (status, answer) => {
    entry.status = status;
    return send(status, answer);
  };
  if (scenario === 'csrf_failed' || !csrfOk) return reply(403, CSRF_FAILED);
  if (scenario === 'assign_denied') return reply(403, BODIES[403]);
  if (scenario === 'assign_missing') return reply(404, BODIES[404]);
  if (scenario === 'assign_invalid') return reply(422, { ...BODIES[422], fields: [{ name: 'reason', message: 'Say why this person was chosen.' }, { name: 'evidence', message: 'This proof is not available.' }] });
  const problems = [];
  const problem = (name, message) => problems.push({ name, message });
  const upload = 'upload_id' in body;
  const allowed = ['intake', 'revision', 'candidate', 'role', 'reason', upload ? 'upload_id' : 'evidence', ...(upload ? ['checked'] : [])];
  for (const k of Object.keys(body)) if (!allowed.includes(k)) problem(k, 'This field is not accepted.');
  for (const k of ['intake', 'revision', 'candidate']) if (!isInt(body[k])) problem(k, 'This must be a whole number.');
  if (upload ? !isInt(body.upload_id) || body.checked !== true : !isInt(body.evidence)) problem(upload ? 'upload_id' : 'evidence', 'Give one proof.');
  if (typeof body.role !== 'string' || !body.role) problem('role', 'This field is required.');
  if (typeof body.reason !== 'string' || body.reason.length < 1 || body.reason.length > 4000) problem('reason', 'Use 1 to 4000 characters.');
  if (problems.length > 0) return reply(422, { ...BODIES[422], fields: problems });
  if (assigned.has(bid.case_id) || scenario === 'rb_assigned') return reply(409, BODIES[409]);
  if (scenario === 'assign_stale' && !staleSpent) {
    staleSpent = true;
    revisions.set(bid.case_id, revisionOf(bid) + 1);
    return reply(409, BODIES[409]);
  }
  if (body.revision !== revisionOf(bid) || body.intake !== bid.intake_id) return reply(409, BODIES[409]);
  if (!NOMINEES.some((n) => n.id === body.candidate)) return reply(422, { ...BODIES[422], fields: [{ name: 'candidate', message: 'Choose someone from the list.' }] });
  const made = { id: 1 + assigned.size, person_id: body.candidate, role: body.role, intake_id: bid.intake_id };
  if (scenario === 'assign_uncertain') return reply(503, BODIES[503]);
  assigned.set(bid.case_id, made);
  if (scenario === 'assign_lost_reply') return reply(503, BODIES[503]);
  return reply(201, made);
}

/** One live received-bid read or write. Returns [status, body]. */
export function receivedBids({ method, url, raw, rawBytes, contentType, scenario, csrfOk, persona }) {
  const status = Number(scenario);
  if (BODIES[status]) return send(status, BODIES[status]);
  const path = url.pathname.replace('/api/v1/received-bids', '');
  if (path === '/organisations') {
    if (scenario === 'rb_orgs_denied') return send(403, BODIES[403]);
    return send(200, { items: persona === 'none' ? [] : ORGS });
  }
  if (path === '' && method === 'post') return logBid({ rawBytes, contentType, scenario, csrfOk });
  if (path === '/assignments') {
    const open = BIDS.filter((b) => !assigned.has(b.case_id));
    const from = Number.parseInt(url.searchParams.get('cursor') ?? '0', 10);
    if (!(from >= 0)) return send(422, { ...BODIES[422], fields: [{ name: 'cursor', message: 'This cursor is not valid.' }] });
    const items = open.slice(from, from + PAGE).map((b) => ({ ...b, revision: revisionOf(b) }));
    return send(200, { items, cursor: from + PAGE < open.length ? String(from + PAGE) : null, checked: items.length });
  }
  const receipt = /^\/([^/]+)\/receipts\/(\d+)$/.exec(path);
  if (receipt && method === 'get') {
    if (scenario === 'rb_receipt_down') return send(500, BODIES[500]);
    const found = Number(receipt[2]) === 501 && receipt[1] === FIRST && receipts.size === 0 ? FIXTURE_RECEIPT : receipts.get(Number(receipt[2]));
    return found && found.case_id === receipt[1] ? send(200, found) : send(404, BODIES[404]);
  }
  const one = /^\/([^/]+)\/assignment$/.exec(path);
  if (one) {
    const bid = BIDS.find((b) => b.case_id === one[1]);
    if (!bid) return send(404, BODIES[404]);
    return method === 'post' ? assign({ bid, raw, scenario, csrfOk }) : send(200, detail(bid, scenario));
  }
  return send(404, BODIES[404]);
}
