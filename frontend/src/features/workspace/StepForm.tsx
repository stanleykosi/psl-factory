'use client';

// The step form (PROPOSAL D-LINE-WORKSPACE): one field per `steps[].fields[]`, in the order returned, through
// Start work's IntakeField for the kinds it draws. Money and evidence, which IntakeField does not draw, use the
// design system's money box and the existing proof field (E-EVIDENCE-UPLOAD). Client checks are only the ones
// the descriptor states: required, a 2000-character note and a whole number. A field named `note` is sent as the
// step's note, never as an input; display fields are shown and never sent; restricted fields draw no value.
import { useEffect, useId, useRef, useState } from 'react';

import { ApiError } from '@/api/errors';
import { NOTE_MAX } from '@/features/decide/format';
import { ProofField, useEvidenceUpload } from '@/features/response';
import { buildIntake, dependentsOf, parentValue, type FieldValue, type Values } from '@/features/start-work/intake';
import { IntakeField } from '@/features/start-work/IntakeField';
import type { Field, LineOption } from '@/features/start-work/types';
import { api, call } from '@/api/client';
import { Button, Callout, MoneyField as MoneyInput, ValidationSummary, type ButtonKind, type FieldProblem } from '@/components';

import type { Step } from './labels';
import type { StepBody, SubmitResult } from './useWorkspaceStep';

import '@/features/response/response.css';

export type StepField = NonNullable<Step['fields']>[number];
/** The money box keeps what was typed; blank is sent as unknown (INV-UNKNOWN), never 0. */
type MoneyValue = { amount: string };

// PROPOSAL: the descriptor names no currency for a money field; the frame sends NGN, the factory's only one today.
const MONEY_CURRENCY = 'NGN';

const FORM_TEXT = {
  required: (label: string) => `Add ${label.toLowerCase()} to continue.`,
  integer: 'Enter a whole number.',
  money: 'Enter an amount such as 4250000.00, or leave it blank if it isn’t known.',
  note: `Keep the note to ${NOTE_MAX} characters.`,
  cancel: 'Cancel',
  restricted: 'Restricted',
} as const;

const isNote = (field: StepField) => field.name === 'note';
const sent = (field: StepField) => field.type !== 'display' && !field.restricted;

function blank(field: StepField, value: unknown): boolean {
  if (value === undefined || value === null) return true;
  if (typeof value === 'string') return value.trim() === '';
  if (Array.isArray(value)) return value.length === 0;
  if (field.type === 'date_range') return !(value as { from?: string }).from && !(value as { to?: string }).to;
  if (field.type === 'money') return (value as MoneyValue).amount.trim() === '';
  return false;
}

/** The descriptor's own checks; anything else is the server's 422. */
export function checkFields(fields: StepField[], values: Record<string, unknown>, evidence: Record<string, string[]>): Record<string, string> {
  const errors: Record<string, string> = {};
  for (const field of fields) {
    if (!sent(field)) continue;
    const value = field.type === 'evidence' ? evidence[field.name] : values[field.name];
    if (field.required && blank(field, value)) errors[field.name] = FORM_TEXT.required(field.label);
    else if (field.type === 'integer' && !blank(field, value) && !/^-?\d+$/.test(String(value).trim())) errors[field.name] = FORM_TEXT.integer;
    else if (field.type === 'money' && !blank(field, value) && !/^\d+(\.\d{1,2})?$/.test((value as MoneyValue).amount.trim())) errors[field.name] = FORM_TEXT.money;
    else if (isNote(field) && typeof value === 'string' && value.length > NOTE_MAX) errors[field.name] = FORM_TEXT.note;
  }
  return errors;
}

function moneyInput(value: MoneyValue | undefined) {
  const amount = value?.amount.trim() ?? '';
  if (amount === '') return { currency: MONEY_CURRENCY, unknown: true };
  const [whole, cents = ''] = amount.split('.');
  return { amount: `${whole}.${cents.padEnd(2, '0')}`, currency: MONEY_CURRENCY, unknown: false };
}

