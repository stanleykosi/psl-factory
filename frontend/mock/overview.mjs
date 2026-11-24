// The factory floor's two live reads in the contract mock (API 1.24.0, not in v7): GET /overview ({as_of, lines[{key,title,total}]})
// and GET /work/counts (the sampled figures per line). A variant is named by cookie psl_mock_overview:
//   empty (no lines), limited (50 most recent items, queue totals null), missing (commercial/v1 absent from the counts, not limited),
//   missing-limited (the same absence, limited), no-counts (counts answers 503; the overview still answers),
//   floors (one line on each of the eight floors, with totals 18, 5, 3 and 28: the board's sample, for the fidelity check).
// Sample data only; the mock never counts anything.
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const read = (path) => JSON.parse(readFileSync(join(here, 'fixtures', 'floor', path), 'utf8'));

export const OVERVIEW_PATH = '/api/v1/overview';
export const COUNTS_PATH = '/api/v1/work/counts';
export const OVERVIEW_VARIANTS = ['empty', 'limited', 'missing', 'missing-limited', 'no-counts', 'floors'];

const READ_LIMITED = { code: 'read_limited', message: 'The counts could not be read right now.' };

const limit = (counts) => ({ ...counts, evaluated: 50, limited: true, queues: counts.queues.map((q) => ({ ...q, total: null })) });
const without = (counts, key) => ({ ...counts, lines: counts.lines.filter((l) => l.key !== key) });

// One line per floor: key, title, open, needs a person, stopped, verified this month.
const FLOORS = [
  ['rfp-response/v1', 'RFP response and project handoff', 3, 1, 0, 4],
  ['engagement/v1', 'Engagement and plan', 2, 0, 1, 3],
  ['delivery-release/v1', 'Release gates', 2, 1, 0, 5],
  ['delivery-hypercare/v1', 'Hypercare', 1, 0, 0, 4],
  ['pmo-finance/v1', 'Invoice preparation and delivery', 4, 2, 1, 3],
  ['finance-accounts/v1', 'Management accounts', 2, 0, 0, 3],
  ['finance-forecast/v1', 'Cash forecast', 2, 0, 0, 3],
  ['finance-payroll/v1', 'Payroll run', 2, 1, 1, 3],
];

function floors(counts, overview) {
  const lines = FLOORS.map(([key, , open, needs, stopped, verified_this_month]) => {
    const intake = Math.floor(open / 2);
    const station = (k, count, needs_person = 0) => ({ key: k, count, needs_person });
    return {
      key, needs_person: needs, held: 0, open, stopped, verified: verified_this_month, verified_this_month,
      stations: [station('intake', intake), station('execution', open - intake - needs), station('decision', needs, needs), station('delivery', 0), station('verified', verified_this_month)],
    };
  });
  return [{ ...overview, lines: FLOORS.map(([key, title, open]) => ({ key, title, total: open })) }, { ...counts, evaluated: 18, lines }];
}

/** Whether the factory floor answers GET /work/counts: a named variant, or the ceo persona the floor is drawn for. */
export const ownsFloorCounts = (cookies) => OVERVIEW_VARIANTS.includes(cookies.psl_mock_overview) || cookies.psl_mock_persona === 'ceo';

/** [status, body] for the two reads, or null for any other path. */
export function floorRead({ pathname, cookies }) {
  if (pathname !== OVERVIEW_PATH && pathname !== COUNTS_PATH) return null;
  const variant = OVERVIEW_VARIANTS.includes(cookies.psl_mock_overview) ? cookies.psl_mock_overview : null;
  if (pathname === OVERVIEW_PATH) {
    const body = read('overview.json');
    if (variant === 'floors') return [200, floors(read('counts.json'), body)[0]];
    return [200, variant === 'empty' ? { ...body, lines: [] } : body];
  }
  const counts = read('counts.json');
  if (variant === 'no-counts') return [503, READ_LIMITED];
  if (variant === 'floors') return [200, floors(counts, read('overview.json'))[1]];
  if (variant === 'empty') return [200, { ...counts, evaluated: 0, lines: [], queues: counts.queues.map((q) => ({ ...q, observed: 0, total: 0 })) }];
  if (variant === 'limited') return [200, limit(counts)];
  if (variant === 'missing') return [200, without(counts, 'commercial/v1')];
  if (variant === 'missing-limited') return [200, limit(without(counts, 'commercial/v1'))];
  return [200, counts];
}
