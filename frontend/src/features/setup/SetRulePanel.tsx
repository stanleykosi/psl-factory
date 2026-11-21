'use client';

// "Set a rule" (SCR-13-desktop-rules aside): pick one editable rule, tick the roles allowed, then save it as the next
// version. Only rows the API marks editable reach this panel (format.isEditable); /me roles are never consulted.
// Outcomes: 200 re-reads and rebuilds from the new row; 409 shows the message and clears every edit (never
// re-applied); 422 keeps the edits and marks the named fields; a network or server error re-reads once and
// never resends. When the view will not show the panel after the re-read (the right was withdrawn), the outcome goes
// to onEditorGone and the view shows it above the list instead.
import { useRef, useState } from 'react';

import { ApiError } from '@/api/errors';
import { Button, Callout, Checkbox, DateField, FileUpload, Panel, Select, TextField, useToast, type FileState } from '@/components';

import { uploadEvidence } from './api';
import type { RulesPage, RuleRow, SaveBody } from './contract-proposal';
import { fieldsFromMessage, fileToBase64, lagosToday, type RuleField } from './format';
import { useRuleSave } from './useRuleSave';
import { asApiError } from './useSetupRules';

export type ProofState =
  | { status: 'empty' }
  | { status: 'uploading'; filename: string }
  | { status: 'uploaded'; filename: string; size: number; evidenceId: string }
  | { status: 'failed'; message: string };

type Edits = { component: string; roles: string[]; starts: string; why: string; proof: ProofState; caseRevision?: number };
export type Notice = { tone: 'success' | 'problem' | 'warning'; text: string };

const startEdits = (row: RuleRow): Edits => ({
  component: row.component,
  roles: [...(row.editor?.selected ?? [])],
  starts: lagosToday(),
  why: '',
  proof: { status: 'empty' },
});

type Props = {
  rows: RuleRow[];
  refresh: () => Promise<RulesPage | ApiError>;
  signOut: (error: ApiError) => void;
  /** Whether the view still shows this panel once a re-read returns this page; the view decides, from its own rows. */
  staysOpen: (page: RulesPage) => boolean;
  /** The re-read closes the panel, so the view shows the outcome above the list. */
  onEditorGone: (notice: Notice) => void;
};

export const EDITOR_GONE = 'You can no longer change these rules, so the Set a rule panel has closed.';
export const NOT_SAVED = 'Nothing you entered was saved.';

/** A save outcome callout; it takes focus when shown. The views also use it above the list once the panel has closed. */
export function OutcomeNotice({ notice }: { notice: Notice }) {
  const box = (
    <Callout kind={notice.tone} focusOnShow className="setup-notice">
      {notice.text}
    </Callout>
  );
  // a warning Callout has no live role of its own: the outcome answers the save, so it is an alert, as on base
  return notice.tone === 'warning' ? <div role="alert">{box}</div> : box;
}

