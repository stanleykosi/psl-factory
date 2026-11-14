'use client';

// SCR-04 intake fields by kind, labelled from the contract: `label`, `placeholder`, `help` as the hint and
// `required` as aria-required ("(optional)" on the label otherwise). A 422 message sits under the control with
// aria-invalid and aria-describedby. Values are kept as typed; intake.ts turns them into the submitted shapes.
// As the boards draw them: a date range is one field box, a display value and a 422 for a field this drawer does
// not render are read-only boxes, and an optional proof field is its dashed box, disabled until FE-M2A-PROOF.
import { useId, useRef, type KeyboardEvent, type ReactNode } from 'react';

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

const NATIVE: Record<string, string> = { date: 'date', period: 'month', datetime: 'datetime-local', integer: 'number' };

function Label({ htmlFor, id, field, as = 'label' }: { htmlFor?: string; id: string; field: Field; as?: 'label' | 'span' | 'legend' }) {
  const Tag = as;
  return (
    <Tag className="psl-label" id={id} {...(as === 'label' ? { htmlFor } : {})}>
      {!field.required && field.type !== 'display' && field.type !== 'evidence' ? `${field.label} (optional)` : field.label}
    </Tag>
  );
}

export function IntakeField({ lineKey, field, value, onChange, parent, parentLabel, readOnly, error, note, movedHelp }: Props) {
  const id = useId();
  const controlId = `${id}-control`;
  const labelId = `${id}-label`;
  const helpId = movedHelp?.id ?? `${id}-help`;
  const errorId = `${id}-error`;
  const noteId = `${id}-note`;
  const waiting = field.depends_on !== undefined && parent === undefined;
  const hint = movedHelp ? undefined : field.help;
  const waitId = `${id}-wait`;
  const describedBy = [waiting && waitId, (hint || (movedHelp && !movedHelp.text)) && helpId, note && noteId, error && errorId].filter(Boolean).join(' ') || undefined;
  const invalid = error !== undefined;
  const common = {
    'aria-describedby': describedBy,
    'aria-invalid': invalid || undefined,
    'aria-required': field.required,
  };

  let control: ReactNode;
  let wrap: 'div' | 'fieldset' = 'div';
  switch (field.type) {
    case 'text':
    case 'long_text': {
      const Tag = field.type === 'text' ? 'input' : 'textarea';
      control = (
        <Tag
          id={controlId}
          className={field.type === 'text' ? 'psl-input' : 'psl-input psl-input--area'}
          placeholder={field.placeholder}
          value={typeof value === 'string' ? value : ''}
          readOnly={readOnly}
          onChange={(event) => onChange(event.target.value)}
          {...common}
        />
      );
      break;
    }
    case 'date':
    case 'period':
    case 'datetime':
    case 'integer':
      control = (
        <input
          id={controlId}
          type={NATIVE[field.type]}
          className="psl-input"
          placeholder={field.placeholder}
          step={field.type === 'integer' ? 1 : undefined}
          inputMode={field.type === 'integer' ? 'numeric' : undefined}
          value={typeof value === 'string' ? value : ''}
          readOnly={readOnly}
          onChange={(event) => onChange(event.target.value)}
          {...common}
        />
      );
      break;
    case 'date_range': {
      wrap = 'fieldset';
      const range = (value as RangeValue | undefined) ?? { from: '', to: '' };
      control = (
        <div className={`psl-input sw-range${invalid ? ' is-error' : ''}${readOnly ? ' is-readonly' : ''}`}>
          {(['from', 'to'] as const).map((part) => (
            <input
              key={part}
              id={`${controlId}-${part}`}
              type="date"
              aria-label={part === 'from' ? 'From' : 'To'}
              value={range[part]}
              readOnly={readOnly}
              onChange={(event) => onChange({ ...range, [part]: event.target.value })}
              {...common}
            />
          ))}
        </div>
      );
      break;
    }
    case 'choice': {
      const options = field.options ?? [];
      if (options.length <= 3) {
        control = <ChoiceSeg field={field} value={value} onChange={onChange} readOnly={readOnly} labelId={labelId} common={common} />;
      } else {
        control = (
          <select
            id={controlId}
            className="psl-input psl-select"
            value={typeof value === 'string' ? value : ''}
            disabled={readOnly}
            onChange={(event) => onChange(event.target.value || undefined)}
            {...common}
          >
            <option value="">{field.placeholder ?? 'Choose…'}</option>
            {options.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        );
      }
      break;
    }
    case 'record':
    case 'records':
      control = (
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
      );
      break;
    case 'display':
      control = <span className="psl-input sw-display">{field.value}</span>;
      break;
    case 'evidence':
      control = (
        <span className="sw-proof" aria-disabled="true">
          <svg className="psl-icon" aria-hidden="true" width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M12.5 5.5L6.5 11.5a1.8 1.8 0 0 0 2.5 2.5l6.5-6.5a3.5 3.5 0 0 0-5-5L4 9a5 5 0 0 0 7 7l4.5-4.5" />
          </svg>
          Proof upload comes next
        </span>
      );
      break;
    default:
      return null;
  }

  const Wrap = wrap;
  // A native control takes a <label>; the combobox, radio group and display text are named by the label's id.
  const native = control !== null && ['text', 'long_text', 'date', 'period', 'datetime', 'integer'].includes(field.type);
  const select = field.type === 'choice' && (field.options ?? []).length > 3;
  const labelAs = wrap === 'fieldset' ? 'legend' : native || select ? 'label' : 'span';
  return (
    <Wrap className="psl-field sw-field" data-field={field.name}>
      <Label htmlFor={controlId} id={labelId} field={field} as={labelAs} />
      {control}
      {waiting && (
        <span className="psl-hint" id={waitId}>
          Choose {parentLabel ?? 'the field above'} first
        </span>
      )}
      {hint && (
        <span className="psl-hint" id={helpId}>
          {hint}
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
        <span className="psl-error" id={errorId}>
          {error}
        </span>
      )}
    </Wrap>
  );
}

type ChoiceProps = {
  field: Field;
  value: FieldValue | undefined;
  onChange: (value: FieldValue | undefined) => void;
  readOnly: boolean;
  labelId: string;
  common: Record<string, unknown>;
};

/** 2 or 3 fixed choices as a psl-seg radio group: one tab stop, arrow keys move and choose. */
function ChoiceSeg({ field, value, onChange, readOnly, labelId, common }: ChoiceProps) {
  const options = field.options ?? [];
  const refs = useRef<(HTMLButtonElement | null)[]>([]);
  const checked = options.findIndex((o) => o.value === value);

  function keys(event: KeyboardEvent<HTMLButtonElement>, at: number) {
    const step = event.key === 'ArrowRight' || event.key === 'ArrowDown' ? 1 : event.key === 'ArrowLeft' || event.key === 'ArrowUp' ? -1 : 0;
    if (step === 0 || readOnly) return;
    event.preventDefault();
    const to = (at + step + options.length) % options.length;
    onChange(options[to].value);
    refs.current[to]?.focus();
  }

  return (
    <div className="psl-seg sw-seg" role="radiogroup" aria-labelledby={labelId} aria-readonly={readOnly || undefined} {...common}>
      {options.map((option, at) => (
        <button
          key={option.value}
          ref={(el) => {
            refs.current[at] = el;
          }}
          type="button"
          role="radio"
          className="psl-seg__opt"
          aria-checked={at === checked}
          aria-disabled={readOnly || undefined}
          tabIndex={at === (checked < 0 ? 0 : checked) ? 0 : -1}
          onClick={() => !readOnly && onChange(option.value)}
          onKeyDown={(event) => keys(event, at)}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}
