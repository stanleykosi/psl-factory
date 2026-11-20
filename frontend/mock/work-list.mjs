// E-WORK-LIST in the contract mock: honours queue, q, line (a line key), project, waiting_on, state,
// cursor and limit over the per-persona rows in fixtures/E-WORK-LIST.rows.json, and returns the
// D-WORKLIST-FILTERS proposal fields (filters.lines, line_key, agent). Rows carry two mock-only keys
// beside the item: project (a case_id) and waiting (the waiting_on category). With the cookie
// psl_mock_worklist=board it serves the SCR-01 boards' own sample rows (fixtures/E-WORK-LIST.board.json)
// for the design-fidelity check; for pm that includes `suggestions` ("While you're free"), a field the v4
// contract does not have yet (proposed in F-02 round 3). Persona pmo_lead (F-36) is a Lead with the W-33xx RFP rows. Sample data only; no business rules.
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

import { loggedRfps } from './start-work.mjs';
import { assignedWorkIds } from './workspace.mjs';

const here = dirname(fileURLToPath(import.meta.url));
const read = (name) => JSON.parse(readFileSync(join(here, 'fixtures', name), 'utf8'));
const fixture = read('E-WORK-LIST.rows.json');
const board = read('E-WORK-LIST.board.json');

export const QUEUES = ['needs_me', 'waiting_on_others', 'done', 'unassigned'];
const LIMITS = [10, 20, 50];
const OPTIONAL = ['q', 'line', 'project', 'waiting_on', 'state', 'cursor'];
const WAITING_ON = ['me', 'someone_else', 'agent', 'outside_party', 'no_owner'];
const LEAD_PERSONAS = ['finance_lead', 'pmo_lead'];

const INVALID_QUERY = { code: 'invalid_query', message: 'We could not read that list request.' };
const QUEUE_NOT_OPEN = { code: 'queue_not_open', message: 'Only Leads can see unassigned work.' };

function decodeCursor(cursor) {
  const match = /^o(\d+)$/.exec(cursor);
  return match ? Number(match[1]) : null;
}

/** Lines the persona has work on, by key, in first-seen order. */
function linesOf(rows) {
  const lines = new Map();
  for (const { item } of rows) if (!lines.has(item.line_key)) lines.set(item.line_key, { key: item.line_key, title: item.line });
  return [...lines.values()].sort((a, b) => a.title.localeCompare(b.title));
}

/** The persona's rows, counts and line list: the main fixture, or the boards' sample when asked for. */
function dataset(persona, lead, name) {
  const drawn = name === 'board' ? board.personas[persona] : undefined;
  // The boards' rows keep the order the boards draw them in.
  if (drawn) return { as_of: board.as_of, rows: drawn.rows, counts: drawn.counts, lines: drawn.lines, suggestions: drawn.suggestions, drawnOrder: true };
  const rows = fixture.rows.filter((row) => row.personas.includes(persona));
  const counts = { needs_me: 0, waiting_on_others: 0, done: 0 };
  if (lead) counts.unassigned = 0;
  for (const row of rows) if (row.queue in counts) counts[row.queue] += 1;
  return { as_of: fixture.as_of, rows, counts, lines: linesOf(rows), drawnOrder: false };
}

/** The Unassigned row of an RFP just logged (F-49): the newest, so it sorts first. */
const loggedRow = ({ work_id: id, reference, client }) => ({
  personas: ['pmo_lead'],
  queue: 'unassigned',
  waiting: 'no_owner',
  item: {
    id,
    title: `${client} · RFP ${reference}`,
    line: 'RFP received',
    line_key: 'rfp_intake',
    reference,
    kind: 'do',
    state: 'owner_needed',
    station: { index: 2, count: 5, name: 'Assign PM' },
    waiting_on: 'PMO Lead',
    age_seconds: 0,
    sample: true,
  },
});

