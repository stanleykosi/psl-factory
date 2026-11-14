'use client';

// SCR-03 "Your decision": the note, Approve v<n>, Return and Reject. Rendered only for a task the API says you
// can act on. The note rules are checked before any request; one write at a time.
import { useId, useRef, useState } from 'react';

import type { TaskDecision, WorkItem, WorkTask } from '@/api/types';
import { WarningIcon } from '@/shell/icons';

import { NOTE_MAX, personStationIndex, VERDICT_WORDS, type Verdict } from './format';
import type { ClaimState, SubmitState } from './useDecision';

type Props = {
  item: WorkItem;
  task: WorkTask & { decision: TaskDecision };
  claim: ClaimState;
  submit: SubmitState;
  onDecide: (verdict: Verdict, note: string) => void;
  onRetryClaim: () => void;
};

export function DecidePanel({ item, task, claim, submit, onDecide, onRetryClaim }: Props) {
  const [note, setNote] = useState('');
  const [noteError, setNoteError] = useState<string | null>(null);
  const noteRef = useRef<HTMLTextAreaElement>(null);
  const ids = { note: useId(), hint: useId(), count: useId(), error: useId(), reason: useId() };

  const busy = submit.status === 'busy';
  const ready = claim.status === 'ready';
  const disabled = !ready || busy;
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
      return;
    }
    setNoteError(null);
    onDecide(verdict, note);
  }

  const label = (verdict: Verdict) =>
    busy && submit.verdict === verdict
      ? VERDICT_WORDS[verdict].busy
      : verdict === 'approve'
        ? `Approve v${task.decision.version.number}`
        : VERDICT_WORDS[verdict].button;
  const describedBy = [ids.hint, ids.count, noteError ? ids.error : null].filter(Boolean).join(' ');

  return (
    <section className="psl-panel psl-panel--decide decide-panel" aria-labelledby="decide-panel-title" aria-busy={busy}>
      <h2 id="decide-panel-title" className="psl-panel__head psl-panel__head--decide">
        Your decision
      </h2>
      <div className="psl-panel__body">
        <p className="decide-plain">
          Only a {task.required_role} can decide. You are {task.required_role}.
        </p>
        <div className="psl-field">
          <label className="psl-label" htmlFor={ids.note}>
            Note <span className="psl-opt" id={ids.hint}>(needed to return or reject)</span>
          </label>
          <textarea
            ref={noteRef}
            id={ids.note}
            className="psl-input psl-input--area"
            value={note}
            maxLength={NOTE_MAX}
            aria-invalid={noteError ? true : undefined}
            aria-describedby={describedBy}
            onChange={(e) => {
              setNote(e.target.value);
              setNoteError(null);
            }}
          />
          <span className="psl-hint" id={ids.count}>
            {note.length} / {NOTE_MAX}
          </span>
          {noteError && (
            <span className="psl-error" id={ids.error}>
              <WarningIcon />
              {noteError}
            </span>
          )}
        </div>
        {claim.status === 'invalid' && (
          <p className="psl-callout psl-callout--problem" role="alert">
            <WarningIcon />
            <span>{claim.message}</span>
          </p>
        )}
        {claim.status === 'failed' && (
          <div className="psl-callout psl-callout--warning decide-retry" role="alert">
            <WarningIcon />
            <span>We couldn&rsquo;t get this decision ready. Try again.</span>
            <button type="button" className="psl-btn psl-btn--secondary psl-btn--sm" onClick={onRetryClaim}>
              Try again
            </button>
          </div>
        )}
        {submit.status === 'invalid' && (
          <p className="psl-callout psl-callout--problem" role="alert">
            <WarningIcon />
            <span>{submit.message}</span>
          </p>
        )}
        <div className="psl-actionbar decide-actions">
          {claim.status === 'pending' && (
            <p className="psl-hint decide-reason" id={ids.reason} role="status">
              Getting this decision ready…
            </p>
          )}
          <button
            type="button"
            className="psl-btn psl-btn--confirm psl-btn--lg psl-btn--block"
            disabled={disabled}
            aria-describedby={claim.status === 'pending' ? ids.reason : undefined}
            onClick={() => press('approve')}
          >
            {label('approve')}
          </button>
          <div className="psl-actionbar__pair">
            <button
              type="button"
              className="psl-btn psl-btn--secondary psl-btn--lg"
              disabled={disabled}
              aria-describedby={claim.status === 'pending' ? ids.reason : undefined}
              onClick={() => press('return')}
            >
              {label('return')}
            </button>
            <button
              type="button"
              className="psl-btn psl-btn--reject psl-btn--lg"
              disabled={disabled}
              aria-describedby={claim.status === 'pending' ? ids.reason : undefined}
              onClick={() => press('reject')}
            >
              {label('reject')}
            </button>
          </div>
          <p className="psl-doesnt decide-doesnt">
            Approving earns APPROVED only.{next && ` ${next.name} is the next station.`}
          </p>
        </div>
      </div>
    </section>
  );
}
