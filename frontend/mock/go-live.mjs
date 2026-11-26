// F-114: go-live acceptance (SCR-45) in the live shapes of contract 1.26.x: GET|POST /work/{id}/go-live-signoff, POST .../proofs,
// GET|POST .../go-live-replies, POST .../successor and GET .../decline. Integer ids 4411 to 4422 and 4429 only; every other id falls
// through. (The spec named 4401 to 4410; those are taken, so the fixtures are 4411 to 4420 in the same order, plus 4421 and 4422.)
// Sample data; no business rules.
// 4411 ready to sign (receipt, two proofs); 4412 accepted; 4413 changes requested; 4414 declined (issue, candidate and remediation
// options); 4415 another PM (the sign-off read answers 403); 4416 an earlier acceptance on file; 4417 conflict (the first sign-off
// answers 409); 4418 a reply the person may not read; 4419 changes then withdrawn; 4420 nothing delivered yet; 4421 a reply may be
// recorded (capture entry); 4422 declined with no options for the reply; 4429 not found.
// Scenarios (cookie psl_mock_scenario or header x-mock-scenario): a status number answers every route with it; w403, w403csrf, w409,
// w422, w429, w503, w500 answer the writes; wdrop (the write ran, the answer is lost) and wdrop0 (the answer is lost, nothing ran).
import { workLive } from './work-live.mjs';

export const GO_LIVE_PATH = /^\/api\/v1\/work\/(44(?:1[1-9]|2[0-2]|29))(\/go-live-signoff|\/go-live-signoff\/proofs|\/go-live-replies|\/go-live-replies\/successor|\/go-live-replies\/decline)?$/;

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
  w403: [403, { code: 'forbidden', message: 'Only the appointed PM can record this.' }],
  w403csrf: [403, CSRF_FAILED],
  w409: [409, BODIES[409]],
  w422: [422, BODIES[422]],
  w429: [429, BODIES[429]],
  w503: [503, BODIES[503]],
  w500: [500, { code: 'server_error', message: 'Something broke.' }],
};
const CHANNELS = ['email', 'customer_portal', 'meeting', 'phone', 'other'];

const signoff = (patch = {}) => ({
  expected_revision: 6,
  case_revision: 41,
  version_id: 11,
  receipts: [{ id: 51, recorded_at: '2026-11-25T10:02:00Z' }],
  prior_acceptance_id: null,
  proofs: [{ id: 61, version: 1, kind: 'signature' }, { id: 62, version: 1, kind: 'signature' }],
  ...patch,
});
const milestone = (patch = {}) => ({ recorded_id: null, configuration_id: null, name: null, acceptance_id: null, proof_ids: [], owner_decision_ids: [], can_confirm: false, confirmation: null, ...patch });
const replies = (patch = {}) => ({
  expected_revision: 6,
  case_revision: 41,
  channels: CHANNELS,
  finding: 'Only the person who sent the document records the reply.',
  capture: [],
  corrections: [],
  replies: [],
  linked_issues: [],
  reviewed_handoffs: [],
  milestone: milestone(),
  ...patch,
});
const reply = (patch = {}) => ({ id: 21, receipt_id: 51, version_id: 11, number: 1, outcome: 'changes_requested', party: 'Ngozi Bello', channel: 'email', responded_at: '2026-11-25T15:00:00Z', note: 'Add the bureau outage contact to the incident plan.', evidence_id: 9101, ...patch });
const hiddenReply = (patch = {}) => reply({ party: null, channel: null, responded_at: null, note: null, evidence_id: null, ...patch });
const RULES = {
  base_configuration_id: null,
  current: { recording_roles: ['PM', 'PMO Lead'], correction_roles: ['PMO Lead'], remediation_roles: ['PMO Lead'], allow_recorder_correction: false, channels: ['email', 'meeting'], changes_handling: 'reviewed_document_successor', decline_handling: 'new_release_candidate', issue_states_for_new_release: ['Resolved'] },
  proofs: [],
};
const decline = (id) => ({
  expected_revision: 6,
  case_revision: 41,
  issues: id === 4422 ? [] : [{ reply_id: 21, existing_issues: [{ id: 301, label: 'ISS-0301 Bureau outage contact' }], owners: [{ id: 31, label: 'Tunde Bello' }, { id: 32, label: 'Amaka Obi' }] }],
  new_candidates: id === 4422 ? [] : [{ reply_id: 21, requirements_id: 81 }],
  review_options: id === 4422 ? [] : [{ reply_id: 21, previous_id: null, roles: ['PMO Lead'], destinations: [{ id: 91, label: 'Support handover' }] }],
  rules: RULES,
});

