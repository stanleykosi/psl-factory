// E-WORK-LIST in the contract mock: honours queue, q, line, state, cursor and limit over the
// per-persona rows in fixtures/E-WORK-LIST.rows.json. Sample data only; no business rules.
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const fixture = JSON.parse(readFileSync(join(here, 'fixtures', 'E-WORK-LIST.rows.json'), 'utf8'));

export const QUEUES = ['needs_me', 'waiting_on_others', 'done', 'unassigned'];
const LIMITS = [10, 20, 50];
const LEAD_PERSONAS = ['finance_lead'];

const INVALID_QUERY = { code: 'invalid_query', message: 'We could not read that list request.' };
const QUEUE_NOT_OPEN = { code: 'queue_not_open', message: 'Only Leads can see unassigned work.' };

function decodeCursor(cursor) {
  const match = /^o(\d+)$/.exec(cursor);
  return match ? Number(match[1]) : null;
}

export function workList({ url, persona }) {
  const params = url.searchParams;
  const queue = params.get('queue');
  const limit = params.has('limit') ? Number(params.get('limit')) : 20;
  const offset = params.has('cursor') ? decodeCursor(params.get('cursor')) : 0;
  if (!QUEUES.includes(queue) || !LIMITS.includes(limit) || offset === null) return { status: 404, body: INVALID_QUERY };

  const lead = LEAD_PERSONAS.includes(persona);
  if (queue === 'unassigned' && !lead) return { status: 403, body: QUEUE_NOT_OPEN };

  const mine = fixture.rows.filter((row) => row.personas.includes(persona));
  const counts = { needs_me: 0, waiting_on_others: 0, done: 0 };
  if (lead) counts.unassigned = 0;
  for (const row of mine) if (row.queue in counts) counts[row.queue] += 1;

  const state = params.get('state');
  const line = params.get('line');
  const q = params.get('q')?.toLowerCase();
  const items = mine
    .filter((row) => row.queue === queue)
    .map((row) => row.item)
    .filter((item) => !state || item.state === state)
    .filter((item) => !line || item.line === line)
    .filter((item) => !q || [item.title, item.reference, item.line].some((text) => text.toLowerCase().includes(q)))
    .sort((a, b) => a.age_seconds - b.age_seconds || a.id.localeCompare(b.id));

  const body = { items: items.slice(offset, offset + limit), as_of: fixture.as_of, counts };
  if (offset + limit < items.length) body.next_cursor = `o${offset + limit}`;
  return { status: 200, body };
}
