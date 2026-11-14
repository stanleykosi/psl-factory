// E-PROJECTS and E-PROJECT in the contract mock. The list honours q, cursor and limit over the per-persona rows in
// fixtures/projects/list.json; a journey comes from fixtures/projects/<case_id>.json (fixtures/E-PROJECT.json for ids
// not in the list). P-0099 is the reserved no-access id. Sample data only; no business rules.
import { readdirSync, readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

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
  if (!LIMITS.includes(limit) || offset === null || q === '') return { status: 404, body: INVALID_QUERY };

  const needle = q?.toLowerCase();
  const items = list.rows
    .filter((row) => row.personas.includes(persona))
    .map((row) => row.item)
    .filter((item) => !needle || item.title.toLowerCase().includes(needle));
  const body = { items: items.slice(offset, offset + limit), as_of: list.as_of };
  if (offset + limit < items.length) body.next_cursor = `o${offset + limit}`;
  return { status: 200, body };
}

function journey(url, persona) {
  const caseId = decodeId(url.pathname.split('/')[4] ?? '');
  if (caseId === NO_ACCESS_CASE_ID) return { status: 404, body: NOT_FOUND };
  const row = list.rows.find((r) => r.item.case_id === caseId);
  if (!row) return { status: 200, body: fallback };
  if (!row.personas.includes(persona)) return { status: 404, body: NOT_FOUND };
  return { status: 200, body: journeys[caseId] ?? fallback };
}

export function projects({ operationId, url, persona }) {
  return operationId === 'E-PROJECTS' ? projectList(url, persona) : journey(url, persona);
}
