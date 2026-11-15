// FactsStrip (design/system/project/components/FactsStrip, CMP-04): the six facts, each in its own box, so nobody
// mistakes a draft for an approval. Earned: ink with the date. Current: signal-tint. Not yet: blank. Verified:
// verified fill. A fact the record does not carry is Unknown (amber), never blank or 0. Paid is a Finance fact and
// sits apart, in the note under the strip. As the work-item overview draws it, the boxes are one list for screen
// readers, and each box's state is in its words.
import type { ReactNode } from 'react';

import { cx } from './internal';

export type FactName = 'drafted' | 'reviewed' | 'approved' | 'sent' | 'receipt_recorded' | 'verified';
export type FactStatus = 'earned' | 'current' | 'not_yet' | 'unknown';
export type FactValue = { status: FactStatus; /** The date earned ("10 Nov"), or what the current one needs ("Needs you"). */ text?: string };

export const FACT_LABELS: Record<FactName, string> = {
  drafted: 'DRAFTED',
  reviewed: 'REVIEWED',
  approved: 'APPROVED',
  sent: 'SENT',
  receipt_recorded: 'RECEIPT RECORDED',
  verified: 'VERIFIED',
};

const ORDER = Object.keys(FACT_LABELS) as FactName[];
const WORDS: Record<FactStatus, string> = { earned: 'Earned', current: 'In progress', not_yet: 'Not yet', unknown: 'Unknown' };

function boxClass(name: FactName, status: FactStatus): string {
  if (status === 'earned') return name === 'verified' ? 'psl-fact psl-fact--verified' : 'psl-fact psl-fact--earned';
  if (status === 'current') return 'psl-fact psl-fact--current';
  if (status === 'unknown') return 'psl-fact psl-fact--unknown';
  return 'psl-fact';
}

export function FactsStrip({ facts, paidNote = 'Paid is tracked by Finance on the receipt, not here.', label = 'Facts earned', className }: {
  /** A fact missing from the record reads Unknown. */
  facts: Partial<Record<FactName, FactValue>>;
  /** The line under the strip that keeps paid apart; null where the screen says it elsewhere. */
  paidNote?: ReactNode | null;
  label?: string;
  className?: string;
}) {
  return (
    <div className={className}>
      <div className="psl-facts" role="list" aria-label={label}>
        {ORDER.map((name) => {
          const fact = facts[name] ?? { status: 'unknown' as const };
          const shown = fact.status === 'unknown' ? 'Unknown' : fact.status === 'not_yet' ? 'Not yet' : (fact.text ?? WORDS[fact.status]);
          const said = fact.status === 'earned' || fact.status === 'current' ? `${WORDS[fact.status]}: ` : '';
          return (
            <div key={name} role="listitem" className={boxClass(name, fact.status)}>
              <b>{FACT_LABELS[name]}</b>
              <strong>
                {said && fact.text && <span className="cmp-sr">{said}</span>}
                {shown}
              </strong>
            </div>
          );
        })}
      </div>
      {paidNote && <p className={cx('psl-doesnt', 'cmp-paidnote')}>{paidNote}</p>}
    </div>
  );
}
