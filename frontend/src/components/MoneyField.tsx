'use client';

// MoneyField (design/system/project/components/MoneyField): amounts in mono with ₦ fixed in front and two decimals.
// Thousands separators appear as the person types; the value kept is the exact digits typed (a string, never a
// float, never rounded). An amount not known yet is Unknown (the amber tag): null, never 0 and never blank.
// "Mark as unknown" sits under the field only where Unknown is allowed. Contract amounts are read-only and say
// where they came from. Show amounts with Money (Values.tsx).
import { useLayoutEffect, useRef, type ChangeEvent } from 'react';

import { Button } from './Button';
import { FieldLabel, FieldMessage, useFieldIds, type FieldText } from './Field';
import { groupDigits as group } from './format';
import { cx } from './internal';

export type MoneyFieldProps = FieldText & {
  /** The exact amount typed ("4250000.00"), '' when empty, null when Unknown. */
  value: string | null;
  onChange: (value: string | null) => void;
  /** Shows "Mark as unknown" under the field. */
  allowUnknown?: boolean;
  /** A contract amount: shown, not editable; the hint says where it came from. */
  readOnly?: boolean;
  disabled?: boolean;
  id?: string;
  fieldClassName?: string;
};

export function MoneyField({ label, optional, hint, error, value, onChange, allowUnknown = false, readOnly = false, disabled = false, id, fieldClassName }: MoneyFieldProps) {
  const ids = useFieldIds(id, { hint, error });
  const input = useRef<HTMLInputElement>(null);
  const caret = useRef<number | null>(null);

  useLayoutEffect(() => {
    if (caret.current === null || !input.current) return;
    input.current.setSelectionRange(caret.current, caret.current);
    caret.current = null;
  });

  function change(event: ChangeEvent<HTMLInputElement>) {
    const typed = event.target.value;
    const at = event.target.selectionStart ?? typed.length;
    // Digits and one point, up to two decimals; separators are drawn, not stored.
    const before = typed.slice(0, at).replace(/[^\d.]/g, '');
    let raw = typed.replace(/[^\d.]/g, '');
    const point = raw.indexOf('.');
    if (point >= 0) raw = `${raw.slice(0, point + 1)}${raw.slice(point + 1).replace(/\./g, '').slice(0, 2)}`;
    // Put the caret back after the same number of digits it followed.
    const shown = group(raw);
    let seen = 0;
    let pos = 0;
    while (pos < shown.length && seen < before.length) {
      if (shown[pos] !== ',') seen += 1;
      pos += 1;
    }
    caret.current = pos;
    onChange(raw);
  }

  if (value === null) {
    return (
      <div className={cx('psl-field', fieldClassName)}>
        <FieldLabel id={ids.label} label={label} optional={optional} />
        <span className="psl-input is-readonly" role="group" aria-labelledby={ids.label} aria-describedby={ids.describedBy}>
          <span className="psl-unknown">Unknown</span>
        </span>
        <FieldMessage id={ids.message} hint={hint} error={error} />
        {allowUnknown && !readOnly && !disabled && (
          <span>
            <Button kind="text" size="sm" className="cmp-under" onClick={() => onChange('')}>
              Enter the amount
            </Button>
          </span>
        )}
      </div>
    );
  }

  return (
    <div className={cx('psl-field', fieldClassName)}>
      <FieldLabel htmlFor={ids.control} id={ids.label} label={label} optional={optional} />
      <span className={cx('psl-input psl-input--money cmp-wrapped', error && 'is-error', readOnly && 'is-readonly', disabled && 'is-disabled')}>
        <span className="psl-affix" aria-hidden="true">
          ₦
        </span>
        <input
          ref={input}
          id={ids.control}
          type="text"
          inputMode="decimal"
          autoComplete="off"
          value={group(value)}
          readOnly={readOnly}
          disabled={disabled}
          aria-invalid={error ? true : undefined}
          aria-describedby={ids.describedBy}
          onChange={change}
        />
      </span>
      <FieldMessage id={ids.message} hint={hint} error={error} />
      {allowUnknown && !readOnly && !disabled && (
        <span>
          <Button kind="text" size="sm" className="cmp-under" onClick={() => onChange(null)}>
            Mark as unknown
          </Button>
        </span>
      )}
    </div>
  );
}
