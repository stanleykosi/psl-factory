// E-DOCUMENT for the review page (F-29, SCR-08) in the contract mock: the statement of work D-2901 at v1 and v2.
// The fields beyond the typed ones are PROPOSALS (mock/proposals/document-review.json, gaps G-SCR08-1..8). Cookie
// psl_mock_document picks the variant of v2: default | returned | returned-hidden | cannot-act | amount-unknown |
// no-review | no-sections | empty-sections | hostile. The review is the decision task on the work item named in
// `review`; once that item is served from its .approve or .return fixture (a decision was recorded) the document says
// so, so the page's re-read shows the result. Any other document answers undefined and the caller carries on. A
// project the persona cannot see answers 404 (list.json), as E-PROJECT does. The mock never computes a value.
// Sample data only.
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const readJson = (path) => JSON.parse(readFileSync(path, 'utf8'));
const list = readJson(join(here, 'fixtures', 'projects', 'list.json'));
const versions = { 1: readJson(join(here, 'fixtures', 'documents', 'D-2901.1.json')), 2: readJson(join(here, 'fixtures', 'documents', 'D-2901.2.json')) };

// F-38: the RFP submission pack D-3501, version 1 only, served as its fixture (no variants, no review).
const pack = readJson(join(here, 'fixtures', 'documents', 'D-3501.1.json'));

const NOT_FOUND = { code: 'not_found', message: 'We could not find that record.' };
const RETURNED = {
  by: 'Kemi Adebayo',
  role: 'PMO Lead',
  at: '2026-11-17T13:20:00Z',
  note: 'Section 4: confirm week 2 or week 3 with the client and match the minutes. Everything else is fine.',
};

/** The variant of v2 for a cookie value; the others read as default. */
function variant(doc, name) {
  const out = structuredClone(doc);
  switch (name) {
    case 'returned':
    case 'returned-hidden':
      out.status = 'Returned to PM';
      out.returned = name === 'returned' ? { ...RETURNED } : { by: RETURNED.by, role: RETURNED.role, at: RETURNED.at };
      break;
    case 'cannot-act':
      out.review = { ...out.review, work_id: 'W-2902', task_id: 'T-2902' };
      break;
    case 'amount-unknown':
      out.checks = out.checks.map((c) => (c.key === 'amounts' ? { key: c.key, label: c.label, status: 'unknown', detail: 'The costing figure is not available.' } : c));
      break;
    case 'no-review':
      out.review = { role_label: out.review.role_label };
      break;
    case 'no-sections':
      delete out.sections;
      break;
    case 'empty-sections':
      out.sections = [];
      break;
    case 'hostile':
      out.sections[0] = { key: 'scope', heading: 'Scope <b>bold</b>', text: 'Plain <script>alert(1)</script> text\n\nSecond <b>paragraph</b>', notes: [{ agent: 'tola', text: '<b>note</b> <script>x()</script>' }] };
      break;
    default:
  }
  return out;
}

/** GET /api/v1/documents/{document_id}/versions/{version}; undefined for a document this module does not own. */
export function documentRead({ url, persona, cookies = {}, work, overrides }) {
  const [, , , , rawId = '', , rawVersion = ''] = url.pathname.split('/');
  let id = rawId;
  try {
    id = decodeURIComponent(rawId);
  } catch {
    // keep the raw segment
  }
  // the pack is served to the people who can open its work item (W-3502); the persona with no sections open gets the same 404 as a missing one
  if (id === 'D-3501') return rawVersion === '1' && persona !== 'none' ? { status: 200, body: pack } : { status: 404, body: NOT_FOUND };
  if (id !== 'D-2901') return undefined;
  const base = versions[rawVersion];
  if (!base) return { status: 404, body: NOT_FOUND };
  const row = list.rows.find((r) => r.id === base.case_id);
  if (row && !row.personas.includes(persona)) return { status: 404, body: NOT_FOUND };
  if (rawVersion === '1') return { status: 200, body: base };

  const doc = variant(base, cookies.psl_mock_document);
  // A decision recorded on this review's work item (the mock's overrides map) shows in the document.
  const served = overrides.get(doc.review.work_id);
  if (served && doc.review.work_id === 'W-2901') {
    if (served === work['W-2901.approve']) doc.status = 'Approved';
    if (served === work['W-2901.return'] && !doc.returned) {
      doc.status = 'Returned to PM';
      doc.returned = { ...RETURNED };
    }
  }
  return { status: 200, body: doc };
}

// F-72 (SCR-08, live contract 1.22.0): the document-review reads and the decision, in the live shape. The version id is
// an integer: 2901 is v2 of the statement of work on P-0101, 2900 is v1 (not current), 2999 answers 404 for everyone.
// Cookie psl_mock_docreview picks the scenario: decidable (default) | return-only | with-reject | blocked | returned |
// empty-sections | hostile | no-publication (the publication read answers 500) | stale (the write answers 409 and the
// revision moves on) | unavailable (the write answers 422 action_unavailable and the document becomes blocked) |
// note-refused (422 on the note field) | forbidden (the write answers 403) | server-error (the write answers 500).
// A recorded decision empties `decisions`, moves the revision on and sets `review_status`, so the next read shows it.
// The mock never computes a value; sample data only.
const liveDoc = readJson(join(here, 'fixtures', 'documents', 'review-2901.json'));
const livePublication = readJson(join(here, 'fixtures', 'documents', 'review-2901.publication.json'));
const LIVE_ID = /^\/api\/v1\/projects\/(P-\d+)\/document-reviews\/([^/]+?)(\/publication)?$/;
const DECIDED = { approve: 'Approved', return: 'Returned to PM' };
const BLOCKED = ['Section Fees is empty.'];

