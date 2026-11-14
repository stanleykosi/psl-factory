// SCR-03 states other than the default board: not open here, cannot act (read-only), stale and done.
import Link from 'next/link';
import type { ReactNode } from 'react';

import type { DecideResult, TaskDecision, WorkItem, WorkTask } from '@/api/types';
import { FactsStrip } from '@/features/work-item/WorkItemOverview';
import { WarningIcon } from '@/shell/icons';

import { AmountValue, ApprovalChain, DecideHeader, DecisionRows, When } from './DecisionContent';
import { channelWords, formatAmount, formatClock, VERDICT_WORDS, type Asked, type CannotActReason, type Verdict } from './format';

const workHref = (id: string) => `/work/${encodeURIComponent(id)}`;

export function NotOpenState({ id }: { id: string }) {
  return (
    <div className="psl-empty">
      <h2 className="decide-h2">This decision isn&rsquo;t open here</h2>
      <p>It may have been decided, withdrawn or moved. The work item shows where things stand.</p>
      <p>
        <Link href={workHref(id)}>Open the work item</Link>
      </p>
    </div>
  );
}

type Copy = { eyebrow: string; heading: string; text?: string };

/** Copy keyed on cannot_act_reason only; no reason (or a 403 on a write) gets the generic copy. */
function cannotActCopy(reason: CannotActReason | undefined, task: WorkTask & { decision: TaskDecision }): Copy {
  switch (reason) {
    case 'not_your_role':
      return {
        eyebrow: 'NOT YOUR DECISION',
        heading: `This decision needs a ${task.required_role}.`,
        text: 'You can read it, but you can’t approve, return or reject it.',
      };
    case 'prepared_by_you':
      return { eyebrow: 'WAITING FOR REVIEW', heading: `You prepared ${task.decision.version.label}, so someone else must review it.` };
    case 'already_decided':
      return {
        eyebrow: 'ALREADY DECIDED',
        heading: 'This decision has already been made.',
        text: 'Nothing more is needed from you here. The work item shows what happens next.',
      };
    case 'not_your_turn': {
      const current = task.decision.chain.steps.find((s) => s.status === 'current');
      return {
        eyebrow: 'NOT YOUR TURN YET',
        heading: current ? `This needs ${current.role} first.` : 'This needs earlier approvals first.',
        text: 'You’ll be asked when it’s your turn.',
      };
    }
    default:
      return {
        eyebrow: 'NOT YOUR DECISION',
        heading: `This decision needs a ${task.required_role}.`,
        text: 'You can’t approve, return or reject it.',
      };
  }
}

function AskedLine({ person }: { person: Asked }) {
  const who = `${person.name} (${person.role})`;
  if (!person.alerted_at) return <li>{who} has been asked.</li>;
  const channels = person.channels?.length ? ` by ${channelWords(person.channels)}` : '';
  return (
    <li>
      {who} was alerted at <When at={person.alerted_at} />
      {channels}
    </li>
  );
}

export function CannotActView({ id, task }: { id: string; task: WorkTask & { decision: TaskDecision } }) {
  const copy = cannotActCopy(task.cannot_act_reason, task);
  const asked = task.asked ?? [];
  return (
    <section className="psl-panel psl-panel--readonly decide-readonly" aria-labelledby="decide-readonly-title">
      <div className="psl-panel__body">
        <span className="psl-tag psl-tag--neutral decide-tag">{copy.eyebrow}</span>
        <h2 id="decide-readonly-title" className="decide-h2">
          {copy.heading}
        </h2>
        {copy.text && <p className="decide-plain">{copy.text}</p>}
        <DecisionRows decision={task.decision} only="amount-basis" />
        <p className="decide-plain">
          <strong>Waiting for {task.required_role}</strong>
        </p>
        <ApprovalChain chain={task.decision.chain} />
        <div>
          <h3 className="decide-h3">Asked</h3>
          {asked.length === 0 ? (
            <p className="decide-plain">Nobody has been asked yet.</p>
          ) : (
            <ul className="decide-list">
              {asked.map((person, i) => (
                <AskedLine key={i} person={person} />
              ))}
            </ul>
          )}
        </div>
        <p className="decide-plain">
          <Link href={workHref(id)}>Open the work item</Link>
        </p>
      </div>
    </section>
  );
}

type Compared = { label: string; old: ReactNode; now: ReactNode; mark: string };

function amountText(amount: TaskDecision['amount']): string | null | undefined {
  return amount === undefined ? undefined : formatAmount(amount);
}

const NOT_GIVEN = <span className="decide-muted">Not given</span>;

