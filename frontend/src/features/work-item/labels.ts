// Contract values (E-WORK-ITEM, E-WORK-HISTORY) to the words and classes on the SCR-02 boards.
// Presentation only: nothing here decides access or business state.
import type { operations } from '@/api/schema';

export type WorkItem = operations['E-WORK-ITEM']['responses'][200]['content']['application/json'];
export type WorkState = WorkItem['state'];
export type Fact = WorkItem['facts'][number];
export type FactName = Fact['name'];
export type StationStatus = WorkItem['stations'][number]['status'];
export type AgentStatus = WorkItem['agent']['status'];
export type WorkHistory = operations['E-WORK-HISTORY']['responses'][200]['content']['application/json'];
export type HistoryEntry = WorkHistory['items'][number];
type HistoryQuery = NonNullable<operations['E-WORK-HISTORY']['parameters']['query']>;
export type HistoryKind = NonNullable<HistoryQuery['kind']>;
export type HistoryLimit = NonNullable<HistoryQuery['limit']>;

type Tone = 'person' | 'waiting' | 'agent' | 'done' | 'neutral';

/** CMP-05 state tag: wording and colour family per contract state. */
export const STATE_TAGS: Record<WorkState, { text: string; tone: Tone }> = {
  ready: { text: 'Ready to continue', tone: 'person' },
  processing: { text: 'Processing', tone: 'agent' },
  waiting: { text: 'Waiting', tone: 'waiting' },
  owner_needed: { text: 'Owner needed', tone: 'person' },
  setup_needed: { text: 'Setup needed', tone: 'person' },
  action_needed: { text: 'Action needed', tone: 'person' },
  effect_uncertain: { text: 'Effect uncertain', tone: 'waiting' },
  awaiting_reconciliation: { text: 'Awaiting reconciliation', tone: 'waiting' },
  verified: { text: 'Verified', tone: 'done' },
  cancelled: { text: 'Cancelled', tone: 'neutral' },
  followup_needed: { text: 'Stopped: invoice follow-up needed', tone: 'person' },
};

/** The six facts in contract order (INV-FACTS: never merged into one status). The boards label the receipt fact
 *  RECEIPT; `more` completes the contract name for screen readers ("RECEIPT RECORDED"). */
export const FACTS: readonly { name: FactName; label: string; more?: string }[] = [
  { name: 'drafted', label: 'DRAFTED' },
  { name: 'reviewed', label: 'REVIEWED' },
  { name: 'approved', label: 'APPROVED' },
  { name: 'sent', label: 'SENT' },
  { name: 'receipt_recorded', label: 'RECEIPT', more: ' RECORDED' },
  { name: 'verified', label: 'VERIFIED' },
];

/** CMP-02 station: one-line status and modifier class. */
export const STATIONS: Record<StationStatus, { text: string; modifier: string }> = {
  done: { text: 'Done', modifier: 'done' },
  current_person: { text: 'Needs a person', modifier: 'person' },
  current_agent: { text: 'Agent working', modifier: 'agent' },
  waiting: { text: 'Waiting', modifier: 'waiting' },
  stopped: { text: 'Stopped', modifier: 'stopped' },
  not_started: { text: 'Not started', modifier: 'todo' },
  verified: { text: 'Verified', modifier: 'verified' },
};

/** The station the item is at: the first one that is neither finished nor still to come. */
export function currentStationIndex(stations: WorkItem['stations']): number {
  return stations.findIndex((s) => s.status !== 'done' && s.status !== 'not_started' && s.status !== 'verified');
}

export const AGENT_TAGS: Record<Exclude<AgentStatus, 'none'>, { text: string; tone: Tone }> = {
  working: { text: 'WORKING', tone: 'agent' },
  done: { text: 'DONE', tone: 'done' },
  waiting: { text: 'WAITING', tone: 'waiting' },
  stopped: { text: 'STOPPED', tone: 'person' },
};

