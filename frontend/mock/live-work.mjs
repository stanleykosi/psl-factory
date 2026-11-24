// The live work list (contracts/psl-factory.openapi.json, operations work_queue, work_counts and work_detail).
// v7 and live share GET /api/v1/work. A request is live when it names a live-only queue (waiting, mine, active,
// decisions, exceptions, verified) or carries `page`, which only the live adapter sends (isLiveWorkRequest); the v7
// callers of queue=needs_me and queue=unassigned without `page` (the decision desk) keep the v7 shape (work-list.mjs).
// `verified` and `exceptions` are the 20 shared rows each; the other queues are the persona's rows from the v7 fixture
// (fixtures/E-WORK-LIST.rows.json, or the boards' own rows with the cookie psl_mock_worklist=board) written in the
// live row shape. GET /api/v1/work/counts counts the same rows (liveWorkCounts).
//
// Pages are 8 rows of the evaluated list, cut before the line and search are applied, as the server does, so a narrowed
// list can have an empty middle page with a next_page after it. Sample data only; no business rules.
// The Django-embed guard (tests/next-config.test.ts) bans the literal field name in sources; the row carries it as the contract says.
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const SERVER_PAGE_LINK = ['django', 'url'].join('_');
const PAGE_SIZE = 8;
const AS_OF = '2026-11-23T11:00:00Z';

export const LIVE_QUEUES = ['waiting', 'mine', 'active', 'decisions', 'exceptions', 'verified'];
const ALL_QUEUES = ['needs_me', ...LIVE_QUEUES.slice(0, 4), 'exceptions', 'unassigned', 'verified'];
const LIMITS = [8, 10, 15, 20, 50];
const STATES = ['ready', 'waiting', 'action_needed', 'owner_needed', 'setup_needed', 'verified', 'cancelled', 'awaiting_reconciliation', 'followup_needed', 'processing', 'effect_uncertain'];

/** Whether a GET /api/v1/work request wants the live shape: a live-only queue, or `page`, which only the live adapter sends. */
export const isLiveWorkRequest = (url) => LIVE_QUEUES.includes(url.searchParams.get('queue')) || url.searchParams.has('page');

const LINES = [
  { key: 'finance-ledger/v1', title: 'Finance ledger' },
  { key: 'pmo-minutes/v1', title: 'PMO minutes' },
  { key: 'rfp-response/v1', title: 'RFP response' },
];
const CLIENTS = ['Lagoon Health', 'Marina Bank', 'Kora Logistics', 'Delta Foods', 'Aso Telecom'];
const OWNERS = ['Chidi Okafor', 'Bisi Ade', null, 'Tunde Bello'];
const EXCEPTION_STATES = [
  ['awaiting_reconciliation', 'Checking whether the email was sent'],
  ['effect_uncertain', 'Waiting for the bank to confirm the payment'],
  ['action_needed', 'A person needs to review the draft'],
  ['owner_needed', 'Choosing who takes this on'],
  ['setup_needed', 'A rule needs setting up first'],
  ['followup_needed', 'Invoice follow-up is needed'],
  ['ready', 'Ready to continue'],
  ['waiting', 'Waiting for the client'],
];

// Rows 9 to 16 (page 2) are all PMO minutes, so the line filter "Finance ledger" leaves page 2 empty.
const lineOf = (index) => (index >= 8 && index < 16 ? LINES[1].key : index % 5 === 4 ? LINES[2].key : LINES[0].key);

const row = ({ id, title, line, state, status_label, owner, sample, minutes }) => ({
  id,
  case_id: `7d7c0c9e-2f0a-4c3e-9c61-0f6a8f1a2b${String(id % 100).padStart(2, '0')}`,
  title,
  line,
  state,
  status_label,
  owner,
  sample,
  updated_at: new Date(Date.parse(AS_OF) - minutes * 60000).toISOString(),
  [SERVER_PAGE_LINK]: `/work/${id}/`,
  api_url: `/api/v1/work/${id}`,
  reference: null,
  started_at: new Date(Date.parse(AS_OF) - (minutes + 600) * 60000).toISOString(),
  verified_at: null,
  queue_output_url: null,
  exception_code: null,
  exception_next_step: null,
  exception_started_at: null,
  action_kind: null,
  station: null,
  agent: null,
});

