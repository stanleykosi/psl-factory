'use client';

// F-33 (PROPOSAL G-C-1, G-C-2): a workspace's decision steps decided in place, as F-29 does on the document page. Each
// step with `task_id` and a `verdict` the page offers is one button in the "Decide · <required_role>" panel; the writes
// are the F-16 claim and decide through useDecision (one write at a time, no automatic resend, a re-read after an
// uncertain write). The buttons exist only while that task's `you_can_act` is true; otherwise the reason is shown and
// nothing is sent. Every word in the panel but the note label and its messages is the backend's. Desktop: the panel
// in the side column. Phone: the buttons pinned to the bottom; Return and Reject open the full-height Drawer with the note.
import { useEffect, useId, useRef, useState, type ReactNode } from 'react';

import { Button, Callout, Drawer, Loading, TextArea, useIsPhone } from '@/components';
import { cannotActCopy, UncertainNotice } from '@/features/decide/DecideStates';
import { findDecisionTask, NOTE_MAX, VERDICT_WORDS, type Verdict } from '@/features/decide/format';
import { useDecision } from '@/features/decide/useDecision';

import type { Step } from './labels';
import { stepVerdict } from './proposals';
import { Consequence } from './Steps';
import { stepKind } from './StepForm';
import type { WorkspacePage } from './usePageReload';
import { STEP_TEXT } from './useWorkspaceStep';

/** Frontend wording (spec Conflicts 7): the note label names only the verdicts this panel offers that need one. */
export const DECIDE_TEXT = {
  head: (role: string) => `Decide · ${role}`,
  note: (verdicts: Verdict[]) => `Note (needed to ${verdicts.filter((v) => v !== 'approve').map((v) => (v === 'return' ? 'return' : 'reject')).join(' or ')})`,
  noteMissing: (verdict: Verdict) => (verdict === 'reject' ? 'Add a note to reject it.' : 'Add a note to return it.'),
  noteLong: `Keep the note to ${NOTE_MAX} characters or fewer.`,
  loading: 'Loading the review…',
  claiming: 'Getting this review ready…',
  claimFailed: 'We couldn’t get this review ready. Try again.',
  loadFailed: 'We couldn’t load this review. Nothing was changed.',
  notOpen: 'This review isn’t open to you here.',
  stale: 'This review changed while you were reading it, so nothing was recorded.',
  latest: 'Review the latest',
  unconfirmed: 'We couldn’t confirm whether your decision was recorded, and we couldn’t reload this item to check, so the decision buttons stay off. Try again reloads the item; it doesn’t send your decision again.',
  recorded: (label: string) => `Decision recorded on ${label}`,
  cancel: 'Cancel',
  tryAgain: 'Try again',
} as const;

const ACCESS_LOST = new Set(['unauthenticated', 'forbidden', 'not_found']);

/** Approve sends no note; return and reject need one of 1 to NOTE_MAX characters, checked before any request. */
function noteProblem(verdict: Verdict, note: string): string | null {
  if (verdict === 'approve') return null;
  if (note.trim() === '') return DECIDE_TEXT.noteMissing(verdict);
  if (note.trim().length > NOTE_MAX) return DECIDE_TEXT.noteLong;
  return null;
}

type Props = {
  id: string;
  taskId: string;
  /** The task's verdict steps, in returned order. */
  steps: Step[];
  page: WorkspacePage;
  /** Another write is in flight on the page, or its refresh failed: nothing can be pressed. */
  off: boolean;
  /** The decide answered 200: the page's notice, from the existing VERDICT_WORDS. */
  onDecided: (text: string) => void;
};

