// F-117: the handover page (SCR-48) in the live shapes of contract 1.26.x: GET|POST /work/{id}/support-publication, .../support-replies,
// .../support-receipt and POST /work/{id}/actions (the check-what-happened control). Integer ids 6101 to 6108 only; every other id falls
// through. (The spec named 4201 to 4208; those are taken, so each is the same number plus 1900.) Sample data: no message is ever sent
// to Support; no business rules.
// 6101 ready to publish; 6102 queued (processing); 6103 a reply may be recorded (one recipient, one role); 6104 Support found two gaps;
// 6105 Support received it after gaps (two roles to choose from); 6106 delivery uncertain (Check what happened); 6107 the Support
// recipient's own view (document and an acknowledge row; the replies and publication reads answer 403); 6108 not yours (404 everywhere).
// Scenarios (cookie psl_mock_scenario or header x-mock-scenario): a status number answers every route here with it; w403, w403csrf, w409,
// w422, w429, w503, w500 answer only the writes; wdrop (the write ran, the answer is lost) and wdrop0 (nothing ran).
import { workLive } from './work-live.mjs';

export const HANDOVER_PATH = /^\/api\/v1\/work\/(610[1-8])(\/support-publication|\/support-replies|\/support-receipt|\/actions)?$/;

const NOW = '2026-11-26T09:00:00Z';
const caseOf = (id) => `00000000-0000-4000-8000-00000000${id}`;
const BODIES = {
  400: { code: 'bad_request', message: 'We could not read that request.' },
  401: { code: 'not_signed_in', message: 'Sign in to continue.' },
  403: { code: 'forbidden', message: 'Your role does not allow this.' },
  404: { code: 'not_found', message: 'This record is unavailable.' },
  409: { code: 'stale_version', message: 'Someone changed this since you opened it.' },
  422: { code: 'invalid', message: 'The request was not accepted.', fields: [{ name: 'note', message: 'A note is needed.' }] },
  429: { code: 'rate_limited', message: 'Too many requests.' },
  503: { code: 'unavailable', message: 'A dependency is unavailable.' },
};
const CSRF_FAILED = { code: 'csrf_failed', message: 'Your session check failed. Reload and try again.' };
const SCENARIO = {
  w403: [403, { code: 'forbidden', message: 'Only the authorised recorder can do this.' }],
  w403csrf: [403, CSRF_FAILED],
  w409: [409, BODIES[409]],
  w422: [422, BODIES[422]],
  w429: [429, BODIES[429]],
  w503: [503, BODIES[503]],
  w500: [500, { code: 'server_error', message: 'Something broke.' }],
};
const CHANNELS = ['email', 'whatsapp', 'client_portal', 'signed_document', 'meeting'];
const PROOFS = [{ id: 7301, version: 1, kind: 'signature' }];

const row = (patch = {}) => ({ id: 8101, recipient: 'Femi Ojo', recorded_at: '2026-11-25T10:00:00Z', previous_id: null, status: null, reply: null, ...patch });
const replyOf = (patch = {}) => ({ party: 'Femi Ojo · Support lead', channel: 'email', responded_at: '2026-11-25T15:00:00Z', note: 'We have read the handover.', gaps: [], ...patch });
const GAPS = ['No contact for the credit bureau outage', 'Runbook misses the nightly export restart'];

const START = {
  6101: { state: 'ready', can_publish: true, version_id: 9101, can_record: false, roles: [], proofs: [], receipts: [] },
  6102: { state: 'processing', can_publish: false, version_id: null, can_record: false, roles: [], proofs: [], receipts: [] },
  6103: { state: 'waiting', can_publish: false, version_id: null, can_record: true, roles: ['Support lead'], proofs: PROOFS, receipts: [row()] },
  6104: {
    state: 'action_needed',
    can_publish: false,
    version_id: null,
    can_record: true,
    roles: ['Support lead'],
    proofs: PROOFS,
    receipts: [row({ previous_id: 9001, status: 'gaps', reply: replyOf({ note: 'Two things are missing.', gaps: GAPS }) })],
  },
  6105: {
    state: 'verified',
    can_publish: false,
    version_id: null,
    can_record: true,
    roles: ['Support lead', 'PMO Lead'],
    proofs: PROOFS,
    receipts: [row({ previous_id: 9002, status: 'received', reply: replyOf({ responded_at: '2026-11-26T08:00:00Z', note: 'Both gaps are now covered.' }) })],
  },
  6106: { state: 'effect_uncertain', can_publish: false, version_id: null, can_record: false, roles: [], proofs: [], receipts: [], reconcile: true },
  6107: {
    state: 'waiting',
    recipientView: true,
    can_publish: false,
    version_id: null,
    can_record: false,
    roles: [],
    proofs: [],
    receipts: [],
    ack: [{ id: 8101, can_acknowledge: true, status: null }],
    ackProofs: [{ id: 7401, version: 1, kind: 'support_acknowledgement' }],
    document: {
      id: 9101,
      title: 'Support handover',
      version: 1,
      sections: [
        { heading: 'Runbook', text: 'Where the runbook lives and who keeps it current.' },
        { heading: 'Escalation contacts', text: 'Who to call first, second and third.' },
      ],
      supporting_records: [],
    },
  },
};

