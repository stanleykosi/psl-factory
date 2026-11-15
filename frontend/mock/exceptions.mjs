// E-EXCEPTIONS in the contract mock: pages the rows of fixtures/E-EXCEPTIONS.json in file order by limit and an
// "o:<offset>" cursor. "Leads; filtered by grants": the pm persona is refused, none sees an empty list (C8).
// Cookie psl_mock_exceptions=empty gives an empty list to anyone allowed to see it; psl_mock_exceptions=board serves
// the four sample rows drawn on the SCR-10 phone board (fixtures/E-EXCEPTIONS.board.json), for the design-fidelity check.
// Sample data only.
//
// Engineering proposal (F-06, for the architecture; not in v4/v5): the query takes optional `q` (search over title,
// reference, what's being done and who acts) and `what` (one kind); the body carries `open_count` (all rows matching
// the search and filter, across pages) and each row an optional `ref` (the work's reference). `contractBody` strips
// the proposal fields so tests can check the rest against the contract schema.
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const read = (name) => JSON.parse(readFileSync(join(here, 'fixtures', name), 'utf8'));
const fixture = read('E-EXCEPTIONS.json');
const boardFixture = read('E-EXCEPTIONS.board.json');

const LIMITS = [10, 20, 50];
const KINDS = ['effect_uncertain', 'owner_needed', 'setup_needed', 'blocked', 'followup_needed'];
const NOT_A_LEAD = { code: 'forbidden', message: 'Only Leads can see all exceptions.' };

/** The body without the proposal fields (`open_count`, row `ref`). */
export function contractBody(body) {
  if (!Array.isArray(body?.items)) return body;
  const without = (object, key) => Object.fromEntries(Object.entries(object).filter(([name]) => name !== key));
  return { ...without(body, 'open_count'), items: body.items.map((row) => without(row, 'ref')) };
}

function matches(row, q, what) {
  if (what && row.what !== what) return false;
  if (!q) return true;
  return [row.title, row.ref, row.doing, row.who_acts].some((text) => text?.toLowerCase().includes(q));
}

export function exceptionsList({ url, persona, cookies }) {
  if (persona === 'pm') return { status: 403, body: NOT_A_LEAD };
  if (persona === 'none' || cookies.psl_mock_exceptions === 'empty') {
    return { status: 200, body: { items: [], as_of: fixture.as_of, open_count: 0 } };
  }
  const params = url.searchParams;
  const q = params.get('q')?.trim().toLowerCase() || undefined;
  const what = KINDS.includes(params.get('what')) ? params.get('what') : undefined;
  const source = cookies.psl_mock_exceptions === 'board' ? boardFixture : fixture;
  const rows = source.items.filter((row) => matches(row, q, what));
  const limit = LIMITS.includes(Number(params.get('limit'))) ? Number(params.get('limit')) : 20;
  const match = /^o:(\d+)$/.exec(params.get('cursor') ?? '');
  const offset = match && Number(match[1]) < rows.length ? Number(match[1]) : 0;
  const body = { items: rows.slice(offset, offset + limit), as_of: source.as_of, open_count: rows.length };
  if (offset + limit < rows.length) body.next_cursor = `o:${offset + limit}`;
  return { status: 200, body };
}
