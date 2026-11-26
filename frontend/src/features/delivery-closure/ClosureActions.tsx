'use client';

// F-118: the closure page's own controls (the adapter's `Actions` slot): close or return, replace the report, confirm milestone
// notifications. Which is drawn is the reads' answer (the work read's `can_decide` and `verdicts`, the Finance read answering); the page
// has no rule about who may act, and a control the reads do not offer is absent. Sending, locking and error words are useWorkCommand's.
// "Closed" and "returned" are said only from the re-read (the sections), never from the answer to a press, so the only success text
// here is none. A changed record leaves a lasting notice and the person's unsent note; the decide buttons come back only if the
// fresh read still offers them.
import Link from 'next/link';
import { useState } from 'react';

import { Callout, TextArea } from '@/components';
import type { LineActionsProps } from '@/features/workspace/adapter';
import { useWorkCommand } from '@/features/workspace/useWorkCommand';

import { closureNotice, decideHeld, decisionTask, IDS, NOTE_LIMIT, TEXT, type Readback } from './closureModel';
import { FinanceForm, ReplaceForm } from './ClosureForms';
import { Press } from './Press';

export function ClosureActions({ readback, ctx, commands, reload, onAccessLost }: LineActionsProps<Readback>) {
  const send = useWorkCommand({ item: ctx, reload, onAccessLost });
  const [note, setNote] = useState('');
  const [lastId, setLastId] = useState<string | null>(null);
  const decide = commands.find((c) => c.id === IDS.decide);
  const replace = commands.find((c) => c.id === IDS.replace);
  const finance = commands.find((c) => c.id === IDS.finance);
  const offered = decisionTask(readback.work)?.verdicts ?? [];
  const notice = send.notice?.kind === 'error' ? closureNotice(send.notice, lastId) : null;
  const changed = notice?.text === TEXT.stale;
  const retro = readback.checklist.checks.find((c) => c.key === 'retrospective');

  const verdict = async (v: 'approve' | 'return') => {
    if (!decide || decideHeld(v, note) !== null) return;
    setLastId(IDS.decide);
    // the note goes as typed; it is kept when the press is refused, and cleared only when the write was accepted
    if ((await send.run(decide, { verdict: v, note })) === 'sent') setNote('');
  };
  const submit = (id: string): typeof send.run => async (command, inputs) => {
    setLastId(id);
    return send.run(command, inputs);
  };
  const tracked = (id: string): typeof send => ({ ...send, run: submit(id) });

  return (
    <div className="wr-actions">
      {retro?.status === 'held' && (
        <p className="wr-line">
          <Link href={`/projects/${readback.caseId}/retrospective?dossier=${readback.dossierId}`}>Write the retrospective</Link>
        </p>
      )}
      {decide && (
        <section className="wr-block" aria-label="Close or return">
          <h3 className="wr-head">Close or return</h3>
          <p className="wr-line">Closing the project doesn’t erase debt.</p>
          <TextArea label={offered.includes('return') ? 'Note (needed to return)' : 'Note'} limit={NOTE_LIMIT} value={note} onChange={(ev) => setNote(ev.target.value)} />
          <div className="wr-buttons">
            {offered.includes('approve') && <Press send={send} command={decide} label="Close the project" held={decideHeld('approve', note)} onPress={() => void verdict('approve')} />}
            {offered.includes('return') && <Press send={send} command={decide} label="Return with a note" kind="secondary" held={decideHeld('return', note)} onPress={() => void verdict('return')} />}
          </div>
        </section>
      )}
      {!decide && changed && note.trim() !== '' && <TextArea label="Your unsent note" readOnly value={note} onChange={() => undefined} />}
      {replace && <ReplaceForm send={tracked(IDS.replace)} command={replace} />}
      {finance && <FinanceForm readback={readback} send={tracked(IDS.finance)} command={finance} />}
      {notice && (
        <Callout kind="problem">
          {notice.text}
          {notice.detail && <> {notice.detail}</>}
        </Callout>
      )}
    </div>
  );
}
