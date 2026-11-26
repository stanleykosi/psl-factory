'use client';

// F-114: the sign-off form. For each of PM and Client: a signed copy (uploaded, then kept through the proofs call once the person ticks
// that they checked it), the signature record to use (chosen from the read's list, never typed), and the six signer details the signed
// record shows. Nothing is prefilled. "Record signatures" sends one request per press; "Recorded" is never said here: the page says what
// the re-read shows.
import { useState } from 'react';

import { Checkbox, Select, TextArea, TextField, type SelectOption } from '@/components';
import { EvidencePicker } from '@/features/workspace/EvidencePicker';
import type { UploadedFile } from '@/features/workspace/evidence';

import { emptySigner, FIELD_LIMIT, latestReceipt, NOTE_LIMIT, signerNeedsReconciliation, signoffHeld, signoffInputs, SIGNER_FIELDS, TEXT, type SignerFields, type Signoff } from './goLiveModel';
import { Press, type Send } from './Press';
import type { CommandDescriptor } from '@/features/workspace/adapter';

type Role = 'PM' | 'Client';
const proofLabel = (p: { id: number; version: number }) => `Signature record #${p.id}, version ${p.version}`;

type SignerProps = {
  who: Role;
  s: Signoff;
  caseId: string;
  send: Send;
  proofCommand: CommandDescriptor | undefined;
  fields: SignerFields;
  onFields: (next: SignerFields) => void;
  value: string | undefined;
  onPick: (id: string) => void;
  /** The proofs listed when a copy was added, so the one new row after the re-read can be chosen. */
  onAdded: (listed: number[]) => void;
  error?: string;
};

function Signer({ who, s, caseId, send, proofCommand, fields, onFields, value, onPick, onAdded, error }: SignerProps) {
  const [file, setFile] = useState<UploadedFile | null>(null);
  const [checked, setChecked] = useState(false);
  const options: SelectOption[] = s.proofs.map((p) => ({ value: String(p.id), label: proofLabel(p) }));

  const heldUpload = !file ? 'Upload the signed copy (a PDF).' : !checked ? 'Tick to confirm you checked the file.' : null;
  const upload = async () => {
    if (!proofCommand || !file || !checked) return;
    const listed = s.proofs.map((p) => p.id);
    const outcome = await send.run(proofCommand, { upload_id: file.upload_id });
    if (outcome === 'sent') {
      onAdded(listed);
      setFile(null);
      setChecked(false);
    }
  };
  const set = (key: keyof SignerFields) => (ev: { target: { value: string } }) => onFields({ ...fields, [key]: ev.target.value });

  return (
    <section className="wr-block" aria-label={`${who} signature`}>
      <h3 className="wr-head">{who === 'PM' ? 'PM signature' : 'Client signature'}</h3>
      <EvidencePicker caseId={caseId} value={file} onChange={setFile} accept={['.pdf']} label={`${who} signed copy`} disabledReason={send.busy ? 'Wait for the press to finish.' : undefined} />
      <Checkbox label="I checked this is the signed copy of this go-live document for this signer" checked={checked} onChange={(ev) => setChecked(ev.target.checked)} />
      {proofCommand && <Press send={send} command={proofCommand} label="Add signed copy" kind="secondary" held={heldUpload} onPress={() => void upload()} />}
      <Select label={`${who} signature record`} placeholder="Choose a signature record" options={options} value={value} onChange={onPick} error={error} />
      {s.proofs.length === 0 && <p className="wr-line">No signature record is on file yet. Add a signed copy first.</p>}
      {SIGNER_FIELDS.map(([key, label]) => (
        <TextField key={key} label={`${who} ${label.toLowerCase()}`} value={fields[key]} maxLength={FIELD_LIMIT} onChange={set(key)} />
      ))}
      <TextField label={`${who} signed at`} type="datetime-local" value={fields.signed_at} onChange={set('signed_at')} />
      {signerNeedsReconciliation(fields) && <p className="wr-line">{TEXT.reconcile}</p>}
    </section>
  );
}

export function SignoffForm({ s, caseId, send, commands }: { s: Signoff; caseId: string; send: Send; commands: CommandDescriptor[] }) {
  const [picked, setPicked] = useState<{ PM?: string; Client?: string }>({});
  // proofs listed when each signer's copy was added; exactly one new row after the re-read is that signer's choice, until they choose
  const [before, setBefore] = useState<{ PM?: number[]; Client?: number[] }>({});
  const valueOf = (role: Role) => {
    const prior = before[role];
    const added = prior === undefined ? [] : s.proofs.filter((p) => !prior.includes(p.id));
    return picked[role] ?? (added.length === 1 ? String(added[0].id) : undefined);
  };
  const pm = valueOf('PM');
  const client = valueOf('Client');
  const [signers, setSigners] = useState<{ PM: SignerFields; Client: SignerFields }>({ PM: emptySigner(), Client: emptySigner() });
  const [mode, setMode] = useState<string | undefined>('fresh_signatures');
  const [note, setNote] = useState('');
  const command = commands.find((c) => c.id === 'go-live.signoff');
  if (!command || latestReceipt(s) === null) return null;

  const choice = { pm, client, signers, mode, note };
  const held = signoffHeld(s, choice);
  const same = pm !== undefined && pm === client;
  const press = () => {
    if (held === null) void send.run(command, signoffInputs(s, choice));
  };
  return (
    <section className="wr-block" aria-label="Record the signatures">
      <h3 className="wr-head">Record the signatures</h3>
      <Signer who="PM" s={s} caseId={caseId} send={send} proofCommand={commands.find((c) => c.id === 'go-live.proof_pm')} fields={signers.PM} onFields={(f) => setSigners({ ...signers, PM: f })} value={pm} onPick={(id) => setPicked({ ...picked, PM: id })} onAdded={(l) => setBefore({ ...before, PM: l })} />
      <Signer who="Client" s={s} caseId={caseId} send={send} proofCommand={commands.find((c) => c.id === 'go-live.proof_client')} fields={signers.Client} onFields={(f) => setSigners({ ...signers, Client: f })} value={client} onPick={(id) => setPicked({ ...picked, Client: id })} onAdded={(l) => setBefore({ ...before, Client: l })} error={same ? TEXT.sameProof : undefined} />
      {s.prior_acceptance_id !== null && (
        <Select
          label="How to record"
          placeholder="Choose how to record"
          options={[
            { value: 'fresh_signatures', label: 'New signatures' },
            { value: 'metadata_binding', label: `Use the earlier acceptance (#${s.prior_acceptance_id})` },
          ]}
          value={mode}
          onChange={setMode}
        />
      )}
      <TextArea label="Note" limit={NOTE_LIMIT} value={note} onChange={(ev) => setNote(ev.target.value)} />
      <div className="wr-buttons">
        <Press send={send} command={command} label="Record signatures" held={held} onPress={press} />
      </div>
    </section>
  );
}
