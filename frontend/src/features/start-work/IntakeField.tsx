'use client';

// SCR-04 intake fields by kind, labelled from the contract: `label`, `placeholder`, `help` as the hint and
// `required` as aria-required ("(optional)" on the label otherwise). A 422 message sits under the control with
// aria-invalid and aria-describedby. Values are kept as typed; intake.ts turns them into the submitted shapes.
// As the boards draw them: a date range is one field box, a display value and a 422 for a field this drawer does
// not render are read-only boxes. Proof (evidence) fields are StartProof's.
import { useId, type ReactNode } from 'react';

import { DateField, Icon, Segmented, Select, TextArea, TextField } from '@/components';

import type { FieldValue, RangeValue } from './intake';
import { RecordPicker } from './RecordPicker';
import type { Field, LineOption } from './types';

type Props = {
  lineKey: string;
  field: Field;
  value: FieldValue | undefined;
  onChange: (value: FieldValue | undefined) => void;
  /** The parent's chosen value for a depends_on field; undefined until it has one. */
  parent: string | undefined;
  parentLabel: string | undefined;
  readOnly: boolean;
  error: string | undefined;
  /** A note under the control that is not an error, e.g. "That choice is no longer available." */
  note: string | undefined;
  /** This field's help, drawn under the proof box that follows it (SCR-04-*-change): its id, so it still
   *  describes this control, and, on the proof box, the text drawn there. */
  movedHelp?: { id: string; text?: string };
};

const NATIVE: Record<string, string> = { period: 'month', datetime: 'datetime-local', integer: 'number' };

/** The label of a field whose control brings none of its own (a choice row, a range, a record picker, a display value). */
function Label({ id, field, as = 'span' }: { id: string; field: Field; as?: 'span' | 'legend' }) {
  const Tag = as;
  return (
    <Tag className="psl-label" id={id}>
      {!field.required && field.type !== 'display' ? `${field.label} (optional)` : field.label}
    </Tag>
  );
}

export function IntakeField({ lineKey, field, value, onChange, parent, parentLabel, readOnly, error, note, movedHelp }: Props) {
  const id = useId();
  const controlId = `${id}-control`;
  const labelId = `${id}-label`;
  const helpId = movedHelp?.id ?? `${id}-help`;
  const noteId = `${id}-note`;
  const waiting = field.depends_on !== undefined && parent === undefined;
  const hintText = movedHelp ? undefined : field.help;
  const waitId = `${id}-wait`;
  const invalid = error !== undefined;
  // The library fields take one hint line; the things this drawer says beside a control are joined into it.
  const lines: ReactNode[] = [
    waiting && <span key="wait" id={waitId}>Choose {parentLabel ?? 'the field above'} first</span>,
    hintText && <span key="help" id={helpId}>{hintText}</span>,
    note && <span key="note" id={noteId}>{note}</span>,
  ].filter(Boolean);
  const hint = lines.length > 0 ? <span className="sw-hintlines">{lines}</span> : undefined;
  // For controls the library does not draw: the same messages under them.
  const under = (
    <>
      {waiting && (
        <span className="psl-hint" id={waitId}>
          Choose {parentLabel ?? 'the field above'} first
        </span>
      )}
      {hintText && (
        <span className="psl-hint" id={helpId}>
          {hintText}
        </span>
      )}
      {movedHelp?.text && (
        <span className="psl-hint" id={movedHelp.id}>
          {movedHelp.text}
        </span>
      )}
      {note && (
        <span className="psl-hint" id={noteId}>
          {note}
        </span>
      )}
      {error && (
        <span className="psl-error" id={`${id}-error`}>
          <Icon name="warn" />
          <span>{error}</span>
        </span>
      )}
    </>
  );
  const describedBy =
    [waiting && waitId, (hintText || (movedHelp && !movedHelp.text)) && helpId, note && noteId, error && `${id}-error`].filter(Boolean).join(' ') || undefined;
  const common = { 'aria-required': field.required || undefined, 'aria-describedby': movedHelp && !movedHelp.text ? movedHelp.id : undefined };
  const label = !field.required ? field.label : field.label;
  const optional = !field.required;
  const text = typeof value === 'string' ? value : '';
  const frame = (children: ReactNode) => (
    <div className="psl-field sw-field" data-field={field.name}>
      {children}
    </div>
  );

  switch (field.type) {
    case 'text':
    case 'integer':
    case 'period':
    case 'datetime':
      return frame(
        <TextField
          id={controlId}
          label={label}
          optional={optional}
          type={field.type === 'text' ? 'text' : NATIVE[field.type]}
          placeholder={field.placeholder}
          step={field.type === 'integer' ? 1 : undefined}
          inputMode={field.type === 'integer' ? 'numeric' : undefined}
          value={text}
          readOnly={readOnly}
          hint={hint}
          error={error}
          onChange={(event) => onChange(event.target.value)}
          {...common}
        />,
      );
    case 'long_text':
      // an optional note starts one line tall, as the SCR-04 boards draw "Anything Chidi should know"
      return frame(
        <TextArea id={controlId} label={label} optional={optional} oneLine={optional} placeholder={field.placeholder} value={text} readOnly={readOnly} hint={hint} error={error} onChange={(event) => onChange(event.target.value)} {...common} />,
      );
    case 'date':
      return frame(<DateField id={controlId} label={label} optional={optional} value={text} disabled={readOnly} hint={hint} error={error} onChange={(iso) => onChange(iso)} />);
    case 'date_range': {
      const range = (value as RangeValue | undefined) ?? { from: '', to: '' };
      return (
        <fieldset className="psl-field sw-field" data-field={field.name} aria-describedby={describedBy}>
          <Label id={labelId} field={field} as="legend" />
          <div className="sw-range">
            <DateField label="From" value={range.from} disabled={readOnly} onChange={(iso) => onChange({ ...range, from: iso })} />
            <DateField label="To" value={range.to} disabled={readOnly} onChange={(iso) => onChange({ ...range, to: iso })} />
          </div>
          {under}
        </fieldset>
      );
    }
    case 'choice': {
      const options = field.options ?? [];
      if (options.length > 3) {
        return frame(
          <Select
            id={controlId}
            label={label}
            optional={optional}
            options={options.map((option) => ({ value: option.value, label: option.label }))}
            value={typeof value === 'string' ? value : undefined}
            placeholder={field.placeholder ?? 'Choose…'}
            disabled={readOnly}
            hint={hint}
            error={error}
            onChange={(next) => onChange(next || undefined)}
          />,
        );
      }
      return frame(
        <>
          <Label id={labelId} field={field} />
          <div aria-describedby={describedBy} aria-invalid={invalid || undefined}>
            <Segmented
              labelledBy={labelId}
              className="sw-seg"
              options={options.map((option) => ({ value: option.value, label: option.label, disabled: readOnly }))}
              value={typeof value === 'string' ? value : undefined}
              onChange={(next) => !readOnly && onChange(next)}
            />
          </div>
          {under}
        </>,
      );
    }
    case 'record':
    case 'records':
      return frame(
        <>
          <Label id={labelId} field={field} />
          <RecordPicker
            key={parent ?? ''}
            lineKey={lineKey}
            field={field}
            parent={parent}
            value={value as LineOption | LineOption[] | undefined}
            onChange={onChange}
            disabled={readOnly || waiting}
            labelId={labelId}
            describedBy={describedBy}
            invalid={invalid}
          />
          {under}
        </>,
      );
    case 'display':
      return frame(
        <>
          <Label id={labelId} field={field} />
          <span className="psl-input sw-display">{field.value}</span>
          {under}
        </>,
      );
    default:
      return null;
  }
}
