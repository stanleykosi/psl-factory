// SCR-03 states other than the default board: not open here, cannot act (read-only), stale and done.
import Image from 'next/image';
import Link from 'next/link';
import { useEffect, useRef, type ReactNode } from 'react';

import type { DecideResult, TaskDecision, WorkItem, WorkTask } from '@/api/types';
import { Button, buttonClass, Callout, EmptyState, formatClock, Panel, Tag, TextArea, Unknown, useIsPhone } from '@/components';
import { FactsStrip } from '@/features/work-item/WorkItemOverview';
import { FACTS } from '@/features/work-item/labels';
import { presentationOf } from '@/features/work-item/presentation';

import { AmountValue, ApprovalChain, DecideHeader, When } from './DecisionContent';
import { AGENT_NAMES, channelWords, formatAmount, VERDICT_WORDS, type Asked, type CannotActReason, type Verdict } from './format';
import { nextDecision, type DecidePresentation } from './presentation';

const workHref = (id: string) => `/work/${encodeURIComponent(id)}`;

export function NotOpenState({ id }: { id: string }) {
  return (
    <EmptyState title="This decision isn&rsquo;t open here">
      It may have been decided, withdrawn or moved. The work item shows where things stand.
      <br />
      <Link href={workHref(id)}>Open the work item</Link>
    </EmptyState>
  );
}

type Copy = { eyebrow: string; heading: string; text?: string };

/** Copy keyed on cannot_act_reason only; no reason (or a 403 on a write) gets the generic copy. */
export function cannotActCopy(reason: CannotActReason | undefined, task: WorkTask & { decision: TaskDecision }): Copy {
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
      {/* the SCR-03 boards write the time alone and end the sentence: "alerted at 10:42 by WhatsApp and email." */}
      {who} was alerted at <time dateTime={person.alerted_at}>{formatClock(person.alerted_at)}</time>
      {channels}.
    </li>
  );
}

function AskedList({ asked }: { asked: Asked[] }) {
  return (
    <div className="decide-asked">
      <h3 className="cmp-sr">Asked</h3>
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
  );
}

/**
 * The not-yours board's comment box, only when the board block carries it. No endpoint takes comments, so the box
 * and its button are disabled and say so; nothing here is ever sent.
 */
function CommentBox({ comment }: { comment: NonNullable<DecidePresentation['comment']> }) {
  return (
    <div className="decide-comment">
      <TextArea id="decide-comment" label={comment.label} hint="Comments aren’t available yet." value="" disabled onChange={() => {}} />
      <p className="decide-comment__action">
        <Button kind="secondary" size="lg" block disabled aria-describedby="decide-comment-message">
          {comment.action}
        </Button>
      </p>
    </div>
  );
}

function PreparedBy({ by }: { by: NonNullable<TaskDecision['prepared_by']> }) {
  return (
    <>
      {by.is_you ? 'You' : by.role ? `${by.name} (${by.role})` : by.name}
      {by.with_agent && ` with ${AGENT_NAMES[by.with_agent]}`}
    </>
  );
}

/** An amount as the box's own text (the boards' value cells); unknown or absent reads Unknown (INV-UNKNOWN). */
function AmountText({ amount }: { amount: NonNullable<TaskDecision['amount']> }) {
  const text = formatAmount(amount);
  return text === null ? <Unknown /> : <>{text}</>;
}

type CannotActProps = { id: string; task: WorkTask & { decision: TaskDecision }; facts: WorkItem['facts']; view?: DecidePresentation };

const FACT_WORD: Record<WorkItem['facts'][number]['status'], string> = { earned: 'Earned', current: 'In progress', not_yet: '—', unknown: 'Unknown' };

/** SCR-03-mobile-not-yours: the last three facts under the decision boxes (phones only); an absent fact reads Unknown. */
function PhoneFacts({ facts }: { facts: WorkItem['facts'] }) {
  return FACTS.slice(3).map(({ name, label, more }) => {
    const status = facts.find((f) => f.name === name)?.status ?? 'unknown';
    return (
      <div key={name} className="decide-strip__box decide-strip__box--phone">
        <dt>
          {label}
          {more && <span className="cmp-sr">{more}</span>}
        </dt>{' '}
        <dd>
          {FACT_WORD[status]}
          {status === 'not_yet' && <span className="cmp-sr"> Not yet</span>}
        </dd>
      </div>
    );
  });
}

/**
 * Read-only. The own board (prepared_by_you): the version card, then the review card with who was asked. Every other
 * reason follows the not-yours board: amount, basis and who it waits for as boxes, then the card with the copy, who
 * was alerted and the (disabled) comment box. The approval chain follows the board content.
 */
