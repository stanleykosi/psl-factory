// F-136: the client's response and SOW signature in the live shapes of contract 1.26.x: GET and POST
// /projects/{case_id}/commercial-response (actions witness, signatures, adopt) and the work items that carry that panel.
// Integer ids 4660 to 4666 only; every other id falls through to work-live.mjs. Sample data; no business rules.
// 4660 a delivery and two proof files: the response can be recorded, 4661 a signed response recorded: signing open, 4662 signatures
// captured: adoption open, 4663 baseline adopted, 4664 nothing sent to the client yet, 4665 a person who may not record,
// 4666 the client asked for changes. Item revision 5, case revision 89 (each write moves both on by one).
// (The server turns a project's UUID into its P-nnnn form before routing, so the desk is matched in both forms.)
// Write scenarios: w409 (the case moves on), w422, any status number, w403csrf is a failed CSRF check.
import { workLive } from './work-live.mjs';

export const COMMERCIAL_IDS = [4660, 4661, 4662, 4663, 4664, 4665, 4666];
export const COMMERCIAL_PATH = /^\/api\/v1\/(?:work\/(466[0-6])|projects\/(?:00000000-0000-4000-8000-00000000|P-)(466[0-6])\/commercial-response)$/;

const NOW = '2026-11-25T09:00:00Z';
const caseOf = (id) => `00000000-0000-4000-8000-00000000${id}`;
const BODIES = {
  400: { code: 'bad_request', message: 'We could not read that request.' },
  401: { code: 'not_signed_in', message: 'Sign in to continue.' },
  403: { code: 'forbidden', message: 'Your role does not allow this.' },
  404: { code: 'not_found', message: 'This record is unavailable.' },
  409: { code: 'stale_version', message: 'Someone changed this since you opened it.' },
  422: { code: 'invalid_input', message: 'The request was not accepted.', fields: [{ name: 'proof_ids', message: 'Select one to twelve distinct private proof files.' }] },
  429: { code: 'rate_limited', message: 'Too many requests.' },
  503: { code: 'unavailable', message: 'A dependency is unavailable.' },
};
const CSRF_FAILED = { code: 'csrf_failed', message: 'Your session check failed. Reload and try again.' };

const FILES = [
  { id: 31, name: 'client-email-reply.pdf', size: 182_000, sha256: 'a'.repeat(64) },
  { id: 32, name: 'signed-sow-scan.pdf', size: 2_400_000, sha256: 'b'.repeat(64) },
];
const SIGNED = { id: 9, evidence_id: 7, revision_id: 2, receipt_id: 5, kind: 'signed' };
const SIGNING = { signature_proofs: [{ id: 143, version: 2, kind: 'signature' }, { id: 7, version: 1, kind: 'signature' }], requirements: [{ id: 142, version: 1, kind: 'prd' }] };
const WITNESS = { id: 4, response_id: 9, client_name: 'Dayo Adesina', outcome: 'signed', responded_at: '2026-11-24T15:20:00Z', received_via: 'email' };
const PACKET = { id: 3, revision_id: 2, sow: 'human reference captured', prd: 'human reference captured', contract: 'pinned', authenticity: 'Not verified by a signature provider' };
const ADOPTION = { id: 2, revision_id: 2, finance_intake_id: 2, current: true };

const desk = (patch) => ({
  case_revision: 89,
  current_revision_id: 2,
  can_record: true,
  receipts: [{ id: 5, label: 'Statement of work · v1 · client · Delivered 24 Nov 2026, 10:00' }],
  owned_files: FILES,
  witness: null,
  witness_files: [],
  parties: [{ reference: 'client-signer', label: 'Client representative' }],
  responses: [],
  packet: null,
  signature_proofs: [],
  requirements: [],
  adoption: null,
  revision_drafts: [],
  ...patch,
});
const START = {
  4660: desk({}),
  4661: desk({ witness: WITNESS, witness_files: [FILES[0]], owned_files: [FILES[1]], responses: [SIGNED], ...SIGNING }),
  4662: desk({ witness: WITNESS, witness_files: [FILES[0]], owned_files: [FILES[1]], responses: [SIGNED], packet: PACKET, ...SIGNING }),
  4663: desk({ witness: WITNESS, witness_files: [FILES[0]], owned_files: [], responses: [SIGNED], packet: PACKET, adoption: ADOPTION }),
  4664: desk({ receipts: [], owned_files: [], parties: [] }),
  4665: desk({ can_record: false, receipts: [], owned_files: [], parties: [] }),
  4666: desk({ witness: { ...WITNESS, outcome: 'changes_requested', received_via: null }, witness_files: [FILES[0]], owned_files: [FILES[1]], responses: [{ ...SIGNED, kind: 'changes_requested' }] }),
};
const TITLES = {
  4660: ['action_needed', 'Action needed'],
  4661: ['action_needed', 'Action needed'],
  4662: ['action_needed', 'Action needed'],
  4663: ['verified', 'Verified'],
  4664: ['waiting', 'Waiting'],
  4665: ['waiting', 'Waiting'],
  4666: ['action_needed', 'Action needed'],
};

