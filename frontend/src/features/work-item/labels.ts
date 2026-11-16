// Contract values (E-WORK-ITEM, E-WORK-HISTORY) to the words and classes on the SCR-02 boards.
// Presentation only: nothing here decides access or business state.
import type { operations } from '@/api/schema';
import { formatWeekdayDayTime, STATE_TAGS as SHARED_STATE_TAGS } from '@/components';

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

const CONTRACT_STATES: WorkState[] = [
  'ready',
  'processing',
  'waiting',
  'owner_needed',
  'setup_needed',
  'action_needed',
  'effect_uncertain',
  'awaiting_reconciliation',
  'verified',
  'cancelled',
  'followup_needed',
];

/** CMP-05 state tag: the shared table's wording and colour family (README), for the contract's states. */
export const STATE_TAGS = Object.fromEntries(CONTRACT_STATES.map((state) => [state, SHARED_STATE_TAGS[state]])) as Record<WorkState, { text: string; tone: Tone }>;

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

// The full-pose images the boards draw (public/agents): Tola waiting on the client, Chidi at work.
const POSES = new Set(['tola-waiting', 'chidi-working']);

/** A full-pose mascot where the boards draw one; the avatar otherwise. */
export function agentPose(name: string | undefined, pose: 'waiting' | 'working'): string | undefined {
  const key = `${name?.toLowerCase()}-${pose}`;
  return POSES.has(key) ? `/agents/${key}.png` : undefined;
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

export const ACTOR_TAGS: Record<HistoryEntry['actor_kind'], { text: string; tone: Tone }> = {
  person: { text: 'PERSON', tone: 'neutral' },
  agent: { text: 'AGENT', tone: 'agent' },
  factory: { text: 'FACTORY', tone: 'neutral' },
};

/** The header's started line from the contract: "Started by Tunde Bello (PMO) · Mon 10 Nov 14:05 · revision 2";
 *  "revision N" alone when the item does not say who started it. */
export function startedLine(item: WorkItem): string {
  if (!item.started_by) return `revision ${item.revision}`;
  const { name, role } = item.started_by;
  const parts = [`Started by ${role ? `${name} (${role})` : name}`];
  if (item.started_at) parts.push(formatWeekdayDayTime(item.started_at));
  return [...parts, `revision ${item.revision}`].join(' · ');
}