export function CannotActView({ id, task, facts, view }: CannotActProps) {
  const copy = cannotActCopy(task.cannot_act_reason, task);
  const asked = task.asked ?? [];
  const { amount, basis, prepared_by: by, version } = task.decision;
  const open = (
    <p className="decide-plain decide-open">
      <Link href={workHref(id)}>Open the work item</Link>
    </p>
  );
  if (task.cannot_act_reason === 'prepared_by_you') {
    return (
      <div className="decide-own">
        <Panel
          className="decide-own__version"
          head={
            <>
              {version.label}
              {amount && (
                <>
                  {' · '}
                  <AmountText amount={amount} />
                </>
              )}
            </>
          }
        >
          <dl className="decide-own__rows">
            {/* the board's first row: "Contract amount · <basis>" with the amount at the end */}
            {amount ? (
              <div>
                <dt>Amount{basis && ` · ${basis}`}</dt>{' '}
                <dd>
                  <AmountText amount={amount} />
                </dd>
              </div>
            ) : (
              basis && (
                <div>
                  <dt>Basis</dt>{' '}
                  <dd>{basis}</dd>
                </div>
              )
            )}
            {by && (
              <div>
                <dt>Prepared by</dt>{' '}
                <dd>
                  <PreparedBy by={by} />
                </dd>
              </div>
            )}
          </dl>
        </Panel>
        {/* the boards draw this card as the page's side panel, so it stays an aside (Panel is a section) */}
        <aside className="psl-panel decide-own__review" aria-labelledby="decide-readonly-title">
          <p className="psl-panel__head">Waiting · {task.required_role}</p>
          <div className="psl-panel__body">
            <Callout kind="info" announce={false}>
              <h2 id="decide-readonly-title" className="decide-callout-text">
                {copy.heading}
              </h2>
            </Callout>
            <AskedList asked={asked} />
            {open}
          </div>
        </aside>
        <div className="decide-own__chain">
          <ApprovalChain chain={task.decision.chain} />
        </div>
      </div>
    );
  }
  return (
    <div className={`decide-readonly${view?.comment ? ' decide-readonly--comment' : ''}`}>
      <dl className="decide-strip" aria-label="Decision">
        {amount && (
          <div className="decide-strip__box decide-strip__box--strong">
            <dt>Amount</dt>
            <dd>
              <AmountText amount={amount} />
            </dd>
          </div>
        )}
        {basis && (
          <div className="decide-strip__box">
            <dt>Basis</dt>
            <dd>{basis}</dd>
          </div>
        )}
        <div className="decide-strip__box decide-strip__box--waiting">
          <dt>Waiting for</dt>{' '}
          <dd>{task.required_role}</dd>
        </div>
        <PhoneFacts facts={facts} />
      </dl>
      <section className="decide-card" aria-labelledby="decide-readonly-title">
        <Tag tone="neutral" className="decide-tag">
          {copy.eyebrow}
        </Tag>
        <div className="decide-lead">
          <h2 id="decide-readonly-title" className="decide-lead__head">
            {copy.heading}
          </h2>{' '}
          {copy.text && <p className="decide-plain">{copy.text}</p>}
        </div>
        <AskedList asked={asked} />
        {view?.comment && <CommentBox comment={view.comment} />}
        {open}
      </section>
      <ApprovalChain chain={task.decision.chain} />
    </div>
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
  // Amount first, then what changed, then what did not (the stale boards list the changed row second).
  const rank = (row: Compared) => (row.label === 'Amount' ? 0 : row.mark === 'changed' ? 1 : 2);
  return rows.map((row, i) => ({ row, i })).sort((a, b) => rank(a.row) - rank(b.row) || a.i - b.i).map(({ row }) => row);
}

type StaleProps = { replaced: TaskDecision; current: TaskDecision; agent?: ReactNode; onReview: () => void };

/** The replaced and current versions side by side (a table on desktop, stacked cards on phones), each current value marked. */
export function StaleView({ replaced, current, agent, onReview }: StaleProps) {
  const rows = compareRows(replaced, current);
  const oldN = replaced.version.number;
  const newN = current.version.number;
  const rowClass = (row: Compared) => `decide-row${row.mark === 'changed' ? ' decide-row--changed' : ''}`;
  const phone = useIsPhone();
  const head = useRef<HTMLHeadingElement>(null);
  // the page changed under the reader: move focus to what happened (the alert also announces it)
  useEffect(() => head.current?.focus(), []);
  return (
    <section className="decide-stale" aria-labelledby="decide-stale-title">
      {/* written out: the boards set this notice as running text with no icon (block flow, see decide.css) */}
      <div className="psl-callout psl-callout--warning decide-stale__notice" role="alert">
        <h2 id="decide-stale-title" ref={head} tabIndex={-1} className="decide-stale__head">
          A newer version arrived while you were reading.
        </h2>{' '}
        <p className="decide-plain">
          {current.version.drafted_at && (
            <>
              Version {newN} was drafted at <When at={current.version.drafted_at} />.{' '}
            </>
          )}
          Version {oldN} can no longer be approved.
        </p>
      </div>
      <div className="decide-compare">
        <section className="decide-compare__old" aria-labelledby="decide-old-title">
          <h3 id="decide-old-title" className="decide-colhead">
            VERSION {oldN} · REPLACED
          </h3>
          <dl className="decide-rows">
            {rows.map((row) => (
              <div key={row.label} className={rowClass(row)}>
                <dt>{row.label}</dt>
                <dd>{row.old}</dd>
              </div>
            ))}
          </dl>
        </section>
        <section className="decide-compare__new" aria-labelledby="decide-new-title">
          <h3 id="decide-new-title" className="decide-colhead">
            VERSION {newN} · CURRENT
          </h3>
          <dl className="decide-rows">
            {rows.map((row) => (
              <div key={row.label} className={rowClass(row)}>
                <dt>{row.label}</dt>
                <dd>
                  {row.now} <span className={row.mark === 'changed' ? 'decide-changed' : 'decide-muted'}>· {row.mark}</span>
                </dd>
              </div>
            ))}
          </dl>
          {current.changes && current.changes.items.length > 0 && (
            <div className="decide-compare__changes">
              <h4 className="decide-h3">Changed since {current.changes.previous_label}:</h4>{' '}
              <ul className="decide-list">
                {current.changes.items.map((change, i) => (
                  <li key={i}>{change}</li>
                ))}
              </ul>
            </div>
          )}
          {phone && agent}
        </section>
      </div>
      {!phone && agent}
      <div className="decide-stale__foot">
        <p className="decide-stale__action">
          <Button size="lg" block onClick={onReview}>
            Review version {newN}
          </Button>
        </p>
        <p className="psl-doesnt">Decisions always apply to one exact version, so an approval can never land on the wrong one.</p>
      </div>
    </section>
  );
}

type DoneProps = {
  id: string;
  item: WorkItem;
  result: DecideResult;
  label: string;
  reloaded: WorkItem | null;
  refreshFailed: boolean;
  view?: DecidePresentation;
};

/** An echo other than the three verdicts gets neutral words: the page never claims a decision it wasn't told. */
const RECORDED = { eyebrow: 'DECISION RECORDED', heading: (label: string) => `Decision recorded on ${label}` };

// The next-step card is the callout's markup written out: the boards draw Chidi's pose where the callout has its icon.
export function DoneView({ id, item, result, label, reloaded, refreshFailed, view }: DoneProps) {
  const known = Object.hasOwn(VERDICT_WORDS, result.verdict);
  const words = known ? VERDICT_WORDS[result.verdict as Verdict] : RECORDED;
  const approved = known && result.verdict === 'approve';
  const next = nextDecision(view);
  const facts = presentationOf(reloaded ?? item);
  // the done boards draw Chidi's thumbs-up pose (public/agents/chidi-done.png); other agents keep their avatar
  const agentName = (reloaded ?? item).agent.name;
  const image = agentName?.toLowerCase() === 'chidi' ? '/agents/chidi-done.png' : undefined;
  // desktop draws Paid once, inside the next-step card; the phone board draws it as its own line
  const phone = useIsPhone();
  const showPaid = approved && (phone || !reloaded?.next_step.includes('Paid is tracked separately'));
  // on the phone the sentence is the separate line, so the card text stops before it
  const nextStep = phone && approved && reloaded ? reloaded.next_step.replace(/\s*Paid is tracked separately[^.]*\.?/, '') : reloaded?.next_step;
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
        title={words.heading(view?.client ? `${label} for ${view.client}` : label)}
        focusHeading
      />
      <p className="cmp-sr" role="status">
        Your decision was recorded.
      </p>
      <div className="decide-done">
        {refreshFailed && (
          <Callout kind="warning">We couldn&rsquo;t refresh this item. Open the work item to see the latest.</Callout>
        )}
        {reloaded && <FactsStrip facts={reloaded.facts} details={facts?.facts} tones={facts?.fact_tones} paidNote={false} />}
        <div className="decide-done__row">
          {reloaded && (
            <div className={`psl-callout psl-callout--${approved ? 'success' : 'info'} decide-next`}>
              {image && <Image className="decide-next__img" src={image} alt="" width={96} height={136} unoptimized />}
              <p className="decide-plain">
                <strong>Next step.</strong> {nextStep}
              </p>
            </div>
          )}
          <p className="decide-links">
            {next && (
              <Link className={buttonClass('dark', 'lg')} href={next.href}>
                {next.label}
              </Link>
            )}
            <Link className={buttonClass('secondary', 'lg')} href={workHref(id)}>
              Open the work item
            </Link>
          </p>
        </div>
        {showPaid && <p className="decide-plain decide-paid">Paid is tracked separately by Finance and is not part of this decision.</p>}
        <p className="decide-plain decide-back">
          <Link href="/my-work">Back to my work</Link>
        </p>
        <p className="decide-plain decide-done__by">Decided by {result.decided_by}</p>
      </div>
    </>
  );
}