export function workList({ url, persona, dataset: name, extra = [] }) {
  const params = url.searchParams;
  const queue = params.get('queue');
  const limit = params.has('limit') ? Number(params.get('limit')) : 20;
  const offset = params.has('cursor') ? decodeCursor(params.get('cursor')) : 0;
  // QA-2-1: every optional parameter has minLength 1, so an empty one (q=) is unreadable too.
  const empty = OPTIONAL.some((name) => params.has(name) && params.get(name) === '');
  const waitingOk = !params.get('waiting_on') || WAITING_ON.includes(params.get('waiting_on'));
  if (!QUEUES.includes(queue) || !LIMITS.includes(limit) || offset === null || empty || !waitingOk) return { status: 404, body: INVALID_QUERY };

  const lead = LEAD_PERSONAS.includes(persona);
  // C8: persona none sees every queue empty; other non-leads are refused unassigned.
  if (queue === 'unassigned' && !lead && persona !== 'none') return { status: 403, body: QUEUE_NOT_OPEN };

  const drawn = dataset(persona, lead, name);
  // F-36: an Unassigned row whose assignment was written is gone, and the count goes down with it (the assignment log is workspace.mjs's).
  const assigned = assignedWorkIds();
  const gone = drawn.rows.filter((row) => row.queue === 'unassigned' && assigned.has(row.item.id)).length;
  const kept = gone === 0 ? drawn : { ...drawn, rows: drawn.rows.filter((row) => !(row.queue === 'unassigned' && assigned.has(row.item.id))), counts: { ...drawn.counts, unassigned: drawn.counts.unassigned - gone } };
  // F-49: an RFP logged from Start work is one more Unassigned row for the PMO Lead, until the mock is reset.
  const logs = persona === 'pmo_lead' ? loggedRfps().filter((rfp) => !assigned.has(rfp.work_id)).map(loggedRow) : [];
  const withLogged = logs.length === 0 ? kept : { ...kept, rows: [...logs, ...kept.rows], counts: { ...kept.counts, unassigned: kept.counts.unassigned + logs.length }, lines: kept.lines.some((l) => l.key === 'rfp_intake') ? kept.lines : [...kept.lines, { key: 'rfp_intake', title: 'RFP received' }] };

  // D-155: the live demo's line runs (line-runs.mjs) are more rows for the persona; the board sample stays as drawn.
  const added = name === 'board' ? [] : extra;
  const data = added.length === 0 ? withLogged : {
    ...withLogged,
    rows: [...added, ...withLogged.rows],
    counts: Object.fromEntries(Object.entries(withLogged.counts).map(([queue, count]) => [queue, count + added.filter((row) => row.queue === queue).length])),
    lines: [...withLogged.lines, ...added.map((row) => ({ key: row.item.line_key, title: row.item.line })).filter((l, i, all) => !withLogged.lines.some((x) => x.key === l.key) && all.findIndex((x) => x.key === l.key) === i)],
  };

  const state = params.get('state');
  const line = params.get('line');
  const project = params.get('project');
  const waiting = params.get('waiting_on');
  const q = params.get('q')?.toLowerCase();
  const items = data.rows
    .filter((row) => row.queue === queue)
    .filter((row) => !project || row.project === project)
    .filter((row) => !waiting || row.waiting === waiting)
    .map((row) => row.item)
    .filter((item) => !state || item.state === state)
    .filter((item) => !line || item.line_key === line)
    .filter((item) => !q || [item.title, item.reference, item.line].some((text) => text.toLowerCase().includes(q)))
    .sort((a, b) => (data.drawnOrder ? 0 : a.age_seconds - b.age_seconds || a.id.localeCompare(b.id)));

  const body = { items: items.slice(offset, offset + limit), as_of: data.as_of, counts: data.counts, filters: { lines: data.lines } };
  if (offset + limit < items.length) body.next_cursor = `o${offset + limit}`;
  // Board sample only: the agent suggestions the empty boards draw. Not in the v4 contract (a proposal).
  if (data.suggestions) body.suggestions = data.suggestions;
  return { status: 200, body };
}