/** Amount, Basis and Send to, each current value marked against the replaced one; rows absent in both are left out. */
function compareRows(old: TaskDecision, now: TaskDecision): Compared[] {
  const rows: Compared[] = [];
  if (old.amount || now.amount) {
    const before = amountText(old.amount);
    const after = amountText(now.amount);
    // Unknown is not a value, so two unknown amounts are not called unchanged.
    const mark = after === null && before === null ? 'still unknown' : before === after ? 'unchanged' : 'changed';
    rows.push({
      label: 'Amount',
      old: old.amount ? <AmountValue amount={old.amount} /> : NOT_GIVEN,
      now: now.amount ? <AmountValue amount={now.amount} /> : NOT_GIVEN,
      mark,
    });
  }
  for (const [label, key] of [
    ['Basis', 'basis'],
    ['Send to', 'recipient'],
  ] as const) {
    if (!old[key] && !now[key]) continue;
    rows.push({ label, old: old[key] ?? NOT_GIVEN, now: now[key] ?? NOT_GIVEN, mark: old[key] === now[key] ? 'unchanged' : 'changed' });
  }
  return rows;
}

export function StaleView({ replaced, current, onReview }: { replaced: TaskDecision; current: TaskDecision; onReview: () => void }) {
  const rows = compareRows(replaced, current);
  const oldN = replaced.version.number;
  const newN = current.version.number;
  return (
    <section className="decide-stale" aria-labelledby="decide-stale-title">
      <div className="psl-callout psl-callout--warning" role="alert">
        <WarningIcon />
        <div>
          <h2 id="decide-stale-title" className="decide-h2">
            A newer version arrived while you were reading.
          </h2>
          <p className="decide-plain">
            {current.version.drafted_at && (
              <>
                Version {newN} was drafted at <When at={current.version.drafted_at} />.{' '}
              </>
            )}
            Version {oldN} can no longer be approved.
          </p>
        </div>
      </div>
      <div className="decide-compare">
        <section className="psl-panel psl-panel--readonly" aria-labelledby="decide-old-title">
          <h3 id="decide-old-title" className="psl-panel__head decide-colhead">
            VERSION {oldN} · REPLACED
          </h3>
          <dl className="decide-rows psl-panel__body">
            {rows.map((row) => (
              <div key={row.label} className="decide-row">
                <dt>{row.label}</dt>
                <dd>{row.old}</dd>
              </div>
            ))}
          </dl>
        </section>
        <section className="psl-panel" aria-labelledby="decide-new-title">
          <h3 id="decide-new-title" className="psl-panel__head decide-colhead">
            VERSION {newN} · CURRENT
          </h3>
          <div className="psl-panel__body">
            <dl className="decide-rows">
              {rows.map((row) => (
                <div key={row.label} className="decide-row">
                  <dt>{row.label}</dt>
                  <dd>
                    {row.now} <span className={row.mark === 'changed' ? 'decide-changed' : 'decide-muted'}>· {row.mark}</span>
                  </dd>
                </div>
              ))}
            </dl>
            {current.changes && current.changes.items.length > 0 && (
              <div>
                <h4 className="decide-h3">Changed since {current.changes.previous_label}</h4>
                <ul className="decide-list">
                  {current.changes.items.map((change, i) => (
                    <li key={i}>{change}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </section>
      </div>
      <p>
        <button type="button" className="psl-btn psl-btn--lg" onClick={onReview}>
          Review version {newN}
        </button>
      </p>
      <p className="psl-doesnt">Decisions always apply to one exact version, so an approval can never land on the wrong one.</p>
    </section>
  );
}

type DoneProps = { id: string; item: WorkItem; result: DecideResult; label: string; reloaded: WorkItem | null; refreshFailed: boolean };

/** An echo other than the three verdicts gets neutral words: the page never claims a decision it wasn't told. */
const RECORDED = { eyebrow: 'DECISION RECORDED', heading: (label: string) => `Decision recorded on ${label}` };

export function DoneView({ id, item, result, label, reloaded, refreshFailed }: DoneProps) {
  const known = Object.hasOwn(VERDICT_WORDS, result.verdict);
  const words = known ? VERDICT_WORDS[result.verdict as Verdict] : RECORDED;
  const approved = known && result.verdict === 'approve';
  return (
    <>
      <DecideHeader
        item={item}
        banner={approved ? 'success' : 'neutral'}
        eyebrow={
          <>
            {words.eyebrow} · <time dateTime={result.decided_at}>{formatClock(result.decided_at)}</time>
          </>
        }
        title={words.heading(label)}
      />
      <div className="decide-done">
        <p className="decide-plain">Decided by {result.decided_by}</p>
        {refreshFailed && (
          <div className="psl-callout psl-callout--warning" role="alert">
            <WarningIcon />
            <span>We couldn&rsquo;t refresh this item. Open the work item to see the latest.</span>
          </div>
        )}
        {reloaded && (
          <>
            <FactsStrip facts={reloaded.facts} />
            <p className={`psl-callout psl-callout--${approved ? 'success' : 'info'} decide-next`}>
              <span>
                <strong>Next step.</strong> {reloaded.next_step}
              </span>
            </p>
          </>
        )}
        {approved && <p className="decide-plain">Paid is tracked separately by Finance and is not part of this decision.</p>}
        <p className="decide-links">
          <Link className="psl-btn psl-btn--lg" href={workHref(id)}>
            Open the work item
          </Link>
          <Link className="psl-btn psl-btn--secondary psl-btn--lg" href="/my-work">
            Back to my work
          </Link>
        </p>
      </div>
    </>
  );
}