const START = {
  4411: { signoff: signoff(), replies: replies() },
  4412: { signoff: signoff(), replies: replies({ milestone: milestone({ name: 'Go-live', acceptance_id: 7001 }) }) },
  4413: { signoff: signoff(), replies: replies({ replies: [reply()] }) },
  4414: { signoff: signoff(), replies: replies({ replies: [reply({ outcome: 'declined', note: 'We are not ready to go live this quarter.' })] }), decline: decline(4414) },
  4415: { signoff: null, replies: replies({ replies: [reply()] }) },
  4416: { signoff: signoff({ prior_acceptance_id: 6990 }), replies: replies() },
  4417: { signoff: signoff(), replies: replies(), conflictOnce: true },
  4418: { signoff: signoff(), replies: replies({ replies: [hiddenReply()] }) },
  4419: { signoff: signoff(), replies: replies({ replies: [reply(), reply({ id: 22, number: 2, outcome: 'withdrawn', note: 'Withdrawn by the recorder.' })] }) },
  4420: { signoff: signoff({ receipts: [], proofs: [] }), replies: replies() },
  4421: { signoff: signoff(), replies: replies({ capture: [{ receipt_id: 51, previous_id: null, roles: ['PM'] }] }) },
  4422: { signoff: signoff(), replies: replies({ replies: [reply({ outcome: 'declined', note: 'We are not ready to go live this quarter.' })] }), decline: decline(4422) },
};

// what the writes changed: id -> the same parts; reset with the mock
let live = {};
let nextProof = 70;
export const resetGoLiveLive = () => {
  live = {};
  nextProof = 70;
};
const current = (id) => live[id] ?? START[id];

const item = (id) => {
  const c = current(id);
  const [, template] = workLive({ method: 'get', url: new URL('http://mock/api/v1/work/4101'), scenario: undefined, csrfOk: true, persona: 'finance_lead' });
  const [state, label] = c.moved ?? ['action_needed', 'Action needed'];
  const revision = (c.signoff ?? c.replies).expected_revision;
  return {
    ...template,
    id,
    case_id: caseOf(id),
    title: 'Go-live acceptance for Kora Logistics',
    line: 'delivery-go-live/v1',
    state,
    status_label: label,
    reference: 'GLV-0044',
    output_url: null,
    tracking_url: null,
    agent: null,
    verified_at: null,
    updated_at: NOW,
    django_url: `/work/${id}/`,
    api_url: `/api/v1/work/${id}`,
    revision,
    case_revision: c.replies.case_revision,
    panels: [
      { key: 'go-live-signoff', url: `/api/v1/work/${id}/go-live-signoff`, contract_path: '/api/v1/work/{work_id}/go-live-signoff' },
      { key: 'go-live-replies', url: `/api/v1/work/${id}/go-live-replies`, contract_path: '/api/v1/work/{work_id}/go-live-replies' },
      { key: 'go-live-milestone', url: `/api/v1/work/${id}/go-live-milestone`, contract_path: '/api/v1/work/{work_id}/go-live-milestone' },
    ],
  };
};

const int = (v) => Number.isInteger(v) && v >= 1;
const text = (v, max) => typeof v === 'string' && v.trim() !== '' && v.length <= max;
const SIGNER_KEYS = ['source_system', 'source_reference', 'decision_id', 'decision_version', 'signer_reference', 'signed_at'];
const SIGNER = (s) => s && typeof s === 'object' && Object.keys(s).length === 6 && SIGNER_KEYS.every((k) => (k === 'signed_at' ? typeof s[k] === 'string' && !Number.isNaN(Date.parse(s[k])) : text(s[k], 160)));
const NULLABLE_INT = (v) => v === null || int(v);
const KEYS = {
  signoff: ['expected_revision', 'case_revision', 'version_id', 'receipt_id', 'pm_signature_id', 'client_signature_id', 'signers', 'mode', 'prior_acceptance_id', 'note'],
  proof: ['case_revision', 'receipt_id', 'upload_id', 'role', 'checked'],
  successor: ['expected_revision', 'case_revision', 'inputs', 'reason'],
  link_decline_issue: ['action', 'expected_revision', 'case_revision', 'reply_id', 'existing_issue_id', 'title', 'owner_id', 'next_action', 'note'],
  prepare_new_candidate: ['action', 'expected_revision', 'case_revision', 'reply_id', 'reference', 'requirements_id', 'note'],
};

