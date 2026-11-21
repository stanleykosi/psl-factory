// SCR-03 states other than the default board: not open here, cannot act (read-only), stale and done.
import Image from 'next/image';
import Link from 'next/link';
import { useEffect, useRef, useState, type ReactNode } from 'react';

import { api, call } from '@/api/client';
import type { DecideResult, TaskDecision, WorkItem, WorkTask } from '@/api/types';
import { Button, buttonClass, Callout, EmptyState, formatClock, formatWeekdayDayTime, Panel, Tag, TextArea, Unknown, useIsPhone, useToastWhen } from '@/components';
import { FactsStrip } from '@/features/work-item/WorkItemOverview';
import { FACTS } from '@/features/work-item/labels';
import { presentationOf } from '@/features/work-item/presentation';

import { AmountValue, ApprovalChain, DecideHeader, When } from './DecisionContent';
import { AGENT_NAMES, channelWords, formatAmount, VERDICT_WORDS, type Asked, type CannotActReason, type Verdict } from './format';
import type { DecidePresentation } from './presentation';

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
      {/* the shared Callout as the boards set it: running text with no icon (block flow, see decide.css); the wrapper
          announces it, as the page changed under the reader */}
      <div role="alert">
        <Callout kind="warning" icon={false} plain className="decide-stale__notice">
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
        </Callout>
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

/* A warning Callout has no live role (D-92), so these notices sit in an alert: they answer the person's press. */
export function UncertainNotice() {
  return (
    <div role="alert">
      <Callout kind="warning">We couldn&rsquo;t confirm your decision. We&rsquo;ve reloaded this item so you can see whether it was recorded.</Callout>
    </div>
  );
}

type DoneProps = {
  id: string;
  item: WorkItem;
  result: DecideResult;
  label: string;
  note?: string;
  reloaded: WorkItem | null;
  refreshFailed: boolean;
  view?: DecidePresentation;
};

/** An echo other than the three verdicts gets neutral words: the page never claims a decision it wasn't told. */
const RECORDED = { eyebrow: 'DECISION RECORDED', heading: (label: string) => `Decision recorded on ${label}` };

/** The person's other waiting decisions: the same read My work uses for Needs me. Null until read, and when the read fails (nothing is claimed then). */
type Waiting = { id: string; title: string }[] | null;
const SHOWN = 3;

function useWaitingDecisions(currentId: string): Waiting {
  const [waiting, setWaiting] = useState<Waiting>(null);
  useEffect(() => {
    let live = true;
    call(api.GET('/api/v1/work', { params: { query: { queue: 'needs_me', limit: 50 } } }))
      .then((data) => {
        if (!live || !Array.isArray(data.items)) return;
        setWaiting(data.items.filter((w) => w.kind === 'decide' && w.id !== currentId).map(({ id, title }) => ({ id, title })));
      })
      .catch(() => {});
    return () => {
      live = false;
    };
  }, [currentId]);
  return waiting;
}

/** "Sat 21 Nov, 12:20 WAT": the summary box's day and time. */
const decidedAt = (at: string) => formatWeekdayDayTime(at).replace(/ (\d\d:\d\d)$/, ', $1 WAT');

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="decide-sum__row">
      <dt>{label}</dt>
      <dd>{children}</dd>
    </div>
  );
}

