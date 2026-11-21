// E-PROJECTS and E-PROJECT in the contract mock. The list honours q, cursor and limit over the per-persona rows in
// fixtures/projects/list.json; a journey comes from fixtures/projects/<case_id>.json (fixtures/E-PROJECT.json for ids
// not in the list). P-0099 is the reserved no-access id. Sample data only; no business rules.
//
// The SCR-22 and SCR-07 board values are in the loaded contract (architecture v7, D-PROJECTS-VIEW), so bodies are
// served and checked in full. `status` (active | closed | all) is the E-PROJECTS query parameter for the Active /
// Closed / All I can see tabs; without it the mock answers Active, the tab the page opens on, and `total` counts the
// rows that match the status and q.
import { readdirSync, readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

import { demoProject, demoProjects, demoVisible, journey as demoJourney, listItem as demoListItem } from './demo-projects.mjs';

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
const LIMITS = [10, 20, 50];
const STATUSES = ['active', 'closed', 'all'];

const INVALID_QUERY = { code: 'invalid_query', message: 'We could not read that list request.' };
const NOT_FOUND = { code: 'not_found', message: 'We could not find that record.' };

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
  const limit = params.has('limit') ? Number(params.get('limit')) : 20;
  const offset = params.has('cursor') ? decodeCursor(params.get('cursor')) : 0;
  const q = params.get('q');
  const status = params.get('status') ?? 'active';
  if (!LIMITS.includes(limit) || offset === null || q === '' || !STATUSES.includes(status)) {
    return { status: 404, body: INVALID_QUERY };
  }

  const needle = q?.toLowerCase();
  // D-164: the projects won RFPs created in the live demo come first, newest first
  const demo = demoProjects().filter(() => demoVisible(persona)).map((p) => ({ personas: [persona], status: 'active', item: demoListItem(p) })).reverse();
  const visible = [...demo, ...list.rows.filter((row) => row.personas.includes(persona))];
  const items = visible
    .filter((row) => status === 'all' || row.status === status)
    .map((row) => row.item)
    .filter((item) => !needle || item.title.toLowerCase().includes(needle));
  const counts = {
    active: visible.filter((row) => row.status === 'active').length,
    closed: visible.filter((row) => row.status === 'closed').length,
    all: visible.length,
  };
  const body = { items: items.slice(offset, offset + limit), as_of: list.as_of, counts, total: items.length };
  if (offset + limit < items.length) body.next_cursor = `o${offset + limit}`;
  return { status: 200, body };
}

function journey(url, persona) {
  const caseId = decodeId(url.pathname.split('/')[4] ?? '');
  if (caseId === NO_ACCESS_CASE_ID) return { status: 404, body: NOT_FOUND };
  const won = demoProject(caseId);
  if (won) return demoVisible(persona) ? { status: 200, body: demoJourney(won) } : { status: 404, body: NOT_FOUND };
  const row = list.rows.find((r) => r.item.case_id === caseId);
  if (!row) return { status: 200, body: fallback };
  if (!row.personas.includes(persona)) return { status: 404, body: NOT_FOUND };
  return { status: 200, body: journeys[caseId] ?? fallback };
}

/** Whether the persona may see the case in the mock: not the no-access id, nor a listed case outside their rows (F-26). */
export function caseVisible(caseId, persona) {
  if (caseId === NO_ACCESS_CASE_ID) return false;
  if (demoProject(caseId)) return demoVisible(persona);
  const row = list.rows.find((r) => r.item.case_id === caseId);
  return !row || row.personas.includes(persona);
}

export function projects({ operationId, url, persona }) {
  return operationId === 'E-PROJECTS' ? projectList(url, persona) : journey(url, persona);
}