const recorded = new Map();
const moved = new Set();
export function resetDocumentReviews() {
  recorded.clear();
  moved.clear();
}

const reply = (status, body) => ({ status, body });
const refusal = (status, code, message, fields) => reply(status, fields ? { code, message, fields } : { code, message });

/** The live state of a version for a scenario, with any decision recorded since the last reset. */
function liveState(id, scenario) {
  const doc = structuredClone(liveDoc);
  const pub = structuredClone(livePublication);
  if (id === '2900') {
    Object.assign(doc, { version: 1, revision: 3, current: false, decisions: [] });
    Object.assign(pub, { version_id: 2900, revision: 3, current: false, review_status: 'Superseded by v2' });
  }
  if (id === '2901') {
    switch (scenario) {
      case 'return-only':
        doc.decisions = ['return'];
        break;
      case 'with-reject':
        doc.decisions = ['approve', 'return', 'reject'];
        break;
      case 'blocked':
        Object.assign(doc, { decisions: [] });
        Object.assign(pub, { findings: BLOCKED, review_status: null });
        break;
      case 'returned':
        doc.decisions = [];
        pub.review_status = 'Returned to PM';
        break;
      case 'empty-sections':
        doc.preview = [];
        break;
      case 'hostile':
        doc.preview[0] = { field: 'Scope <b>bold</b>', text: 'Plain <script>alert(1)</script> text\n\nSecond <b>paragraph</b>' };
        break;
      default:
    }
  }
  if (moved.has(id)) {
    doc.revision += 1;
    pub.revision += 1;
  }
  const done = recorded.get(id);
  if (done) {
    doc.decisions = [];
    doc.revision = done.revision;
    pub.revision = done.revision;
    pub.review_status = done.status;
    pub.findings = done.findings ?? pub.findings;
  }
  return { doc, pub };
}

/** The live document-review path in the mock; the route is answered by liveDocumentReview. */
export const isLiveDocumentPath = (pathname) => LIVE_ID.test(pathname);

/** GET .../document-reviews/{n}, GET .../publication and POST .../document-reviews/{n}. */
export function liveDocumentReview({ method, url, raw, persona, cookies = {}, canSee }) {
  const [, caseId, id, publication] = LIVE_ID.exec(url.pathname);
  const scenario = cookies.psl_mock_docreview;
  if (!/^[1-9]\d{0,18}$/.test(id)) return refusal(404, 'not_found', 'We could not find that record.');
  if (!['2900', '2901'].includes(id) || caseId !== 'P-0101' || !canSee(caseId, persona)) return refusal(404, 'not_found', 'We could not find that record.');
  const { doc, pub } = liveState(id, scenario);
  if (method === 'get') {
    if (publication) return scenario === 'no-publication' ? refusal(500, 'server_error', 'Something went wrong.') : reply(200, pub);
    return reply(200, doc);
  }
  if (publication) return refusal(405, 'method_not_allowed', 'Not available in the mock.');
  let body;
  try {
    body = JSON.parse(raw);
  } catch {
    return refusal(400, 'bad_request', 'We could not read that request.');
  }
  const keys = Object.keys(body ?? {}).sort().join(',');
  const verdict = body?.verdict;
  if (keys !== 'delegated,expected_revision,note,verdict' || !['approve', 'return', 'reject'].includes(verdict) || !Number.isInteger(body.expected_revision) || typeof body.delegated !== 'boolean' || typeof body.note !== 'string') {
    return refusal(422, 'invalid', 'Check the highlighted fields and try again.');
  }
  if (body.note.trim() === '' || body.note.length > 4000) return refusal(422, 'invalid', 'Check the note and try again.', [{ name: 'note', message: 'Add a note of 1 to 4000 characters.' }]);
  if (scenario === 'forbidden') return refusal(403, 'forbidden', 'Your role does not allow this.');
  if (scenario === 'server-error') return refusal(500, 'server_error', 'Something went wrong.');
  if (scenario === 'note-refused') return refusal(422, 'invalid', 'Check the note and try again.', [{ name: 'note', message: 'That note can’t be used. Say what to change.' }]);
  if (scenario === 'stale' && !moved.has(id)) {
    moved.add(id);
    return refusal(409, 'stale_revision', 'Someone changed this since you opened it.');
  }
  if (body.expected_revision !== doc.revision) return refusal(409, 'stale_revision', 'Someone changed this since you opened it.');
  if (scenario === 'unavailable') {
    recorded.set(id, { revision: doc.revision + 1, status: null, findings: BLOCKED });
    return refusal(422, 'action_unavailable', 'This version can’t be decided yet: a section is empty.');
  }
  if (!doc.decisions.includes(verdict)) return refusal(422, 'action_unavailable', 'That decision is not open on this version.');
  recorded.set(id, { revision: doc.revision + 1, status: DECIDED[verdict] ?? verdict });
  return reply(200, { review_id: 55, verdict });
}