/** A problem with the body (a field name), or null. The contract's exact keys and types; every key is required. */
function problem(kind, body) {
  const allowed = KEYS[kind];
  if (!allowed) return 'action';
  if (Object.keys(body).length !== allowed.length || !allowed.every((k) => k in body)) return Object.keys(body).find((k) => !allowed.includes(k)) ?? allowed.find((k) => !(k in body));
  if ('expected_revision' in body && !int(body.expected_revision)) return 'expected_revision';
  if (!int(body.case_revision)) return 'case_revision';
  if (kind === 'signoff') {
    for (const k of ['version_id', 'receipt_id', 'pm_signature_id', 'client_signature_id']) if (!int(body[k])) return k;
    if (!body.signers || !SIGNER(body.signers.PM)) return 'signers.PM';
    if (!SIGNER(body.signers.Client)) return 'signers.Client';
    if (!['fresh_signatures', 'metadata_binding'].includes(body.mode)) return 'mode';
    if (!NULLABLE_INT(body.prior_acceptance_id)) return 'prior_acceptance_id';
    if (!text(body.note, 4000)) return 'note';
  } else if (kind === 'proof') {
    if (!int(body.receipt_id)) return 'receipt_id';
    if (!int(body.upload_id)) return 'upload_id';
    if (!['PM', 'Client'].includes(body.role)) return 'role';
    if (body.checked !== true) return 'checked';
  } else if (kind === 'successor') {
    const i = body.inputs;
    if (!i || Object.keys(i).length !== 4 || !['template_id', 'checklist', 'incident_reporting', 'rollback'].every((k) => k in i && NULLABLE_INT(i[k]))) return 'inputs';
    if (!text(body.reason, 2000)) return 'reason';
  } else if (kind === 'link_decline_issue') {
    if (!int(body.reply_id)) return 'reply_id';
    if (!NULLABLE_INT(body.existing_issue_id) || !NULLABLE_INT(body.owner_id)) return 'existing_issue_id';
    if (body.title !== null && !text(body.title, 240)) return 'title';
    if (body.next_action !== null && !text(body.next_action, 1000)) return 'next_action';
    if (!text(body.note, 4000)) return 'note';
  } else if (kind === 'prepare_new_candidate') {
    if (!int(body.reply_id)) return 'reply_id';
    if (!text(body.reference, 160)) return 'reference';
    if (!int(body.requirements_id)) return 'requirements_id';
    if (!text(body.note, 4000)) return 'note';
  }
  return null;
}

const refused = (field, message = 'This field is missing or not accepted.') => [400, { code: 'bad_request', message: 'We could not read that request.', fields: [{ name: field, message }] }];
const invalid = (field, message) => [422, { code: 'invalid', message, fields: [{ name: field, message }] }];

