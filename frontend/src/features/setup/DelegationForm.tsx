'use client';

// The add form (SCR-13-desktop-delegation panel; the same form in the phone sheet). From, To and Authority offer only
// what the latest E-DELEGATIONS read returned, in its order, with nothing chosen first; the submit takes each value
// from those lists again, so a value that is not listed is never sent. Checks here are format only (chosen, a date,
// Ends on or after Starts); every other rule is the backend's. Persona and /me roles are never read.
// The view sends the body and handles the outcome; the form keeps its entries unless told to clear them.
import { useId, useState, type ReactNode } from 'react';

import { Button, Callout, DateField, Select, TextField } from '@/components';

import type { FieldProblem } from './api';
import type { DelegateOption, DelegationBody, DelegationPerson, DelegationsPage } from './contract-proposal';
import { dateRange, lagosToday } from './format';
import { OutcomeNotice, type Notice } from './SetRulePanel';

export type AddField = 'from_person_id' | 'delegate' | 'authority' | 'starts' | 'ends' | 'reason';
const FIELD_ORDER: AddField[] = ['from_person_id', 'delegate', 'authority', 'starts', 'ends', 'reason'];

/** Why Add is held after an unconfirmed write: the list moved (Start again) or could not be read (Try again). */
export type Blocked = 'changed' | 'locked' | null;
export type SendResult = { kind: 'clear' } | { kind: 'keep' } | { kind: 'invalid'; message: string; fields: FieldProblem[] };
/** The words for the outcome notice when the re-read does not list the new row. */
export type Summary = { from?: string; to: string; dates: string };

// The board's two sentences (SCR-13-desktop-delegation), shown as drawn; the frontend enforces neither (D-103).
export const TO_HINT = 'Only people who already hold the same role are listed';
export const NOTE = "Delegating can't give anyone authority they don't already have. Decisions made by the delegate are recorded under their own name.";
export const CHOOSE_FROM_FIRST = 'Choose who is delegating first.';
export const CHANGED = 'The list changed while we were checking. Look for your delegation before adding it again.';
const HELD = 'Check the list for your delegation, or start again.';

type Entries = { fromId?: string; toId?: string; authority?: string; starts: string; ends: string; reason: string };
const EMPTY: Entries = { starts: '', ends: '', reason: '' };

const personLabel = (p: { name: string; role?: string }) => (p.role ? `${p.name} · ${p.role}` : p.name);

/** The visible label of each field a 422 can name, so the top message speaks the form's words, not the body's keys. */
const FIELD_LABELS: Record<AddField, string> = { from_person_id: 'From', delegate: 'To', authority: 'Authority', starts: 'Starts', ends: 'Ends', reason: 'Reason' };
const isField = (name: string): name is AddField => (FIELD_ORDER as string[]).includes(name);

/** "Check these fields: To, Ends." from the named fields; the backend's own message when it names none, or one the form lacks. */
export function invalidMessage(message: string, fields: FieldProblem[]): string {
  if (fields.length === 0 || !fields.every((f) => isField(f.name))) return message;
  const labels = FIELD_ORDER.filter((f) => fields.some((p) => p.name === f)).map((f) => FIELD_LABELS[f]);
  return `Check ${labels.length === 1 ? 'this field' : 'these fields'}: ${labels.join(', ')}.`;
}

/** Desktop: everything in the panel. Phone: the fields and note in the sheet's body, the buttons in its footer. */
export type FormFrame = (parts: { fields: ReactNode; actions: ReactNode; note: ReactNode }) => ReactNode;
const inPanel: FormFrame = ({ fields, actions, note }) => (
  <div className="setup-deleg__form">
    {fields}
    {actions}
    {note}
  </div>
);

