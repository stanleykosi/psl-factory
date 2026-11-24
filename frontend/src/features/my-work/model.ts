// My work (SCR-01): view state, URL rules and display mappings over the live work list. Pure functions only.
import { formatClock } from '@/components';
import { stateTag, type LineKey, type WorkCounts, type WorkLimit, type WorkListRow, type WorkQueue, type WorkState } from '@/features/work-list';

export type Station = NonNullable<WorkListRow['station']>;
export type Kind = NonNullable<WorkListRow['action_kind']>;
export type Limit = Extract<WorkLimit, 10 | 20 | 50>;
export type Family = ReturnType<typeof stateTag>['tone'];

/** The tabs, in the order the screen draws them (D-202). `Unassigned` is drawn only when something is unassigned. */
export const QUEUES: { key: WorkQueue; label: string; empty: string }[] = [
  { key: 'needs_me', label: 'Needs me', empty: 'Nothing needs you right now' },
  { key: 'waiting', label: 'Waiting on others', empty: 'Nothing is waiting on others' },
  { key: 'mine', label: 'Started by me', empty: 'You haven’t started anything that is still open' },
  { key: 'active', label: 'Active', empty: 'Nothing is active right now' },
  { key: 'decisions', label: 'Decisions', empty: 'No decisions are waiting' },
  { key: 'exceptions', label: 'Exceptions', empty: 'No exceptions right now' },
  { key: 'unassigned', label: 'Unassigned', empty: 'Nothing is unassigned' },
  { key: 'verified', label: 'Verified', empty: 'Nothing has been verified yet' },
];
export const LIMITS: Limit[] = [10, 20, 50];
const DEFAULT_LIMIT: Limit = 10;
export const MAX_Q = 120;

/** The 26 line keys the contract accepts; anything else in the URL is dropped. */
export const LINE_KEYS: LineKey[] = [
  'process-handoff/v1', 'pmo-issues/v1', 'pmo-leadership-report/v1', 'finance-ledger/v1', 'finance-bu/v1', 'engagement/v1', 'pmo-minutes/v1', 'pmo-escalation/v1',
  'pmo-weekly-report/v1', 'finance-schedules/v1', 'finance-ppe/v1', 'finance-forecast/v1', 'finance-payroll/v1', 'pmo-emergency/v1', 'pmo-change/v1', 'rfp-response/v1',
  'finance-accounts/v1', 'pmo-finance/v1', 'planning/v1', 'commercial/v1', 'delivery-release/v1', 'delivery-hypercare/v1', 'delivery-archive/v1', 'delivery-handover/v1',
  'delivery-closure/v1', 'delivery-go-live/v1',
];

/** The 11 live states, in the order the filter offers them, with the words every list uses. */
export const STATE_KEYS: WorkState[] = [
  'ready', 'processing', 'waiting', 'owner_needed', 'setup_needed', 'action_needed', 'effect_uncertain', 'awaiting_reconciliation', 'verified', 'cancelled', 'followup_needed',
];
export const stateWords = (state: WorkState) => stateTag(state).text;

export const KINDS: Record<Kind, { words: string; tone: Family }> = {
  decide: { words: 'DECIDE', tone: 'person' },
  do: { words: 'DO', tone: 'person' },
  fix: { words: 'FIX', tone: 'person' },
  started: { words: 'STARTED', tone: 'neutral' },
};

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/** `assign` (F-88): the received RFP's case whose "Assign accountable PM" drawer is open over the Unassigned list; not part of the list's own request. */
export type View = { queue: WorkQueue; q?: string; line?: LineKey; project?: string; state?: WorkState; limit: Limit; assign?: string };

/** Reads the view from the URL; a value the contract does not accept is dropped. */
export function parseView(params: URLSearchParams): View {
  const queue = QUEUES.find((x) => x.key === params.get('queue'))?.key ?? 'needs_me';
  const q = params.get('q')?.trim().slice(0, MAX_Q).trim() || undefined;
  const line = LINE_KEYS.find((key) => key === params.get('line'));
  const rawState = params.get('state');
  const state = STATE_KEYS.find((key) => key === rawState);
  const rawProject = params.get('project');
  const project = rawProject && UUID.test(rawProject) ? rawProject : undefined;
  const limit = LIMITS.find((n) => String(n) === params.get('limit')) ?? DEFAULT_LIMIT;
  const rawAssign = params.get('assign');
  const assign = queue === 'unassigned' && rawAssign && UUID.test(rawAssign) ? rawAssign : undefined;
  return { queue, q, line, project, state, limit, assign };
}

