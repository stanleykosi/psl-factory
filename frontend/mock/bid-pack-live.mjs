// F-98: the RFP submission panel in the live shapes of contract 1.26.0: GET /work/{id}/bid-pack and /bid-submission, and the writes
// POST /bid-pack/review-request, POST /reviews (kind bid, subject document: what the live API accepts for an RFP pack) and
// POST /bid-submission (202). work-live.mjs serves the work items and routes these operations here. Sample data; no business rules.
// Ids: 4501 a pack ready to send (the PM), 4502 in review and this person may decide, 4503 in review and this person may not,
// 4504 approved and ready to send to the client, 4505 sent with a receipt, 4506 returned with a note, 4507 approved but the file
// check found problems, 4508 no pack, 4509 a pack with no document version yet. 4401 (the F-96 response) also has a pack, so its
// Send for review works. Item revision 9, case revision 89 (the write moves both on by one).
// Write scenarios: w403, w409 (the pack moves on), w422, w429, w503, w500, wdrop (the answer is lost after the write ran), wdrop0.
import { BID_ANSWERS_IDS, bidBump } from './bid-answers-live.mjs';

export const BID_PACK_IDS = [4501, 4502, 4503, 4504, 4505, 4506, 4507, 4508, 4509];
const PACK_IDS = [...BID_PACK_IDS, ...BID_ANSWERS_IDS.filter((id) => id === 4401)];
const NOW = '2026-11-24T09:00:00Z';
const PACK = 77;
const VERSION = 801;
const BODIES = {
  400: { code: 'bad_request', message: 'We could not read that request.' },
  403: { code: 'forbidden', message: 'Your role does not allow this.' },
  404: { code: 'not_found', message: 'This record is unavailable.' },
  409: { code: 'stale_version', message: 'Someone changed this since you opened it.' },
  429: { code: 'rate_limited', message: 'Too many requests.' },
  500: { code: 'server_error', message: 'Something went wrong.' },
  503: { code: 'unavailable', message: 'A dependency is unavailable.' },
};
const FIRST = { 4501: 'draft', 4401: 'draft', 4502: 'in_review', 4503: 'in_review', 4504: 'approved', 4505: 'sent', 4506: 'returned', 4507: 'approved', 4508: 'none', 4509: 'draft' };
const STATES = {
  draft: ['action_needed', 'Action needed'],
  in_review: ['waiting', 'Waiting for a decision'],
  approved: ['action_needed', 'Action needed'],
  returned: ['action_needed', 'Action needed'],
  rejected: ['action_needed', 'Action needed'],
  processing: ['processing', 'Processing'],
  sent: ['verified', 'Verified'],
  none: ['action_needed', 'Action needed'],
};
const FINDING = { code: 'file_format_mismatch', message: 'The client asks for a PDF; this file is a Word document.' };
const REVIEW_BY = { 4502: 'Quality reviewer' };

let state = {};
export const resetBidPack = () => {
  state = {};
};
const of = (id) => (state[id] ??= { phase: FIRST[id], rev: 9, case: 89, note: null, at: null });

/** What the pack moved on the work item: its tasks, and (for the lines this panel owns) its state and revision. */
export function packMoved(id) {
  if (!PACK_IDS.includes(id)) return undefined;
  const s = of(id);
  const tasks =
    s.phase === 'in_review'
      ? [{ id: 9500 + (id % 100), kind: 'document_review', role: REVIEW_BY[id] ?? 'Document reviewer', status: 'open', revision: 1, claimed_by_you: false, can_claim: false, can_decide: id !== 4503, verdicts: ['approve', 'return', 'reject'], url: `/api/v1/tasks/${9500 + (id % 100)}` }]
      : [];
  if (BID_ANSWERS_IDS.includes(id)) return s.phase === 'draft' ? undefined : { tasks };
  return { state: STATES[s.phase][0], status_label: STATES[s.phase][1], revision: s.rev, case_revision: s.case, tasks };
}

const decision = (s) =>
  ['approved', 'processing', 'sent'].includes(s.phase)
    ? { label: 'Approved', created_at: '2026-11-24T08:30:00Z', document_number: 2, note: null }
    : s.phase === 'returned' || s.phase === 'rejected'
      ? { label: s.phase === 'returned' ? 'Returned' : 'Refused', created_at: s.at ?? '2026-11-24T08:30:00Z', document_number: 2, note: s.note ?? 'The cover note needs the client’s name.' }
      : null;

function packRead(id) {
  const s = of(id);
  if (s.phase === 'none') return [404, BODIES[404]];
  return [200, { pack_id: PACK, number: 2, cover_note: 'Dear Lagoon Health team, our response and forms are attached.', document_version_id: id === 4509 ? null : VERSION, decision: decision(s), django_url: `/work/${id}/decision/` }];
}

