// SCR-03 states other than the default board: not open here, cannot act (read-only), stale and done. Board parts with
// no live source are left out (D-182): the approval chain, basis, change list, preparer, alert line, reasons and the
// agent's notes.
import Link from 'next/link';
import { useEffect, useRef, useState, type ReactNode } from 'react';

import type { LiveHistoryItem, LiveTaskRead, LiveWork } from '@/api/types';
import { Button, buttonClass, Callout, EmptyState, formatClock, formatWeekdayDayTime, Tag, TextArea, useToastWhen } from '@/components';

import { AmountValue, DecideHeader } from './LiveContent';
import { formatAmount, roleWords, VERDICT_WORDS, WORK_STATE_WORDS, type Verdict, type WorkState } from './liveFormat';
import type { CommentState, QueueEntry, Snapshot } from './useLiveDecision';

const workHref = (id: number | string) => `/work/${encodeURIComponent(String(id))}`;

export function NotOpenState({ id }: { id: string }) {
  return (
    <EmptyState title="This decision isn&rsquo;t open here">
      It may have been decided, withdrawn or moved. The work item shows where things stand.
      <br />
      <Link href={workHref(id)}>Open the work item</Link>
    </EmptyState>
  );
}

/** Not-yours copy: the server gives no reason, so every read-only case gets the same plain sentence. */
export function cannotActCopy(role: string): { eyebrow: string; heading: string; text: string } {
  return { eyebrow: 'NOT YOUR DECISION', heading: `This decision needs a ${roleWords(role)}.`, text: 'You can’t approve, return or reject it.' };
}

const COMMENT_MAX = 2000;

type CommentProps = { role: string; onComment: (body: string) => Promise<boolean>; state: CommentState };

/** The not-yours board's comment box. The server decides who may comment: a 403 takes the box away. */
function CommentBox({ role, onComment, state }: CommentProps) {
  const [text, setText] = useState('');
  const [problem, setProblem] = useState<string | null>(null);
  const busy = state.status === 'busy';
  if (state.status === 'closed') return <p className="decide-plain decide-comment__closed">{state.message}</p>;
  const send = async () => {
    if (busy) return;
    if (text.trim() === '') return setProblem('Write a comment first.');
    if (text.length > COMMENT_MAX) return setProblem(`Keep the comment to ${COMMENT_MAX} characters or fewer.`);
    setProblem(null);
    if (await onComment(text)) setText('');
  };
  return (
    <div className="decide-comment">
      <TextArea
        id="decide-comment"
        label={`Comment for the ${roleWords(role)} (optional)`}
        value={text}
        limit={COMMENT_MAX}
        error={problem ?? undefined}
        disabled={busy}
        onChange={(e) => {
          setText(e.target.value);
          setProblem(null);
        }}
      />
      {state.status === 'error' && <Callout kind="problem">{state.message}</Callout>}
      {state.status === 'uncertain' && (
        <div role="alert">
          <Callout kind="warning">We couldn&rsquo;t confirm your comment. Check whether it was added before you send it again.</Callout>
        </div>
      )}
      {state.status === 'sent' && (
        <p className="psl-hint" role="status">
          Your comment was added.
        </p>
      )}
      <p className="decide-comment__action">
        <Button kind="secondary" size="lg" block busy={busy} busyLabel="Adding…" onClick={() => void send()}>
          Add comment
        </Button>
      </p>
    </div>
  );
}

type CannotActProps = { id: string; read: LiveTaskRead; commentState: CommentState; onComment: (body: string) => Promise<boolean> };

/** Read-only: the amount and who it waits for as boxes, then the card with the plain sentence and the comment box. */
export function CannotActView({ id, read, commentState, onComment }: CannotActProps) {
  const { task, invoice_packet: packet } = read;
  const copy = cannotActCopy(task.role);
  return (
    <div className="decide-readonly decide-readonly--comment">
      <dl className="decide-strip" aria-label="Decision">
        <div className="decide-strip__box decide-strip__box--strong">
          <dt>Amount</dt>
          <dd>
            <AmountValue packet={packet} />
          </dd>
        </div>
        <div className="decide-strip__box decide-strip__box--waiting">
          <dt>Waiting for</dt> <dd>{roleWords(task.role)}</dd>
        </div>
      </dl>
      <section className="decide-card" aria-labelledby="decide-readonly-title">
        <Tag tone="neutral" className="decide-tag">
          {copy.eyebrow}
        </Tag>
        <div className="decide-lead">
          <h2 id="decide-readonly-title" className="decide-lead__head">
            {copy.heading}
          </h2>{' '}
          <p className="decide-plain">{copy.text}</p>
        </div>
        <CommentBox role={task.role} onComment={onComment} state={commentState} />
        <p className="decide-plain decide-open">
          <Link href={workHref(id)}>Open the work item</Link>
        </p>
      </section>
    </div>
  );
}

type Compared = { label: string; old: ReactNode; now: ReactNode; mark: string };

const NOT_GIVEN = <span className="decide-muted">Not given</span>;
const amountText = (s: Snapshot) => formatAmount(s.amount ? { amount: s.amount, currency: s.currency ?? '' } : null);