// what the writes changed: id -> the same parts; reset with the mock
let live = {};
let next = 9100;
export const resetHandoverLive = () => {
  live = {};
  next = 9100;
};
const current = (id) => live[id] ?? { ...START[id], revision: 8 };

const item = (id) => {
  const c = current(id);
  const [, template] = workLive({ method: 'get', url: new URL('http://mock/api/v1/work/4101'), scenario: undefined, csrfOk: true, persona: 'finance_lead' });
  const labels = { ready: 'Ready', waiting: 'Waiting', action_needed: 'Action needed', processing: 'Processing', verified: 'Verified', effect_uncertain: 'Effect uncertain' };
  return {
    ...template,
    id,
    case_id: caseOf(id),
    title: 'Support handover for Kora Logistics',
    line: 'delivery-handover/v1',
    state: c.state,
    status_label: labels[c.state],
    reference: 'HND-0071',
    output_url: null,
    tracking_url: null,
    agent: null,
    verified_at: null,
    updated_at: `${NOW.slice(0, 17)}${String(c.revision).padStart(2, '0')}Z`,
    django_url: `/work/${id}/`,
    api_url: `/api/v1/work/${id}`,
    revision: c.revision,
    case_revision: 41,
    actions: c.reconcile ? ['reconcile'] : [],
    available_control: [],
    current_activity: null,
    panels: ['support-receipt', 'support-replies', 'support-publication'].map((key) => ({ key, url: `/api/v1/work/${id}/${key}`, contract_path: `/api/v1/work/{work_id}/${key}` })),
  };
};

const int = (v) => Number.isInteger(v) && v >= 1;
const text = (v, max) => typeof v === 'string' && v.trim() !== '' && v.length <= max;
const KEYS = {
  publish: ['expected_revision', 'case_revision', 'version_id'],
  reply: ['expected_revision', 'case_revision', 'receipt_id', 'previous_id', 'status', 'evidence_id', 'note', 'party', 'channel', 'responded_at', 'role'],
  ack: ['expected_revision', 'case_revision', 'receipt_id', 'evidence_id', 'status', 'note'],
  reconcile: ['expected_revision', 'action'],
};

/** A problem with the body (a field name), or null. The contract's exact keys and types; `gaps` is the one optional key. */
function problem(kind, body) {
  const allowed = KEYS[kind];
  const keys = Object.keys(body).filter((k) => !(kind === 'reply' && k === 'gaps'));
  if (keys.length !== allowed.length || !allowed.every((k) => k in body)) return keys.find((k) => !allowed.includes(k)) ?? allowed.find((k) => !(k in body));
  if (!int(body.expected_revision)) return 'expected_revision';
  if (kind === 'reconcile') return body.action === 'reconcile' ? null : 'action';
  if (!int(body.case_revision)) return 'case_revision';
  if (kind === 'publish') return int(body.version_id) ? null : 'version_id';
  if (!int(body.receipt_id)) return 'receipt_id';
  if (!int(body.evidence_id)) return 'evidence_id';
  if (!['received', 'gaps'].includes(body.status)) return 'status';
  if (!text(body.note, 4000)) return 'note';
  if (kind === 'reply') {
    if (!(body.previous_id === null || int(body.previous_id))) return 'previous_id';
    if (!text(body.party, 200)) return 'party';
    if (!CHANNELS.includes(body.channel)) return 'channel';
    if (typeof body.responded_at !== 'string' || Number.isNaN(Date.parse(body.responded_at)) || !/(Z|[+-]\d\d:\d\d)$/.test(body.responded_at)) return 'responded_at';
    if (!text(body.role, 100)) return 'role';
    if ('gaps' in body && (!Array.isArray(body.gaps) || body.gaps.length > 10 || !body.gaps.every((g) => text(g, 400)))) return 'gaps';
  }
  return null;
}

const refused = (field) => [400, { code: 'bad_request', message: 'We could not read that request.', fields: [{ name: field, message: 'This field is missing or not accepted.' }] }];
const invalid = (field, message) => [422, { code: 'invalid', message, fields: [{ name: field, message }] }];

