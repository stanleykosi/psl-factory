// FactsStrip (design/system/project/components/FactsStrip, CMP-04): the six facts, each in its own box, so nobody
// mistakes a draft for an approval. Earned: ink with the time ("12 Nov 16:40"). Current: signal-tint. Not yet:
// blank, with "—" as the boards draw it (D-93) and "Not yet" for screen readers. Verified: verified fill. A fact
// the record does not carry is Unknown (amber), never blank or 0. Paid is a Finance fact and sits apart, in the
// note under the strip. The boxes are one list for screen readers, and each box's state is in its words; where a
// board writes its own words in a box ("Needs you"), the state word stays in the accessible text beside them.
import type { ReactNode } from 'react';

import { formatDayTime } from './format';
import { cx } from './internal';

export type FactName = 'drafted' | 'reviewed' | 'approved' | 'sent' | 'receipt_recorded' | 'verified';
export type FactStatus = 'earned' | 'current' | 'not_yet' | 'unknown';
export type FactValue = {
  status: FactStatus;
  /** The board's words for the box ("10 Nov", "Needs you"); the state word otherwise. */
  text?: string;
  /** When an earned fact was earned (ISO); shown as "12 Nov 16:40" under "Earned". */
  at?: string | null;
  /** The board's tint on a fact that has not happened: amber (waiting) or orange (a person must act). */
  tone?: 'waiting' | 'signal';
};

/** The boards' box words; RECEIPT is RECEIPT RECORDED for screen readers. */
export const FACT_LABELS: Record<FactName, { label: string; more?: string }> = {
  drafted: { label: 'DRAFTED' },
  reviewed: { label: 'REVIEWED' },
  approved: { label: 'APPROVED' },
  sent: { label: 'SENT' },
  receipt_recorded: { label: 'RECEIPT', more: ' RECORDED' },
  verified: { label: 'VERIFIED' },
};

const ORDER = Object.keys(FACT_LABELS) as FactName[];
const WORDS: Record<FactStatus, string> = { earned: 'Earned', current: 'In progress', not_yet: 'Not yet', unknown: 'Unknown' };

function boxClass(name: FactName, { status, tone }: FactValue): string {
  if (status === 'not_yet' && tone) return tone === 'waiting' ? 'psl-fact psl-fact--unknown' : 'psl-fact psl-fact--current';
  if (status === 'earned') return name === 'verified' ? 'psl-fact psl-fact--verified' : 'psl-fact psl-fact--earned';
  if (status === 'current') return 'psl-fact psl-fact--current';
  if (status === 'unknown') return 'psl-fact psl-fact--unknown';
  return 'psl-fact';
}

function Value({ fact }: { fact: FactValue }) {
  if (fact.text && fact.status !== 'unknown') {
    return (
      <>
        <span className="cmp-sr">{WORDS[fact.status]}: </span>
        <strong>{fact.text}</strong>
      </>
    );
  }
  if (fact.status === 'earned') {
    return (
      <>
        <strong>Earned</strong>
        {fact.at && <time dateTime={fact.at}>{formatDayTime(fact.at)}</time>}
      </>
    );
  }
  if (fact.status === 'not_yet') {
    return (
      <>
        <strong>—</strong>
        <span className="cmp-sr">Not yet</span>
      </>
    );
  }
  return <strong>{WORDS[fact.status]}</strong>;
}

export function FactsStrip({ facts, paidNote = 'Paid is tracked by Finance on the receipt, not here.', paidNoteClassName, label = 'Facts earned', className }: {
  /** A fact missing from the record reads Unknown. */
  facts: Partial<Record<FactName, FactValue>>;
  /** The line under the strip that keeps paid apart; null where the screen says it elsewhere. */
  paidNote?: ReactNode | null;
  paidNoteClassName?: string;
  label?: string;
  className?: string;
}) {
  return (
    <div className={className}>
      <div className="psl-facts" role="list" aria-label={label}>
        {ORDER.map((name) => {
          const fact = facts[name] ?? { status: 'unknown' as const };
          const { label: word, more } = FACT_LABELS[name];
          return (
            <div key={name} role="listitem" className={boxClass(name, fact)}>
              <b>{word}</b>
              {more && <span className="cmp-sr">{more}</span>}
              <Value fact={fact} />
            </div>
          );
        })}
      </div>
      {paidNote && <p className={paidNoteClassName ?? cx('psl-doesnt', 'cmp-paidnote')}>{paidNote}</p>}
    </div>
  );
}