/** The request parts from the form: inputs shaped per kind (buildIntake for Start work's kinds), the note, evidence, and a chosen record's case revision. */
export function stepRequest(fields: StepField[], values: Record<string, unknown>, evidence: Record<string, string[]>): Pick<StepBody, 'inputs' | 'evidence_ids' | 'note' | 'case_revision'> {
  const shown = fields.filter((f) => sent(f) && !isNote(f));
  const inputs: Record<string, unknown> = buildIntake(shown as Field[], values as Values);
  for (const field of shown) if (field.type === 'money') inputs[field.name] = moneyInput(values[field.name] as MoneyValue | undefined);
  const request: Pick<StepBody, 'inputs' | 'evidence_ids' | 'note' | 'case_revision'> = {};
  if (Object.keys(inputs).length > 0) request.inputs = inputs;
  const ids = fields.filter((f) => f.type === 'evidence' && sent(f)).flatMap((f) => evidence[f.name] ?? []);
  if (ids.length > 0) request.evidence_ids = ids;
  const note = fields.find((f) => isNote(f) && sent(f));
  const text = note && typeof values[note.name] === 'string' ? (values[note.name] as string).trim() : '';
  if (text !== '') request.note = text;
  for (const field of shown) {
    const chosen = values[field.name] as LineOption | undefined;
    if (field.type === 'record' && chosen?.case_id !== undefined && chosen.case_revision !== undefined) {
      request.case_revision = chosen.case_revision;
      break;
    }
  }
  return request;
}

function Restricted({ field }: { field: StepField }) {
  const id = useId();
  return (
    <div className="psl-field sw-field" data-field={field.name}>
      <span className="psl-label" id={id}>
        {field.label}
      </span>
      <span className="psl-input sw-display" aria-labelledby={id}>
        {FORM_TEXT.restricted}
      </span>
    </div>
  );
}

function MoneyField({ field, value, onChange, error }: { field: StepField; value: MoneyValue | undefined; onChange: (v: MoneyValue) => void; error?: string }) {
  return (
    <MoneyInput
      fieldClassName="sw-field"
      label={field.label}
      optional={!field.required}
      hint={field.help}
      error={error}
      value={value?.amount ?? ''}
      onChange={(amount) => onChange({ amount: amount ?? '' })}
    />
  );
}

function EvidenceField(props: { workId: string; caseId?: string; caseRevision?: number; field: StepField; error?: string; onIds: (ids: string[]) => void; onAccessError: (e: ApiError) => void }) {
  const { workId, caseId, caseRevision, field, error, onIds, onAccessError } = props;
  const proof = useEvidenceUpload({
    caseId,
    caseRevision,
    kind: field.evidence_kind,
    reloadCaseRevision: async () => (await call(api.GET('/api/v1/work/{work_id}', { params: { path: { work_id: workId } } }))).case_revision,
    onAccessError,
  });
  const ids = proof.evidenceIds.join(' ');
  useEffect(() => {
    onIds(ids ? ids.split(' ') : []);
    // only the uploaded ids matter
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ids]);
  return (
    <div className="psl-field sw-field" data-field={field.name}>
      <ProofField proof={proof} hint={field.help} label={field.label} />
      {error && (
        <span className="psl-error" role="alert">
          {error}
        </span>
      )}
    </div>
  );
}

type FormProps = {
  workId: string;
  lineKey: string;
  step: Step;
  caseId?: string;
  caseRevision?: number;
  pending: boolean;
  off: boolean;
  /** Text after the submit button's label while the step can't be pressed again (Try again on a network failure). */
  submitLabel?: string;
  /** The row's current values (item-scope steps), by field name; they win over the descriptor's `value`. */
  initial?: Record<string, unknown>;
  onSubmit: (request: Pick<StepBody, 'inputs' | 'evidence_ids' | 'note' | 'case_revision'>) => Promise<SubmitResult>;
  onClose: () => void;
  onAccessError: (error: ApiError) => void;
  consequence?: React.ReactNode;
  /** A top summary of the problems, linked to their fields (F-30 criterion 12); other lines draw none. */
  summary?: boolean;
};

