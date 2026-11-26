'use client';

// F-113B: the release page's own controls (the adapter's `Actions` slot): decide the planning exit (Approve for release, Return with a
// note), prepare release readiness, and record the release with its checked PDF. Which of them is drawn is the reads' answer
// (`verdicts`, `actions`); the page has no rule about who may decide. Sending, locking and error words are useWorkCommand's. The
// result is told from the re-read (the sections), never from the 200, so no success text is drawn here.
import Link from 'next/link';
import { useState } from 'react';

import { Button, Callout, Checkbox, Select, TextArea, TextField, type SelectOption } from '@/components';
import type { CommandDescriptor, LineActionsProps } from '@/features/workspace/adapter';
import { EvidencePicker } from '@/features/workspace/EvidencePicker';
import type { EvidenceId, UploadedFile } from '@/features/workspace/evidence';
import { useWorkCommand } from '@/features/workspace/useWorkCommand';

import { boardState, decideInputs, decisionHeld, NO_EVIDENCE, observeInputs, type Readback } from './releaseModel';

const NOTE_LIMIT = 4000;
const REFERENCE_LIMIT = 240;
const ENVIRONMENT_LIMIT = 160;
const LOCKED = 'Check the page before trying again.';
const IDS = ['release.decide', 'release.prepare_readiness', 'release.observe'];

const proofLabel = (p: { kind: string; version: number }) => `${p.kind.replaceAll('_', ' ')} · version ${p.version}`;

/** A date-time-local value as the ISO time the server reads, or null when it is not a time. */
const isoOf = (value: string): string | null => {
  const at = new Date(value);
  return value && !Number.isNaN(at.getTime()) ? at.toISOString() : null;
};