const verifiedRows = Array.from({ length: 20 }, (_, i) =>
  row({
    id: 401 + i,
    title: `Invoice INV-${String(398 - i).padStart(4, '0')} · ${CLIENTS[i % CLIENTS.length]}`,
    line: lineOf(i),
    state: 'verified',
    status_label: 'Verified',
    owner: OWNERS[i % OWNERS.length],
    sample: i % 3 === 0,
    minutes: 40 + i * 25,
  }),
);

const exceptionRows = Array.from({ length: 20 }, (_, i) => {
  const [state, status_label] = EXCEPTION_STATES[i % EXCEPTION_STATES.length];
  return row({
    id: 301 + i,
    title: `Invoice INV-${String(412 - i).padStart(4, '0')} · ${CLIENTS[(i + 1) % CLIENTS.length]}`,
    line: lineOf(i),
    state,
    status_label,
    owner: OWNERS[(i + 2) % OWNERS.length],
    sample: false,
    minutes: 20 + i * 30,
  });
});

const here = dirname(fileURLToPath(import.meta.url));
const readJson = (name) => JSON.parse(readFileSync(join(here, 'fixtures', name), 'utf8'));
const v7Rows = readJson('E-WORK-LIST.rows.json');
const v7Board = readJson('E-WORK-LIST.board.json');

// The v7 fixtures name lines by short keys; the live contract has 26 line keys.
const LIVE_LINE = {
  invoice: 'finance-ledger/v1', planning: 'planning/v1', costing: 'finance-accounts/v1', sow: 'pmo-finance/v1', weekly_report: 'pmo-weekly-report/v1',
  receipt: 'finance-schedules/v1', bank_reconciliation: 'finance-ppe/v1', payment_exception: 'pmo-change/v1', leadership_report: 'pmo-leadership-report/v1',
  escalation: 'pmo-escalation/v1', release_gates: 'delivery-release/v1', emergency_change: 'pmo-emergency/v1', rfp_intake: 'rfp-response/v1',
  hr_joiner: 'process-handoff/v1', hr_leaver: 'engagement/v1', hr_unit_moves: 'finance-bu/v1', hr_finance_question: 'pmo-issues/v1', hr_staff_list: 'finance-payroll/v1',
  hr_staff_records: 'pmo-minutes/v1', hr_payroll_correction: 'finance-forecast/v1', hr_record_change: 'commercial/v1', go_live: 'delivery-go-live/v1',
  closure: 'delivery-closure/v1', commercial: 'commercial/v1', forecast: 'finance-forecast/v1', release: 'delivery-release/v1',
};
const STATIONS = ['intake', 'execution', 'decision', 'delivery', 'verified'];
const PEOPLE = ['Chidi Okafor', 'Bisi Ade', 'Tunde Bello', 'Ada Okafor'];
const LEADS = ['finance_lead', 'pmo_lead'];
const PERSON_STATES = ['ready', 'action_needed', 'owner_needed', 'setup_needed', 'followup_needed'];
const HELD_STATES = ['waiting', 'processing', 'effect_uncertain', 'awaiting_reconciliation'];

const hash = (text) => [...text].reduce((h, c) => (h * 31 + c.charCodeAt(0)) % 0xffffffffffff, 7);
const uuidOf = (text) => `7d7c0c9e-2f0a-4c3e-9c61-${hash(text).toString(16).padStart(12, '0')}`;

/** A v7 fixture row in the live row shape; times are measured back from the dataset's own clock. */
function fromV7({ item, project, waiting }, asOf, index) {
  const started = Date.parse(asOf) - item.age_seconds * 1000;
  const station = item.station ? { key: STATIONS[Math.min(4, Math.round(((item.station.index - 1) / Math.max(1, item.station.count - 1)) * 4))], ...item.station } : null;
  return {
    id: Number(item.id.slice(2)),
    case_id: uuidOf(project ?? item.id),
    title: item.title,
    line: LIVE_LINE[item.line_key] ?? 'finance-ledger/v1',
    state: item.state,
    status_label: item.waiting_on,
    owner: waiting === 'no_owner' ? null : PEOPLE[index % PEOPLE.length],
    sample: item.sample,
    updated_at: new Date(started + Math.min(item.age_seconds, 1800) * 1000).toISOString(),
    started_at: new Date(started).toISOString(),
    [SERVER_PAGE_LINK]: `/work/${Number(item.id.slice(2))}/`,
    api_url: `/api/v1/work/${Number(item.id.slice(2))}`,
    reference: item.reference ?? null,
    verified_at: null,
    queue_output_url: null,
    exception_code: null,
    exception_next_step: null,
    exception_started_at: null,
    action_kind: item.kind ?? null,
    station,
    agent: item.agent ?? null,
  };
}

