'use client';

// "Set an owner" (F-30, PROPOSAL E-WORK-ASSIGN, contract mock only): a labelled Select of exactly `assign.candidates`
// (no preselection, no typed owner), a Note, Set owner and Cancel. Nothing here filters candidates or looks up who is signed in; the
// backend names who may be chosen. Checks are only the ones the response states: an owner, a note when
// `note_required`, and the 2000-character limit.
// F-31: with `preset` (the response names a default among the candidates) the form is the engagement's "Confirm PM": drawn
// open inside the side panel (`bare`), that person chosen with the response's help line, labelled with `assign.role`,
// and no Cancel. The person still presses Confirm.
// F-36 (RFP, "Assign accountable PM"): `words` replaces the owner words, `hint` is the line under the field, `lead`, `middle` and
// `tail` are extra parts of the same form (the intro, the acting role and proof, "What happens next"), and `formId` with `actions: false` leaves the
// buttons to the Drawer's footer. Nothing is chosen ahead, nothing is filtered.
import { useEffect, useId, useRef, useState, type FormEvent, type ReactNode } from 'react';

import { Button, Callout, Select, TextArea, ValidationSummary, type FieldProblem } from '@/components';
import { NOTE_MAX } from '@/features/decide/format';
import type { WorkItem } from '@/features/work-item/labels';

import { assignCandidateKind } from './proposals';
import { ASSIGN_TEXT } from './useWorkspaceAssign';
import type { SubmitResult } from './useWorkspaceStep';

export type Assign = NonNullable<WorkItem['assign']>;
export type AssignWords = Partial<Record<'owner' | 'choose' | 'submit' | 'chooseOwner' | 'gone', string>>;

type Props = {
  assign: Assign;
  pending: boolean;
  /** Text for the submit button while a failed attempt can be repeated. */
  submitLabel?: string;
  /** F-31: the person the response names as the default, and its help line. */
  preset?: { personId: string; hint?: string };
  /** F-31: no panel of its own: the form sits in the side panel and is named by that panel's heading. */
  labelledBy?: string;
  onSubmit: (request: { person_id: string; note?: string }) => Promise<SubmitResult>;
  /** Absent for a preset form, which has nothing to cancel. */
  onClose?: () => void;
  /** F-36: the field and button words of another kind of owner ("Accountable PM"). */
  words?: AssignWords;
  /** F-36: the line under the field when nothing is preset. */
  hint?: string;
  /** F-36: parts drawn before the field, between the field and the note, and after the note. */
  lead?: ReactNode;
  middle?: ReactNode;
  tail?: ReactNode;
  /** F-36: the form's id and whether it draws its own buttons (false: the Drawer footer's submit button names the form). */
  formId?: string;
  actions?: boolean;
  ariaLabel?: string;
};

const OWNER_ID = 'assign-owner';
const NOTE_ID = 'assign-note';

export function AssignForm({ assign, pending, submitLabel, preset, labelledBy, onSubmit, onClose, words, hint, lead, middle, tail, formId, actions = true, ariaLabel }: Props) {
  const headId = useId();
  const heading = useRef<HTMLHeadingElement>(null);
  const formRef = useRef<HTMLFormElement>(null);
  const [picked, setOwner] = useState<string | undefined>(preset?.personId);
  // F-36: a re-read that no longer lists the person chosen clears the choice and says so
  const owner = picked !== undefined && assign.candidates.some((c) => c.person_id === picked) ? picked : undefined;
  const gone = picked !== undefined && owner === undefined;
  const [note, setNote] = useState('');
  const [errors, setErrors] = useState<{ owner?: string; note?: string }>({});
  const [message, setMessage] = useState<string>();
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    if (!preset) heading.current?.focus();
  }, [preset]);

  // Escape closes the form with no request.
  useEffect(() => {
    const el = formRef.current;
    if (!onClose) return;
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
  const role = assign.role ?? ASSIGN_TEXT.owner;
  const text = { ...ASSIGN_TEXT, ...words };

  const focusFirst = (found: { owner?: string; note?: string }) => {
    requestAnimationFrame(() => document.getElementById(found.owner ? OWNER_ID : NOTE_ID)?.focus());
  };

  const submit = async () => {
    if (pending) return;
    const trimmed = note.trim();
    const found: { owner?: string; note?: string } = {};
    if (owner === undefined) found.owner = text.chooseOwner;
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

  const fields = (
    <>
      <ValidationSummary problems={problems} attempt={attempt} />
      {message && <Callout kind="problem">{message}</Callout>}
      {lead}
      <Select
        id={OWNER_ID}
        label={preset ? role : text.owner}
        hint={preset?.hint ?? hint}
        options={options}
        value={owner}
        onChange={setOwner}
        placeholder={text.choose}
        error={errors.owner ?? (gone ? (text.gone ?? 'That person can no longer be chosen.') : undefined)}
      />
      {middle}
      <TextArea id={NOTE_ID} label={ASSIGN_TEXT.note} optional={!noteRequired} value={note} limit={NOTE_MAX} onChange={(event) => setNote(event.target.value)} error={errors.note} />
      {tail}
      {actions && (
        <div className="ws-form__actions">
          <Button type="submit" kind="primary" busy={pending} busyLabel={`${preset ? ASSIGN_TEXT.confirm(role) : text.submit}…`} aria-disabled={pending || undefined}>
            {submitLabel ?? (preset ? ASSIGN_TEXT.confirm(role) : text.submit)}
          </Button>
          {onClose && (
            <Button kind="secondary" onClick={onClose}>
              {ASSIGN_TEXT.cancel}
            </Button>
          )}
        </div>
      )}
    </>
  );
  const onFormSubmit = (event: FormEvent) => {
    event.preventDefault();
    void submit();
  };

  if (labelledBy || formId) {
    return (
      <form ref={formRef} id={formId} className="ws-form ws-form--bare" aria-labelledby={labelledBy} aria-label={labelledBy ? undefined : ariaLabel} noValidate onSubmit={onFormSubmit}>
        {fields}
      </form>
    );
  }
  return (
    <form ref={formRef} className="psl-panel ws-form" aria-labelledby={headId} noValidate onSubmit={onFormSubmit}>
      <h3 id={headId} ref={heading} tabIndex={-1} className="psl-panel__head ws-form__head">
        {ASSIGN_TEXT.open}
      </h3>
      <div className="psl-panel__body ws-form__body">{fields}</div>
    </form>
  );
}