export type StepKind = 'done' | 'now' | 'wait' | 'stopped' | 'next';

/** Agent step status is a free string; anything unrecognised counts as still to come, never as done. */
export function stepKind(status: string): StepKind {
  const s = status.toLowerCase();
  if (s === 'done') return 'done';
  if (s === 'working' || s === 'current' || s === 'now') return 'now';
  if (s === 'waiting') return 'wait';
  if (s === 'stopped') return 'stopped';
  return 'next';
}

export const STEP_WORDS: Record<StepKind, string> = {
  done: 'Done',
  now: 'In progress',
  wait: 'Waiting',
  stopped: 'Stopped',
  next: 'To do',
};

const AVATARS = new Set(['chidi', 'tola', 'zainab']);

export function avatarClass(name: string | undefined): string {
  const key = name?.toLowerCase();
  return key && AVATARS.has(key) ? `psl-avatar psl-avatar--${key}` : 'psl-avatar';
}

/** The agent's mascot (public/agents, as on My work); undefined for an agent without one. */
export function agentImage(name: string | undefined): string | undefined {
  const key = name?.toLowerCase();
  return key && AVATARS.has(key) ? `/agents/${key}.png` : undefined;
}

const WARNING_STATES = new Set<WorkState>([
  'effect_uncertain',
  'awaiting_reconciliation',
  'owner_needed',
  'setup_needed',
  'action_needed',
  'followup_needed',
]);

/** CMP-24 callout kind for the next step. */
export function nextStepKind(state: WorkState): 'warning' | 'success' | 'info' {
  if (WARNING_STATES.has(state)) return 'warning';
  if (state === 'verified') return 'success';
  return 'info';
}

export const HISTORY_FILTERS: readonly { kind: HistoryKind; label: string }[] = [
  { kind: 'all', label: 'All' },
  { kind: 'decisions', label: 'Decisions' },
  { kind: 'agent_work', label: 'Agent work' },
  { kind: 'evidence', label: 'Evidence' },
];

export const HISTORY_LIMITS: readonly HistoryLimit[] = [10, 20, 50];

export const ACTOR_TAGS: Record<HistoryEntry['actor_kind'], { text: string; className: string }> = {
  person: { text: 'PERSON', className: 'psl-tag psl-tag--neutral' },
  agent: { text: 'AGENT', className: 'psl-tag psl-tag--agent' },
  factory: { text: 'FACTORY', className: 'psl-tag work-tag--outline' },
};

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const WAT = new Intl.DateTimeFormat('en-GB', {
  timeZone: 'Africa/Lagos',
  day: 'numeric',
  month: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
  hourCycle: 'h23',
});

/** "12 Nov 16:40" in Africa/Lagos (the boards say "Times are WAT"). */
export function formatWat(value: string | Date): string {
  const parts = Object.fromEntries(WAT.formatToParts(new Date(value)).map((p) => [p.type, p.value]));
  return `${parts.day} ${MONTHS[Number(parts.month) - 1]} ${parts.hour}:${parts.minute}`;
}

const WEEKDAY = new Intl.DateTimeFormat('en-GB', { timeZone: 'Africa/Lagos', weekday: 'short' });

/** "Mon 10 Nov 14:05" in Africa/Lagos, for the header's started line. */
export function formatWatDay(value: string): string {
  return `${WEEKDAY.format(new Date(value))} ${formatWat(value)}`;
}

/** The header's started line from the contract: "Started by Tunde Bello (PMO) · Mon 10 Nov 14:05 · revision 2";
 *  "revision N" alone when the item does not say who started it. */
export function startedLine(item: WorkItem): string {
  if (!item.started_by) return `revision ${item.revision}`;
  const { name, role } = item.started_by;
  const parts = [`Started by ${role ? `${name} (${role})` : name}`];
  if (item.started_at) parts.push(formatWatDay(item.started_at));
  return [...parts, `revision ${item.revision}`].join(' · ');
}