/** Amount and Send to, each current value marked against the replaced one; the live read has no other rows. */
function compareRows(old: Snapshot, now: Snapshot): Compared[] {
  const before = amountText(old);
  const after = amountText(now);
  // Unknown is not a value, so two unknown amounts are not called unchanged.
  const amountMark = after === null && before === null ? 'still unknown' : before === after ? 'unchanged' : 'changed';
  const rows: Compared[] = [
    {
      label: 'Amount',
      old: <AmountValue packet={old.amount ? { amount: old.amount, currency: old.currency ?? '' } : null} />,
      now: <AmountValue packet={now.amount ? { amount: now.amount, currency: now.currency ?? '' } : null} />,
      mark: amountMark,
    },
  ];
  if (old.recipient || now.recipient) {
    rows.push({ label: 'Send to', old: old.recipient ?? NOT_GIVEN, now: now.recipient ?? NOT_GIVEN, mark: old.recipient === now.recipient ? 'unchanged' : 'changed' });
  }
  // Amount first, then what changed, then what did not.
  const rank = (row: Compared) => (row.label === 'Amount' ? 0 : row.mark === 'changed' ? 1 : 2);
  return rows.map((row, i) => ({ row, i })).sort((a, b) => rank(a.row) - rank(b.row) || a.i - b.i).map(({ row }) => row);
}

type StaleProps = { replaced: Snapshot; current: Snapshot; note: string; onReview: () => void };

/** The replaced and current versions side by side (a table on desktop, stacked cards on phones), each current value marked. */
export function StaleView({ replaced, current, note, onReview }: StaleProps) {
  const rows = compareRows(replaced, current);
  const oldN = replaced.version;
  const newN = current.version;
  const rowClass = (row: Compared) => `decide-row${row.mark === 'changed' ? ' decide-row--changed' : ''}`;
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
          <p className="decide-plain">{oldN === null ? 'The version you were reading can no longer be decided.' : `Version ${oldN} can no longer be approved.`}</p>
        </Callout>
      </div>
      {note.trim() !== '' && <p className="decide-plain decide-unsent">Your note wasn&rsquo;t sent: &ldquo;{note}&rdquo;</p>}
      <div className="decide-compare">
        <section className="decide-compare__old" aria-labelledby="decide-old-title">
          <h3 id="decide-old-title" className="decide-colhead">
            {oldN === null ? 'EARLIER VERSION' : `VERSION ${oldN}`} · REPLACED
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
            {newN === null ? 'CURRENT VERSION' : `VERSION ${newN}`} · CURRENT
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
        </section>
      </div>
      <div className="decide-stale__foot">
        <p className="decide-stale__action">
          <Button size="lg" block onClick={onReview}>
            {newN === null ? 'Review the current version' : `Review version ${newN}`}
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
  work: LiveWork;
  result: { verdict: string; work_state: WorkState };
  label: string;
  note: string;
  reloaded: LiveWork | null;
  history: LiveHistoryItem | null;
  refreshFailed: boolean;
  /** The person's decision list, without this work; null when the read failed (then the list and link are hidden). */
  waiting: QueueEntry[] | null;
};

/** An echo other than the three verdicts gets neutral words: the page never claims a decision it wasn't told. */
const RECORDED = { eyebrow: 'DECISION RECORDED', heading: (label: string) => `Decision recorded on ${label}` };
const SHOWN = 3;

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

// SCR-03-done-concepts, concept B: the banner, then the record beside the "what happens next" panel. The banner says
// approved, returned or rejected only after the re-read confirms the work moved; until then it says recorded.
export function DoneView({ id, work, result, label, note, reloaded, history, refreshFailed, waiting }: DoneProps) {
  const known = Object.hasOwn(VERDICT_WORDS, result.verdict);
  const words = known ? VERDICT_WORDS[result.verdict as Verdict] : RECORDED;
  // An effect that could not be confirmed (the decide answered effect_uncertain, or the re-read work is effect_uncertain) is never shown as an outcome.
  const uncertain = result.work_state === 'effect_uncertain' || reloaded?.state === 'effect_uncertain';
  const confirmed = known && reloaded !== null && !uncertain;
  const approved = confirmed && result.verdict === 'approve';
  useToastWhen(uncertain ? null : 'Your decision was recorded.');
  const decision = known ? (result.verdict === 'approve' ? 'Approve' : result.verdict === 'return' ? 'Return' : 'Reject') : 'Decision recorded';
  const youDecided = uncertain ? `${decision}, result not confirmed` : note ? `${decision}, with the note “${note}”` : known ? `${decision}, with no note` : decision;
  const next = waiting?.[0];
  const state = WORK_STATE_WORDS[reloaded?.state ?? result.work_state];
  return (
    <>
      <DecideHeader
        work={work}
        banner={approved ? 'success' : 'neutral'}
        eyebrow={
          <>
            {uncertain ? 'NOT CONFIRMED' : confirmed ? words.eyebrow : RECORDED.eyebrow}
            {history && (
              <>
                {' · '}
                <time dateTime={history.at}>{formatClock(history.at)}</time>
              </>
            )}
          </>
        }
        title={uncertain ? `${label}: result not confirmed` : confirmed ? words.heading(label) : RECORDED.heading(label)}
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
            <dl className="decide-sum" aria-label="Summary">
              <Row label="Work">{work.title}</Row>
              <Row label="You decided">{youDecided}</Row>
              <Row label="Now">{state}</Row>
              {history?.actor && (
                <Row label="Decided">
                  <time dateTime={history.at}>{decidedAt(history.at)}</time>, by {history.actor}
                </Row>
              )}
            </dl>
            {approved && <p className="decide-plain decide-paid">Paid is tracked separately by Finance and is not part of this decision.</p>}
          </div>
          <div className="decide-done__side">
            <section className="decide-donepanel" aria-labelledby="decide-next-head">
              <h2 id="decide-next-head" className="decide-donepanel__head">
                WHAT HAPPENS NEXT
              </h2>
              <p className="decide-links">
                {next && waiting && (
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