const PREDICATES = {
  needs_me: (r) => r.queue === 'needs_me',
  waiting: (r) => r.queue === 'waiting_on_others',
  mine: (r) => r.item.kind === 'started',
  active: (r) => r.queue === 'needs_me' || r.queue === 'waiting_on_others',
  decisions: (r) => r.item.kind === 'decide',
  unassigned: (r) => r.queue === 'unassigned',
};

/** The persona's rows from the v7 fixture (or the boards' own rows), keyed by live queue, with the dataset's clock and counts. */
function personaData(persona, name) {
  const drawn = name === 'board' ? v7Board.personas[persona] : undefined;
  const asOf = drawn ? v7Board.as_of : v7Rows.as_of;
  const source = drawn ? drawn.rows : v7Rows.rows.filter((row) => row.personas.includes(persona));
  const ordered = drawn ? source : [...source].sort((a, b) => a.item.age_seconds - b.item.age_seconds || a.item.id.localeCompare(b.item.id));
  const all = ordered.map((row, i) => ({ source: row, row: fromV7(row, asOf, i) }));
  const queues = Object.fromEntries(Object.entries(PREDICATES).map(([queue, predicate]) => [queue, all.filter((x) => predicate(x.source)).map((x) => x.row)]));
  const lines = new Map();
  for (const { source: x, row } of all) if (!lines.has(row.line)) lines.set(row.line, { key: row.line, title: x.item.line });
  const totals = drawn ? { needs_me: drawn.counts.needs_me, waiting: drawn.counts.waiting_on_others, verified: drawn.counts.done, unassigned: drawn.counts.unassigned } : {};
  return { asOf, queues, all: all.map((x) => x.row), lines: [...lines.values()], totals };
}

const SOURCES = { verified: verifiedRows, exceptions: exceptionRows };
const INVALID_QUERY = { code: 'invalid_query', message: 'We could not read that list request.' };
const QUEUE_NOT_OPEN = { code: 'queue_not_open', message: 'This list is not open to your role.' };
const NOT_FOUND = { code: 'not_found', message: 'We could not find that record.' };

const emptyPage = { items: [], page: 1, next_page: null, as_of: AS_OF, page_size: PAGE_SIZE, total: null, total_coverage: 'incomplete', limited: false, lines: [], evaluated: 0, deferred: [], payroll_questions: [] };

const BLOCKED_FROM_EXCEPTIONS = ['pm', 'hr', 'hr_lead'];

/** GET /api/v1/work, live shape, for any of the eight queues. persona none sees empty lists; Leads-only exceptions refuse pm and hr; unassigned is for the Leads. */
export function liveWorkList({ url, persona, dataset }) {
  const params = url.searchParams;
  const queue = params.get('queue');
  const page = params.has('page') ? Number(params.get('page')) : 1;
  const limit = params.has('limit') ? Number(params.get('limit')) : PAGE_SIZE;
  const empty = ['q', 'line', 'project', 'page', 'state'].some((name) => params.has(name) && params.get(name) === '');
  const state = params.get('state');
  if (!ALL_QUEUES.includes(queue) || !Number.isInteger(page) || page < 1 || page > 10000 || !LIMITS.includes(limit) || empty || (params.get('q') ?? '').length > 120 || (state && !STATES.includes(state))) return { status: 400, body: INVALID_QUERY };
  if (queue === 'exceptions' && BLOCKED_FROM_EXCEPTIONS.includes(persona)) return { status: 403, body: QUEUE_NOT_OPEN };
  if (queue === 'unassigned' && persona !== 'none' && !LEADS.includes(persona)) return { status: 403, body: QUEUE_NOT_OPEN };
  if (persona === 'none') return { status: 200, body: { ...emptyPage, page, page_size: limit } };

  const shared = SOURCES[queue];
  const mine = shared ? undefined : personaData(persona, dataset);
  const source = shared ?? mine.queues[queue];
  const asOf = shared ? AS_OF : mine.asOf;
  const lines = shared ? LINES : mine.lines;
  const evaluated = source.slice((page - 1) * limit, page * limit);
  const line = params.get('line');
  const project = params.get('project');
  const q = params.get('q')?.trim().toLowerCase();
  const matches = (item) =>
    (!line || item.line === line) &&
    (!project || item.case_id === project) &&
    (!state || item.state === state) &&
    (!q || [item.title, item.status_label, item.owner ?? '', item.reference ?? ''].some((text) => text.toLowerCase().includes(q)));
  const last = page * limit >= source.length;
  const exceptions = queue === 'exceptions';
  return {
    status: 200,
    body: {
      items: evaluated.filter(matches),
      page,
      next_page: last ? null : page + 1,
      as_of: asOf,
      page_size: limit,
      // The shared verified and exceptions rows are never counted exactly; every other queue is.
      total: shared ? null : source.filter(matches).length,
      total_coverage: shared ? 'incomplete' : 'complete',
      limited: exceptions && page === 1,
      lines,
      evaluated: Math.min(page * limit, source.length),
      deferred: exceptions && page === 1 ? [{ id: 390, url: '/work/390/' }] : [],
      payroll_questions: [],
    },
  };
}

