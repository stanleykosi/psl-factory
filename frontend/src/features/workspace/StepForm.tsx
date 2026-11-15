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
import { WarningIcon } from '@/shell/icons';

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
  cites: 'Saved records are not shown here. Choose at least one record for this part before you send.',
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
  const id = useId();
  const described = [field.help && `${id}-help`, error && `${id}-error`].filter(Boolean).join(' ') || undefined;
  return (
    <div className="psl-field sw-field" data-field={field.name}>
      <label className="psl-label" htmlFor={`${id}-control`}>
        {field.required ? field.label : `${field.label} (optional)`}
      </label>
      <span className="psl-input psl-input--money ws-money">
        <span aria-hidden="true">₦</span>
        <input
          id={`${id}-control`}
          inputMode="decimal"
          placeholder={field.placeholder}
          value={value?.amount ?? ''}
          aria-required={field.required}
          aria-invalid={error ? true : undefined}
          aria-describedby={described}
          onChange={(event) => onChange({ amount: event.target.value })}
        />
      </span>
      {field.help && (
        <span className="psl-hint" id={`${id}-help`}>
          {field.help}
        </span>
      )}
      {error && (
        <span className="psl-error" id={`${id}-error`}>
          {error}
        </span>
      )}
    </div>
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
  onSubmit: (request: Pick<StepBody, 'inputs' | 'evidence_ids' | 'note' | 'case_revision'>) => Promise<SubmitResult>;
  onClose: () => void;
  onAccessError: (error: ApiError) => void;
  consequence?: React.ReactNode;
};

export function StepForm({ workId, lineKey, step, caseId, caseRevision, pending, off, submitLabel, onSubmit, onClose, onAccessError, consequence }: FormProps) {
  const fields = step.fields ?? [];
  const headId = useId();
  const heading = useRef<HTMLHeadingElement>(null);
  const formRef = useRef<HTMLFormElement>(null);
  // A text or long text field opens with the words the descriptor carries (a saved draft); the person edits from there.
  const [values, setValues] = useState<Record<string, unknown>>(() =>
    Object.fromEntries(fields.filter((f) => (f.type === 'text' || f.type === 'long_text') && !f.restricted && f.value !== undefined).map((f) => [f.name, f.value])),
  );
  const [evidence, setEvidence] = useState<Record<string, string[]>>({});
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [messages, setMessages] = useState<string[]>([]);
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

  const focusFirst = (names: string[]) => {
    requestAnimationFrame(() => {
      for (const name of names) {
        const control = formRef.current?.querySelector<HTMLElement>(`[data-field="${CSS.escape(name)}"] [aria-invalid="true"], [data-field="${CSS.escape(name)}"] input, [data-field="${CSS.escape(name)}"] textarea, [data-field="${CSS.escape(name)}"] button`);
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
    const named = fields.map((f) => f.name).filter((name) => found[name]);
    if (named.length > 0) return focusFirst(named);
    const result = await onSubmit(stepRequest(fields, values, evidence));
    if (result.kind !== 'invalid') return;
    const known = fields.map((f) => f.name).filter((name) => result.fields[name]);
    setErrors(Object.fromEntries(known.map((name) => [name, result.fields[name]])));
    // A message for a field the form doesn't show still reaches the person, at the top.
    const unmatched = Object.entries(result.fields).filter(([name]) => !known.includes(name)).map(([, text]) => text);
    const unnamed = Object.keys(result.fields).length === 0 || unmatched.length > 0;
    // The same sentence is told once (a server may name a whole-form problem as a field the form doesn't show and in `message`).
    setMessages(unnamed ? [...new Set([result.message, ...unmatched].filter((m): m is string => Boolean(m)))] : []);
    if (known.length > 0) focusFirst(known);
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
        {fields.some((f) => f.type === 'records') && <p className="psl-hint">{FORM_TEXT.cites}</p>}
        {consequence}
        {messages.length > 0 && (
          <div className="psl-callout psl-callout--problem" role="alert">
            <WarningIcon />
            <span className="ws-stack">
              {messages.map((m, i) => (
                <span key={i}>{m}</span>
              ))}
            </span>
          </div>
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
                onIds={(ids) => setEvidence((current) => ({ ...current, [field.name]: ids }))}
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
          <button type="submit" className={submitClass(step)} aria-disabled={pending || off || undefined}>
            {pending ? `${step.label}…` : (submitLabel ?? step.label)}
          </button>
          <button type="button" className="psl-btn psl-btn--secondary" onClick={onClose}>
            {FORM_TEXT.cancel}
          </button>
        </div>
      </div>
    </form>
  );
}

export function stepClass(step: Step): string {
  if (step.emphasis === 'primary') return 'psl-btn';
  if (step.emphasis === 'danger') return 'psl-btn psl-btn--reject';
  return 'psl-btn psl-btn--secondary';
}

/** A form's submit is its main action: filled, whatever the step that opened it looked like (danger stays red). */
function submitClass(step: Step): string {
  return step.emphasis === 'danger' ? 'psl-btn psl-btn--reject' : 'psl-btn';
}
