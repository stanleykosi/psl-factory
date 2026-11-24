// The factory floor's two live reads in the contract mock (API 1.24.0, not in v7): GET /overview ({as_of, lines[{key,title,total}]})
// and GET /work/counts (the sampled figures per line). A variant is named by cookie psl_mock_overview:
//   empty (no lines), limited (50 most recent items, queue totals null), missing (commercial/v1 absent from the counts, not limited),
//   missing-limited (the same absence, limited), no-counts (counts answers 503; the overview still answers).
// Sample data only; the mock never counts anything.
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const read = (path) => JSON.parse(readFileSync(join(here, 'fixtures', 'floor', path), 'utf8'));

export const OVERVIEW_PATH = '/api/v1/overview';
export const COUNTS_PATH = '/api/v1/work/counts';
export const OVERVIEW_VARIANTS = ['empty', 'limited', 'missing', 'missing-limited', 'no-counts'];

const READ_LIMITED = { code: 'read_limited', message: 'The counts could not be read right now.' };

const limit = (counts) => ({ ...counts, evaluated: 50, limited: true, queues: counts.queues.map((q) => ({ ...q, total: null })) });
const without = (counts, key) => ({ ...counts, lines: counts.lines.filter((l) => l.key !== key) });

/** [status, body] for the two reads, or null for any other path. */
export function floorRead({ pathname, cookies }) {
  if (pathname !== OVERVIEW_PATH && pathname !== COUNTS_PATH) return null;
  const variant = OVERVIEW_VARIANTS.includes(cookies.psl_mock_overview) ? cookies.psl_mock_overview : null;
  if (pathname === OVERVIEW_PATH) {
    const body = read('overview.json');
    return [200, variant === 'empty' ? { ...body, lines: [] } : body];
  }
  const counts = read('counts.json');
  if (variant === 'no-counts') return [503, READ_LIMITED];
  if (variant === 'empty') return [200, { ...counts, evaluated: 0, lines: [], queues: counts.queues.map((q) => ({ ...q, observed: 0, total: 0 })) }];
  if (variant === 'limited') return [200, limit(counts)];
  if (variant === 'missing') return [200, without(counts, 'commercial/v1')];
  if (variant === 'missing-limited') return [200, limit(without(counts, 'commercial/v1'))];
  return [200, counts];
}
