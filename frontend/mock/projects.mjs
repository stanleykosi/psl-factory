// GET /api/v1/projects and GET /api/v1/projects/{case_id} in the contract mock, in the live shape (live contract 1.22.0,
// operations workspaces_projects and workspaces_project). The list honours status (default all, as live), q and cursor over
// the per-persona rows in fixtures/projects/list.json; a journey comes from fixtures/projects/<P-nnnn>.json, 20 work items a
// page (fixtures/E-PROJECT.json for ids not in the list). Every case_id is a UUID; the P-nnnn form of the same id is
// accepted too, because the tab and money fixtures are keyed by it (idOf, normaliseProjectPath). P-0099 is the reserved
// no-access id. Sample data only; no business rules.
import { readdirSync, readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

import { demoProject, demoProjects, demoVisible, journey as demoJourney, listItem as demoListItem, uuidOf } from './demo-projects.mjs';

export { uuidOf };

const here = dirname(fileURLToPath(import.meta.url));
const dir = join(here, 'fixtures', 'projects');
const readJson = (path) => JSON.parse(readFileSync(path, 'utf8'));
const list = readJson(join(dir, 'list.json'));
const fallback = readJson(join(here, 'fixtures', 'E-PROJECT.json'));
const journeys = Object.fromEntries(
  readdirSync(dir)
    .filter((name) => /^P-\d+\.json$/.test(name))
    .map((name) => [name.slice(0, -5), readJson(join(dir, name))]),
);

export const NO_ACCESS_CASE_ID = 'P-0099';
const STATUSES = ['active', 'closed', 'all'];
const PAGE_SIZE = 20;
const MAX_Q = 120;

const INVALID_FILTER = { code: 'invalid_filter', message: 'We could not read that list request.' };
const NOT_FOUND = { code: 'not_found', message: 'We could not find that record.' };

const UUID_FORM = /^00000000-0000-4000-8000-(\d{12})$/;

/** The P-nnnn form of a project id given as either form; other text is returned as it is. */
export function idOf(value) {
  const match = UUID_FORM.exec(value);
  return match ? `P-${match[1].slice(-4)}` : value;
}

/** A /api/v1/projects/<id>... path with the project id in its P-nnnn form, for the tab and money fixtures. */
export function normaliseProjectPath(pathname) {
  return pathname.replace(/^(\/api\/v1\/projects\/)([^/]+)/, (_, head, id) => head + idOf(decodeId(id)));
}

function decodeCursor(cursor) {
  const match = /^o(\d+)$/.exec(cursor);
  return match ? Number(match[1]) : null;
}

function decodeId(value) {
  try {
    return decodeURIComponent(value);
  } catch {
    return value;
  }
}

function projectList(url, persona) {
  const params = url.searchParams;
  const offset = params.has('cursor') ? decodeCursor(params.get('cursor')) : 0;
  const q = params.get('q');
  const status = params.get('status') ?? 'all';
  if (offset === null || q === '' || (q !== null && q.length > MAX_Q) || !STATUSES.includes(status)) {
    return { status: 422, body: INVALID_FILTER };
  }

  const needle = q?.toLowerCase();
  // D-164: the projects won RFPs created in the live demo come first, newest first
  const demo = demoProjects().filter(() => demoVisible(persona)).map((p) => ({ personas: [persona], status: 'active', item: demoListItem(p) })).reverse();
  const visible = [...demo, ...list.rows.filter((row) => row.personas.includes(persona))];
  const items = visible
    .filter((row) => status === 'all' || row.status === status)
    .map((row) => row.item)
    .filter((item) => !needle || item.title.toLowerCase().includes(needle));
  const page = items.slice(offset, offset + PAGE_SIZE);
  const nextCursor = offset + PAGE_SIZE < items.length ? `o${offset + PAGE_SIZE}` : null;
  const totals = { all: visible.length, active: visible.filter((row) => row.status === 'active').length, closed: visible.filter((row) => row.status === 'closed').length };
  return { status: 200, body: { items: page, next_cursor: nextCursor, as_of: list.as_of, totals } };
}

/** One page of a journey body: the fixture holds every work item; 20 go out a page with page and next_page. */
function pageOf(body, url) {
  const page = Number(url.searchParams.get('page') ?? 1);
  if (!Number.isInteger(page) || page < 1) return { status: 422, body: INVALID_FILTER };
  const start = (page - 1) * PAGE_SIZE;
  if (start > 0 && start >= body.items.length) return { status: 404, body: NOT_FOUND };
  return { status: 200, body: { ...body, items: body.items.slice(start, start + PAGE_SIZE), page, next_page: start + PAGE_SIZE < body.items.length ? page + 1 : null } };
}

function journey(url, persona) {
  const caseId = idOf(decodeId(url.pathname.split('/')[4] ?? ''));
  if (caseId === NO_ACCESS_CASE_ID) return { status: 404, body: NOT_FOUND };
  const won = demoProject(caseId);
  if (won) return demoVisible(persona) ? pageOf(demoJourney(won), url) : { status: 404, body: NOT_FOUND };
  const row = list.rows.find((r) => r.id === caseId);
  if (!row) return /^P-\d{4}$/.test(caseId) ? pageOf({ ...fallback, case_id: uuidOf(caseId) }, url) : { status: 404, body: NOT_FOUND };
  if (!row.personas.includes(persona)) return { status: 404, body: NOT_FOUND };
  return pageOf(journeys[caseId] ?? { ...fallback, case_id: uuidOf(caseId) }, url);
}

/** Whether the persona may see the case in the mock: not the no-access id, nor a listed case outside their rows (F-26). */
export function caseVisible(caseId, persona) {
  caseId = idOf(caseId);
  if (caseId === NO_ACCESS_CASE_ID) return false;
  if (demoProject(caseId)) return demoVisible(persona);
  const row = list.rows.find((r) => r.id === caseId);
  return !row || row.personas.includes(persona);
}

export function projects({ operationId, url, persona }) {
  return operationId === 'E-PROJECTS' ? projectList(url, persona) : journey(url, persona);
}
