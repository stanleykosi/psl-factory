// My work (SCR-01): view state, the E-WORK-LIST query and display mappings. Pure functions only.
import type { operations } from '@/api/schema';

type Operation = operations['E-WORK-LIST'];
export type WorkQuery = Operation['parameters']['query'];
export type WorkList = Operation['responses'][200]['content']['application/json'];
export type WorkItem = WorkList['items'][number];
export type Counts = NonNullable<WorkList['counts']>;
export type Queue = WorkQuery['queue'];
export type WorkState = WorkItem['state'];
export type Limit = NonNullable<WorkQuery['limit']>;

export const QUEUES: { key: Queue; label: string; empty: string }[] = [
  { key: 'needs_me', label: 'Needs me', empty: 'Nothing needs you right now' },
  { key: 'waiting_on_others', label: 'Waiting on others', empty: 'Nothing is waiting on others' },
  { key: 'done', label: 'Done', empty: 'Nothing done yet' },
  { key: 'unassigned', label: 'Unassigned', empty: 'Nothing is unassigned' },
];
export const LIMITS: Limit[] = [10, 20, 50];
const DEFAULT_LIMIT: Limit = 20;

export type Family = 'person' | 'agent' | 'waiting' | 'done' | 'neutral';

/** CMP-05 words and colour family for each contract state, in contract order. */
export const STATES: Record<WorkState, { words: string; family: Family }> = {
  ready: { words: 'Ready to continue', family: 'person' },
  processing: { words: 'Processing', family: 'agent' },
  waiting: { words: 'Waiting', family: 'waiting' },
  owner_needed: { words: 'Owner needed', family: 'person' },
  setup_needed: { words: 'Setup needed', family: 'person' },
  action_needed: { words: 'Action needed', family: 'person' },
  effect_uncertain: { words: 'Effect uncertain', family: 'person' },
  awaiting_reconciliation: { words: 'Awaiting reconciliation', family: 'waiting' },
  verified: { words: 'Verified', family: 'done' },
  cancelled: { words: 'Cancelled', family: 'neutral' },
  followup_needed: { words: 'Stopped: invoice follow-up needed', family: 'person' },
};
export const STATE_KEYS = Object.keys(STATES) as WorkState[];

/** A state outside the table (only if the contract changes) shows its raw value as neutral. */
export function stateTag(state: string): { words: string; family: Family } {
  return Object.hasOwn(STATES, state) ? STATES[state as WorkState] : { words: state, family: 'neutral' };
}

export const KINDS: Record<WorkItem['kind'], { words: string; family: Family }> = {
  decide: { words: 'DECIDE', family: 'person' },
  do: { words: 'DO', family: 'person' },
  fix: { words: 'FIX', family: 'person' },
  started: { words: 'STARTED', family: 'neutral' },
};

export type View = { queue: Queue; q?: string; line?: string; state?: WorkState; limit: Limit };

/** Reads the view from the URL; invalid values fall back to the defaults. */
export function parseView(params: URLSearchParams): View {
  const queue = QUEUES.find((x) => x.key === params.get('queue'))?.key ?? 'needs_me';
  const q = params.get('q')?.trim() || undefined;
  const line = params.get('line') || undefined;
  const rawState = params.get('state');
  const state = rawState && Object.hasOwn(STATES, rawState) ? (rawState as WorkState) : undefined;
  const limit = LIMITS.find((n) => String(n) === params.get('limit')) ?? DEFAULT_LIMIT;
  return { queue, q, line, state, limit };
}

/** The URL search for a view; defaults are left out. Cursors are never written. */
export function viewSearch(view: View): string {
  const params = new URLSearchParams();
  if (view.queue !== 'needs_me') params.set('queue', view.queue);
  if (view.q) params.set('q', view.q);
  if (view.line) params.set('line', view.line);
  if (view.state) params.set('state', view.state);
  if (view.limit !== DEFAULT_LIMIT) params.set('limit', String(view.limit));
  const search = params.toString();
  return search ? `?${search}` : '';
}