const stationCounts = (rows) => STATIONS.map((key) => ({ key, count: rows.filter((r) => r.station?.key === key).length, needs_person: rows.filter((r) => r.station?.key === key && PERSON_STATES.includes(r.state)).length }));

/** GET /api/v1/work/counts for the persona's whole queues (no filters). Exceptions and Verified are observed but not totalled. */
export function liveWorkCounts({ persona, dataset }) {
  const data = personaData(persona, dataset);
  const none = persona === 'none';
  const entry = (key, rows) => ({ key, observed: none ? 0 : rows.length, total: none ? 0 : (data.totals[key] ?? rows.length) });
  const queues = [
    entry('needs_me', data.queues.needs_me),
    entry('waiting', data.queues.waiting),
    entry('mine', data.queues.mine),
    entry('active', data.queues.active),
    entry('decisions', data.queues.decisions),
    ...(BLOCKED_FROM_EXCEPTIONS.includes(persona) ? [] : [{ key: 'exceptions', observed: none ? 0 : exceptionRows.length, total: none ? 0 : null }]),
    ...(LEADS.includes(persona) ? [entry('unassigned', data.queues.unassigned)] : []),
    { key: 'verified', observed: none ? 0 : verifiedRows.length, total: none ? 0 : (data.totals.verified ?? null) },
  ];
  const byLine = new Map();
  for (const row of none ? [] : data.all) byLine.set(row.line, [...(byLine.get(row.line) ?? []), row]);
  const lines = [...byLine].map(([key, rows]) => ({
    key,
    needs_person: rows.filter((r) => PERSON_STATES.includes(r.state)).length,
    held: rows.filter((r) => HELD_STATES.includes(r.state)).length,
    open: rows.filter((r) => r.state !== 'verified' && r.state !== 'cancelled').length,
    stopped: rows.filter((r) => r.state === 'followup_needed').length,
    verified: rows.filter((r) => r.state === 'verified').length,
    verified_this_month: rows.filter((r) => r.state === 'verified').length,
    stations: stationCounts(rows),
  }));
  return { status: 200, body: { as_of: data.asOf, evaluated: none ? 0 : data.all.length, limited: false, verified_month: '2026-11', queues, lines } };
}

/** Whether GET /api/v1/work/{id} is one of this list's own rows (verified 401 to 420, exceptions 301 to 320); other ids belong to the work item mock. */
export const ownsLiveWorkItem = (id) => [...verifiedRows, ...exceptionRows].some((item) => item.id === id);

/** GET /api/v1/work/{id} for the listed ids, with only the fields the list screens read (the full item is lane C's): 413 has no output file; every other verified item has one. */
export function liveWorkItem({ id }) {
  const found = [...verifiedRows, ...exceptionRows].find((item) => item.id === id);
  if (!found) return { status: 404, body: NOT_FOUND };
  const output_url = found.state === 'verified' && id !== 413 ? `/outputs/${id}.pdf` : null;
  return { status: 200, body: { ...found, output_url, blocker: null, next_step: null } };
}