function write(id, route, scenario, csrfOk, rawBytes) {
  if (!csrfOk) return [403, CSRF_FAILED];
  const c = current(id);
  let body;
  try {
    body = JSON.parse(Buffer.from(rawBytes ?? []).toString('utf8') || '{}');
  } catch {
    return [400, BODIES[400]];
  }
  const kind = { '/support-publication': 'publish', '/support-replies': 'reply', '/support-receipt': 'ack', '/actions': 'reconcile' }[route];
  if (kind === 'publish' && !c.can_publish) return [403, BODIES[403]];
  if (kind === 'reply' && !c.can_record) return [403, BODIES[403]];
  if (kind === 'ack' && !(c.ack ?? []).some((r) => r.can_acknowledge)) return [403, BODIES[403]];
  if (kind === 'reconcile' && !c.reconcile) return [403, BODIES[403]];
  const bad = problem(kind, body);
  if (bad) return refused(bad);
  if (scenario === 'wdrop0') return ['drop'];
  if (SCENARIO[scenario]) return SCENARIO[scenario];
  if (body.expected_revision !== c.revision || (kind !== 'reconcile' && body.case_revision !== 41)) return [409, BODIES[409]];
  const after = { ...c, revision: c.revision + 1 };
  if (kind === 'publish') {
    if (body.version_id !== c.version_id) return invalid('version_id', 'Publish the exact approved version.');
    Object.assign(after, { state: 'processing', can_publish: false, version_id: null });
  } else if (kind === 'reply') {
    const target = c.receipts.find((r) => r.id === body.receipt_id);
    if (!target) return invalid('receipt_id', 'Choose a listed recipient.');
    if (body.previous_id !== target.previous_id) return invalid('previous_id', 'This must name the reply it replaces.');
    if (!c.roles.includes(body.role)) return invalid('role', 'Choose a listed role.');
    if (!c.proofs.some((p) => p.id === body.evidence_id)) return invalid('evidence_id', 'Choose a listed proof record.');
    const gaps = body.gaps ?? [];
    if ((body.status === 'gaps') !== (gaps.length > 0)) return invalid('gaps', 'List the gaps only when Support found gaps.');
    next += 1;
    after.receipts = c.receipts.map((r) => (r === target ? { ...r, previous_id: next, status: body.status, reply: { party: body.party, channel: body.channel, responded_at: body.responded_at, note: body.note, gaps } } : r));
    after.state = body.status === 'received' ? 'verified' : 'action_needed';
  } else if (kind === 'ack') {
    const target = c.ack.find((r) => r.id === body.receipt_id && r.can_acknowledge);
    if (!target) return invalid('receipt_id', 'Choose a receipt you can acknowledge.');
    if (!c.ackProofs.some((p) => p.id === body.evidence_id)) return invalid('evidence_id', 'Choose a listed proof record.');
    after.ack = c.ack.map((r) => (r === target ? { ...r, can_acknowledge: false, status: body.status } : r));
  } else {
    Object.assign(after, { state: 'waiting', reconcile: false });
  }
  live[id] = after;
  if (scenario === 'wdrop') return ['drop'];
  const out = { work_id: id, state: after.state, revision: after.revision };
  return kind === 'ack' ? [200, { ...out, record_id: 100 + after.revision }] : kind === 'reconcile' ? [202, out] : [kind === 'reply' ? 201 : 202, { ...out, record_id: 100 + after.revision }];
}

/** One handover read or write. `scenario` is the cookie or header value. */
export function handoverLive({ method, url, scenario, csrfOk, persona, rawBytes }) {
  const found = HANDOVER_PATH.exec(url.pathname);
  const status = Number(scenario);
  if (BODIES[status]) return [status, BODIES[status]];
  const id = Number(found[1]);
  if (persona === 'none' || id === 6108) return [404, BODIES[404]];
  const part = found[2];
  if (method === 'post') return part ? write(id, part, scenario, csrfOk, rawBytes) : [405, { code: 'method_not_allowed', message: 'Read only.' }];
  if (method !== 'get' || part === '/actions') return [405, { code: 'method_not_allowed', message: 'Read only.' }];
  if (!part) return [200, item(id)];
  const c = current(id);
  const tokens = { expected_revision: c.revision, case_revision: 41 };
  if (part === '/support-publication') return c.recipientView ? [403, BODIES[403]] : [200, { ...tokens, can_publish: c.can_publish, version_id: c.version_id }];
  if (part === '/support-replies') return c.recipientView ? [403, BODIES[403]] : [200, { ...tokens, roles: c.roles, channels: c.can_record ? CHANNELS : [], can_record: c.can_record, proofs: c.proofs, receipts: c.receipts }];
  return c.recipientView ? [200, { ...tokens, receipts: c.ack, document: c.document, proofs: c.ackProofs }] : [403, BODIES[403]];
}
