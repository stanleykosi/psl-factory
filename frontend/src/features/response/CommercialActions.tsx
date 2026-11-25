'use client';

// F-136: the client's response and SOW signature controls (the adapter's `Actions` slot): record the client's response, record the
// two signatures, adopt the signed baseline. The choices (sent versions, signers, proof files, requirements) are the response's own
// lists; who may do what is the server's answer, shown as the reason beside a button that cannot be pressed. Recording a signature
// is an uncertain-effect write: it is sent only from a press, never repeated, and useWorkCommand locks it after an unknown result.
// The result is told from the re-read, never from the 201.
import { useState } from 'react';

import { Button, Callout, Checkbox, Select, TextArea, TextField, useToastWhen, type SelectOption } from '@/components';
import type { CommandDescriptor, LineActionsProps } from '@/features/workspace/adapter';
import { useWorkCommand } from '@/features/workspace/useWorkCommand';

import { CHANNELS, OUTCOMES, signedResponse, type CommercialDesk } from './commercialModel';

const NOTE_LIMIT = 4000;
const NAME_LIMIT = 160;
const TEXT_LIMIT = 200;
const LOCATOR_LIMIT = 500;
const LOCKED = 'Check the page before trying again.';
const DONE: Record<string, string> = {
  'commercial-response.witness': 'The client’s response is recorded.',
  'commercial-response.signatures': 'The signatures are recorded.',
  'commercial-response.adopt': 'The signed baseline is adopted.',
};
const labelled = (table: Record<string, string>): SelectOption[] => Object.entries(table).map(([value, label]) => ({ value, label }));

