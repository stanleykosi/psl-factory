'use client';

// F-101: the income schedule's decision form (the adapter's `Actions` slot). Which verdicts are offered is the read's `review_verdicts`
// (and only while a review is open and nothing holds it); who may decide is the server's answer, never a rule here. Every verdict
// needs an evidence record from the schedule's own `evidence[]` and a note. Sending, locking and error words are useWorkCommand's;
// the result is told from the re-read, never from the 200.
import { useState } from 'react';

import type { LiveSchedule } from '@/api/types';
import { Button, Callout, Select, TextArea, useToastWhen, type SelectOption } from '@/components';

import type { LineActionsProps } from './adapter';
import { offeredVerdicts, VERDICTS } from './incomeSchedulesAdapter';
import { useWorkCommand, WORK_COMMAND_TEXT } from './useWorkCommand';

const NOTE_LIMIT = 4000;
const NEED_EVIDENCE = 'Choose the evidence this decision rests on.';
const NEED_NOTE = 'Add a note.';
const NO_EVIDENCE = 'There is no evidence on this schedule to cite, so a decision can’t be recorded yet.';
const DONE: Record<string, string> = { approve: 'Your approval is recorded.', return: 'The schedule is returned.', reject: 'Your refusal is recorded.', revoke: 'The approval is withdrawn.' };
// this line's words for what the shared sender says
const WORDS: Record<string, string> = {
  [WORK_COMMAND_TEXT.changed]: 'This schedule changed while you were reading it, so nothing was recorded.',
  [WORK_COMMAND_TEXT.uncertain]: 'We couldn’t confirm whether your decision was recorded. Check the schedule before trying again.',
  'You can’t do this.': 'You can’t review this schedule.',
};

export function IncomeScheduleReview({ readback, ctx, commands, reload, onAccessLost }: LineActionsProps<LiveSchedule>) {
  const send = useWorkCommand({ item: ctx, reload, onAccessLost });
  const [evidenceId, setEvidenceId] = useState('');
  const [note, setNote] = useState('');
  const [last, setLast] = useState<string | null>(null);

  const command = commands.find((c) => c.id === 'income-schedules.review');
  const verdicts = offeredVerdicts(readback);
  const evidence = readback.evidence;
  const options: SelectOption[] = evidence.map((e) => ({ value: String(e.id), label: `${e.kind} · version ${e.version}` }));
  const chosen = evidence.find((e) => String(e.id) === evidenceId);
  const noteOver = note.length > NOTE_LIMIT;
  const lockedReason = command ? send.lockedReason(command.id) : null;
  const gate = command?.disabledReason ?? lockedReason ?? (!chosen ? NEED_EVIDENCE : note.trim() === '' ? NEED_NOTE : noteOver ? `The note is over ${NOTE_LIMIT} characters.` : null);

  const press = async (verdict: string) => {
    if (!command || !chosen || gate !== null) return;
    setLast(verdict);
    const outcome = await send.run(command, { verdict, evidence_id: chosen.id, note: note.trim() });
    if (outcome === 'sent') setNote('');
  };

  const notice = send.notice;
  const done = notice?.kind === 'success' ? notice.text.replace(/^Done\./, DONE[last ?? ''] ?? 'Recorded.') : null;
  useToastWhen(done);
  const open = verdicts.length > 0 && !!command;

  return (
    <div className="wr-actions">
      {open && evidence.length === 0 && <p className="wr-line">{NO_EVIDENCE}</p>}
      {open && evidence.length > 0 && (
        <section className="wr-block" aria-label="Your decision">
          <h3 className="wr-head">Your decision</h3>
          <Select label="Evidence" hint="The record this decision rests on" placeholder="Choose the evidence" options={options} value={evidenceId || undefined} onChange={setEvidenceId} />
          <TextArea label="Note" hint="Needed for every decision" limit={NOTE_LIMIT} value={note} onChange={(e) => setNote(e.target.value)} />
          <div className="wr-buttons">
            {VERDICTS.filter(([v]) => verdicts.includes(v)).map(([verdict, label]) => (
              <Button
                key={verdict}
                kind={verdict === 'approve' ? 'primary' : verdict === 'reject' ? 'reject' : 'secondary'}
                disabled={send.busy || gate !== null}
                busy={send.pending === command.id && last === verdict && !lockedReason}
                busyLabel="Working…"
                reason={gate}
                onClick={() => void press(verdict)}
              >
                {label}
              </Button>
            ))}
          </div>
        </section>
      )}
      {!open && notice?.kind === 'error' && note.trim() !== '' && <p className="wr-line">Your unsent note: {note}</p>}
      {notice?.kind === 'error' && (
        <Callout kind="problem">
          {WORDS[notice.text] ?? notice.text}
          {notice.detail && <> {notice.detail}</>}
        </Callout>
      )}
    </div>
  );
}
