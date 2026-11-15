'use client';

// SCR-03 "Your decision": the note, Approve v<n>, Return and Reject. Rendered only for a task the API says you
// can act on. The note rules are checked before any request; one write at a time.
import { useId, useRef, useState } from 'react';

import type { TaskDecision, WorkItem, WorkTask } from '@/api/types';
import { Button, Callout, Panel, TextArea } from '@/components';

import { NOTE_MAX, personStationIndex, VERDICT_WORDS, type Verdict } from './format';
import type { ClaimState, SubmitState } from './useDecision';

type Props = {
  item: WorkItem;
  task: WorkTask & { decision: TaskDecision };
  claim: ClaimState;
  submit: SubmitState;
  /** True while a decision's effect is unconfirmed: every control stays off. */
  locked: boolean;
  onDecide: (verdict: Verdict, note: string) => void;
  onRetryClaim: () => void;
};

export function DecidePanel({ item, task, claim, submit, locked, onDecide, onRetryClaim }: Props) {
  const [note, setNote] = useState('');
  const [noteError, setNoteError] = useState<string | null>(null);
  const noteRef = useRef<HTMLTextAreaElement>(null);
  const ids = { reason: useId() };

  const busy = submit.status === 'busy';
  const ready = claim.status === 'ready';
  const disabled = !ready || busy || locked;
  const index = personStationIndex(item.stations);
  const next = index >= 0 ? item.stations[index + 1] : undefined;

  function press(verdict: Verdict) {
    if (disabled) return;
    let problem: string | null = null;
    if (note.length > NOTE_MAX) problem = 'Keep the note to 2000 characters or fewer.';
    else if (verdict !== 'approve' && note.trim() === '') problem = 'Add a note to return or reject.';
    if (problem) {
      setNoteError(problem);
      noteRef.current?.focus();
      // on a phone the note sits behind the pinned action bar: bring it (and its message) above the bar
      noteRef.current?.scrollIntoView?.({ block: 'nearest' });
      return;
    }
    setNoteError(null);
    onDecide(verdict, note);
  }


  const hold = !ready || locked;
  const reasonFor = claim.status === 'pending' ? ids.reason : undefined;
  // One write at a time: while one decision is recorded the pressed button shows busy and the others wait.
  const state = (verdict: Verdict) => ({
    busy: busy && submit.verdict === verdict,
    busyLabel: VERDICT_WORDS[verdict].busy,
    disabled: hold || (busy && submit.verdict !== verdict),
    'aria-describedby': reasonFor,
  });

  return (
    <Panel kind="decide" head="Your decision" className="decide-panel">
      <p className="decide-plain decide-who">
        Only a {task.required_role} can decide. You are {task.required_role}.
      </p>
      <TextArea
        ref={noteRef}
        label={
          <>
            Note <span className="psl-opt">(needed to return or reject)</span>
          </>
        }
        value={note}
        limit={NOTE_MAX}
        error={noteError ?? undefined}
        onChange={(e) => {
          setNote(e.target.value);
          setNoteError(null);
        }}
      />
      {claim.status === 'invalid' && <Callout kind="problem">{claim.message}</Callout>}
      {claim.status === 'failed' && (
        <Callout kind="warning" className="decide-retry">
          We couldn&rsquo;t get this decision ready. Try again.{' '}
          <Button kind="secondary" size="sm" onClick={onRetryClaim}>
            Try again
          </Button>
        </Callout>
      )}
      {submit.status === 'invalid' && <Callout kind="problem">{submit.message}</Callout>}
      <div className="psl-actionbar decide-actions">
        {claim.status === 'pending' && (
          <p className="psl-hint decide-reason" id={ids.reason} role="status">
            Getting this decision ready…
          </p>
        )}
        <Button size="lg" block className="decide-approve" {...state('approve')} onClick={() => press('approve')}>
          {`Approve v${task.decision.version.number}`}
        </Button>
        <div className="psl-actionbar__pair">
          <Button kind="secondary" size="lg" {...state('return')} onClick={() => press('return')}>
            {VERDICT_WORDS.return.button}
          </Button>
          <Button kind="reject" size="lg" {...state('reject')} onClick={() => press('reject')}>
            {VERDICT_WORDS.reject.button}
          </Button>
        </div>
        <p className="psl-doesnt decide-doesnt">
          Approving earns APPROVED only.{next && ` ${next.name} is the next station.`}
        </p>
      </div>
    </Panel>
  );
}
