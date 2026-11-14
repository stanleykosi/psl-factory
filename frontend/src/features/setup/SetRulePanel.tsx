'use client';

// "Set a rule" (SCR-13-desktop-rules aside): pick one editable rule, tick the roles allowed, then save it as the next
// version. Only rows the API marks editable reach this panel (format.isEditable); /me roles are never consulted.
// Outcomes: 200 re-reads and rebuilds from the new row; 409 shows the message and clears every edit (never
// re-applied); 422 keeps the edits and marks the named fields; a network or server error re-reads once and
// never resends.
import { useEffect, useId, useRef, useState } from 'react';

import { ApiError } from '@/api/errors';
import { WarningIcon } from '@/shell/icons';

import { uploadEvidence } from './api';
import type { RulesPage, RuleRow, SaveBody } from './contract-proposal';
import { fieldsFromMessage, lagosToday, type RuleField } from './format';
import { TickIcon } from './icons';
import { ProofField, type ProofState } from './ProofField';
import { useRuleSave } from './useRuleSave';
import { asApiError } from './useSetupRules';

type Edits = { component: string; roles: string[]; starts: string; why: string; proof: ProofState; caseRevision?: number };
type Notice = { tone: 'success' | 'problem' | 'warning'; text: string };

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
};

export function SetRulePanel({ rows, refresh, signOut }: Props) {
  const id = useId();
  const [selected, setSelected] = useState(rows[0].component);
  const row = rows.find((r) => r.component === selected) ?? rows[0];
  const [edits, setEdits] = useState<Edits>(() => startEdits(row));
  const current = edits.component === row.component ? edits : startEdits(row);
  const [notice, setNotice] = useState<Notice | null>(null);
  const [invalid, setInvalid] = useState<Set<RuleField>>(new Set());
  const [locked, setLocked] = useState(false);
  const noticeRef = useRef<HTMLDivElement>(null);
  // Bumped whenever the edits are thrown away, so an upload that finishes later cannot attach to the new edit.
  const generation = useRef(0);
  const { busy, save } = useRuleSave(refresh);
  const options = row.editor?.options ?? [];

  useEffect(() => {
    if (notice) noticeRef.current?.focus();
  }, [notice]);

  const patch = (change: Partial<Edits>) => setEdits((e) => ({ ...(e.component === row.component ? e : startEdits(row)), ...change }));
  const resetTo = (next: RuleRow) => {
    generation.current += 1;
    setEdits(startEdits(next));
  };
  const reloadedRow = (page: RulesPage | ApiError) => (page instanceof ApiError ? undefined : page.items.find((r) => r.component === row.component));

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
      const content = await toBase64(file);
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
        setNotice({ tone: 'success', text: `Saved as version ${outcome.revision}.` });
        return;
      case 'rejected':
        if (outcome.error.kind === 'stale') {
          resetTo(reloadedRow(outcome.page) ?? row);
          setInvalid(new Set());
        }
        setNotice({ tone: 'problem', text: outcome.error.message });
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
          setNotice({ tone: 'warning', text: 'We couldn’t confirm the save. Nothing new is shown for this rule, so you can save again.' });
        } else {
          resetTo(fresh ?? row);
          setInvalid(new Set());
          setNotice({ tone: 'warning', text: 'This rule changed. Check the version shown before saving again.' });
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
  return (
    <section className="psl-panel setup-panel" aria-labelledby={`${id}-head`}>
      <h2 className="psl-panel__head setup-panel__head" id={`${id}-head`}>
        Set a rule
      </h2>
      <div className="psl-panel__body">
        {notice && (
          <div
            ref={noticeRef}
            tabIndex={-1}
            role={notice.tone === 'success' ? 'status' : 'alert'}
            className={`psl-callout psl-callout--${notice.tone} setup-notice`}
          >
            {notice.tone === 'success' ? <TickIcon /> : <WarningIcon />}
            <span>{notice.text}</span>
          </div>
        )}
        <div className="psl-field">
          <label className="psl-label" htmlFor={`${id}-rule`}>
            Rule
          </label>
          <select id={`${id}-rule`} className="psl-input setup-select" value={row.component} onChange={(e) => pickRule(e.target.value)}>
            {rows.map((r) => (
              <option key={r.component} value={r.component}>
                {r.name}
              </option>
            ))}
          </select>
        </div>
        <fieldset className={`setup-roles${err('roles') ? ' is-error' : ''}`}>
          <legend className="psl-label">Roles allowed</legend>
          {options.map((o) => (
            <label key={o.role} className={`psl-check setup-check${err('roles') ? ' is-error' : ''}`}>
              <input
                type="checkbox"
                checked={current.roles.includes(o.role)}
                aria-invalid={err('roles') || undefined}
                onChange={(e) => toggleRole(o.role, e.target.checked)}
              />
              <span>{o.label}</span>
            </label>
          ))}
        </fieldset>
        <div className="psl-field">
          <label className="psl-label" htmlFor={`${id}-starts`}>
            Starts
          </label>
          <input
            id={`${id}-starts`}
            type="date"
            className={`psl-input${err('starts') ? ' is-error' : ''}`}
            value={current.starts}
            aria-invalid={err('starts') || undefined}
            onChange={(e) => patch({ starts: e.target.value })}
          />
        </div>
        <div className="psl-field">
          <label className="psl-label" htmlFor={`${id}-why`}>
            Why
          </label>
          <input
            id={`${id}-why`}
            className={`psl-input${err('reason') ? ' is-error' : ''}`}
            value={current.why}
            aria-invalid={err('reason') || undefined}
            onChange={(e) => patch({ why: e.target.value })}
          />
        </div>
        <ProofField
          id={`${id}-proof`}
          enabled={row.proof_case !== undefined}
          state={current.proof}
          invalid={err('evidence_id')}
          onPick={(file) => void pickProof(file)}
        />
        <button type="button" className="psl-btn psl-btn--lg psl-btn--block setup-save" disabled={busy || locked} onClick={() => void onSave()}>
          {busy ? 'Saving…' : `Save as version ${row.revision + 1}`}
        </button>
        <p className="setup-footnote">Rules are versioned. Work already decided keeps the version it was decided under.</p>
      </div>
    </section>
  );
}

function without<T>(set: Set<T>, value: T): Set<T> {
  if (!set.has(value)) return set;
  const next = new Set(set);
  next.delete(value);
  return next;
}

async function toBase64(file: File): Promise<string> {
  const bytes = new Uint8Array(await file.arrayBuffer());
  let text = '';
  for (let i = 0; i < bytes.length; i += 0x8000) text += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  return btoa(text);
}
