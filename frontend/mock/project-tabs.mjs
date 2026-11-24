// E-PROJECT-TAB in the contract mock (F-25, Documents F-29): the Milestones, Documents, Registers and Actions rows of a project, from
// fixtures/projects/tabs/<case_id>.<tab>.json. Visibility follows fixtures/projects/list.json as E-PROJECT does:
// P-0099 and a project the persona cannot see answer 404; P-0103 answers 403 for every tab. Money goes to money.mjs (F-26). `register` (Registers only), `q`, `cursor` (o<n>) and `limit` (10, 20, 50) are honoured;
// anything else unreadable answers 404 invalid_query. F-71: milestones is the live shape (one section of recorded completions, `page`, 25 a page;
// P-0105 answers 404 for it) and the changed state lives in money.mjs. The mock never adds or computes a value: it slices the rows a fixture holds. Sample data only.
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
const MILESTONES_REFUSED_CASE_ID = 'P-0105'; // scripted: the milestones read answers 404 while its money reads
const COMPLETIONS_PAGE = 25;
const LISTED_TABS = ['milestones', 'documents', 'registers', 'actions']; // money is answered by money.mjs before this handler (F-26)
const LIMITS = [10, 20, 50];
const REGISTERS = ['issues', 'changes', 'emergencies', 'rfps'];
const EMPTY_CASE_ID = 'P-0106';

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
function fixtureFor(caseId, tab) {
  return files[`${caseId}.${tab}`] ?? files[`${EMPTY_CASE_ID}.${tab}`];
}

/** F-71: the live milestones read, one section of recorded completions, 25 a page (`page`); other tabs keep the v7 shape. */
function milestonesTab(caseId, params) {
  const fixture = files[`${caseId}.milestones`] ?? files[`${EMPTY_CASE_ID}.milestones`];
  const page = params.has('page') ? Number(params.get('page')) : 1;
  const all = fixture.sections[0].items;
  if (!Number.isInteger(page) || page < 1 || (page > 1 && (page - 1) * COMPLETIONS_PAGE >= all.length)) return { status: 404, body: INVALID_QUERY };
  const items = all.slice((page - 1) * COMPLETIONS_PAGE, page * COMPLETIONS_PAGE);
  const section = { ...fixture.sections[0], items, page, has_more: page * COMPLETIONS_PAGE < all.length, total: all.length };
  return { status: 200, body: { ...fixture, case_id: uuidOf(caseId), sections: [section] } };
}

export function projectTab({ url, persona }) {
  const [, , , , rawId = '', tab = ''] = url.pathname.split('/');
  const caseId = decodeId(rawId);
  if (!LISTED_TABS.includes(tab)) return { status: 404, body: NOT_FOUND };

  const row = list.rows.find((r) => r.id === caseId);
  if (caseId === NO_ACCESS_CASE_ID || (row && !row.personas.includes(persona)) || (demoProject(caseId) && !demoVisible(persona))) return { status: 404, body: NOT_FOUND };
  if (caseId === FORBIDDEN_CASE_ID) return { status: 403, body: FORBIDDEN };
  if (tab === 'milestones') return caseId === MILESTONES_REFUSED_CASE_ID ? { status: 404, body: NOT_FOUND } : milestonesTab(caseId, url.searchParams);

  const params = url.searchParams;
  const limit = params.has('limit') ? Number(params.get('limit')) : 20;
  const offset = params.has('cursor') ? decodeCursor(params.get('cursor')) : 0;
  const register = params.get('register');
  const q = params.get('q');
  if (!LIMITS.includes(limit) || offset === null || q === '' || (register !== null && (tab !== 'registers' || !REGISTERS.includes(register)))) {
    return { status: 404, body: INVALID_QUERY };
  }

  const fixture = fixtureFor(caseId, tab);
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