function write(id, route, scenario, csrfOk, rawBytes) {
  const c = current(id);
  if (!c) return [404, BODIES[404]];
  if (!csrfOk) return [403, CSRF_FAILED];
  let body;
  try {
    body = JSON.parse(Buffer.from(rawBytes ?? []).toString('utf8') || '{}');
  } catch {
    return [400, BODIES[400]];
  }
  const kind = route === '/go-live-signoff' ? 'signoff' : route === '/go-live-signoff/proofs' ? 'proof' : route === '/go-live-replies/successor' ? 'successor' : body.action;
  if ((kind === 'signoff' || kind === 'proof') && !c.signoff) return [403, BODIES[403]];
  const bad = problem(kind, body);
  if (bad) return refused(bad);
  if (scenario === 'wdrop0') return ['drop'];
  if (SCENARIO[scenario]) return SCENARIO[scenario];
  const next = { ...c, signoff: c.signoff && { ...c.signoff }, replies: { ...c.replies }, decline: c.decline && { ...c.decline } };
  const bumpRevision = () => {
    if (next.signoff) next.signoff.expected_revision += 1;
    next.replies.expected_revision += 1;
    if (next.decline) next.decline.expected_revision += 1;
  };
  const bumpCase = () => {
    if (next.signoff) next.signoff.case_revision += 1;
    next.replies.case_revision += 1;
    if (next.decline) next.decline.case_revision += 1;
  };
  const exp = kind === 'proof' ? null : (kind === 'signoff' ? c.signoff : c.replies).expected_revision;
  const caseRev = (kind === 'proof' || kind === 'signoff' ? c.signoff : c.replies).case_revision;
  if (c.conflictOnce && kind === 'signoff') {
    // someone else changed the record: the revisions move on and the next press succeeds
    bumpRevision();
    bumpCase();
    live[id] = { ...next, conflictOnce: false };
    return [409, BODIES[409]];
  }
  if ((exp !== null && body.expected_revision !== exp) || body.case_revision !== caseRev || scenario === 'w409') return [409, BODIES[409]];

  if (kind === 'proof') {
    if (!c.signoff.receipts.some((r) => r.id === body.receipt_id)) return invalid('receipt_id', 'Choose the exact delivered go-live report and receipt.');
    const evidence = nextProof;
    nextProof += 1;
    next.signoff.proofs = [{ id: evidence, version: 1, kind: 'signature' }, ...c.signoff.proofs];
    bumpCase();
    live[id] = next;
    if (scenario === 'wdrop') return ['drop'];
    return [201, { evidence_id: evidence, case_revision: next.signoff.case_revision }];
  }
  if (kind === 'signoff') {
    if (!c.signoff.receipts.some((r) => r.id === body.receipt_id) || body.version_id !== c.signoff.version_id) return invalid('receipt_id', 'Choose the exact delivered report and current receipt.');
    if (body.pm_signature_id === body.client_signature_id) return invalid('client_signature_id', 'The PM and the client need two different signature records.');
    if (![body.pm_signature_id, body.client_signature_id].every((p) => c.signoff.proofs.some((x) => x.id === p))) return invalid('pm_signature_id', 'Choose a listed signature record.');
    if (body.mode === 'metadata_binding' ? body.prior_acceptance_id !== c.signoff.prior_acceptance_id || body.prior_acceptance_id === null : body.prior_acceptance_id !== null) return invalid('prior_acceptance_id', 'This does not match the acceptance on file.');
    next.replies.milestone = { ...c.replies.milestone, name: 'Go-live', acceptance_id: 7001 };
    next.moved = ['waiting', 'Waiting'];
  } else if (kind === 'successor') {
    next.replies.finding = 'A new go-live report is being prepared.';
    next.moved = ['waiting', 'Waiting'];
  } else if (kind === 'link_decline_issue') {
    if (!c.decline || !c.decline.issues.some((i) => i.reply_id === body.reply_id)) return invalid('reply_id', 'There is nothing to link for this reply.');
    const known = c.decline.issues.find((i) => i.reply_id === body.reply_id);
    if (body.existing_issue_id !== null ? !known.existing_issues.some((i) => i.id === body.existing_issue_id) : body.title === null || !known.owners.some((o) => o.id === body.owner_id)) return invalid('existing_issue_id', 'Choose a listed issue or give a title and a listed owner.');
    next.replies.linked_issues = [...c.replies.linked_issues, { reply_id: body.reply_id, issue_id: body.existing_issue_id ?? 400 + c.replies.linked_issues.length }];
  } else {
    if (!c.decline || !c.decline.new_candidates.some((n) => n.reply_id === body.reply_id && n.requirements_id === body.requirements_id)) return invalid('requirements_id', 'That is not a listed requirements record.');
    next.decline.new_candidates = c.decline.new_candidates.filter((n) => n.reply_id !== body.reply_id);
    next.moved = ['waiting', 'Waiting'];
  }
  bumpRevision();
  bumpCase();
  live[id] = next;
  if (scenario === 'wdrop') return ['drop'];
  const revision = (next.signoff ?? next.replies).expected_revision;
  return kind === 'successor' ? [200, { work_id: id, state: 'waiting', revision }] : [kind === 'signoff' ? 200 : 201, { work_id: id, state: 'waiting', revision, record_id: 100 + revision }];
}

/** One go-live read or write. `scenario` is the cookie or header value. */
export function goLiveLive({ method, url, scenario, csrfOk, persona, rawBytes }) {
  const found = GO_LIVE_PATH.exec(url.pathname);
  const status = Number(scenario);
  if (BODIES[status]) return [status, BODIES[status]];
  if (persona === 'none') return [404, BODIES[404]];
  const id = Number(found[1]);
  const part = found[2];
  if (id === 4429) return [404, BODIES[404]];
  if (method === 'post') return part && part !== '/go-live-replies/decline' ? write(id, part, scenario, csrfOk, rawBytes) : [405, { code: 'method_not_allowed', message: 'Read only.' }];
  if (method !== 'get') return [405, { code: 'method_not_allowed', message: 'Read only.' }];
  const c = current(id);
  if (!part) return [200, item(id)];
  if (part === '/go-live-signoff') return c.signoff ? [200, c.signoff] : [403, BODIES[403]];
  if (part === '/go-live-replies') return [200, c.replies];
  if (part === '/go-live-replies/decline') return c.decline ? [200, c.decline] : [409, BODIES[409]];
  return [405, { code: 'method_not_allowed', message: 'Read only.' }];
}
