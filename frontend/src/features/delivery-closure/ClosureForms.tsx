'use client';

// F-118: the replace-the-report form and the Finance confirmation form. Nothing is prefilled; the Finance proof is chosen from the
// list the read serves (empty: the form says so and stays held); a form keeps what was typed when a press is refused. One press sends
// one request, and the result is told from the re-read, never from the answer to the press.
import { useState } from 'react';

import { Checkbox, Select, TextArea, TextField } from '@/components';
import type { CommandDescriptor } from '@/features/workspace/adapter';

import { emptyFinance, emptyReplace, financeHeld, financeInputs, FINANCE_NOTE_LIMIT, REASON_LIMIT, replaceHeld, replaceInputs, REPORT_LIMIT, SOURCE_LIMIT, TEXT, type Readback } from './closureModel';
import { Press, type Send } from './Press';

export function ReplaceForm({ send, command }: { send: Send; command: CommandDescriptor }) {
  const [form, setForm] = useState(emptyReplace);
  const held = replaceHeld(form);
  const press = async () => {
    if (held !== null) return;
    if ((await send.run(command, replaceInputs(form))) === 'sent') setForm(emptyReplace());
  };
  return (
    <section className="wr-block" aria-label="Replace the report">
      <h3 className="wr-head">Replace the report</h3>
      <TextArea label="Report" limit={REPORT_LIMIT} value={form.report} onChange={(ev) => setForm({ ...form, report: ev.target.value })} />
      <TextField label="Where it comes from" maxLength={SOURCE_LIMIT} value={form.source} onChange={(ev) => setForm({ ...form, source: ev.target.value })} />
      <TextArea label="Why it is replaced" limit={REASON_LIMIT} value={form.reason} onChange={(ev) => setForm({ ...form, reason: ev.target.value })} />
      <div className="wr-buttons">
        <Press send={send} command={command} label="Replace the report" held={held} onPress={() => void press()} />
      </div>
    </section>
  );
}

export function FinanceForm({ readback, send, command }: { readback: Readback; send: Send; command: CommandDescriptor }) {
  const [form, setForm] = useState(emptyFinance);
  const held = financeHeld(readback, form);
  const evidence = readback.financeEvidence;
  const press = async () => {
    if (held !== null) return;
    if ((await send.run(command, financeInputs(form))) === 'sent') setForm(emptyFinance());
  };
  return (
    <section className="wr-block" aria-label="Confirm milestone notifications">
      <h3 className="wr-head">Confirm milestone notifications</h3>
      <Checkbox label="These are all the milestone notifications" checked={form.complete} onChange={() => setForm({ ...form, complete: !form.complete })} />
      {evidence.length === 0 ? (
        <p className="wr-line">{TEXT.noFinanceProof}</p>
      ) : (
        <Select label="Finance proof" placeholder="Choose a proof record" options={evidence.map((p) => ({ value: String(p.id), label: p.label }))} value={form.proof} onChange={(v) => setForm({ ...form, proof: v })} />
      )}
      <TextArea label="Note" limit={FINANCE_NOTE_LIMIT} value={form.note} onChange={(ev) => setForm({ ...form, note: ev.target.value })} />
      <div className="wr-buttons">
        <Press send={send} command={command} label="Confirm milestone notifications" held={held} onPress={() => void press()} />
      </div>
    </section>
  );
}
