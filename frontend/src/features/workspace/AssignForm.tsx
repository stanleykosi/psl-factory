'use client';

// "Set an owner" (F-30, PROPOSAL E-WORK-ASSIGN, contract mock only): a labelled Select of exactly `assign.candidates`
// (no preselection, no typed owner), a Note, Set owner and Cancel. Nothing here filters candidates or reads /me; the
// backend names who may be chosen. Checks are only the ones the response states: an owner, a note when
// `note_required`, and the 2000-character limit.
import { useEffect, useId, useRef, useState } from 'react';

import { Button, Callout, Select, TextArea, ValidationSummary, type FieldProblem } from '@/components';
import { NOTE_MAX } from '@/features/decide/format';
import type { WorkItem } from '@/features/work-item/labels';

import { assignCandidateKind } from './proposals';
import { ASSIGN_TEXT } from './useWorkspaceAssign';
import type { SubmitResult } from './useWorkspaceStep';

export type Assign = NonNullable<WorkItem['assign']>;

type Props = {
  assign: Assign;
  pending: boolean;
  /** Text for the submit button while a failed attempt can be repeated. */
  submitLabel?: string;
  onSubmit: (request: { person_id: string; note?: string }) => Promise<SubmitResult>;
  onClose: () => void;
};

const OWNER_ID = 'assign-owner';
const NOTE_ID = 'assign-note';

export function AssignForm({ assign, pending, submitLabel, onSubmit, onClose }: Props) {
  const headId = useId();
  const heading = useRef<HTMLHeadingElement>(null);
  const formRef = useRef<HTMLFormElement>(null);
  const [owner, setOwner] = useState<string>();
  const [note, setNote] = useState('');
  const [errors, setErrors] = useState<{ owner?: string; note?: string }>({});
  const [message, setMessage] = useState<string>();
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    heading.current?.focus();
  }, []);

  // Escape closes the form with no request.
  useEffect(() => {
    const el = formRef.current;
    const onKey = (event: globalThis.KeyboardEvent) => {
      if (event.key !== 'Escape' || (event.target instanceof Element && event.target.closest('[role="listbox"]'))) return;
      event.preventDefault();
      onClose();
    };
    el?.addEventListener('keydown', onKey);
    return () => el?.removeEventListener('keydown', onKey);
  }, [onClose]);

  const options = assign.candidates.map((c) => {
    const kind = assignCandidateKind(c);
    const words = [c.role, c.hint, kind === 'team' || kind === 'outside_party' ? (ASSIGN_TEXT.kind[kind] === c.role ? undefined : ASSIGN_TEXT.kind[kind]) : undefined].filter(Boolean);
    return { value: c.person_id, label: c.name, hint: words.length > 0 ? words.join(' · ') : undefined };
  });
  const noteRequired = assign.note_required === true;

  const focusFirst = (found: { owner?: string; note?: string }) => {
    requestAnimationFrame(() => document.getElementById(found.owner ? OWNER_ID : NOTE_ID)?.focus());
  };

  const submit = async () => {
    if (pending) return;
    const trimmed = note.trim();
    const found: { owner?: string; note?: string } = {};
    if (owner === undefined) found.owner = ASSIGN_TEXT.chooseOwner;
    if (note.length > NOTE_MAX) found.note = ASSIGN_TEXT.noteLong;
    else if (noteRequired && trimmed === '') found.note = ASSIGN_TEXT.needNote;
    setErrors(found);
    setMessage(undefined);
    if (found.owner || found.note) {
      setAttempt((n) => n + 1);
      return focusFirst(found);
    }
    const result = await onSubmit({ person_id: owner!, ...(trimmed !== '' ? { note: trimmed } : {}) });
    if (result.kind !== 'invalid') return;
    const next = { owner: result.fields.person_id, note: result.fields.note };
    setErrors(next);
    setMessage(next.owner || next.note ? undefined : result.message);
    setAttempt((n) => n + 1);
    if (next.owner || next.note) focusFirst(next);
  };

  const problems: FieldProblem[] = [
    ...(errors.owner ? [{ fieldId: OWNER_ID, message: errors.owner }] : []),
    ...(errors.note ? [{ fieldId: NOTE_ID, message: errors.note }] : []),
  ];

  return (
    <form
      ref={formRef}
      className="psl-panel ws-form"
      aria-labelledby={headId}
      noValidate
      onSubmit={(event) => {
        event.preventDefault();
        void submit();
      }}
    >
      <h3 id={headId} ref={heading} tabIndex={-1} className="psl-panel__head ws-form__head">
        {ASSIGN_TEXT.open}
      </h3>
      <div className="psl-panel__body ws-form__body">
        <ValidationSummary problems={problems} attempt={attempt} />
        {message && <Callout kind="problem">{message}</Callout>}
        <Select id={OWNER_ID} label={ASSIGN_TEXT.owner} options={options} value={owner} onChange={setOwner} placeholder={ASSIGN_TEXT.choose} error={errors.owner} />
        <TextArea id={NOTE_ID} label={ASSIGN_TEXT.note} optional={!noteRequired} value={note} limit={NOTE_MAX} onChange={(event) => setNote(event.target.value)} error={errors.note} />
        <div className="ws-form__actions">
          <Button type="submit" kind="primary" busy={pending} busyLabel={`${ASSIGN_TEXT.submit}…`} aria-disabled={pending || undefined}>
            {submitLabel ?? ASSIGN_TEXT.submit}
          </Button>
          <Button kind="secondary" onClick={onClose}>
            {ASSIGN_TEXT.cancel}
          </Button>
        </div>
      </div>
    </form>
  );
}