export function ReleaseActions({ readback, ctx, commands, reload, onAccessLost }: LineActionsProps<Readback>) {
  const { register: r, exit: e } = readback;
  const send = useWorkCommand({ item: ctx, reload, onAccessLost });
  const state = boardState(readback, ctx);
  const byId = (id: string) => commands.find((c) => c.id === id);
  const locked = IDS.some((id) => send.lockedReason(id) !== null);

  const [pressed, setPressed] = useState('');
  const [note, setNote] = useState('');
  const [evidence, setEvidence] = useState<string | undefined>();
  const [issue, setIssue] = useState<string | undefined>();

  const [releasedAt, setReleasedAt] = useState('');
  const [reference, setReference] = useState('');
  const [environment, setEnvironment] = useState('');
  const [releaseNote, setReleaseNote] = useState('');
  const [file, setFile] = useState<UploadedFile | null>(null);
  const [checked, setChecked] = useState(false);
  const [readinessId, setReadinessId] = useState<string | undefined>();

  const button = (c: CommandDescriptor, label: string, kind: 'primary' | 'secondary', held: string | null, onClick: () => void) => {
    const reason = c.disabledReason ?? send.lockedReason(c.id) ?? (locked ? LOCKED : null) ?? held;
    return (
      <Button key={c.id + label} kind={kind} disabled={send.busy || reason !== null} busy={send.pending === c.id && pressed === label && !send.lockedReason(c.id)} busyLabel="Working…" reason={reason}
        onClick={() => {
          setPressed(label);
          onClick();
        }}
      >
        {label}
      </Button>
    );
  };

  // ---- decide the planning exit ----
  const decide = byId('release.decide');
  const offers = (v: 'approve' | 'return') => e.verdicts.includes(v);
  const showDecide = !!decide && (offers('approve') || offers('return')) && (state === 'default' || state === 'decision' || state === 'returned');
  const proofs: SelectOption[] = e.proofs.map((p) => ({ value: String(p.id), label: proofLabel(p) }));
  const issues: SelectOption[] = e.blockers.map((b) => ({ value: String(b.id), label: b.reference }));
  const chosenEvidence = evidence === undefined ? null : (Number(evidence) as EvidenceId);
  const choice = (verdict: 'approve' | 'return') => ({ verdict, note, evidenceId: chosenEvidence, issueId: issue === undefined ? null : Number(issue) });
  const decideNow = (verdict: 'approve' | 'return') => {
    if (decide) void send.run(decide, decideInputs(e, choice(verdict)));
  };

  // ---- prepare readiness ----
  const prepare = byId('release.prepare_readiness');
  const showPrepare = !!prepare && r.actions.includes('prepare_readiness');

  // ---- record the release ----
  const observe = byId('release.observe');
  const showObserve = !!observe && r.actions.includes('observe_release') && r.release === null;
  const at = isoOf(releasedAt);
  const needsPick = r.readiness_ids.length > 1;
  const observeHeld =
    at === null ? 'Add when the release happened.'
    : reference.trim() === '' ? 'Add the release reference.'
    : releaseNote.trim() === '' ? 'Add a note.'
    : needsPick && readinessId === undefined ? 'Choose which readiness record this release is for.'
    : !file ? 'Upload the release record (a PDF).'
    : !checked ? 'Tick to confirm you checked the file.'
    : null;
  const observeNow = () => {
    if (!observe || at === null || !file) return;
    void send.run(
      observe,
      observeInputs(r, { releasedAt: at, reference, environment, note: releaseNote, readinessId: readinessId === undefined ? null : Number(readinessId), uploadId: file.upload_id }),
    );
  };

  const notice = send.notice;
  return (
    <div className="wr-actions">
      {state === 'owner_needed' && (
        <p className="wr-line">
          <Link className="psl-link cmp-target" href="/setup/roles">
            Open Setup roles
          </Link>{' '}
          to appoint a PMO Lead.
        </p>
      )}
      {showDecide && decide && (
        <section className="wr-block" aria-label="Decide the planning exit">
          <h3 className="wr-head">Decide the planning exit</h3>
          <TextArea label="Note" hint={offers('return') ? 'Needed to return' : undefined} limit={NOTE_LIMIT} value={note} onChange={(ev) => setNote(ev.target.value)} />
          <Select
            label={e.can_approve_directly ? 'Evidence (optional)' : 'Evidence for this decision'}
            hint={e.can_approve_directly && offers('return') ? 'Needed to return' : undefined}
            placeholder="Choose evidence"
            options={proofs}
            value={evidence}
            onChange={setEvidence}
          />
          {e.proofs.length === 0 && <p className="wr-line">{NO_EVIDENCE}</p>}
          {offers('return') && issues.length > 0 && <Select label="Related issue" optional placeholder="Choose an issue" options={issues} value={issue} onChange={setIssue} />}
          <div className="wr-buttons">
            {offers('approve') && button(decide, 'Approve for release', 'primary', decisionHeld(e, choice('approve')), () => decideNow('approve'))}
            {offers('return') && button(decide, 'Return with a note', 'secondary', decisionHeld(e, choice('return')), () => decideNow('return'))}
          </div>
          {e.can_approve_directly && <p className="wr-line">You can approve this yourself.</p>}
        </section>
      )}
      {showPrepare && prepare && (
        <section className="wr-block" aria-label="Prepare release readiness">
          <div className="wr-buttons">{button(prepare, 'Prepare release readiness', 'primary', null, () => void send.run(prepare))}</div>
        </section>
      )}
      {showObserve && observe && (
        <section className="wr-block" aria-label="Record the release">
          <h3 className="wr-head">Record the release</h3>
          <TextField label="Release date and time" type="datetime-local" value={releasedAt} onChange={(ev) => setReleasedAt(ev.target.value)} />
          <TextField label="Reference" value={reference} maxLength={REFERENCE_LIMIT} onChange={(ev) => setReference(ev.target.value)} />
          <TextField label="Environment" optional value={environment} maxLength={ENVIRONMENT_LIMIT} onChange={(ev) => setEnvironment(ev.target.value)} />
          <TextArea label="Note" limit={NOTE_LIMIT} value={releaseNote} onChange={(ev) => setReleaseNote(ev.target.value)} />
          {needsPick && (
            <Select
              label="Readiness record"
              placeholder="Choose a readiness record"
              options={r.readiness_ids.map((id) => ({ value: String(id), label: `Readiness record ${id}` }))}
              value={readinessId}
              onChange={setReadinessId}
            />
          )}
          <EvidencePicker caseId={ctx.caseId} value={file} onChange={setFile} accept={['.pdf']} label="Release record file" disabledReason={send.busy ? 'Wait for the press to finish.' : undefined} />
          <Checkbox label="I have checked this file is the release record" checked={checked} onChange={(ev) => setChecked(ev.target.checked)} />
          <div className="wr-buttons">{button(observe, 'Record the release', 'primary', observeHeld, observeNow)}</div>
        </section>
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
