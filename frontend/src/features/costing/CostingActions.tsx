'use client';

// F-99: the costing sheet's own controls (the adapter's `Actions` slot): the decision on the approval waiting now (Approve, Return
// with a note, Refuse) and the price change forms. Which of them is drawn follows the response (the step waiting, can_propose,
// can_decide); who may decide a step is the server's answer, never a rule here. Sending, locking and error words are
// useWorkCommand's, and the result is told from the re-read, never from the 200.
import { useState } from 'react';

import { Button, Callout, Select, TextArea, TextField, useToastWhen, type SelectOption } from '@/components';
import type { CommandDescriptor, LineActionsProps } from '@/features/workspace/adapter';
import { useWorkCommand } from '@/features/workspace/useWorkCommand';

import { nextApproval, type Readback } from './model';

const NOTE_LIMIT = 4000;
const REASON_LIMIT = 2000;
const LOCKED = 'Check the page before trying again.';
const AMOUNT = /^-?\d+(\.\d{1,2})?$/;
const DONE: Record<string, string> = {
  'costing.approve': 'Your approval is recorded.',
  'costing.return': 'The costing is returned.',
  'costing.reject': 'Your refusal is recorded.',
  'costing.adjust': 'The price change is proposed.',
  'costing.change-approve': 'The price change is approved.',
  'costing.change-return': 'The price change is returned.',
};

export function CostingActions({ readback, ctx, commands, reload, onAccessLost }: LineActionsProps<Readback>) {
  const p = readback.pricing;
  const send = useWorkCommand({ item: ctx, reload, onAccessLost });
  const [last, setLast] = useState<string | null>(null);
  const [note, setNote] = useState('');
  const [noteError, setNoteError] = useState<string | null>(null);
  const [target, setTarget] = useState('');
  const [amount, setAmount] = useState('');
  const [reason, setReason] = useState('');
  const [tried, setTried] = useState(false);
  const [decision, setDecision] = useState('');

  const byId = (id: string) => commands.find((c) => c.id === id);
  const step = nextApproval(p.approvals);
  const locked = commands.some((c) => send.lockedReason(c.id) !== null);
  const targets: SelectOption[] = p.adjustment_targets.map((t) => ({ value: t.key, label: `${t.label} (up to ${t.max_absolute_value}${p.adjustment_currency ? ` ${p.adjustment_currency}` : ''})` }));

  const press = async (command: CommandDescriptor, inputs: Record<string, unknown>) => {
    setLast(command.id);
    await send.run(command, inputs);
  };
  const button = (c: CommandDescriptor, kind: 'primary' | 'secondary' | 'reject', onClick: () => void) => {
    const reasonText = c.disabledReason ?? send.lockedReason(c.id) ?? (locked ? LOCKED : null);
    return (
      <Button key={c.id} kind={kind} disabled={send.busy || reasonText !== null} busy={send.pending === c.id && !send.lockedReason(c.id)} busyLabel="Working…" reason={reasonText} onClick={onClick}>
        {c.label}
      </Button>
    );
  };

  const done = send.notice?.kind === 'success' ? send.notice.text.replace(/^Done\./, DONE[last ?? ''] ?? 'Recorded.') : null;
  useToastWhen(done);

  const decide = (c: CommandDescriptor) => {
    if (c.id !== 'costing.approve' && note.trim() === '') {
      setNoteError('Write a note first.');
      return;
    }
    setNoteError(null);
    void press(c, { note });
  };
  const approvals = (['costing.approve', 'costing.return', 'costing.reject'] as const).map(byId).filter((c): c is CommandDescriptor => !!c);
  const adjust = byId('costing.adjust');
  const changeApprove = byId('costing.change-approve');
  const changeReturn = byId('costing.change-return');
  const adjustError = !target ? 'Choose what to adjust.' : !AMOUNT.test(amount.trim()) ? 'Write the amount in naira, for example 250000 or -50000.50.' : reason.trim() === '' ? 'Say why.' : null;

  return (
    <div className="wr-actions">
      {step && p.current && approvals.length > 0 && (
        <section className="wr-block" aria-label="Your approval">
          <h3 className="wr-head">Your approval: {step.label}</h3>
          <p className="wr-line">The server checks that you are the person for this step. A new price change starts the approvals again.</p>
          <TextArea label="Note" hint="Needed to return or refuse" limit={NOTE_LIMIT} value={note} error={noteError ?? undefined} onChange={(e) => setNote(e.target.value)} />
          <div className="wr-buttons">{approvals.map((c) => button(c, c.id === 'costing.approve' ? 'primary' : c.id === 'costing.reject' ? 'reject' : 'secondary', () => decide(c)))}</div>
        </section>
      )}
      {adjust && p.can_propose && p.adjustment_targets.length > 0 && (
        <section className="wr-block" aria-label="Propose a price change">
          <h3 className="wr-head">Propose a price change</h3>
          <Select label="What to adjust" placeholder="Choose a line" options={targets} value={target || undefined} onChange={setTarget} error={tried && !target ? 'Choose what to adjust.' : undefined} />
          <TextField label="Amount" hint={`In naira${p.adjustment_currency ? ` (${p.adjustment_currency})` : ''}; a negative amount lowers the price`} value={amount} maxLength={40} onChange={(e) => setAmount(e.target.value)} error={tried && target && !AMOUNT.test(amount.trim()) ? 'Write the amount in naira, for example 250000 or -50000.50.' : undefined} />
          <TextArea label="Reason" limit={REASON_LIMIT} value={reason} error={tried && target && AMOUNT.test(amount.trim()) && reason.trim() === '' ? 'Say why.' : undefined} onChange={(e) => setReason(e.target.value)} />
          <div className="wr-buttons">
            {button(adjust, 'primary', () => {
              setTried(true);
              if (adjustError) return;
              void press(adjust, { target, amount: amount.trim(), reason });
            })}
          </div>
        </section>
      )}
      {changeApprove && changeReturn && p.can_decide && p.finance_pending && (
        <section className="wr-block" aria-label="Decide the price change">
          <h3 className="wr-head">Decide the price change</h3>
          <TextArea label="Reason" limit={REASON_LIMIT} value={decision} error={tried && decision.trim() === '' ? 'Say why.' : undefined} onChange={(e) => setDecision(e.target.value)} />
          <div className="wr-buttons">
            {[changeApprove, changeReturn].map((c) =>
              button(c, c === changeApprove ? 'primary' : 'secondary', () => {
                setTried(true);
                if (decision.trim() === '') return;
                void press(c, { reason: decision });
              }),
            )}
          </div>
        </section>
      )}
      {send.notice?.kind === 'error' && (
        <Callout kind="problem">
          {send.notice.text}
          {send.notice.detail && <> {send.notice.detail}</>}
        </Callout>
      )}
    </div>
  );
}
