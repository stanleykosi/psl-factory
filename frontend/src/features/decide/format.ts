// SCR-03 decision values to the words on the boards. Presentation only: amounts are formatted from the
// decimal string (never a float), unknown stays Unknown, and nothing here decides who may act.
import type { TaskDecision, WorkItem, WorkTask } from '@/api/types';

export type Verdict = 'approve' | 'return' | 'reject';
export type Amount = NonNullable<TaskDecision['amount']>;
export type ChainStep = TaskDecision['chain']['steps'][number];
export type CannotActReason = NonNullable<WorkTask['cannot_act_reason']>;
export type Asked = NonNullable<WorkTask['asked']>[number];

export const NOTE_MAX = 2000;

/** "₦4,250,000.00", or "USD 1,200.00"; null when the amount is unknown or absent (INV-UNKNOWN: never 0). */
export function formatAmount(amount: Amount): string | null {
  if (amount.unknown || !amount.amount) return null;
  const match = /^(-?)(\d+)\.(\d{2})$/.exec(amount.amount);
  if (!match) return null;
  const [, sign, whole, cents] = match;
  const grouped = whole.replace(/\B(?=(\d{3})+(?!\d))/g, ',');
  const prefix = amount.currency === 'NGN' ? '₦' : `${amount.currency} `;
  return `${sign}${prefix}${grouped}.${cents}`;
}

const HHMM = new Intl.DateTimeFormat('en-GB', { timeZone: 'Africa/Lagos', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' });

/** "10:47" in Africa/Lagos, for the done eyebrow only. */
export function formatClock(value: string): string {
  return HHMM.format(new Date(value));
}

export const STEP_STATUS: Record<ChainStep['status'], string> = {
  approved: 'Approved',
  returned: 'Returned',
  rejected: 'Rejected',
  withdrawn: 'Withdrawn',
  current: 'Current',
  not_yet: 'Not yet',
};

export const AGENT_NAMES: Record<NonNullable<NonNullable<TaskDecision['prepared_by']>['with_agent']>, string> = {
  tola: 'Tola',
  chidi: 'Chidi',
  zainab: 'Zainab',
};

export const VERDICT_WORDS: Record<Verdict, { button: string; busy: string; eyebrow: string; heading: (label: string) => string }> = {
  approve: { button: 'Approve', busy: 'Approving…', eyebrow: 'YOU APPROVED', heading: (label) => `${label} is approved` },
  return: { button: 'Return', busy: 'Returning…', eyebrow: 'YOU RETURNED', heading: (label) => `${label} was returned` },
  reject: { button: 'Reject', busy: 'Rejecting…', eyebrow: 'YOU REJECTED', heading: (label) => `${label} was rejected` },
};

/** The station waiting for a person (0-based), or -1. */
export function personStationIndex(stations: WorkItem['stations']): number {
  return stations.findIndex((s) => s.status === 'current_person');
}

const CHANNELS: Record<string, string> = { whatsapp: 'WhatsApp', email: 'email' };

export function channelWords(channels: string[]): string {
  return channels.map((c) => CHANNELS[c] ?? c).join(' and ');
}

/** The task the page decides: by the `task` query parameter; undefined when absent or without a decision. */
export function findDecisionTask(item: WorkItem, taskId: string | undefined): (WorkTask & { decision: TaskDecision }) | undefined {
  const task = taskId ? item.tasks.find((t) => t.id === taskId) : undefined;
  return task?.decision ? (task as WorkTask & { decision: TaskDecision }) : undefined;
}