// what the writes changed: id -> desk; reset with the mock
let live = {};
export const resetCommercialLive = () => {
  live = {};
};
const current = (id) => live[id] ?? START[id];
// the work item's revision follows the case revision (5 at 89)
const revisionOf = (d) => d.case_revision - 84;

const item = (id, d) => {
  const [, template] = workLive({ method: 'get', url: new URL('http://mock/api/v1/work/4101'), scenario: undefined, csrfOk: true, persona: 'finance_lead' });
  return {
    ...template,
    id,
    case_id: caseOf(id),
    title: 'Costing and commercial submission',
    line: 'commercial/v1',
    state: TITLES[id][0],
    status_label: d.adoption?.current ? 'Verified' : TITLES[id][1],
    reference: 'Costing: Kora Logistics · fleet tracker',
    output_url: null,
    tracking_url: null,
    agent: null,
    verified_at: null,
    updated_at: NOW,
    django_url: `/work/${id}/`,
    api_url: `/api/v1/work/${id}`,
    revision: revisionOf(d),
    case_revision: d.case_revision,
    panels: [{ key: 'commercial-response', url: `/api/v1/projects/${caseOf(id)}/commercial-response`, contract_path: '/api/v1/projects/{case_id}/commercial-response' }],
  };
};

const int = (v) => Number.isInteger(v) && v >= 1;
const text = (v, max) => typeof v === 'string' && v.trim() !== '' && v.length <= max;
const KEYS = {
  witness: ['action', 'case_revision', 'revision_id', 'receipt_id', 'client_name', 'responded_at', 'outcome', 'genuine', 'proof_ids', 'note', 'operation_key', 'predecessor_id', 'party_ref', 'received_via'],
  signatures: ['action', 'case_revision', 'response_id', 'prd_id', 'signatures', 'note', 'operation_key', 'predecessor_id'],
  adopt: ['action', 'case_revision', 'response_id'],
};
const CHANNELS = ['email', 'whatsapp', 'call', 'portal', 'in_person', 'other'];
const SIGNATURE_KEYS = ['evidence_id', 'party_ref', 'method', 'locator', 'human_verified'];

/** A problem with the body, as the name of the field, or null. Exact keys and types of the contract's three bodies used here. */
function problem(body) {
  const keys = KEYS[body.action];
  if (!keys) return 'action';
  const extra = Object.keys(body).find((k) => !keys.includes(k));
  if (extra) return extra;
  const missing = keys.find((k) => !(k in body) && !(body.action === 'witness' && k === 'received_via'));
  if (missing) return missing;
  if (!int(body.case_revision)) return 'case_revision';
  if (body.action === 'adopt') return int(body.response_id) ? null : 'response_id';
  if (body.predecessor_id !== null && !int(body.predecessor_id)) return 'predecessor_id';
  if (!text(body.note, 4000)) return 'note';
  if (body.action === 'witness') {
    if (!/^[0-9a-f-]{36}$/.test(String(body.operation_key))) return 'operation_key';
    if (!int(body.revision_id)) return 'revision_id';
    if (!int(body.receipt_id)) return 'receipt_id';
    if (!text(body.client_name, 160)) return 'client_name';
    if (Number.isNaN(Date.parse(body.responded_at)) || !/Z$|[+-]\d\d:\d\d$/.test(body.responded_at)) return 'responded_at';
    if (!['signed', 'changes_requested', 'declined'].includes(body.outcome)) return 'outcome';
    if (body.genuine !== true) return 'genuine';
    if (!Array.isArray(body.proof_ids) || body.proof_ids.length < 1 || body.proof_ids.length > 12 || !body.proof_ids.every(int) || new Set(body.proof_ids).size !== body.proof_ids.length) return 'proof_ids';
    if (body.party_ref !== null && !text(body.party_ref, 100)) return 'party_ref';
    if ('received_via' in body && !CHANNELS.includes(body.received_via)) return 'received_via';
    return null;
  }
  if (!text(body.operation_key, 100)) return 'operation_key';
  if (!int(body.response_id)) return 'response_id';
  if (!int(body.prd_id)) return 'prd_id';
  const { signatures } = body;
  if (typeof signatures !== 'object' || signatures === null || Object.keys(signatures).some((k) => !['sow', 'prd'].includes(k))) return 'signatures';
  for (const part of ['sow', 'prd']) {
    const s = signatures[part];
    if (!s || Object.keys(s).length !== SIGNATURE_KEYS.length || SIGNATURE_KEYS.some((k) => !(k in s)) || !int(s.evidence_id) || typeof s.human_verified !== 'boolean') return `signatures.${part}`;
    if (['party_ref', 'method', 'locator'].some((k) => s[k] !== null && !text(s[k], 500))) return `signatures.${part}`;
  }
  return null;
}