export function SetRulePanel({ rows, refresh, signOut, staysOpen, onEditorGone }: Props) {
  const [selected, setSelected] = useState(rows[0].component);
  const row = rows.find((r) => r.component === selected) ?? rows[0];
  const [edits, setEdits] = useState<Edits>(() => startEdits(row));
  const current = edits.component === row.component ? edits : startEdits(row);
  const toast = useToast();
  const [notice, setNotice] = useState<Notice | null>(null);
  const [invalid, setInvalid] = useState<Set<RuleField>>(new Set());
  const [locked, setLocked] = useState(false);
  // Bumped whenever the edits are thrown away, so an upload that finishes later cannot attach to the new edit.
  const generation = useRef(0);
  const { busy, save } = useRuleSave(refresh);
  const options = row.editor?.options ?? [];

  const patch = (change: Partial<Edits>) => setEdits((e) => ({ ...(e.component === row.component ? e : startEdits(row)), ...change }));
  const resetTo = (next: RuleRow) => {
    generation.current += 1;
    setEdits(startEdits(next));
  };
  const reloadedRow = (page: RulesPage | ApiError) => (page instanceof ApiError ? undefined : page.items.find((r) => r.component === row.component));
  // Shows the outcome in the panel, or hands it to the view when the re-read closes the panel.
  // A save that went through is a toast (D-151); when the panel closes, the permission state stays as a Callout.
  const announce = (page: RulesPage | ApiError, next: Notice, rejected = false) => {
    const gone = !(page instanceof ApiError) && !staysOpen(page);
    if (next.tone === 'success') {
      toast.show(next.text);
      if (gone) onEditorGone({ tone: 'warning', text: EDITOR_GONE });
      else setNotice(null);
      return;
    }
    if (gone) {
      onEditorGone({ ...next, text: [next.text, EDITOR_GONE, rejected ? NOT_SAVED : ''].join(' ').trim() });
      return;
    }
    setNotice(next);
  };

  const pickRule = (component: string) => {
    generation.current += 1;
    setSelected(component);
    setEdits(startEdits(rows.find((r) => r.component === component) ?? rows[0]));
    setNotice(null);
    setInvalid(new Set());
    setLocked(false);
  };

  const toggleRole = (role: string, on: boolean) => {
    patch({ roles: on ? [...current.roles.filter((r) => r !== role), role] : current.roles.filter((r) => r !== role) });
  };

  const pickProof = async (file: File) => {
    const proofCase = row.proof_case;
    if (!proofCase) return;
    const gen = generation.current;
    patch({ proof: { status: 'uploading', filename: file.name } });
    try {
      const content = await fileToBase64(file);
      const result = await uploadEvidence(proofCase.case_id, {
        kind: proofCase.evidence_kind,
        filename: file.name,
        content_base64: content,
        case_revision: current.caseRevision ?? proofCase.case_revision,
      });
      if (gen !== generation.current) return;
      setInvalid((s) => without(s, 'evidence_id'));
      setEdits((e) => ({
        ...e,
        proof: { status: 'uploaded', filename: file.name, size: file.size, evidenceId: result.evidence_id },
        caseRevision: result.case_revision ?? e.caseRevision,
      }));
    } catch (error) {
      if (gen !== generation.current) return;
      const apiError = asApiError(error);
      if (apiError.kind === 'unauthenticated') {
        signOut(apiError);
        return;
      }
      if (apiError.kind === 'stale') {
        setEdits((e) => ({ ...e, proof: { status: 'failed', message: 'The record changed. Choose the file again.' }, caseRevision: undefined }));
        void refresh();
        return;
      }
      if (apiError.kind === 'invalid') setInvalid((s) => new Set(s).add('evidence_id'));
      const message =
        apiError.kind === 'invalid' || apiError.kind === 'forbidden' || apiError.kind === 'not_found'
          ? apiError.message
          : 'We couldn’t attach the file. Choose it again.';
      setEdits((e) => ({ ...e, proof: { status: 'failed', message } }));
    }
  };

  const onSave = async () => {
    if (locked) return;
    const sentRevision = row.revision;
    const body: SaveBody = {
      expected_revision: sentRevision,
      value: { roles: options.filter((o) => current.roles.includes(o.role)).map((o) => o.role) },
      starts: current.starts,
    };
    if (current.why.trim() !== '') body.reason = current.why.trim();
    if (current.proof.status === 'uploaded') body.evidence_id = current.proof.evidenceId;

    const outcome = await save(row.component, body);
    if (!outcome) return;
    switch (outcome.kind) {
      case 'saved':
        resetTo(reloadedRow(outcome.page) ?? row);
        setInvalid(new Set());
        announce(outcome.page, { tone: 'success', text: `Saved as version ${outcome.revision}.` });
        return;
      case 'rejected':
        if (outcome.error.kind === 'stale') {
          resetTo(reloadedRow(outcome.page) ?? row);
          setInvalid(new Set());
        }
        announce(outcome.page, { tone: 'problem', text: outcome.error.message }, true);
        return;
      case 'invalid':
        setInvalid(fieldsFromMessage(outcome.message));
        setNotice({ tone: 'problem', text: outcome.message });
        return;
      case 'signed_out':
        signOut(outcome.error);
        return;
      case 'unconfirmed': {
        const fresh = reloadedRow(outcome.page);
        if (fresh && fresh.revision === sentRevision) {
          announce(outcome.page, { tone: 'warning', text: 'We couldn’t confirm the save. Nothing new is shown for this rule, so you can save again.' });
        } else {
          resetTo(fresh ?? row);
          setInvalid(new Set());
          announce(outcome.page, { tone: 'warning', text: 'This rule changed. Check the version shown before saving again.' });
        }
        return;
      }
      case 'unchecked':
        setLocked(true);
        setNotice({ tone: 'problem', text: 'We couldn’t check whether the save went through. Reload the page before saving again.' });
        return;
    }
  };

  const err = (field: RuleField) => invalid.has(field);
  const proof = current.proof;
  const proofState: FileState =
    proof.status === 'uploading'
      ? { status: 'uploading', name: proof.filename }
      : proof.status === 'uploaded'
        ? { status: 'uploaded', name: proof.filename, size: proof.size }
        : { status: 'empty' };
  const proofError = proof.status === 'failed' ? proof.message : err('evidence_id') ? 'Check this proof and choose it again.' : undefined;
  return (
    <Panel head={<h2>Set a rule</h2>} className="setup-panel">
      {notice && <OutcomeNotice notice={notice} />}
      <Select
        label="Rule"
        placeholder="Choose a rule"
        options={rows.map((r) => ({ value: r.component, label: r.name }))}
        value={row.component}
        onChange={pickRule}
      />
      <fieldset className="setup-roles">
        <legend className="psl-label">Roles allowed</legend>
        {options.map((o, i) => (
          <Checkbox
            key={o.role}
            label={o.label}
            checked={current.roles.includes(o.role)}
            error={i === 0 && err('roles') ? 'Choose the roles that may do this.' : undefined}
            onChange={(e) => toggleRole(o.role, e.target.checked)}
          />
        ))}
      </fieldset>
      <DateField
        label="Starts"
        value={current.starts}
        error={err('starts') ? 'Check the start date.' : undefined}
        onChange={(starts) => patch({ starts })}
      />
      <TextField
        label="Why"
        value={current.why}
        error={err('reason') ? 'Check the reason.' : undefined}
        onChange={(e) => patch({ why: e.target.value })}
      />
      {row.proof_case === undefined ? (
        <FileUpload label="Proof" state={{ status: 'empty' }} onFile={() => {}} onRemove={() => {}} disabledReason="Proof can’t be attached here yet." />
      ) : (
        <FileUpload
          label="Proof"
          state={proofState}
          error={proofError}
          onFile={(file) => void pickProof(file)}
          onRemove={() => patch({ proof: { status: 'empty' } })}
        />
      )}
      <Button size="lg" block busy={busy} busyLabel="Saving…" disabled={locked} onClick={() => void onSave()}>
        Save as version {row.revision + 1}
      </Button>
      <p className="setup-footnote">Rules are versioned. Work already decided keeps the version it was decided under.</p>
    </Panel>
  );
}

function without<T>(set: Set<T>, value: T): Set<T> {
  if (!set.has(value)) return set;
  const next = new Set(set);
  next.delete(value);
  return next;
}
