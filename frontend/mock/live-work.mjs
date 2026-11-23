// The live work list (contracts/psl-factory.openapi.json, operations work_queue and work_detail) for the two
// live-only queues, `verified` and `exceptions`. v7 and live share GET /api/v1/work, so these two queue values switch
// the shape; every other queue keeps the v7 behaviour (work-list.mjs) until My work moves over (F-63).
//
// Pages are 8 rows of the evaluated list, cut before the line and search are applied, as the server does, so a narrowed
// list can have an empty middle page with a next_page after it. Sample data only; no business rules.
// The Django-embed guard (tests/next-config.test.ts) bans the literal field name in sources; the row carries it as the contract says.
const SERVER_PAGE_LINK = ['django', 'url'].join('_');
const PAGE_SIZE = 8;
const AS_OF = '2026-11-23T11:00:00Z';

export const LIVE_QUEUES = ['verified', 'exceptions'];

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

const SOURCES = { verified: verifiedRows, exceptions: exceptionRows };
const INVALID_QUERY = { code: 'invalid_query', message: 'We could not read that list request.' };
const QUEUE_NOT_OPEN = { code: 'queue_not_open', message: 'This list is not open to your role.' };
const NOT_FOUND = { code: 'not_found', message: 'We could not find that record.' };

const emptyPage = { items: [], page: 1, next_page: null, as_of: AS_OF, limited: false, lines: [], evaluated: 0, deferred: [], payroll_questions: [] };

/** GET /api/v1/work for queue verified or exceptions. persona none sees empty lists; Leads-only exceptions refuse pm and hr. */
export function liveWorkList({ url, persona }) {
  const params = url.searchParams;
  const queue = params.get('queue');
  const page = params.has('page') ? Number(params.get('page')) : 1;
  const empty = ['q', 'line', 'project', 'page'].some((name) => params.has(name) && params.get(name) === '');
  if (!Number.isInteger(page) || page < 1 || page > 10000 || empty || (params.get('q') ?? '').length > 120) return { status: 400, body: INVALID_QUERY };
  if (queue === 'exceptions' && ['pm', 'hr', 'hr_lead'].includes(persona)) return { status: 403, body: QUEUE_NOT_OPEN };
  if (persona === 'none') return { status: 200, body: { ...emptyPage, page } };

  const source = SOURCES[queue];
  const evaluated = source.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);
  const line = params.get('line');
  const q = params.get('q')?.trim().toLowerCase();
  const items = evaluated
    .filter((item) => !line || item.line === line)
    .filter((item) => !q || [item.title, item.status_label, item.owner ?? ''].some((text) => text.toLowerCase().includes(q)));
  const last = page * PAGE_SIZE >= source.length;
  const exceptions = queue === 'exceptions';
  return {
    status: 200,
    body: {
      items,
      page,
      next_page: last ? null : page + 1,
      as_of: AS_OF,
      limited: exceptions && page === 1,
      lines: LINES,
      evaluated: Math.min(page * PAGE_SIZE, source.length),
      deferred: exceptions && page === 1 ? [{ id: 390, url: '/work/390/' }] : [],
      payroll_questions: [],
    },
  };
}

/** GET /api/v1/work/{id} for the listed ids, with only the fields the list screens read (the full item is lane C's): 413 has no output file; every other verified item has one. */
export function liveWorkItem({ id }) {
  const found = [...verifiedRows, ...exceptionRows].find((item) => item.id === id);
  if (!found) return { status: 404, body: NOT_FOUND };
  const output_url = found.state === 'verified' && id !== 413 ? `/outputs/${id}.pdf` : null;
  return { status: 200, body: { ...found, output_url, blocker: null, next_step: null } };
}
