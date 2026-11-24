// What the server says about how complete a list is. Never a total, never "0" for an unknown.
import { formatDayTime } from '@/components';

import type { MoreState, WorkCoverage } from './types';

/** The deferred list holds at most 8, so 8 reads "8 or more". */
const DEFERRED_CAP = 8;

/** One secondary line each: as-of always, then the incomplete and still-being-checked notes when they apply. */
export function coverageNotes(coverage: WorkCoverage, asOf: string): string[] {
  const notes = [`As of ${formatDayTime(asOf)}`];
  if (coverage.limited) notes.push('This list may be incomplete. Some work could not be checked yet.');
  const n = coverage.deferredCount;
  if (n > 0) notes.push(n >= DEFERRED_CAP ? `${DEFERRED_CAP} or more items are still being checked.` : n === 1 ? '1 more item is still being checked.' : `${n} more items are still being checked.`);
  return notes;
}

/** "{n} shown", and "so far" while the server has more pages. */
export function shownText(rows: number, more: MoreState): string {
  return more === 'done' ? `${rows} shown` : `${rows} shown so far`;
}