export function buildWorkQuery(view: View, cursor?: string): WorkQuery {
  const query: WorkQuery = { queue: view.queue, limit: view.limit };
  const q = view.q?.trim();
  if (q) query.q = q;
  if (view.line) query.line = view.line;
  if (view.state) query.state = view.state;
  if (cursor) query.cursor = cursor;
  return query;
}

export const isNarrowed = (view: View) => Boolean(view.q || view.line || view.state);

export function formatAge(seconds: number): string {
  if (seconds < 3600) return `${Math.max(1, Math.floor(seconds / 60))}m`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h`;
  return `${Math.floor(seconds / 86400)}d`;
}

/** 24-hour HH:MM in the browser's time zone. */
export function formatTime(iso: string): string {
  return new Date(iso).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', hour12: false });
}

const SEGMENT_BY_FAMILY: Record<Family, string> = { person: 'p', agent: 'a', waiting: 'w', done: '', neutral: '' };

/** CMP-03 segment classes: done before the current station, the state's class on it, empty after. */
export function miniSegments(station: WorkItem['station'], state: string): string[] {
  if (state === 'verified') return Array.from({ length: station.count }, (_, i) => (i === station.count - 1 ? 'v' : 'd'));
  const current = state === 'followup_needed' ? 's' : state === 'cancelled' ? '' : SEGMENT_BY_FAMILY[stateTag(state).family];
  return Array.from({ length: station.count }, (_, i) => {
    const n = i + 1;
    if (n < station.index) return 'd';
    return n === station.index ? current : '';
  });
}

export function stationText(station: WorkItem['station'], state: string): string {
  return state === 'verified' ? `All ${station.count} stations done` : `Station ${station.index} of ${station.count} · ${station.name}`;
}

/** Line options: the distinct lines loaded for this view plus the applied one, A–Z. */
export function lineOptions(items: WorkItem[], applied?: string): string[] {
  const lines = new Set(items.map((i) => i.line));
  if (applied) lines.add(applied);
  return [...lines].sort((a, b) => a.localeCompare(b));
}

/** CMP-22 result count, uppercase mono. */
export function resultCount(view: View, counts: Counts | null | undefined, loaded: number, more: boolean): string {
  const total = counts?.[view.queue];
  if (total === undefined) return `${loaded}${more ? '+' : ''} ITEMS`;
  if (!isNarrowed(view)) return `${total} ITEMS`;
  return `${loaded}${more ? '+' : ''} OF ${total} ITEMS`;
}

/** Footer text: how many rows are showing. */
export function shownText(view: View, counts: Counts | null | undefined, loaded: number, more: boolean): string {
  if (!more) return `All ${loaded} showing`;
  const total = counts?.[view.queue];
  if (isNarrowed(view) || total === undefined) return `${loaded} showing`;
  return `${loaded} of ${total} showing`;
}

export function showMoreLabel(view: View, counts: Counts | null | undefined, loaded: number): string {
  const total = counts?.[view.queue];
  if (isNarrowed(view) || total === undefined || total - loaded <= 0) return 'Show more';
  return `Show ${Math.min(view.limit, total - loaded)} more`;
}

/** A refresh replaces page 1 and keeps the rows loaded after it, minus any id now on page 1. */
export function mergeRefresh(items: WorkItem[], firstCount: number, page: WorkItem[]): WorkItem[] {
  const fresh = new Set(page.map((i) => i.id));
  return [...page, ...items.slice(firstCount).filter((i) => !fresh.has(i.id))];
}

/** Show more appends the next page, skipping ids already shown. */
export function appendPage(items: WorkItem[], page: WorkItem[]): WorkItem[] {
  const shown = new Set(items.map((i) => i.id));
  return [...items, ...page.filter((i) => !shown.has(i.id))];
}
