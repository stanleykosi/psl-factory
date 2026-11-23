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
