// F-78: the live milestone completion (SCR-19) in the contract mock: the options read (GET /projects/{case_id}/milestones/completions,
// with ?name= and ?page=) and the write (POST, one of two body shapes). A recorded completion is kept by id so the re-read
// (GET /projects/{case_id}/milestones/{id}) answers it. Cookie psl_mock_complete picks the case: ok (default) | baseline |
// proofreq | inuse | norole | paged | conflict | uncertain | uncertain-saved | reread-fail | forbidden | notfound. The mock never
// computes a value and starts no invoice. A project the persona cannot see answers 404. Sample data only.
import { idOf } from './projects.mjs';

const PATH = /^\/api\/v1\/projects\/([^/]+)\/milestones\/completions$/;
const READ = /^\/api\/v1\/projects\/([^/]+)\/milestones\/(\d+)$/;
const NOT_FOUND = { code: 'not_found', message: 'We could not find that record.' };
const FORBIDDEN = { code: 'forbidden', message: 'You do not have access.' };
const STALE = { code: 'stale_revision', message: 'This project changed. Reload and try again.' };
const SERVER_ERROR = { code: 'server_error', message: 'Something went wrong on our side.' };
const PROOFS = [
  { id: 31, label: 'Completion evidence · version 2' },
  { id: 29, label: 'Completion evidence · version 1' },
];
const PAGE_2 = [
  { id: 29, label: 'Completion evidence · version 1' },
  { id: 27, label: 'Completion evidence · version 0' },
];

let recorded = new Map(); // `${caseId}|${name}` -> completion
let byId = new Map();
let nextId = 412;
let conflicted = false;
let rereadFailed = false;

export function resetMilestoneComplete() {
  recorded = new Map();
  byId = new Map();
  nextId = 412;
  conflicted = false;
  rereadFailed = false;
}

export const isCompletionsPath = (pathname) => PATH.test(pathname);

/** GET /projects/{case_id}/milestones/{id} for a completion recorded here; undefined for any other id. */
export function recordedRead(pathname, cookies) {
  const found = READ.exec(pathname);
  if (!found || !byId.has(`${idOf(found[1])}|${found[2]}`)) return undefined;
  if (cookies.psl_mock_complete === 'reread-fail' && !rereadFailed) {
    rereadFailed = true;
    return { status: 503, body: SERVER_ERROR };
  }
  const c = byId.get(`${idOf(found[1])}|${found[2]}`);
  return { status: 200, body: { id: c.id, name: c.name, completed_at: c.completed_at, evidence_id: c.evidence_id, proof_version: c.proof_version } };
}

function options(scenario, caseId, name, page) {
  const done = name !== null && recorded.has(`${caseId}|${name}`);
  const base = { revision: scenario === 'conflict' && conflicted ? 6 : 5, proofs: PROOFS, next_page: null, can_complete: true, can_attach_pdf: true, hold: null };
  if (scenario === 'baseline') return { ...base, proofs: [], can_complete: false, can_attach_pdf: false, hold: 'baseline_required' };
  if (scenario === 'proofreq') return { ...base, proofs: [], can_complete: false, can_attach_pdf: false, hold: 'proof_required' };
  if (scenario === 'norole') return { ...base, can_complete: false };
  if (scenario === 'inuse' && name !== null) return { ...base, can_complete: false, hold: 'name_in_use' };
  if (done) return { ...base, can_complete: false, hold: 'name_in_use' };
  if (scenario === 'paged') return page > 1 ? { ...base, proofs: PAGE_2, next_page: null } : { ...base, next_page: 2 };
  return base;
}

/** { status, body } for a read or write of the completions path; the caller has checked the CSRF token on a write. */
export function milestoneComplete({ method, url, raw, persona, cookies = {}, canSee }) {
  const caseId = idOf(decodeURIComponent(PATH.exec(url.pathname)[1]));
  const scenario = cookies.psl_mock_complete ?? 'ok';
  if (!canSee(caseId, persona) || scenario === 'notfound') return { status: 404, body: NOT_FOUND };
  if (scenario === 'forbidden') return { status: 403, body: FORBIDDEN };
  if (method === 'get') {
    const name = url.searchParams.get('name');
    const page = Number(url.searchParams.get('page') ?? 1);
    return { status: 200, body: options(scenario, caseId, name, page) };
  }
  let body;
  try {
    body = JSON.parse(raw);
  } catch {
    return { status: 400, body: { code: 'bad_request', message: 'Not JSON.' } };
  }
  const name = typeof body?.name === 'string' ? body.name : '';
  const current = options(scenario, caseId, name, 1);
  if (name.length < 1 || name.length > 200) return { status: 422, body: { code: 'invalid', message: 'Check the fields.', fields: [{ name: 'name', message: 'Enter the milestone name.' }] } };
  if (scenario === 'conflict' && !conflicted) {
    conflicted = true;
    return { status: 409, body: STALE };
  }
  if (body.revision !== current.revision) return { status: 409, body: STALE };
  const withProof = Number.isInteger(body.evidence_id);
  const withPdf = Number.isInteger(body.upload_id) && body.checked === true;
  if (withProof === withPdf || (withProof && 'upload_id' in body) || (withPdf && 'evidence_id' in body)) return { status: 422, body: { code: 'invalid', message: 'Send one proof.', fields: [] } };
  if (!current.can_complete) return { status: 403, body: FORBIDDEN };
  if (scenario === 'uncertain') return { status: 503, body: SERVER_ERROR };
  const completion = { id: nextId++, revision: current.revision + 1, name, evidence_id: withProof ? body.evidence_id : 7900, completed_at: '2026-11-23T10:15:00Z', proof_version: 2 };
  recorded.set(`${caseId}|${name}`, completion);
  byId.set(`${caseId}|${completion.id}`, completion);
  if (scenario === 'uncertain-saved') return { status: 503, body: SERVER_ERROR };
  return { status: 201, body: { id: completion.id, revision: completion.revision, name, evidence_id: completion.evidence_id } };
}
