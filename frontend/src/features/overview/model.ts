// The factory floor's figures: /overview's lines joined to /work/counts, grouped by floor.
// Counts are a sample (the most recent items), so they are shown as observed and an unknown figure is never 0.
import { floorOf, FLOORS, OTHER_FLOOR } from './lines';
import type { CountsLine, Overview, WorkCounts } from './types';

export const STATION_LABEL: Record<string, string> = { intake: 'Intake', execution: 'Execution', decision: 'Decision', delivery: 'Delivery', verified: 'Verified' };
const STATION_KEYS = Object.keys(STATION_LABEL);

export type Station = { key: string; name: string; count: number; needs_person: number };
/** `stations` is null when the line's counts are unknown (counts failed, or the sample did not reach this line). */
export type FloorLine = { key: string; title: string; total: number; stations: Station[] | null };
export type Floor = { name: string; total: number; lines: FloorLine[] };

const stationOf = (key: string, found?: { count: number; needs_person: number }): Station => ({
  key,
  name: STATION_LABEL[key],
  count: found?.count ?? 0,
  needs_person: found?.needs_person ?? 0,
});

function stationsFor(entry: CountsLine | undefined, counts: WorkCounts | null): Station[] | null {
  if (!counts) return null;
  if (!entry) return counts.limited ? null : STATION_KEYS.map((k) => stationOf(k));
  return STATION_KEYS.map((k) => stationOf(k, entry.stations.find((s) => s.key === k)));
}

const sum = (values: readonly number[]) => {
  let n = 0;
  for (const v of values) n += v;
  return n;
};

/** Floors in drawn order with "Other lines" last; a floor with no returned line is left out, and no key is dropped. */
export function floorsOf(overview: Overview, counts: WorkCounts | null): Floor[] {
  const by = new Map<string, FloorLine[]>();
  for (const l of overview.lines) {
    const entry = counts?.lines.find((c) => c.key === l.key);
    const name = floorOf(l.key);
    by.set(name, [...(by.get(name) ?? []), { key: l.key, title: l.title, total: l.total, stations: stationsFor(entry, counts) }]);
  }
  return [...FLOORS.map((f) => f.name), OTHER_FLOOR].flatMap((name) => {
    const lines = by.get(name);
    return lines ? [{ name, total: sum(lines.map((l) => l.total)), lines }] : [];
  });
}

export type Totals = { inProgress: number; needPerson: number; stopped: number; verifiedThisMonth: number };

/** Sums over every line /work/counts returns, including lines /overview does not list. */
export function totalsOf(counts: WorkCounts): Totals {
  const total = (pick: (l: CountsLine) => number) => sum(counts.lines.map(pick));
  return { inProgress: total((l) => l.open), needPerson: total((l) => l.needs_person), stopped: total((l) => l.stopped), verifiedThisMonth: total((l) => l.verified_this_month) };
}

/** "at least N" when the counts did not cover every item; never a bare number then. */
export const figure = (n: number, limited: boolean) => (limited ? `at least ${n}` : String(n));

export const coverageText = (counts: WorkCounts) =>
  counts.limited ? `Counted from the ${counts.evaluated} most recent items you can see` : `Counted from all ${counts.evaluated} items you can see`;

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
/** "2026-11" as "Nov 2026". */
export function monthLabel(month: string) {
  const [y, m] = month.split('-');
  const name = MONTHS[parseInt(m, 10) - 1];
  return name ? `${name} ${y}` : month;
}

export const workLink = (key: string) => `/my-work?line=${encodeURIComponent(key)}`;