export function InlineDecide({ id, taskId, steps, page, off, onDecided }: Props) {
  const review = useDecision(id, taskId);
  const { view, claim, submit } = review;
  const phone = useIsPhone();
  const [note, setNote] = useState('');
  const [noteError, setNoteError] = useState<string | null>(null);
  const [sheet, setSheet] = useState<Step | null>(null);
  const noteRef = useRef<HTMLTextAreaElement>(null);
  const sheetNote = useRef<HTMLTextAreaElement>(null);
  const opener = useRef(new Map<string, HTMLButtonElement | null>());
  const bar = useRef<HTMLElement>(null);
  const waiting = useId();
  const headId = useId();

  // Losing access on the review's read or write replaces the page (401 signed out; 403 and 404 alike).
  const lost = view.kind === 'error' && ACCESS_LOST.has(view.error.kind) ? view.error : null;
  useEffect(() => {
    if (lost) page.onAccessLost(lost);
  }, [lost, page]);

  // After a write has settled the page re-reads and draws what the backend says (never a state from the click): a 200
  // first gives its notice, the backend's verdict echo in the existing words. Each outcome is handled once.
  const settled = view.kind === 'done' ? view.result : view.kind === 'stale' || view.kind === 'forbidden' || (view.kind === 'item' && review.uncertain) ? view : null;
  const handled = useRef<unknown>(null);
  const { reload } = page;
  useEffect(() => {
    if (!settled || handled.current === settled) return;
    handled.current = settled;
    if (view.kind === 'done') {
      const words = VERDICT_WORDS[view.result.verdict as Verdict];
      onDecided(words ? words.heading(view.label) : DECIDE_TEXT.recorded(view.label));
    }
    void reload();
  }, [settled, view, onDecided, reload]);

  const task = view.kind === 'item' ? findDecisionTask(view.item, taskId) : undefined;
  const offered = steps.map((step) => ({ step, verdict: stepVerdict(step)! }));
  const canAct = task?.you_can_act === true && claim !== null;
  const ready = claim?.status === 'ready';
  const busy = submit.status === 'busy';
  const needsNote = offered.some((o) => o.verdict !== 'approve');
  const fieldError = noteError ?? (submit.status === 'invalid' ? submit.message : undefined);

  // On a phone the buttons are pinned to the bottom: the page keeps their height clear below them (workspace.css).
  useEffect(() => {
    const el = bar.current;
    if (!el || !phone || !canAct) return;
    const root = document.documentElement;
    const measure = () => root.style.setProperty('--ws-bar-h', `${el.offsetHeight}px`);
    measure();
    const watch = typeof ResizeObserver === 'undefined' ? null : new ResizeObserver(measure);
    watch?.observe(el);
    return () => {
      watch?.disconnect();
      root.style.removeProperty('--ws-bar-h');
    };
  }, [phone, canAct]);

  // The sheet closes when the write has finished without a field error (a 422 keeps it open on the note).
  const wasBusy = useRef(false);
  useEffect(() => {
    if (wasBusy.current && !busy && submit.status !== 'invalid') setSheet(null);
    wasBusy.current = busy;
  }, [busy, submit.status]);

  const send = async (verdict: Verdict) => {
    if (!ready || busy || off) return;
    await review.decide(verdict, verdict === 'approve' ? '' : note.trim());
  };

  const press = (step: Step, verdict: Verdict, inSheet = false) => {
    if (!ready || busy || off) return;
    if (phone && verdict !== 'approve' && !inSheet) {
      setSheet(step);
      return;
    }
    const problem = noteProblem(verdict, note);
    if (problem) {
      setNoteError(problem);
      (inSheet ? sheetNote : noteRef).current?.focus();
      return;
    }
    setNoteError(null);
    void send(verdict);
  };

  const closeSheet = () => {
    if (busy || !sheet) return;
    const key = sheet.key;
    setSheet(null);
    setNoteError(null);
    requestAnimationFrame(() => opener.current.get(key)?.focus());
  };

  const noteField = (ref: typeof noteRef) => (
    <TextArea
      ref={ref}
      label={DECIDE_TEXT.note(offered.map((o) => o.verdict))}
      value={note}
      rows={3}
      error={fieldError}
      onChange={(event) => {
        setNote(event.target.value);
        setNoteError(null);
      }}
    />
  );

  const notices = (
    <>
      {claim?.status === 'invalid' && <Callout kind="problem">{claim.message}</Callout>}
      {claim?.status === 'failed' && (
        <div role="alert">
          <Callout kind="warning">
            {DECIDE_TEXT.claimFailed}{' '}
            <Button kind="secondary" size="sm" onClick={review.retryClaim}>
              {DECIDE_TEXT.tryAgain}
            </Button>
          </Callout>
        </div>
      )}
      {claim?.status === 'pending' && (
        <p className="psl-hint" id={waiting} role="status">
          {DECIDE_TEXT.claiming}
        </p>
      )}
    </>
  );

  const buttons = offered.map(({ step, verdict }) => (
    <Button
      key={step.key}
      ref={(el) => {
        opener.current.set(step.key, el);
      }}
      kind={stepKind(step)}
      size="lg"
      busy={busy && submit.verdict === verdict && !sheet}
      busyLabel={VERDICT_WORDS[verdict].busy}
      disabled={!ready || off || (busy && submit.verdict !== verdict)}
      aria-describedby={claim?.status === 'pending' ? waiting : undefined}
      aria-haspopup={phone && verdict !== 'approve' ? 'dialog' : undefined}
      onClick={() => press(step, verdict)}
    >
      {step.label}
    </Button>
  ));

  const role = 'item' in view ? findDecisionTask(view.item, taskId)?.required_role : undefined;
  const panel = (body: ReactNode, info = true) => (
    <section ref={info ? undefined : bar} className={`psl-panel psl-panel--decide ws-decide ws-idecide${info ? ' ws-decide--info' : ''}`} aria-labelledby={headId}>
      <h2 id={headId} className="psl-panel__head psl-panel__head--decide ws-decide__head">
        {role ? DECIDE_TEXT.head(role) : STEP_TEXT.decide}
      </h2>
      <div className="psl-panel__body ws-decide__body">{body}</div>
    </section>
  );

  if (lost) return null;
  if (view.kind === 'loading') return <Loading className="ws-idecide__loading">{DECIDE_TEXT.loading}</Loading>;
  if (view.kind === 'error') {
    return (
      <Callout kind="problem" className="ws-notice">
        <span>{DECIDE_TEXT.loadFailed}</span>
        <Button kind="secondary" onClick={() => void review.retry()}>
          {DECIDE_TEXT.tryAgain}
        </Button>
      </Callout>
    );
  }
  // The page re-reads after a 200 and draws the state the backend returns; nothing here says what it became.
  if (view.kind === 'done') return review.uncertain ? <UncertainNotice /> : null;
  if (view.kind === 'stale') {
    return panel(
      <div role="alert">
        <Callout kind="warning">
          {DECIDE_TEXT.stale}{' '}
          <Button kind="secondary" size="sm" onClick={review.reviewCurrent}>
            {DECIDE_TEXT.latest}
          </Button>
        </Callout>
      </div>,
    );
  }
  if (view.kind === 'unconfirmed') {
    return panel(
      <div role="alert">
        <Callout kind="warning">
          {DECIDE_TEXT.unconfirmed}{' '}
          <Button kind="secondary" size="sm" busy={view.checking} busyLabel="Checking…" onClick={review.recheck}>
            {DECIDE_TEXT.tryAgain}
          </Button>
        </Callout>
      </div>,
    );
  }
  if (view.kind === 'forbidden') {
    const now = findDecisionTask(view.item, taskId);
    const copy = now ? cannotActCopy(now.cannot_act_reason, now) : null;
    return panel(
      <p className="ws-consequence">{copy ? <><strong>{copy.heading}</strong>{copy.text && <> {copy.text}</>}</> : DECIDE_TEXT.notOpen}</p>,
    );
  }
  if (!task) return <p className="ws-consequence">{DECIDE_TEXT.notOpen}</p>;
  if (!canAct) {
    const copy = cannotActCopy(task.cannot_act_reason, task);
    return panel(
      <p className="ws-consequence">
        <strong>{copy.heading}</strong>
        {copy.text && <> {copy.text}</>}
      </p>,
    );
  }

  const basis = task.decision.basis;
  const consequences = offered.map(({ step }) => <Consequence key={step.key} step={step} />);
  if (phone) {
    return (
      <>
        <div className="ws-idecide__words">
          {basis && <p className="ws-consequence">{basis}</p>}
          {consequences}
          {review.uncertain && <UncertainNotice />}
        </div>
        {panel(
          <>
            {notices}
            <div className="ws-idecide__buttons">{buttons}</div>
          </>,
          false,
        )}
        {sheet && (
          <Drawer
            title={sheet.label}
            initialFocus={sheetNote}
            onClose={closeSheet}
            footer={
              <div className="ws-form__actions">
                <Button size="lg" kind={stepKind(sheet)} busy={busy} busyLabel={VERDICT_WORDS[stepVerdict(sheet)!].busy} disabled={!ready || off} onClick={() => press(sheet, stepVerdict(sheet)!, true)}>
                  {sheet.label}
                </Button>
                <Button size="lg" kind="secondary" disabled={busy} onClick={closeSheet}>
                  {DECIDE_TEXT.cancel}
                </Button>
              </div>
            }
          >
            {noteField(sheetNote)}
          </Drawer>
        )}
      </>
    );
  }
  return (
    <>
      {panel(
        <>
          {basis && <p className="ws-consequence">{basis}</p>}
          {needsNote && noteField(noteRef)}
          {notices}
          <div className="ws-idecide__buttons">{buttons}</div>
          {consequences}
        </>,
        false,
      )}
      {review.uncertain && <UncertainNotice />}
    </>
  );
}