export function StepForm({ workId, lineKey, step, caseId, caseRevision, pending, off, submitLabel, initial, onSubmit, onClose, onAccessError, consequence, summary }: FormProps) {
  const fields = step.fields ?? [];
  const headId = useId();
  const heading = useRef<HTMLHeadingElement>(null);
  const formRef = useRef<HTMLFormElement>(null);
  // A text or long text field opens with the words the descriptor carries (a saved draft); the person edits from there. A choice opens on the option the descriptor names.
  // A records field opens with its saved records, when the descriptor carries them as a list of {value, label} (PROPOSAL, BACKEND-HANDOFF 2).
  const [values, setValues] = useState<Record<string, unknown>>(() => {
    const opened: Record<string, unknown> = {};
    for (const f of fields) {
      if (f.restricted || f.value === undefined) continue;
      if (f.type === 'text' || f.type === 'long_text') opened[f.name] = f.value;
      else if (f.type === 'choice' && f.options?.some((o) => o.value === f.value)) opened[f.name] = f.value;
      else if (f.type === 'records') {
        const saved = (Array.isArray(f.value) ? (f.value as unknown[]) : []).filter((o): o is LineOption => typeof o === 'object' && o !== null && typeof (o as LineOption).value === 'string' && typeof (o as LineOption).label === 'string');
        if (saved.length > 0) opened[f.name] = saved;
      }
    }
    // the row being edited: its current text, record (owner) and date
    for (const f of fields) {
      const v = initial?.[f.name];
      if (f.restricted || v === undefined) continue;
      if ((f.type === 'text' || f.type === 'long_text' || f.type === 'date') && typeof v === 'string') opened[f.name] = v;
      else if (f.type === 'record' && typeof v === 'object' && v !== null && typeof (v as LineOption).value === 'string' && typeof (v as LineOption).label === 'string') opened[f.name] = v;
    }
    return opened;
  });
  const [evidence, setEvidence] = useState<Record<string, string[]>>({});
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [messages, setMessages] = useState<string[]>([]);
  const [attempt, setAttempt] = useState(0);
  const [problems, setProblems] = useState<FieldProblem[]>([]);
  const labels = Object.fromEntries(fields.map((f) => [f.name, f.label]));

  useEffect(() => {
    heading.current?.focus();
  }, []);

  // Escape closes the form with no request, from anywhere inside it.
  useEffect(() => {
    const el = formRef.current;
    const onKey = (event: globalThis.KeyboardEvent) => {
      if (event.key !== 'Escape') return;
      // Escape inside an open record picker closes the picker's list only (RecordPicker handles it); the form stays.
      if (event.target instanceof Element && event.target.closest('.sw-picker__pop')) return;
      event.preventDefault();
      onClose();
    };
    el?.addEventListener('keydown', onKey);
    return () => el?.removeEventListener('keydown', onKey);
  }, [onClose]);

  const setValue = (name: string, value: unknown) => {
    const cleared = dependentsOf(fields as Field[], name);
    setValues((current) => {
      const next = { ...current, [name]: value };
      for (const dependent of cleared) delete next[dependent];
      return next;
    });
  };

  // The first control inside a field that can take focus (an invalid choice field's wrapper cannot, its first option can).
  const controlOf = (name: string) => formRef.current?.querySelector<HTMLElement>(`[data-field="${CSS.escape(name)}"] :is(input, textarea, button, select)`) ?? undefined;

  // The top summary links each message to its field's first control (ids are given to those controls when needed).
  const summarise = (messages: Record<string, string>) =>
    setProblems(
      fields.flatMap((f) => {
        const control = messages[f.name] ? controlOf(f.name) : undefined;
        if (!control) return [];
        control.id ||= `${headId}-${f.name}`;
        return [{ fieldId: control.id, message: messages[f.name] }];
      }),
    );

  const focusFirst = (names: string[]) => {
    requestAnimationFrame(() => {
      for (const name of names) {
        const control = controlOf(name);
        if (control) {
          control.focus();
          return;
        }
      }
    });
  };

  const submit = async () => {
    if (pending || off) return;
    const found = checkFields(fields, values, evidence);
    setErrors(found);
    setMessages([]);
    setProblems([]);
    const named = fields.map((f) => f.name).filter((name) => found[name]);
    if (named.length > 0) {
      summarise(found);
      setAttempt((n) => n + 1);
      return focusFirst(named);
    }
    const result = await onSubmit(stepRequest(fields, values, evidence));
    if (result.kind !== 'invalid') return;
    const known = fields.map((f) => f.name).filter((name) => result.fields[name]);
    setErrors(Object.fromEntries(known.map((name) => [name, result.fields[name]])));
    // A message for a field the form doesn't show still reaches the person, at the top.
    const unmatched = Object.entries(result.fields).filter(([name]) => !known.includes(name)).map(([, text]) => text);
    const unnamed = Object.keys(result.fields).length === 0 || unmatched.length > 0;
    // The same sentence is told once (a server may name a whole-form problem as a field the form doesn't show and in `message`).
    setMessages(unnamed ? [...new Set([result.message, ...unmatched].filter((m): m is string => Boolean(m)))] : []);
    if (known.length > 0) {
      summarise(result.fields);
      setAttempt((n) => n + 1);
      focusFirst(known);
    }
  };

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
        {step.label}
      </h3>
      <div className="psl-panel__body ws-form__body">
        {consequence}
        {summary && <ValidationSummary problems={problems} attempt={attempt} />}
        {messages.length > 0 && (
          <Callout kind="problem">
            <span className="ws-stack">
              {messages.map((m, i) => (
                <span key={i}>{m}</span>
              ))}
            </span>
          </Callout>
        )}
        {fields.map((field) => {
          if (field.restricted) return <Restricted key={field.name} field={field} />;
          if (field.type === 'money') {
            return <MoneyField key={field.name} field={field} value={values[field.name] as MoneyValue | undefined} onChange={(v) => setValue(field.name, v)} error={errors[field.name]} />;
          }
          if (field.type === 'evidence') {
            return (
              <EvidenceField
                key={field.name}
                workId={workId}
                caseId={caseId}
                caseRevision={caseRevision}
                field={field}
                error={errors[field.name]}
                onIds={(ids) => {
                  setEvidence((current) => ({ ...current, [field.name]: ids }));
                  // a file now uploaded answers the "add proof" message
                  if (ids.length > 0) setErrors((current) => (current[field.name] === undefined ? current : Object.fromEntries(Object.entries(current).filter(([name]) => name !== field.name))));
                }}
                onAccessError={onAccessError}
              />
            );
          }
          return (
            <IntakeField
              key={field.name}
              lineKey={lineKey}
              field={field as Field}
              value={values[field.name] as FieldValue | undefined}
              onChange={(value) => setValue(field.name, value)}
              parent={parentValue(field as Field, values as Values)}
              parentLabel={field.depends_on ? labels[field.depends_on] : undefined}
              readOnly={false}
              error={errors[field.name]}
              note={undefined}
            />
          );
        })}
        {step.confirm && <p className="ws-confirm">{step.confirm}</p>}
        <div className="ws-form__actions">
          <Button type="submit" kind={step.emphasis === 'danger' ? 'reject' : 'primary'} busy={pending} busyLabel={`${step.label}…`} aria-disabled={pending || off || undefined}>
            {submitLabel ?? step.label}
          </Button>
          <Button kind="secondary" onClick={onClose}>
            {FORM_TEXT.cancel}
          </Button>
        </div>
      </div>
    </form>
  );
}

/** A step's button kind from its emphasis: a form's submit is filled whatever opened it (danger stays red). */
export function stepKind(step: Step): ButtonKind {
  if (step.emphasis === 'primary') return 'primary';
  if (step.emphasis === 'danger') return 'reject';
  return 'secondary';
}
