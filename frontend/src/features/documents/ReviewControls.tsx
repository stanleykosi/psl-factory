'use client';

// SCR-08 "Your review": Approve v<n> and Return with note, shown only for a task the API says the person can act on.
// Desktop: the panel beside the document. Phone: Return and Approve in a bar pinned to the bottom; Return opens the
// shared Drawer with the note field. The note rule is checked before any request; one write at a time (useDecision).
import { useEffect, useId, useRef, useState } from 'react';

import { Button, Callout, Drawer, Panel, TextArea } from '@/components';
import type { Verdict } from '@/features/decide-v7/format';
import type { ClaimState, SubmitState } from '@/features/decide-v7/useDecision';

import { noteProblem } from './documentModel';

const NOTE_LABEL = 'Note for the PM (needed to return)';
const RULE = 'Approving records your name and time. Approving does not send it to the client.';

type Props = {
  version: string;
  roleLabel?: string;
  claim: ClaimState;
  submit: SubmitState;
  phone: boolean;
  onDecide: (verdict: Verdict, note: string) => void;
  onRetryClaim: () => void;
};

export function ReviewControls({ version, roleLabel, claim, submit, phone, onDecide, onRetryClaim }: Props) {
  const [note, setNote] = useState('');
  const [noteError, setNoteError] = useState<string | null>(null);
  const [sheet, setSheet] = useState(false);
  const noteRef = useRef<HTMLTextAreaElement>(null);
  const sheetNote = useRef<HTMLTextAreaElement>(null);
  const waiting = useId();
  const wasBusy = useRef(false);

  const busy = submit.status === 'busy';
  const ready = claim.status === 'ready';
  const hold = !ready;
  // A 422 from the server is the note's error too (the mock and the backend name the field).
  const fieldError = noteError ?? (submit.status === 'invalid' ? submit.message : undefined);

  // The sheet closes when the write has finished without a field error (a 422 keeps it open on the note).
  useEffect(() => {
    if (wasBusy.current && submit.status === 'idle') setSheet(false);
    wasBusy.current = busy;
  }, [busy, submit.status]);

  function press(verdict: Verdict) {
    if (hold || busy) return;
    const problem = noteProblem(verdict, note);
    if (problem) {
      setNoteError(problem);
      (phone ? sheetNote : noteRef).current?.focus();
      return;
    }
    setNoteError(null);
    onDecide(verdict, verdict === 'approve' ? '' : note);
  }

  const reason = claim.status === 'pending' ? waiting : undefined;
  const state = (verdict: Verdict) => ({
    busy: busy && submit.verdict === verdict,
    disabled: hold || (busy && submit.verdict !== verdict),
    'aria-describedby': reason,
  });
  const notices = (
    <>
      {claim.status === 'invalid' && <Callout kind="problem">{claim.message}</Callout>}
      {claim.status === 'failed' && (
        <div role="alert">
          <Callout kind="warning">
            We couldn&rsquo;t get this review ready. Try again.{' '}
            <Button kind="secondary" size="sm" onClick={onRetryClaim}>
              Try again
            </Button>
          </Callout>
        </div>
      )}
      {claim.status === 'pending' && (
        <p className="psl-hint" id={waiting} role="status">
          Getting this review ready…
        </p>
      )}
    </>
  );

  const noteField = (ref: typeof noteRef) => (
    <TextArea
      ref={ref}
      label={NOTE_LABEL}
      value={note}
      rows={3}
      error={fieldError}
      onChange={(e) => {
        setNote(e.target.value);
        setNoteError(null);
      }}
    />
  );

  if (phone) {
    return (
      <>
        {notices}
        <div className="psl-actionbar docrev__bar">
          <div className="psl-actionbar__pair">
            <Button kind="secondary" size="lg" {...state('return')} aria-haspopup="dialog" onClick={() => !hold && !busy && setSheet(true)}>
              Return
            </Button>
            <Button kind="confirm" size="lg" {...state('approve')} busyLabel="Approving…" onClick={() => press('approve')}>
              Approve
            </Button>
          </div>
          <span className="psl-doesnt">{RULE}</span>
        </div>
        {sheet && (
          <Drawer
            title="Return with a note"
            subline={`Your note goes to the PM with v${version}.`}
            initialFocus={sheetNote}
            onClose={() => !busy && setSheet(false)}
            footer={
              <Button size="lg" block busy={busy && submit.verdict === 'return'} busyLabel="Returning…" disabled={hold} onClick={() => press('return')}>
                Return with note
              </Button>
            }
          >
            {noteField(sheetNote)}
          </Drawer>
        )}
      </>
    );
  }

  return (
    <Panel kind="decide" head={roleLabel ? `Your review · ${roleLabel}` : 'Your review'} headingLevel={2} className="docrev__review">
      {noteField(noteRef)}
      {notices}
      <div className="docrev__actions">
        <Button kind="confirm" size="lg" block {...state('approve')} busyLabel="Approving…" onClick={() => press('approve')}>
          {`Approve v${version}`}
        </Button>
        <Button kind="secondary" size="lg" block {...state('return')} busyLabel="Returning…" onClick={() => press('return')}>
          Return with note
        </Button>
        <p className="psl-doesnt docrev__rulenote">{RULE}</p>
      </div>
    </Panel>
  );
}