/** The URL search for a view; defaults are left out. */
export function viewSearch(view: View): string {
  const params = new URLSearchParams();
  if (view.queue !== 'needs_me') params.set('queue', view.queue);
  if (view.q) params.set('q', view.q);
  if (view.line) params.set('line', view.line);
  if (view.project) params.set('project', view.project);
  if (view.state) params.set('state', view.state);
  if (view.limit !== DEFAULT_LIMIT) params.set('limit', String(view.limit));
  if (view.assign) params.set('assign', view.assign);
  const search = params.toString();
  return search ? `?${search}` : '';
}

export const isNarrowed = (view: View) => Boolean(view.q || view.line || view.project || view.state);

/** Applied filters (search not counted), for the Filter badge. */
export const filterCount = (view: View) => [view.line, view.project, view.state].filter(Boolean).length;

/** What a tab's count says. `atLeast`: the server counted some but not all. No entry: nothing to show, never 0. */
export type TabCount = { count: number; atLeast: boolean };
export function tabCount(counts: WorkCounts | undefined, queue: WorkQueue): TabCount | undefined {
  const entry = counts?.queues.find((x) => x.key === queue);
  if (!entry) return undefined;
  if (entry.total !== null) return { count: entry.total, atLeast: false };
  return entry.observed > 0 ? { count: entry.observed, atLeast: true } : undefined;
}

/** Whether the Unassigned tab is drawn: something is unassigned, or the address already names it. */
export function showUnassigned(counts: WorkCounts | undefined, selected: WorkQueue): boolean {
  const entry = counts?.queues.find((x) => x.key === 'unassigned');
  return selected === 'unassigned' || Boolean(entry && ((entry.total ?? 0) > 0 || entry.observed > 0));
}

/** "34 open records you can see": the per-line open counts added up; "at least" when the server says it could not check everything. */
export function recordsText(counts: WorkCounts | undefined): string | undefined {
  if (!counts) return undefined;
  const total = counts.lines.reduce((sum, line) => sum + line.open, 0);
  const words = `${total === 1 ? 'open record' : 'open records'} you can see`;
  return counts.limited ? `at least ${total} ${words}` : `${total} ${words}`;
}

/** Seconds since `from`, written as the lists write an age: "5m", "2h", "3d". */
export function formatAge(seconds: number): string {
  if (seconds < 3600) return `${Math.max(1, Math.floor(seconds / 60))}m`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h`;
  return `${Math.floor(seconds / 86400)}d`;
}

/** How long ago the row started, measured to the list's own `as_of` so a skewed browser clock cannot change it. */
export const startAge = (row: WorkListRow, asOf: string) => formatAge(Math.max(0, (Date.parse(asOf) - Date.parse(row.started_at)) / 1000));

/** "10:42" in WAT, as the SCR-01 boards write it ("updated 10:42"). */
export const formatTime = formatClock;

const SEGMENT_BY_FAMILY: Record<Family, string> = { person: 'p', agent: 'a', waiting: 'w', done: '', neutral: '' };

/** CMP-03 segment classes: done before the current station, the state's class on it, empty after. */
export function miniSegments(station: Station, state: WorkState): string[] {
  if (state === 'verified') return Array.from({ length: station.count }, (_, i) => (i === station.count - 1 ? 'v' : 'd'));
  // The segment says who holds the station, not the tag's colour: a Ready item is held by a person.
  const current = state === 'followup_needed' ? 's' : state === 'cancelled' ? '' : state === 'ready' ? 'p' : SEGMENT_BY_FAMILY[stateTag(state).tone];
  return Array.from({ length: station.count }, (_, i) => {
    const n = i + 1;
    if (n < station.index) return 'd';
    return n === station.index ? current : '';
  });
}

export function stationText(station: Station, state: WorkState): string {
  return state === 'verified' ? `All ${station.count} stations done` : `Station ${station.index} of ${station.count} · ${station.name}`;
}

/** CMP-22 result count, uppercase mono: exact only when the server marks the total complete. */
export function resultCount(loaded: number, more: boolean, total: number | null, totalComplete: boolean): string {
  if (!totalComplete || total === null) return `${loaded}${more ? '+' : ''} ITEMS`;
  return loaded >= total ? `${total} ITEMS` : `${loaded} OF ${total} ITEMS`;
}