function write(id, scenario, csrfOk, rawBytes) {
  const d = current(id);
  if (!d) return [404, BODIES[404]];
  if (!csrfOk) return [403, CSRF_FAILED];
  let body;
  try {
    body = JSON.parse(Buffer.from(rawBytes ?? []).toString('utf8') || '{}');
  } catch {
    return [400, BODIES[400]];
  }
  const bad = problem(body);
  if (bad) return [400, { code: 'bad_request', message: 'We could not read that request.', fields: [{ name: bad, message: 'This field is missing or not accepted.' }] }];
  if (scenario === 'w422') return [422, BODIES[422]];
  if (scenario === 'w409' || body.case_revision !== d.case_revision) {
    live[id] = { ...d, case_revision: d.case_revision + 1 };
    return [409, BODIES[409]];
  }
  const next = { ...d, case_revision: d.case_revision + 1 };
  const refused = (message, name) => [422, { code: 'invalid_input', message, fields: [{ name, message }] }];
  if (body.action === 'witness') {
    if (!d.can_record) return [403, BODIES[403]];
    if (body.revision_id !== d.current_revision_id) return refused('Reload this response form before recording it.', 'revision_id');
    if (!d.receipts.some((r) => r.id === body.receipt_id)) return refused('Choose a delivery of this project.', 'receipt_id');
    if (!body.proof_ids.every((p) => d.owned_files.some((f) => f.id === p))) return refused('Only your own exact project files can support this response.', 'proof_ids');
    if (body.predecessor_id !== (d.witness?.id ?? null)) return refused('Refresh and identify the current response predecessor.', 'predecessor_id');
    const signed = body.outcome === 'signed';
    Object.assign(next, {
      witness: { id: 4 + (d.witness ? 1 : 0), response_id: 9, client_name: body.client_name, outcome: body.outcome, responded_at: body.responded_at, received_via: body.received_via ?? null },
      witness_files: d.owned_files.filter((f) => body.proof_ids.includes(f.id)),
      owned_files: d.owned_files.filter((f) => !body.proof_ids.includes(f.id)),
      responses: [{ ...SIGNED, receipt_id: body.receipt_id, kind: body.outcome }],
      ...(signed ? SIGNING : { signature_proofs: [], requirements: [] }),
    });
  } else if (body.action === 'signatures') {
    const signed = d.responses.find((r) => r.kind === 'signed');
    if (!signed || body.response_id !== signed.id) return refused('Select the actual signed client response.', 'response_id');
    if (body.signatures.sow?.evidence_id !== signed.evidence_id) return refused('Use the exact statement-of-work signature from the selected response.', 'signatures');
    if (!d.requirements.some((r) => r.id === body.prd_id)) return refused('Select the current requirements document.', 'prd_id');
    if (!d.signature_proofs.some((s) => s.id === body.signatures.prd?.evidence_id)) return refused('Choose a signature proof on file.', 'signatures');
    if (body.predecessor_id !== (d.packet?.id ?? null)) return refused('Refresh and identify the current signature packet predecessor.', 'predecessor_id');
    next.packet = { ...PACKET, id: (d.packet?.id ?? 2) + 1 };
  } else {
    if (!d.packet || body.response_id !== d.responses.find((r) => r.kind === 'signed')?.id) return refused('Record the signatures first.', 'response_id');
    next.adoption = ADOPTION;
  }
  live[id] = next;
  return [201, { case_revision: next.case_revision, record_ids: [100 + next.case_revision] }];
}

/** One commercial-response read or write, or the work item that carries it. `scenario` is the cookie or header value. */
export function commercialLive({ method, url, scenario, csrfOk, persona, rawBytes }) {
  const found = COMMERCIAL_PATH.exec(url.pathname);
  const status = Number(scenario);
  if (BODIES[status]) return [status, BODIES[status]];
  if (persona === 'none') return [404, BODIES[404]];
  const id = Number(found[1] ?? found[2]);
  if (method === 'post') return found[2] ? write(id, scenario, csrfOk, rawBytes) : [405, { code: 'method_not_allowed', message: 'Read only.' }];
  if (method !== 'get') return [405, { code: 'method_not_allowed', message: 'Read only.' }];
  return found[1] ? [200, item(id, current(id))] : [200, current(id)];
}