function submissionRead(id) {
  const s = of(id);
  const sent = s.phase === 'sent';
  const file = s.phase === 'none' ? null : { id: 31, version_id: VERSION, sha256: 'b'.repeat(64), size: 6400000, findings: id === 4507 ? [FINDING.code] : [], checks: id === 4507 ? [FINDING] : [] };
  return [
    200,
    {
      expected_revision: s.rev,
      case_revision: s.case,
      version_id: VERSION,
      file,
      route: 'client_portal',
      job_id: s.phase === 'processing' || sent ? 4 : null,
      job_status: s.phase === 'processing' ? 'queued' : sent ? 'confirmed' : null,
      submission: sent ? { id: 3, submitted_at: '2026-11-24T08:50:00Z', receipt_ids: [4, 5], late: false } : null,
      sections: ['executive_summary', 'scope', 'commercial_terms', 'timeline'].map((name) => ({ name })),
      sample: true,
      approval_recorded: ['approved', 'processing', 'sent'].includes(s.phase),
    },
  ];
}

export function packReads(id, route, persona) {
  if (persona === 'none' || !PACK_IDS.includes(id)) return [404, BODIES[404]];
  if (route === '/bid-pack') return packRead(id);
  if (BID_ANSWERS_IDS.includes(id)) return [404, BODIES[404]];
  return submissionRead(id);
}

const bad = (message, name) => [422, { code: 'invalid', message, fields: [{ name, message }] }];

/** The three writes. `item` is the work item as served now (its revision and case revision are what a write must carry). */
export function packWrite(id, route, scenario, csrfOk, rawBytes, item) {
  if (!PACK_IDS.includes(id) || !item) return [404, BODIES[404]];
  if (scenario === 'w403csrf' || !csrfOk) return [403, { code: 'csrf_failed', message: 'Your session check failed. Reload and try again.' }];
  let body;
  try {
    body = JSON.parse(Buffer.from(rawBytes ?? []).toString('utf8') || '{}');
  } catch {
    return [400, BODIES[400]];
  }
  const s = of(id);
  if (body.expected_revision !== item.revision || body.case_revision !== item.case_revision) return [409, BODIES[409]];
  if (scenario === 'w409') {
    s.rev += 2;
    return [409, BODIES[409]];
  }
  if (scenario === 'w403') return [403, { code: 'forbidden', message: 'You can’t do this for this pack.' }];
  const status = Number(scenario);
  if (BODIES[status]) return [status, BODIES[status]];
  const moveOn = (phase) => {
    s.phase = phase;
    s.rev = item.revision + 1;
    s.case = item.case_revision + 1;
    if (BID_ANSWERS_IDS.includes(id)) bidBump(id);
  };
  let review = null;
  if (route === '/bid-pack/review-request') {
    if (body.pack_id !== PACK || body.version_id !== VERSION || id === 4509) return bad('Choose the exact current prepared pack and document version for review.', 'version_id');
    if (s.phase !== 'draft') return bad('Review was already requested for this pack.', 'pack_id');
    if (scenario === 'w422') return bad('The pack was not accepted.', 'pack_id');
    if (scenario === 'wdrop0') return ['drop'];
    moveOn('in_review');
  } else if (route === '/reviews') {
    if (body.kind !== 'bid' || body.subject !== 'document') return [404, BODIES[404]];
    if (s.phase !== 'in_review' || id === 4503) return [403, { code: 'forbidden', message: 'This review is not yours to decide.' }];
    if (body.target_id !== VERSION || typeof body.role !== 'string' || body.role === '' || body.evidence_id !== null || !['approve', 'return', 'reject'].includes(body.verdict) || typeof body.note !== 'string') return bad('Review the exact response document.', 'target_id');
    if (scenario === 'w422') return bad('The review was not accepted.', 'note');
    if (body.verdict !== 'approve' && body.note.trim() === '') return bad('Say why you are returning this pack.', 'note');
    if (scenario === 'wdrop0') return ['drop'];
    s.note = body.note || null;
    s.at = NOW;
    moveOn(body.verdict === 'approve' ? 'approved' : body.verdict === 'return' ? 'returned' : 'rejected');
    review = 8100;
  } else if (route === '/bid-submission') {
    if (body.version_id !== VERSION || s.phase !== 'approved') return bad('Approve the exact current pack before sending it.', 'version_id');
    if (id === 4507) return bad('Fix the file checks before sending.', 'version_id');
    if (scenario === 'w422') return bad('The submission was not accepted.', 'version_id');
    if (scenario === 'wdrop0') return ['drop'];
    moveOn('processing');
  } else return [404, BODIES[404]];
  if (scenario === 'wdrop') return ['drop'];
  const result = { work_id: id, state: STATES[s.phase][0], revision: s.rev };
  return [route === '/bid-submission' ? 202 : 200, review ? { ...result, review_id: review } : result];
}
