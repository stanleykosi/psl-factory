'use client';

// F-117: the two forms. "Record Support's reply" is the PM's own record, labelled so; "Support's own acknowledgement" is the receipt the
// signed-in recipient gives, and is drawn only for a row the read says can acknowledge. Nothing is prefilled; every choice is from a
// served list; a form keeps what was typed when a press is refused. One press sends one request.
import { useState } from 'react';

import { Button, Segmented, Select, TextArea, TextField, type SelectOption } from '@/components';
import type { CommandDescriptor } from '@/features/workspace/adapter';

import { ackHeld, ackInputs, ackRows, channelWord, emptyAck, emptyReply, GAP_LIMIT, NOTE_LIMIT, parseGaps, replyHeld, replyInputs, TEXT, type Receipts, type Replies } from './handoverModel';
import { Press, type Send } from './Press';

const STATUS_OPTIONS = [
  { value: 'received' as const, label: 'Received' },
  { value: 'gaps' as const, label: 'Gaps found' },
];
const proofOptions = (proofs: { id: number; version: number; kind: string }[]): SelectOption[] => proofs.map((p) => ({ value: String(p.id), label: `${p.kind} v${p.version}` }));

export function ReplyForm({ replies, send, command, closed, onClosed }: { replies: Replies; send: Send; command: CommandDescriptor; closed: boolean; onClosed: (closed: boolean) => void }) {
  const [form, setForm] = useState(emptyReply);
  // one row is the recipient and one role is the role (shown as fixed text); with several the person chooses, and nothing is chosen for them
  const only = replies.receipts.length === 1 ? String(replies.receipts[0].id) : undefined;
  const f = { ...form, receipt: form.receipt ?? only, role: form.role ?? (replies.roles.length === 1 ? replies.roles[0] : undefined) };
  const set = <K extends keyof typeof form>(key: K, value: (typeof form)[K]) => setForm({ ...form, [key]: value });
  const held = replyHeld(replies, f);
  const gaps = f.status === 'gaps' ? parseGaps(f.gaps) : null;
  const press = async () => {
    if (held !== null) return;
    const outcome = await send.run(command, replyInputs(replies, f));
    if (outcome === 'sent') {
      setForm(emptyReply());
      onClosed(true);
    }
  };
  if (closed) {
    return (
      <div className="wr-buttons">
        <Button kind="secondary" onClick={() => onClosed(false)}>
          Record another reply
        </Button>
      </div>
    );
  }
  return (
    <section className="wr-block" aria-label="Record Support’s reply">
      <h3 className="wr-head">Record Support’s reply</h3>
      <p className="wr-line">Recorded by you for Support.</p>
      {replies.receipts.length > 1 && (
        <Select label="Which Support recipient?" placeholder="Choose a recipient" options={replies.receipts.map((r) => ({ value: String(r.id), label: r.recipient }))} value={f.receipt} onChange={(v) => set('receipt', v)} />
      )}
      <TextField label="Who replied" value={f.party} maxLength={200} onChange={(ev) => set('party', ev.target.value)} />
      {replies.roles.length === 1 ? (
        <p className="wr-line">Recording as {replies.roles[0]}</p>
      ) : (
        <Select label="Role" placeholder="Choose your role" options={replies.roles.map((r) => ({ value: r, label: r }))} value={f.role} onChange={(v) => set('role', v)} />
      )}
      <Select label="How they replied" placeholder="Choose a channel" options={replies.channels.map((c) => ({ value: c, label: channelWord(c) }))} value={f.channel} onChange={(v) => set('channel', v)} />
      <TextField label="When they replied" type="datetime-local" value={f.when} onChange={(ev) => set('when', ev.target.value)} />
      <div className="psl-field">
        <span className="wr-sub" id="handover-status-label">
          What Support said
        </span>
        <Segmented labelledBy="handover-status-label" options={STATUS_OPTIONS} value={f.status} onChange={(v) => set('status', v)} />
      </div>
      {f.status === 'gaps' && (
        <TextArea label="Gaps" hint={`One gap per line, up to ${GAP_LIMIT} characters each.`} value={f.gaps} onChange={(ev) => set('gaps', ev.target.value)} error={f.gaps.trim() !== '' ? (gaps?.problem ?? undefined) : undefined} />
      )}
      <TextArea label="Note" limit={NOTE_LIMIT} value={f.note} onChange={(ev) => set('note', ev.target.value)} />
      {replies.proofs.length === 0 ? <p className="wr-line">{TEXT.noProof}</p> : <Select label="Proof" placeholder="Choose a proof record" options={proofOptions(replies.proofs)} value={f.proof} onChange={(v) => set('proof', v)} />}
      <div className="wr-buttons">
        <Press send={send} command={command} label="Record reply" held={held} onPress={() => void press()} />
      </div>
    </section>
  );
}

export function AckForm({ receipt, send, command }: { receipt: Receipts; send: Send; command: CommandDescriptor }) {
  const [form, setForm] = useState(emptyAck);
  const rows = ackRows(receipt);
  const f = { ...form, receipt: form.receipt ?? (rows.length === 1 ? String(rows[0].id) : undefined) };
  const set = <K extends keyof typeof form>(key: K, value: (typeof form)[K]) => setForm({ ...form, [key]: value });
  const held = ackHeld(receipt, f);
  const press = async () => {
    if (held !== null) return;
    if ((await send.run(command, ackInputs(f))) === 'sent') setForm(emptyAck());
  };
  return (
    <section className="wr-block" aria-label="Support’s own acknowledgement">
      <h3 className="wr-head">Support’s own acknowledgement</h3>
      {rows.length > 1 && <Select label="Which receipt?" placeholder="Choose a receipt" options={rows.map((r) => ({ value: String(r.id), label: `Receipt ${r.id}` }))} value={f.receipt} onChange={(v) => set('receipt', v)} />}
      <div className="psl-field">
        <span className="wr-sub" id="handover-ack-label">
          What you are acknowledging
        </span>
        <Segmented labelledBy="handover-ack-label" options={STATUS_OPTIONS} value={f.status} onChange={(v) => set('status', v)} />
      </div>
      <TextArea label="Acknowledgement note" limit={NOTE_LIMIT} value={f.note} onChange={(ev) => set('note', ev.target.value)} />
      {receipt.proofs.length === 0 ? <p className="wr-line">{TEXT.noProof}</p> : <Select label="Acknowledgement proof" placeholder="Choose a proof record" options={proofOptions(receipt.proofs)} value={f.proof} onChange={(v) => set('proof', v)} />}
      <div className="wr-buttons">
        <Press send={send} command={command} label="Acknowledge" held={held} onPress={() => void press()} />
      </div>
    </section>
  );
}
