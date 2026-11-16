// Tag and StateTag (design/system/project/components/StateTag, CMP-05). Five colour families only, each with one
// meaning; the words are always there, so colour is never the only signal. StateTag names a work item's state in
// the factory's own words (README "Content fundamentals"), one colour per state everywhere.
import type { ReactNode } from 'react';

import type { operations } from '@/api/schema';

import { cx } from './internal';

/** person: a person must act · waiting: on someone else · agent: agent or processing work only · done: done or
 *  verified · neutral: closed, not applicable, information, people and role labels. */
export type TagTone = 'person' | 'waiting' | 'agent' | 'done' | 'neutral';

export function Tag({ tone, children, pulse = false, className }: {
  tone: TagTone;
  /** The words; required, never only a colour. */
  children: ReactNode;
  /** The small pulsing square of a WORKING agent tag (stops when motion is reduced). */
  pulse?: boolean;
  className?: string;
}) {
  return (
    <span className={cx('psl-tag', `psl-tag--${tone}`, className)}>
      {pulse && <span className="psl-pulse psl-now" aria-hidden="true" />}
      {children}
    </span>
  );
}

export type Priority = 'high' | 'medium' | 'low';

const PRIORITY: Record<Priority, { marker: string; text: string }> = {
  high: { marker: '■■■', text: 'High' },
  medium: { marker: '■■□', text: 'Medium' },
  low: { marker: '■□□', text: 'Low' },
};

/** Priority is a grey tag with a mono marker, never a status colour. */
export function PriorityTag({ priority }: { priority: Priority }) {
  const { marker, text } = PRIORITY[priority];
  return (
    <span className="psl-tag psl-tag--neutral">
      <span className="psl-prio" aria-hidden="true">
        {marker}
      </span>
      {text}
    </span>
  );
}

type ContractState = operations['E-WORK-ITEM']['responses'][200]['content']['application/json']['state'];

/** The contract's work states plus the two README states the contract does not carry yet. */
export type FactoryState = ContractState | 'awaiting_finance_decision' | 'cancellation_requested';

/** The state words and their one colour family, as the StateTag page lists them: Ready to continue is orange (a
 *  person must act, as the boards draw it); Effect uncertain is amber (waiting) everywhere (D-92b); green is for
 *  verified outputs only. */
export const STATE_TAGS: Record<FactoryState, { text: string; tone: TagTone }> = {
  ready: { text: 'Ready to continue', tone: 'person' },
  processing: { text: 'Processing', tone: 'agent' },
  waiting: { text: 'Waiting', tone: 'waiting' },
  awaiting_finance_decision: { text: 'Awaiting Finance decision', tone: 'person' },
  owner_needed: { text: 'Owner needed', tone: 'person' },
  setup_needed: { text: 'Setup needed', tone: 'person' },
  action_needed: { text: 'Action needed', tone: 'person' },
  effect_uncertain: { text: 'Effect uncertain', tone: 'waiting' },
  awaiting_reconciliation: { text: 'Awaiting reconciliation', tone: 'waiting' },
  verified: { text: 'Verified', tone: 'done' },
  cancellation_requested: { text: 'Cancellation requested', tone: 'waiting' },
  cancelled: { text: 'Cancelled', tone: 'neutral' },
  followup_needed: { text: 'Stopped: invoice follow-up needed', tone: 'person' },
};

export function StateTag({ state, className }: { state: FactoryState; className?: string }) {
  const { text, tone } = STATE_TAGS[state];
  return (
    <Tag tone={tone} className={className}>
      {text}
    </Tag>
  );
}
