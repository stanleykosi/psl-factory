// E-PROJECT-TAB in the contract mock (F-25, Documents F-29): the Milestones, Documents, Registers and Actions rows of a project, from
// fixtures/projects/tabs/<case_id>.<tab>.json. Visibility follows fixtures/projects/list.json as E-PROJECT does:
// P-0099 and a project the persona cannot see answer 404; P-0103 answers 403 for every tab. Money goes to money.mjs (F-26). `register` (Registers only), `q`, `cursor` (o<n>) and `limit` (10, 20, 50) are honoured;
// anything else unreadable answers 404 invalid_query. Cookie psl_mock_milestones=changed serves the milestones file with
// a change on Go-live. F-75: registers and actions answer the live sections shape (sectionsTab). The mock never adds or computes a value: it slices the rows a fixture holds. Sample data only.
import { readdirSync, readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

import { demoProject, demoVisible } from './demo-projects.mjs';
import { NO_ACCESS_CASE_ID, uuidOf } from './projects.mjs';

const here = dirname(fileURLToPath(import.meta.url));
const dir = join(here, 'fixtures', 'projects', 'tabs');
const readJson = (path) => JSON.parse(readFileSync(path, 'utf8'));
const list = readJson(join(here, 'fixtures', 'projects', 'list.json'));
const files = Object.fromEntries(readdirSync(dir).filter((name) => name.endsWith('.json')).map((name) => [name.slice(0, -5), readJson(join(dir, name))]));

export const FORBIDDEN_CASE_ID = 'P-0103';
const LISTED_TABS = ['milestones', 'documents', 'registers', 'actions']; // money is answered by money.mjs before this handler (F-26)
const LIMITS = [10, 20, 50];
const REGISTERS = ['issues', 'changes', 'emergencies', 'rfps'];
const EMPTY_CASE_ID = 'P-0106';
const SECTION_PAGE = 25;
const MAX_Q = 120;
const NO_ISSUE_READ_PERSONA = 'pmo_lead'; // scripted: this persona cannot read Issues or Escalations, so their sections are not returned
const INACTIVE_CODES = ['completed', 'cancelled', 'paused'];

const INVALID_FILTER = { code: 'invalid_filter', message: 'We could not read that list request.' };
const INVALID_QUERY = { code: 'invalid_query', message: 'We could not read that list request.' };
const NOT_FOUND = { code: 'not_found', message: 'We could not find that record.' };
const FORBIDDEN = { code: 'forbidden', message: 'Your role does not allow this.' };

const decodeId = (value) => {
  try {
    return decodeURIComponent(value);
  } catch {
    return value;
  }
};

const decodeCursor = (cursor) => {
  const match = /^o(\d+)$/.exec(cursor);
  return match ? Number(match[1]) : null;
};

/** The fixture for a project and tab; a project with no fixtures of its own answers like P-0106 (empty). */
function fixtureFor(caseId, tab, cookies) {
  const changed = tab === 'milestones' && cookies.psl_mock_milestones === 'changed' ? files[`${caseId}.milestones.changed`] : undefined;
  return changed ?? files[`${caseId}.${tab}`] ?? files[`${EMPTY_CASE_ID}.${tab}`];
}

/**
 * F-75: the live Registers and Actions read. A fixture holds every row of each section; this slices 25 a section by one shared
 * `page` (a section with fewer pages answers its last page again, with its own `page`), filters by `q` on title, reference and
 * detail, and gives `total` for the rows matching `q`. Actions `counts` are over the matching rows (overdue: a due date before
 * `as_of` on a state that is not completed, cancelled or paused; unassigned: "Owner needed" on an active state); other sections
 * `counts: null`. `state`, `owner` and `severity` are ignored; an unreadable `page` or `q` answers 422 invalid_filter.
 */
function sectionsTab(caseId, tab, params, persona, cookies) {
  const pageText = params.get('page');
  const page = pageText === null ? 1 : Number(pageText);
  const q = params.get('q');
  if (!Number.isInteger(page) || page < 1 || (pageText !== null && !/^\d+$/.test(pageText)) || (q !== null && (q === '' || q.length > MAX_Q))) return { status: 422, body: INVALID_FILTER };

  const fixture = fixtureFor(caseId, tab, cookies);
  const needle = q?.toLowerCase();
  const asOf = Date.parse(fixture.as_of);
  const active = (item) => !INACTIVE_CODES.includes(item.state_code);
  const sections = fixture.sections
    .filter((section) => persona !== NO_ISSUE_READ_PERSONA || !['issues', 'escalations'].includes(section.key))
    .map((section) => {
      const matching = section.items.filter((item) => !needle || [item.title, item.reference, item.detail].some((text) => text?.toLowerCase().includes(needle)));
      const pages = Math.max(1, Math.ceil(matching.length / SECTION_PAGE));
      const answered = Math.min(page, pages);
      const counts =
        tab === 'actions'
          ? {
              total: matching.length,
              overdue: matching.filter((item) => item.due && Date.parse(item.due) < asOf && active(item)).length,
              unassigned: matching.filter((item) => item.detail === 'Owner needed' && active(item)).length,
            }
          : null;
      return {
        ...section,
        page: answered,
        has_more: answered < pages,
        total: matching.length,
        counts,
        items: matching.slice((answered - 1) * SECTION_PAGE, answered * SECTION_PAGE),
      };
    });
  return { status: 200, body: { case_id: uuidOf(caseId), tab, sections, as_of: fixture.as_of } };
}

export function projectTab({ url, persona, cookies = {} }) {
  const [, , , , rawId = '', tab = ''] = url.pathname.split('/');
  const caseId = decodeId(rawId);
  if (!LISTED_TABS.includes(tab)) return { status: 404, body: NOT_FOUND };

  const row = list.rows.find((r) => r.id === caseId);
  if (caseId === NO_ACCESS_CASE_ID || (row && !row.personas.includes(persona)) || (demoProject(caseId) && !demoVisible(persona))) return { status: 404, body: NOT_FOUND };
  if (caseId === FORBIDDEN_CASE_ID) return { status: 403, body: FORBIDDEN };
  if (tab === 'registers' || tab === 'actions') return sectionsTab(caseId, tab, url.searchParams, persona, cookies);

  const params = url.searchParams;
  const limit = params.has('limit') ? Number(params.get('limit')) : 20;
  const offset = params.has('cursor') ? decodeCursor(params.get('cursor')) : 0;
  const register = params.get('register');
  const q = params.get('q');
  if (!LIMITS.includes(limit) || offset === null || q === '' || (register !== null && (tab !== 'registers' || !REGISTERS.includes(register)))) {
    return { status: 404, body: INVALID_QUERY };
  }

  const fixture = fixtureFor(caseId, tab, cookies);
  const needle = q?.toLowerCase();
  const rows = (fixture[tab] ?? [])
    .filter((item) => register === null || item.register === register)
    .filter((item) => !needle || [item.title ?? item.name, item.reference].some((text) => text?.toLowerCase().includes(needle)));
  if (offset > rows.length) return { status: 404, body: INVALID_QUERY };

  const page = rows.slice(offset, offset + limit);
  const body = { items: page, as_of: fixture.as_of, [tab]: page };
  if (fixture.summary) body.summary = fixture.summary;
  if (offset + limit < rows.length) body.next_cursor = `o${offset + limit}`;
  return { status: 200, body };
}