// SCR-03-done-concepts, concept B: the banner, then the record (facts and summary) beside the "what happens next" panel.
// The DOM runs record then panel; on phones decide.css orders it banner, panel, facts, summary, still waiting.
export function DoneView({ id, item, result, label, note, reloaded, refreshFailed, view }: DoneProps) {
  const known = Object.hasOwn(VERDICT_WORDS, result.verdict);
  const words = known ? VERDICT_WORDS[result.verdict as Verdict] : RECORDED;
  // An effect that could not be confirmed (the decide answered effect_uncertain, or the reloaded item awaits a reconcile) is never shown
  // as an outcome: no approved banner and no next-step claim, whatever the line.
  const uncertain = (result as { work_state?: string }).work_state === 'effect_uncertain' || reloaded?.state === 'effect_uncertain' || Boolean(reloaded?.reconcile);
  const approved = known && result.verdict === 'approve' && !uncertain;
  useToastWhen(uncertain ? null : 'Your decision was recorded.');
  const facts = presentationOf(reloaded ?? item);
  const waiting = useWaitingDecisions(id);
  // the agent's working pose beside the next step (public/agents/<agent>-working.png)
  const agent = (reloaded ?? item).agent.name?.toLowerCase();
  const image = agent && ['tola', 'chidi', 'zainab'].includes(agent) ? `/agents/${agent}-working.png` : undefined;
  // Paid is its own hint under the summary, never inside the next step
  const nextStep = reloaded?.next_step.replace(/\s*Paid is tracked separately[^.]*\.?/, '');
  const decision = known ? (result.verdict === 'approve' ? 'Approve' : result.verdict === 'return' ? 'Return' : 'Reject') : 'Decision recorded';
  const youDecided = uncertain ? `${decision}, result not confirmed` : note ? `${decision}, with the note “${note}”` : known ? `${decision}, with no note` : decision;
  const next = waiting?.[0];
  return (
    <>
      <DecideHeader
        item={item}
        banner={approved ? 'success' : 'neutral'}
        eyebrow={
          <>
            {uncertain ? 'NOT CONFIRMED' : words.eyebrow} · <time dateTime={result.decided_at}>{formatClock(result.decided_at)}</time>
          </>
        }
        title={uncertain ? `${label}: result not confirmed` : words.heading(view?.client ? `${label} for ${view.client}` : label)}
        focusHeading
      />
      <div className="decide-done">
        {uncertain && <UncertainNotice />}
        {refreshFailed && (
          <div role="alert">
            <Callout kind="warning">We couldn&rsquo;t refresh this item. Open the work item to see the latest.</Callout>
          </div>
        )}
        <div className="decide-done__cols">
          <div className="decide-done__record">
            {reloaded && <FactsStrip facts={reloaded.facts} details={facts?.facts} tones={facts?.fact_tones} paidNote={false} />}
            <dl className="decide-sum" aria-label="Summary">
              <Row label="Work">
                {item.reference} · {item.line}
              </Row>
              {view?.subject && <Row label="Project">{view.subject}</Row>}
              <Row label="You decided">{youDecided}</Row>
              <Row label="Decided">
                <time dateTime={result.decided_at}>{decidedAt(result.decided_at)}</time>, by {result.decided_by}
              </Row>
            </dl>
            {approved && <p className="decide-plain decide-paid">Paid is tracked separately by Finance and is not part of this decision.</p>}
          </div>
          <div className="decide-done__side">
            <section className="decide-panel" aria-labelledby="decide-next-head">
              <h2 id="decide-next-head" className="decide-panel__head">
                WHAT HAPPENS NEXT
              </h2>
              {reloaded && !uncertain && (
                <div className={`psl-callout psl-callout--${approved ? 'success' : 'info'} decide-next`}>
                  {image && <Image className="decide-next__img" src={image} alt="" width={64} height={91} unoptimized />}
                  <p className="decide-plain">
                    <strong>Next step.</strong> {nextStep}
                  </p>
                </div>
              )}
              <p className="decide-links">
                {next && (
                  <Link className={buttonClass('dark', 'lg')} href={workHref(next.id)}>
                    Next decision · 1 of {waiting.length}
                  </Link>
                )}
                <Link className={buttonClass('secondary', 'lg')} href={workHref(id)}>
                  Open the work item
                </Link>
              </p>
            </section>
            {waiting && (
              <section className="decide-still" aria-labelledby="decide-still-head">
                <h2 id="decide-still-head" className="decide-still__head">
                  {waiting.length === 0 ? 'ALL CAUGHT UP' : `STILL WAITING ON YOU · ${waiting.length}`}
                </h2>
                {waiting.length === 0 ? (
                  <p className="decide-plain">
                    You&rsquo;re all caught up. <Link href="/my-work">Back to my work</Link>
                  </p>
                ) : (
                  <>
                    <ul>
                      {waiting.slice(0, SHOWN).map((w) => (
                        <li key={w.id}>
                          <Link href={workHref(w.id)}>{w.title}</Link>
                        </li>
                      ))}
                    </ul>
                    {waiting.length > SHOWN && (
                      <p className="decide-plain">
                        <Link href="/my-work">See all</Link>
                      </p>
                    )}
                  </>
                )}
              </section>
            )}
          </div>
        </div>
      </div>
    </>
  );
}
