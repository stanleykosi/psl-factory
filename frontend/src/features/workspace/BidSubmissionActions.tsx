'use client';

// F-98: the RFP submission panel's controls, drawn under its sections (the adapter's `Actions` slot): the PM's Send for review, the
// document reviewer's Approve, Return and Refuse on the exact pack, and Send to the client once the approval is recorded. What is
// offered is what the server's reads say (an open review this person may decide, a recorded approval, the pack's own version); the
// client has no rule about who may review or send. Sending, locking and error words are useWorkCommand's. The result is told from
// the re-read, never from the 200/202.
// Approving records the decision on the pack; it does not send it (C-36): sending is its own press.
// HELD, not drawn: editing the cover note or the file rules (needs the response id the pack save names), and recording a portal
// receipt (a proof picked from a list and an attestation the contract does not word).
import { useState } from 'react';

import { Button, Callout, TextArea, useToastWhen } from '@/components';

import type { CommandDescriptor, LineActionsProps } from './adapter';
import { openReviews } from './bidPack';
import { VERDICTS, type BidSubmissionReadback } from './bidSubmissionAdapter';
import { useWorkCommand } from './useWorkCommand';

const NOTE_LIMIT = 4000;
const LOCKED = 'Check the page before trying again.';
const SAID: Record<string, string> = {
  'bid-submission.send': 'The pack was sent for review.',
  'bid-submission.approve': 'Your approval was recorded.',
  'bid-submission.return': 'Your return was recorded.',
  'bid-submission.reject': 'Your refusal was recorded.',
  'bid-submission.queue': 'The pack was handed over to be sent.',
};

export function BidSubmissionActions({ readback, ctx, commands, reload, onAccessLost }: LineActionsProps<BidSubmissionReadback>) {
  const send = useWorkCommand({ item: ctx, reload, onAccessLost });
  const [note, setNote] = useState('');
  const [noteError, setNoteError] = useState<string | null>(null);
  const [last, setLast] = useState<string | null>(null);

  const byId = (id: string) => commands.find((c) => c.id === id);
  const { pack } = readback.context;
  const reviews = VERDICTS.map(([verdict]) => byId(`bid-submission.${verdict}`)).filter((c): c is CommandDescriptor => !!c);
  const sendCommand = byId('bid-submission.send');
  const queue = byId('bid-submission.queue');
  const anyLocked = commands.some((c) => send.lockedReason(c.id) !== null);
  // the PM's send is drawn only while the pack is undecided and not already with a reviewer; its own reason says why it can't be pressed
  const showSend = !!sendCommand && !!pack && !pack.decision && openReviews(readback.context.tasks).length === 0;
  const pdf = readback.file ? `/api/v1/work/${ctx.workId}/bid-submission/pdf/${readback.version_id}` : null;

  const press = async (command: CommandDescriptor, inputs: Record<string, unknown> = {}) => {
    setLast(command.id);
    await send.run(command, inputs);
  };
  const decide = (command: CommandDescriptor) => {
    const verdict = command.id.slice(command.id.indexOf('.') + 1);
    if (verdict !== 'approve' && note.trim() === '') {
      setNoteError('Write a note first.');
      return;
    }
    setNoteError(null);
    void press(command, { note });
  };
  const button = (c: CommandDescriptor, kind: 'primary' | 'secondary' | 'reject', onClick: () => void) => {
    const lockedReason = send.lockedReason(c.id) ?? (anyLocked ? LOCKED : null);
    const reason = c.disabledReason ?? lockedReason;
    return (
      <Button key={c.id} kind={kind} disabled={send.busy || reason !== null} busy={send.pending === c.id && !lockedReason} busyLabel="Working…" reason={reason} onClick={onClick}>
        {c.label}
      </Button>
    );
  };

  const notice = send.notice;
  useToastWhen(notice?.kind === 'success' && last ? notice.text.replace(/^Done\./, SAID[last] ?? 'Recorded.') : null);

  return (
    <div className="wr-actions">
      {pdf && (
        <p className="wr-line">
          <a className="psl-link cmp-target" href={pdf}>
            Open the pack as a PDF
          </a>
        </p>
      )}
      {reviews.length > 0 && pack && (
        <section className="wr-block" aria-label="Your review">
          <h3 className="wr-head">Your review of pack version {pack.number}</h3>
          <p className="wr-line">Approving records that this exact pack may go to the client. It does not send it.</p>
          <TextArea label="Note" hint="Needed to return or refuse" limit={NOTE_LIMIT} value={note} error={noteError ?? undefined} onChange={(e) => setNote(e.target.value)} />
          <div className="wr-buttons">{reviews.map((c) => button(c, c.id.endsWith('.approve') ? 'primary' : c.id.endsWith('.reject') ? 'reject' : 'secondary', () => decide(c)))}</div>
        </section>
      )}
      {(showSend || queue) && (
        <div className="wr-buttons">
          {showSend && sendCommand && button(sendCommand, 'primary', () => void press(sendCommand))}
          {queue && button(queue, 'primary', () => void press(queue))}
        </div>
      )}
      {notice?.kind === 'error' && (
        <Callout kind="problem">
          {notice.text}
          {notice.detail && <> {notice.detail}</>}
        </Callout>
      )}
    </div>
  );
}
