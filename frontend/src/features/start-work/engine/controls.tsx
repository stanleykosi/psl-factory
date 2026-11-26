'use client';

// F-92: the control slots the engine draws: `record`, `choice`, `text`, `file`. A later line adds a slot here, not a second renderer.
// Each wraps one existing control (SourcePicker, RecordPicker, Segmented/Select, TextField, FileUpload) in the drawer's field frame.
import { useId, type ReactNode } from 'react';

import { FileUpload, Icon, Segmented, Select, TextField } from '@/components';

import { RecordPicker, type OptionSource } from '../RecordPicker';
import { SourcePicker } from '../SourcePicker';
import type { LineOption } from '../types';
import type { EngineField } from './plan';

export const NO_ESCALATIONS = 'No escalation requests to start from.';
export const CHOOSE_PROJECT_FIRST = 'Choose a project first.';

const capital = (word: string) => word.charAt(0).toUpperCase() + word.slice(1);
const withOptional = (field: { label: string; required: boolean }) => (field.required ? field.label : `${field.label} (optional)`);

type Frame = { name: string; children: ReactNode };

/** The frame every control sits in: the summary's link target and the 422's own `data-field`. */
function Field({ name, children }: Frame) {
  return (
    <div className="psl-field sw-field" data-field={name} id={`sw-field-${name}`} tabIndex={-1}>
      {children}
    </div>
  );
}

function Problem({ id, message }: { id: string; message: string | undefined }) {
  if (!message) return null;
  return (
    <span className="psl-error" id={id}>
      <Icon name="warn" />
      <span>{message}</span>
    </span>
  );
}

/** A record control that cannot be used yet (no project, or its parent not chosen): drawn disabled, and says why. */
export function WaitingRecord({ field, why }: { field: EngineField; why: string }) {
  const id = useId();
  return (
    <Field name={field.name}>
      <span className="psl-label">{withOptional(field)}</span>
      <span className="psl-input sw-display" aria-disabled="true" aria-describedby={`${id}-why`}>
        —
      </span>
      <span className="psl-hint" id={`${id}-why`}>
        {why}
      </span>
    </Field>
  );
}

type RecordProps = {
  field: EngineField;
  caseId: string;
  lineKey: string;
  /** The parent's chosen id, for a control that depends on one. */
  parentId: number | undefined;
  value: LineOption | undefined;
  onChange: (value: LineOption | undefined) => void;
  onRevision: (caseRevision: number) => void;
  /** The line's own list (the escalation register); otherwise the served intake sources. */
  list?: { source: OptionSource; emptyText: string };
  disabled: boolean;
  error: string | undefined;
};

export function RecordControl({ field, caseId, lineKey, parentId, value, onChange, onRevision, list, disabled, error }: RecordProps) {
  const labelId = `${useId()}-label`;
  const label = withOptional(field);
  // The same change handler for both pickers: one chosen row, or none.
  const pick = (one: { id: number; label: string } | undefined) => onChange(one ? ({ value: String(one.id), label: one.label } as LineOption) : undefined);
  if (list) {
    return (
      <Field name={field.name}>
        <span className="psl-label" id={labelId}>
          {label}
        </span>
        <RecordPicker
          lineKey={lineKey}
          field={{ name: field.name, label: field.label, type: 'record', required: field.required } as never}
          parent={undefined}
          value={value}
          onChange={(option) => {
            const one = option && !Array.isArray(option) && 'value' in option ? option : undefined;
            pick(one ? { id: Number.parseInt(one.value, 10), label: one.label } : undefined);
          }}
          disabled={disabled}
          labelId={labelId}
          describedBy={undefined}
          invalid={error !== undefined}
          source={list.source}
          emptyText={list.emptyText}
        />
        <Problem id={`${labelId}-error`} message={error} />
      </Field>
    );
  }
  return (
    <Field name={field.name}>
      <SourcePicker
        // A new parent is a new list.
        key={parentId ?? 'none'}
        caseId={caseId}
        lineKey={lineKey}
        field={field.source?.kind === 'sources' ? field.source.field : undefined}
        label={label}
        parentId={parentId}
        value={value ? { id: Number.parseInt(value.value, 10), label: value.label } : undefined}
        onChange={pick}
        onRevision={onRevision}
        disabled={disabled}
        error={error}
      />
    </Field>
  );
}

export function ChoiceControl({ field, value, onChange, disabled, error }: { field: EngineField; value: string | undefined; onChange: (value: string | undefined) => void; disabled: boolean; error: string | undefined }) {
  const id = useId();
  const options = field.values.map((v) => ({ value: v, label: field.valueLabels?.[v] ?? capital(v) }));
  const label = withOptional(field);
  if (options.length > 3) {
    return (
      <Field name={field.name}>
        <Select label={label} options={options} value={value} placeholder="Choose…" disabled={disabled} error={error} onChange={(next) => onChange(next || undefined)} />
      </Field>
    );
  }
  return (
    <Field name={field.name}>
      <span className="psl-label" id={`${id}-label`}>
        {label}
      </span>
      <div aria-invalid={error ? true : undefined} aria-describedby={error ? `${id}-error` : undefined}>
        <Segmented labelledBy={`${id}-label`} className="sw-seg" options={options.map((o) => ({ ...o, disabled }))} value={value} onChange={(next) => !disabled && onChange(next)} />
      </div>
      <Problem id={`${id}-error`} message={error} />
    </Field>
  );
}

export function TextControl({ name, label, required, maxLength, date, value, onChange, disabled, error }: { name: string; label: string; required: boolean; maxLength?: number; date?: boolean; value: string; onChange: (value: string) => void; disabled: boolean; error: string | undefined }) {
  return (
    <Field name={name}>
      <TextField label={label} type={date ? 'date' : undefined} optional={!required} maxLength={maxLength} value={value} readOnly={disabled} error={error} aria-required={required || undefined} onChange={(event) => onChange(event.target.value)} />
    </Field>
  );
}

/** One file, held in the form and sent with the start. No type or size rule here; the server's 413 or 415 is shown. */
export function FileControl({ name, label, value, onChange, disabledReason, error }: { name: string; label: string; value: File | null; onChange: (file: File | null) => void; disabledReason: string | undefined; error: string | undefined }) {
  return (
    <Field name={name}>
      <FileUpload
        label={label}
        accept={[]}
        maxBytes={null}
        state={value ? { status: 'uploaded', name: value.name, size: value.size } : { status: 'empty' }}
        onFile={onChange}
        onRemove={() => onChange(null)}
        disabledReason={disabledReason}
        error={error}
      />
    </Field>
  );
}