export function CommercialActions({ readback: d, ctx, commands, reload, onAccessLost }: LineActionsProps<CommercialDesk>) {
  const send = useWorkCommand({ item: ctx, reload, onAccessLost });
  const [last, setLast] = useState<string | null>(null);
  const [form, setForm] = useState<Record<string, string>>({});
  const [proofs, setProofs] = useState<number[]>([]);
  const [checked, setChecked] = useState<Record<string, boolean>>({});
  const [tried, setTried] = useState<string | null>(null);

  const field = (name: string) => form[name] ?? '';
  const set = (name: string) => (value: string) => setForm({ ...form, [name]: value });
  const tick = (name: string) => (on: boolean) => setChecked({ ...checked, [name]: on });
  const byId = (id: string) => commands.find((c) => c.id === id);
  const locked = commands.some((c) => send.lockedReason(c.id) !== null);
  const signed = signedResponse(d);

  const press = async (command: CommandDescriptor, inputs: Record<string, unknown>) => {
    setLast(command.id);
    await send.run(command, inputs);
  };
  const button = (c: CommandDescriptor, onClick: () => void) => {
    const reason = c.disabledReason ?? send.lockedReason(c.id) ?? (locked ? LOCKED : null);
    return (
      <Button kind="primary" disabled={send.busy || reason !== null} busy={send.pending === c.id && !send.lockedReason(c.id)} busyLabel="Working…" reason={reason} onClick={onClick}>
        {c.label}
      </Button>
    );
  };
  const shown = (id: string, ...problems: (string | null)[]) => (tried === id ? (problems.find(Boolean) ?? undefined) : undefined);
  const need = (value: string, message: string) => (value.trim() ? null : message);

  const done = send.notice?.kind === 'success' ? send.notice.text.replace(/^Done\./, DONE[last ?? ''] ?? 'Recorded.') : null;
  useToastWhen(done);

  const receipts: SelectOption[] = d.receipts.map((r) => ({ value: String(r.id), label: r.label }));
  const parties: SelectOption[] = d.parties.map((p) => ({ value: p.reference, label: p.label }));
  const prds: SelectOption[] = d.requirements.map((r) => ({ value: String(r.id), label: `Requirements, version ${r.version} (record ${r.id})` }));
  const signatureProofs: SelectOption[] = d.signature_proofs.map((s) => ({ value: String(s.id), label: `Signature proof, version ${s.version} (record ${s.id})` }));

  const witness = byId('commercial-response.witness');
  const signatures = byId('commercial-response.signatures');
  const adopt = byId('commercial-response.adopt');
  const open = !d.adoption?.current;

  const record = () => {
    if (!witness) return;
    setTried('witness');
    const at = new Date(field('at'));
    if (!field('receipt') || !field('name').trim() || Number.isNaN(at.getTime()) || !field('outcome') || proofs.length === 0 || !field('note').trim() || !checked.genuine) return;
    void press(witness, {
      receipt_id: Number(field('receipt')),
      client_name: field('name').trim(),
      responded_at: at.toISOString(),
      outcome: field('outcome'),
      genuine: true,
      proof_ids: proofs,
      note: field('note'),
      party_ref: field('party') || null,
      ...(field('via') ? { received_via: field('via') } : {}),
    });
  };
  const sign = () => {
    if (!signatures || !signed) return;
    setTried('signatures');
    const names = ['sow', 'prd'] as const;
    if (!field('prd') || !field('prd_proof') || !field('note2').trim() || !checked.verified) return;
    if (names.some((n) => !field(`${n}_party`) || !field(`${n}_method`).trim() || !field(`${n}_locator`).trim())) return;
    const one = (n: (typeof names)[number], evidence: number) => ({ evidence_id: evidence, party_ref: field(`${n}_party`), method: field(`${n}_method`).trim(), locator: field(`${n}_locator`).trim(), human_verified: true });
    void press(signatures, { prd_id: Number(field('prd')), signatures: { sow: one('sow', signed.evidence_id), prd: one('prd', Number(field('prd_proof'))) }, note: field('note2') });
  };

  const signer = (n: 'sow' | 'prd', title: string) => (
    <>
      <h4 className="wr-sub">{title}</h4>
      <Select label="Who signed" placeholder="Choose the signer" options={parties} value={field(`${n}_party`) || undefined} onChange={set(`${n}_party`)} error={shown('signatures', field(`${n}_party`) ? null : 'Choose who signed.')} />
      <TextField label="How it was signed" hint="As the signature itself shows it" value={field(`${n}_method`)} maxLength={TEXT_LIMIT} onChange={(ev) => set(`${n}_method`)(ev.target.value)} error={shown('signatures', need(field(`${n}_method`), 'Say how it was signed.'))} />
      <TextField label="Where in the document" hint="The page or place of the signature" value={field(`${n}_locator`)} maxLength={LOCATOR_LIMIT} onChange={(ev) => set(`${n}_locator`)(ev.target.value)} error={shown('signatures', need(field(`${n}_locator`), 'Say where the signature is.'))} />
    </>
  );

  return (
    <div className="wr-actions">
      {witness && open && (
        <section className="wr-block" aria-label="Record the client’s response">
          <h3 className="wr-head">Record the client’s response</h3>
          <Select label="What the client answered" placeholder="Choose what was sent" options={receipts} value={field('receipt') || undefined} onChange={set('receipt')} error={shown('witness', field('receipt') ? null : 'Choose what the client was sent.')} />
          <TextField label="Name of the person who answered" value={field('name')} maxLength={NAME_LIMIT} onChange={(ev) => set('name')(ev.target.value)} error={shown('witness', need(field('name'), 'Add the name.'))} />
          <Select label="Signer the project names" optional placeholder="Not decided" options={parties} value={field('party') || undefined} onChange={set('party')} />
          <Select label="Answer" placeholder="Choose the answer" options={labelled(OUTCOMES)} value={field('outcome') || undefined} onChange={set('outcome')} error={shown('witness', field('outcome') ? null : 'Choose the answer.')} />
          <TextField label="When the client answered" type="datetime-local" value={field('at')} onChange={(ev) => set('at')(ev.target.value)} error={shown('witness', field('at') ? null : 'Add when the client answered.')} />
          <Select label="How the answer reached us" optional placeholder="Not recorded" options={labelled(CHANNELS)} value={field('via') || undefined} onChange={set('via')} />
          <fieldset className="wr-block" aria-label="Proof files">
            <legend className="wr-sub">Proof files</legend>
            {d.owned_files.map((f) => (
              <Checkbox key={f.id} label={f.name} checked={proofs.includes(f.id)} onChange={(ev) => setProofs(ev.target.checked ? [...proofs, f.id] : proofs.filter((p) => p !== f.id))} />
            ))}
            {tried === 'witness' && proofs.length === 0 && <p className="wr-line" role="alert">Choose at least one proof file.</p>}
          </fieldset>
          <TextArea label="Note" limit={NOTE_LIMIT} value={field('note')} onChange={(ev) => set('note')(ev.target.value)} error={shown('witness', need(field('note'), 'Add a note on what the client said.'))} />
          <Checkbox label="This is the client’s own response and I checked it" checked={checked.genuine ?? false} onChange={(ev) => tick('genuine')(ev.target.checked)} error={shown('witness', checked.genuine ? null : 'Tick to confirm.')} />
          <div className="wr-buttons">{button(witness, record)}</div>
        </section>
      )}
      {signatures && signed && open && (
        <section className="wr-block" aria-label="Record the signatures">
          <h3 className="wr-head">Record the signatures</h3>
          <p className="wr-line">The statement of work signature is the one on the client’s signed response. The requirements document is signed separately.</p>
          {signer('sow', 'Statement of work')}
          <h4 className="wr-sub">Requirements document</h4>
          <Select label="Document" placeholder="Choose the document" options={prds} value={field('prd') || undefined} onChange={set('prd')} error={shown('signatures', field('prd') ? null : 'Choose the document.')} />
          <Select label="Signature proof" placeholder="Choose the proof" options={signatureProofs} value={field('prd_proof') || undefined} onChange={set('prd_proof')} error={shown('signatures', field('prd_proof') ? null : 'Choose the proof.')} />
          {signer('prd', 'Requirements signature')}
          <TextArea label="Note" limit={NOTE_LIMIT} value={field('note2')} onChange={(ev) => set('note2')(ev.target.value)} error={shown('signatures', need(field('note2'), 'Add a note.'))} />
          <Checkbox label="I checked each signature against its document myself" checked={checked.verified ?? false} onChange={(ev) => tick('verified')(ev.target.checked)} error={shown('signatures', checked.verified ? null : 'Tick to confirm.')} />
          <div className="wr-buttons">{button(signatures, sign)}</div>
        </section>
      )}
      {adopt && signed && d.packet && open && (
        <section className="wr-block" aria-label="Adopt the signed baseline">
          <h3 className="wr-head">Adopt the signed baseline</h3>
          <p className="wr-line">This makes the signed statement of work and requirements the baseline for the project.</p>
          <div className="wr-buttons">{button(adopt, () => void press(adopt, {}))}</div>
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
