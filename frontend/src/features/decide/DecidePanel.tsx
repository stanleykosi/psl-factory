'use client';

// SCR-03 "Your decision": the evidence the person relies on, the note, and Approve, Return and Reject. Rendered only
// for a task the server says the person can decide. Nothing is pre-selected; the note rules are checked before any
// request; one write at a time.
import { useId, useRef, useState } from 'react';

import type { LiveTaskRead } from '@/api/types';
import { Button, Callout, Panel, RadioGroup, TextArea } from '@/components';

import { NOTE_MAX, roleWords, shortHash, VERDICT_WORDS, type Verdict } from './format';
import type { ClaimState, SubmitState } from './useDecision';

type Props = {
  read: LiveTaskRead;
  claim: ClaimState;
  submit: SubmitState;
  /** True while a decision's effect is unconfirmed: every control stays off. */
  locked: boolean;
  onDecide: (verdict: Verdict, evidenceId: number, note: string) => void;
  onRetryClaim: () => void;
};

export function DecidePanel({ read, claim, submit, locked, onDecide, onRetryClaim }: Props) {
  const { task, review_evidence: evidence, invoice_packet: packet } = read;
  const [chosen, setChosen] = useState<string | undefined>(undefined);
  const [note, setNote] = useState('');
  const [noteError, setNoteError] = useState<string | null>(null);
  const noteRef = useRef<HTMLTextAreaElement>(null);
  const ids = { reason: useId(), evidence: useId() };

  const busy = submit.status === 'busy';
  const ready = claim.status === 'ready';
  const hold = !ready || locked;
  const picked = evidence.find((item) => String(item.id) === chosen);
  const disabled = hold || !picked;
  const serverFields = submit.status === 'invalid' ? submit.fields : [];
  const fieldMessage = (match: (name: string) => boolean) => serverFields.find((f) => match(f.name))?.message;
  const evidenceError = fieldMessage((name) => name.includes('evidence'));
  const serverNoteError = fieldMessage((name) => name === 'note');

  function press(verdict: Verdict) {
    if (disabled || busy || !picked) return;
    let problem: string | null = null;
    if (note.length > NOTE_MAX) problem = 'Keep the note to 2000 characters or fewer.';
    else if (verdict !== 'approve' && note.trim() === '') problem = 'Add a note to return or reject.';
    if (problem) {
      setNoteError(problem);
      noteRef.current?.focus();
      // on a phone the note sits behind the pinned action bar: once the message has drawn, bring the whole field, the
      // message included, above the bar
      const field = noteRef.current?.closest('.psl-field') ?? noteRef.current;
      requestAnimationFrame(() => field?.scrollIntoView?.({ block: 'nearest' }));
      return;
    }
    setNoteError(null);
    onDecide(verdict, picked.id, note);
  }

  // Why the buttons are off, in words beside them (never a disabled button with no reason).
  const why = claim.status === 'pending' ? 'Getting this decision ready…' : !ready || locked ? null : evidence.length === 0 ? 'There is no evidence to cite yet, so this can’t be decided.' : !picked ? 'Choose the evidence you are relying on to turn on these buttons.' : null;
  const reasonFor = why ? ids.reason : undefined;
  // One write at a time: while one decision is recorded the pressed button shows busy and the others wait.
  const state = (verdict: Verdict) => ({
    busy: busy && submit.verdict === verdict,
    busyLabel: VERDICT_WORDS[verdict].busy,
    disabled: disabled || (busy && submit.verdict !== verdict),
    'aria-describedby': reasonFor,
  });
  const offered = (verdict: Verdict) => task.verdicts.includes(verdict);

  return (
    <Panel kind="decide" head="Your decision" className="decide-panel">
      <p className="decide-plain decide-who">Only a {roleWords(task.role)} can decide.</p>
      {evidence.length > 0 && (
        <RadioGroup
          legend="Evidence you are relying on"
          className="decide-evidence"
          options={evidence.map((item) => ({
            value: String(item.id),
            label: `${item.source}, version ${item.version}`,
            detail: `checksum ${shortHash(item.sha256)}`,
          }))}
          value={chosen}
          onChange={setChosen}
          disabled={busy || locked}
          error={evidenceError}
        />
      )}
      <TextArea
        ref={noteRef}
        label={
          <>
            Note <span className="psl-opt">(needed to return or reject)</span>
          </>
        }
        value={note}
        limit={NOTE_MAX}
        error={noteError ?? serverNoteError ?? undefined}
        onChange={(e) => {
          setNote(e.target.value);
          setNoteError(null);
        }}
      />
      {claim.status === 'invalid' && <Callout kind="problem">{claim.message}</Callout>}
      {claim.status === 'failed' && (
        // announced: it answers the person's press (a warning Callout has no live role of its own)
        <div role="alert">
          <Callout kind="warning" className="decide-retry">
            We couldn&rsquo;t get this decision ready. Try again.{' '}
            <Button kind="secondary" size="sm" onClick={onRetryClaim}>
              Try again
            </Button>
          </Callout>
        </div>
      )}
      {submit.status === 'invalid' && <Callout kind="problem">{submit.message}</Callout>}
      <div className="psl-actionbar decide-actions">
        {why && (
          <p className="psl-hint decide-reason" id={ids.reason} role="status">
            {why}
          </p>
        )}
        {offered('approve') && (
          <Button size="lg" block className="decide-approve" {...state('approve')} onClick={() => press('approve')}>
            {packet ? `Approve v${packet.version}` : VERDICT_WORDS.approve.button}
          </Button>
        )}
        {(offered('return') || offered('reject')) && (
          <div className="psl-actionbar__pair">
            {offered('return') && (
              <Button kind="secondary" size="lg" {...state('return')} onClick={() => press('return')}>
                {VERDICT_WORDS.return.button}
              </Button>
            )}
            {offered('reject') && (
              <Button kind="reject" size="lg" {...state('reject')} onClick={() => press('reject')}>
                {VERDICT_WORDS.reject.button}
              </Button>
            )}
          </div>
        )}
        {offered('approve') && <p className="psl-doesnt decide-doesnt">Approving earns APPROVED only.</p>}
      </div>
    </Panel>
  );
}
