'use client';

// SCR-08 "Your review": Approve v<n> and Return with note, drawn only for the verdicts the response offers.
// Desktop: the panel beside the document. Phone: Return and Approve in a bar pinned to the bottom; each opens the shared
// Drawer with the note field (a note is needed for both). The note rule is checked before any request; one write at a
// time (useReview). The page's notices (stale, unconfirmed, uncertain) sit outside, so they outlive these controls.
import { useEffect, useRef, useState } from 'react';

import { Button, Drawer, Panel, TextArea } from '@/components';

import { noteProblem, type Verdict } from './documentModel';
import type { Submit } from './useReview';

const NOTE_LABEL = 'Note for the PM';
const RULE = 'Approving records your name and time. Approving does not send it to the client.';
const SHEET: Record<Verdict, { title: string; button: string; busy: string }> = {
  approve: { title: 'Approve with a note', button: 'Approve', busy: 'Approving…' },
  return: { title: 'Return with a note', button: 'Return with note', busy: 'Returning…' },
};

type Props = {
  version: number;
  verdicts: Verdict[];
  submit: Submit;
  /** The id of the notice that explains why the buttons are off, when it is showing. */
  heldBy: string | undefined;
  phone: boolean;
  onDecide: (verdict: Verdict, note: string) => void;
};

export function ReviewControls({ version, verdicts, submit, heldBy, phone, onDecide }: Props) {
  const [note, setNote] = useState('');
  const [noteError, setNoteError] = useState<string | null>(null);
  const [sheet, setSheet] = useState<Verdict | null>(null);
  const noteRef = useRef<HTMLTextAreaElement>(null);
  const sheetNote = useRef<HTMLTextAreaElement>(null);
  const wasBusy = useRef(false);

  const busy = submit.status === 'busy';
  const hold = busy || submit.status === 'uncertain' || submit.status === 'unconfirmed';
  // A 422 on the note field is the note's error too.
  const fieldError = noteError ?? (submit.status === 'note' ? submit.message : undefined);

  // The sheet closes when the write has finished, unless the server refused the note: that stays open on the field.
  useEffect(() => {
    if (wasBusy.current && !busy && submit.status !== 'note') setSheet(null);
    wasBusy.current = busy;
  }, [busy, submit.status]);

  function press(verdict: Verdict) {
    if (hold) return;
    const problem = noteProblem(note);
    if (problem) {
      setNoteError(problem);
      (phone ? sheetNote : noteRef).current?.focus();
      return;
    }
    setNoteError(null);
    onDecide(verdict, note);
  }

  const state = (verdict: Verdict) => ({
    busy: busy && submit.verdict === verdict,
    disabled: hold && !(busy && submit.verdict === verdict),
    'aria-describedby': hold && !busy ? heldBy : undefined,
  });
  const can = (verdict: Verdict) => verdicts.includes(verdict);

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
        <div className="psl-actionbar docrev__bar">
          <div className="psl-actionbar__pair">
            {can('return') && (
              <Button kind="secondary" size="lg" {...state('return')} aria-haspopup="dialog" onClick={() => !hold && setSheet('return')}>
                Return
              </Button>
            )}
            {can('approve') && (
              <Button kind="confirm" size="lg" {...state('approve')} aria-haspopup="dialog" onClick={() => !hold && setSheet('approve')}>
                Approve
              </Button>
            )}
          </div>
          <span className="psl-doesnt">{RULE}</span>
        </div>
        {sheet && (
          <Drawer
            title={SHEET[sheet].title}
            subline={`Your note goes to the PM with v${version}.`}
            initialFocus={sheetNote}
            onClose={() => !busy && setSheet(null)}
            footer={
              <Button size="lg" block busy={busy && submit.verdict === sheet} busyLabel={SHEET[sheet].busy} disabled={hold && !busy} onClick={() => press(sheet)}>
                {sheet === 'approve' ? `Approve v${version}` : SHEET[sheet].button}
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
    <Panel kind="decide" head="Your review" headingLevel={2} className="docrev__review">
      {noteField(noteRef)}
      <div className="docrev__actions">
        {can('approve') && (
          <Button kind="confirm" size="lg" block {...state('approve')} busyLabel="Approving…" onClick={() => press('approve')}>
            {`Approve v${version}`}
          </Button>
        )}
        {can('return') && (
          <Button kind="secondary" size="lg" block {...state('return')} busyLabel="Returning…" onClick={() => press('return')}>
            Return with note
          </Button>
        )}
        <p className="psl-doesnt docrev__rulenote">{RULE}</p>
      </div>
    </Panel>
  );
}