type Props = {
  page: DelegationsPage & { revision: number };
  busy: boolean;
  blocked: Blocked;
  notice: Notice | null;
  onSend: (body: DelegationBody, summary: Summary) => Promise<SendResult>;
  onStartAgain: () => void;
  onTryAgain: () => void;
  /** The phone sheet's Cancel. */
  onCancel?: () => void;
  frame?: FormFrame;
};

export function DelegationForm({ page, busy, blocked, notice, onSend, onStartAgain, onTryAgain, onCancel, frame = inPanel }: Props) {
  const id = useId();
  const [entries, setEntries] = useState<Entries>(EMPTY);
  const [errors, setErrors] = useState<Partial<Record<AddField, string>>>({});
  const [top, setTop] = useState<string | null>(null);

  const fromOptions: DelegationPerson[] = page.from_options ?? [];
  const delegateOptions: DelegateOption[] = page.delegate_options ?? [];
  const authorities = page.authorities ?? [];
  const fromPerson = fromOptions.length === 1 ? fromOptions[0] : fromOptions.find((o) => o.person_id === entries.fromId);
  // When the backend pairs delegates with a From (for_person_id), To lists only those paired with the From shown: an
  // exact key match, no role logic. With no From list the From is the caller, so only unpaired options remain.
  const paired = delegateOptions.some((o) => o.for_person_id !== undefined);
  const toWaits = paired && fromOptions.length > 1 && fromPerson === undefined;
  const toOptions = !paired ? delegateOptions : toWaits ? [] : delegateOptions.filter((o) => o.for_person_id === fromPerson?.person_id);
  const fieldId = (field: AddField) => `${id}-${field}`;

  const change = (patch: Partial<Entries>, ...fields: AddField[]) => {
    setEntries((e) => ({ ...e, ...patch }));
    setErrors((e) => {
      const next = { ...e };
      for (const f of fields) delete next[f];
      return next;
    });
  };

  const showProblems = (found: Partial<Record<AddField, string>>) => {
    setErrors(found);
    const first = FIELD_ORDER.find((f) => found[f]);
    if (first) document.getElementById(fieldId(first))?.focus();
  };

  const submit = async () => {
    if (busy || blocked) return;
    const found: Partial<Record<AddField, string>> = {};
    if (fromOptions.length > 1 && fromPerson === undefined) found.from_person_id = 'Choose who is delegating.';
    const delegate = toOptions.find((o) => o.person_id === entries.toId);
    if (!delegate) found.delegate = toWaits ? CHOOSE_FROM_FIRST : 'Choose who to delegate to.';
    const authority = authorities.length === 1 ? authorities[0] : authorities.find((a) => a.value === entries.authority);
    if (authorities.length > 1 && !authority) found.authority = 'Choose an authority.';
    if (entries.starts === '') found.starts = 'Enter the start date, for example 18 Nov 2026.';
    if (entries.ends === '') found.ends = 'Enter the end date, for example 25 Nov 2026.';
    else if (entries.starts !== '' && entries.ends < entries.starts) found.ends = "Ends can't be before Starts.";
    setTop(null);
    if (Object.keys(found).length > 0 || !delegate) {
      showProblems(found);
      return;
    }

    // expected_revision goes as read (0 included); a blank reason is left out. from_person_id names whoever From shows from
    // from_options[] (one option or a chosen one), so the request asks for exactly the delegator on screen (SEC-1-1).
    const body: DelegationBody = { expected_revision: page.revision, delegate: delegate.person_id, starts: entries.starts, ends: entries.ends };
    if (fromPerson) body.from_person_id = fromPerson.person_id;
    if (authority) body.authority = authority.value;
    if (entries.reason.trim() !== '') body.reason = entries.reason.trim();

    const result = await onSend(body, { from: fromPerson?.name, to: delegate.name, dates: dateRange(entries.starts, entries.ends) });
    if (result.kind === 'clear') {
      setEntries(EMPTY);
      setErrors({});
    } else if (result.kind === 'invalid') {
      setTop(invalidMessage(result.message, result.fields));
      const named: Partial<Record<AddField, string>> = {};
      for (const f of result.fields) if (isField(f.name)) named[f.name] ??= f.message;
      showProblems(named);
    }
  };

  const startAgain = () => {
    setEntries(EMPTY);
    setErrors({});
    setTop(null);
    onStartAgain();
  };

  const fields = (
    <>
      {notice && <OutcomeNotice notice={notice} />}
      {blocked === 'locked' && (
        <div>
          <Button kind="secondary" size="sm" onClick={onTryAgain}>
            Try again
          </Button>
        </div>
      )}
      {top && <Callout kind="problem">{top}</Callout>}
      {fromOptions.length > 1 ? (
        <Select
          id={fieldId('from_person_id')}
          label="From"
          placeholder="Choose who is delegating"
          options={fromOptions.map((o) => ({ value: o.person_id, label: personLabel(o) }))}
          value={fromPerson?.person_id}
          error={errors.from_person_id}
          onChange={(fromId) => change(paired && fromId !== entries.fromId ? { fromId, toId: undefined } : { fromId }, 'from_person_id', 'delegate')}
        />
      ) : (
        <div className="psl-field">
          <span className="psl-label">From</span>
          <span className="setup-deleg__value">{fromPerson ? personLabel(fromPerson) : 'You'}</span>
        </div>
      )}
      <Select
        id={fieldId('delegate')}
        label="To"
        placeholder="Choose a delegate"
        options={toOptions.map((o) => ({ value: o.person_id, label: personLabel(o) }))}
        value={toOptions.some((o) => o.person_id === entries.toId) ? entries.toId : undefined}
        disabled={toWaits}
        hint={
          toWaits ? (
            <>
              <span className="setup-deleg__line">{TO_HINT}</span>
              <span className="setup-deleg__line">{CHOOSE_FROM_FIRST}</span>
            </>
          ) : (
            TO_HINT
          )
        }
        error={errors.delegate}
        onChange={(toId) => change({ toId }, 'delegate')}
      />
      {authorities.length === 1 && <p className="setup-plain">Authority: {authorities[0].label}</p>}
      {authorities.length > 1 && (
        <Select
          id={fieldId('authority')}
          label="Authority"
          placeholder="Choose an authority"
          options={authorities.map((a) => ({ value: a.value, label: a.label }))}
          value={authorities.some((a) => a.value === entries.authority) ? entries.authority : undefined}
          error={errors.authority}
          onChange={(authority) => change({ authority }, 'authority')}
        />
      )}
      <fieldset className="setup-deleg__dates">
        <legend className="psl-label">Dates</legend>
        <DateField
          id={fieldId('starts')}
          label="Starts"
          value={entries.starts}
          today={lagosToday()}
          error={errors.starts}
          onChange={(starts) => change({ starts }, 'starts', 'ends')}
        />
        <DateField
          id={fieldId('ends')}
          label="Ends"
          value={entries.ends}
          today={lagosToday()}
          error={errors.ends}
          onChange={(ends) => change({ ends }, 'ends')}
        />
      </fieldset>
      <TextField id={fieldId('reason')} label="Reason" value={entries.reason} error={errors.reason} onChange={(e) => change({ reason: e.target.value }, 'reason')} />
    </>
  );
  const actions = (
    <>
      <Button size="lg" block busy={busy} busyLabel="Adding…" disabled={blocked !== null} reason={blocked === 'changed' ? HELD : undefined} onClick={() => void submit()}>
        Add delegation
      </Button>
      {blocked === 'changed' && (
        <Button kind="secondary" block onClick={startAgain}>
          Start again
        </Button>
      )}
      {onCancel && (
        <Button kind="secondary" block disabled={busy} onClick={onCancel}>
          Cancel
        </Button>
      )}
    </>
  );
  return frame({ fields, actions, note: <p className="setup-footnote">{NOTE}</p> });
}
