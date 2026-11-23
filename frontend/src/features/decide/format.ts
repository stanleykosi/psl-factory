// SCR-03 decision values to the words on the boards. Presentation only: amounts are formatted from the
// decimal string (never a float), unknown stays Unknown, and nothing here decides who may act.
import type { LiveDecisionResult, LiveTaskRead } from '@/api/types';

export type Verdict = 'approve' | 'return' | 'reject';
export type Packet = NonNullable<LiveTaskRead['invoice_packet']>;
export type WorkState = LiveDecisionResult['work_state'];

export const NOTE_MAX = 2000;

/** "₦4,250,000.00", or "USD 1,200.00"; null when the packet or its amount is absent or unreadable (INV-UNKNOWN: never 0). */
export function formatAmount(packet: Pick<Packet, 'amount' | 'currency'> | null | undefined): string | null {
  if (!packet?.amount) return null;
  const match = /^(-?)(\d+)\.(\d{2})$/.exec(packet.amount);
  if (!match) return null;
  const [, sign, whole, cents] = match;
  const grouped = whole.replace(/\B(?=(\d{3})+(?!\d))/g, ',');
  const prefix = packet.currency === 'NGN' ? '₦' : `${packet.currency} `;
  return `${sign}${prefix}${grouped}.${cents}`;
}

/** "finance_reviewer" as words for a sentence: the API's role key with the underscores taken out. */
export const roleWords = (role: string) => role.replace(/_/g, ' ');

/** The first eight characters of a checksum: technical detail, never the lead. */
export const shortHash = (sha256: string) => sha256.slice(0, 8);

export const VERDICT_WORDS: Record<Verdict, { button: string; busy: string; eyebrow: string; heading: (label: string) => string }> = {
  approve: { button: 'Approve', busy: 'Approving…', eyebrow: 'YOU APPROVED', heading: (label) => `${label} is approved` },
  return: { button: 'Return', busy: 'Returning…', eyebrow: 'YOU RETURNED', heading: (label) => `${label} was returned` },
  reject: { button: 'Reject', busy: 'Rejecting…', eyebrow: 'YOU REJECTED', heading: (label) => `${label} was rejected` },
};

/** The work state the decision left the work in, in plain words. */
export const WORK_STATE_WORDS: Record<WorkState, string> = {
  ready: 'Ready',
  waiting: 'Waiting on others',
  action_needed: 'Action needed',
  owner_needed: 'Needs an owner',
  setup_needed: 'Setup needed',
  verified: 'Verified',
  cancelled: 'Cancelled',
  awaiting_reconciliation: 'Waiting to be reconciled',
  followup_needed: 'Follow-up needed',
  processing: 'In progress',
  effect_uncertain: 'Not confirmed',
};

/** A route id as the integer the live API takes; null for anything else ("17x", "-1", "1.5", "0", ""). */
export function liveId(value: string | undefined): number | null {
  if (value === undefined || !/^[1-9]\d*$/.test(value)) return null;
  const id = Number.parseInt(value, 10);
  return Number.isSafeInteger(id) ? id : null;
}
