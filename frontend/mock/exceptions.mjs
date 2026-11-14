// E-EXCEPTIONS in the contract mock: pages the rows of fixtures/E-EXCEPTIONS.json in file order by limit and an
// "o:<offset>" cursor. "Leads; filtered by grants": the pm persona is refused, none sees an empty list (C8).
// Cookie psl_mock_exceptions=empty gives an empty list to anyone allowed to see it. Sample data only.
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const fixture = JSON.parse(readFileSync(join(here, 'fixtures', 'E-EXCEPTIONS.json'), 'utf8'));

const LIMITS = [10, 20, 50];
const NOT_A_LEAD = { code: 'forbidden', message: 'Only Leads can see all exceptions.' };

export function exceptionsList({ url, persona, cookies }) {
  if (persona === 'pm') return { status: 403, body: NOT_A_LEAD };
  if (persona === 'none' || cookies.psl_mock_exceptions === 'empty') {
    return { status: 200, body: { items: [], as_of: fixture.as_of } };
  }
  const params = url.searchParams;
  const limit = LIMITS.includes(Number(params.get('limit'))) ? Number(params.get('limit')) : 20;
  const match = /^o:(\d+)$/.exec(params.get('cursor') ?? '');
  const offset = match && Number(match[1]) < fixture.items.length ? Number(match[1]) : 0;
  const body = { items: fixture.items.slice(offset, offset + limit), as_of: fixture.as_of };
  if (offset + limit < fixture.items.length) body.next_cursor = `o:${offset + limit}`;
  return { status: 200, body };
}
