'use client';

// Checkbox (design/system/project/components/Checkbox): any number of options, or confirming a statement. The
// whole label is the target (36px, 44px on phones). Mixed is for select-all when only some rows are chosen. An
// error (a required confirmation not ticked) shows under it.
import { useEffect, useId, useRef, type ComponentPropsWithRef, type ReactNode } from 'react';

import { FieldMessage } from './Field';
import { assignRef, cx } from './internal';

export type CheckboxProps = Omit<ComponentPropsWithRef<'input'>, 'type' | 'children'> & {
  label: ReactNode;
  /** A second line on what ticking it means. */
  detail?: ReactNode;
  mixed?: boolean;
  error?: ReactNode;
};

export function Checkbox({ label, detail, mixed = false, error, disabled, className, id, ref: outer, ...rest }: CheckboxProps) {
  const ref = useRef<HTMLInputElement | null>(null);
  const auto = useId();
  const messageId = `${id ?? auto}-message`;
  useEffect(() => {
    if (ref.current) ref.current.indeterminate = mixed;
  }, [mixed]);
  const box = (
    <label className={cx('psl-check cmp-check', error && 'is-error', disabled && 'is-disabled', className)}>
      <input
        {...rest}
        ref={(el) => {
          ref.current = el;
          assignRef(outer, el);
        }}
        id={id}
        type="checkbox"
        disabled={disabled}
        aria-invalid={error ? true : undefined}
        aria-describedby={cx(error && messageId, rest['aria-describedby']) || undefined}
      />
      <span>
        {label}
        {detail && <small>{detail}</small>}
      </span>
    </label>
  );
  if (!error) return box;
  return (
    <span className="psl-field">
      {box}
      <FieldMessage id={messageId} error={error} />
    </span>
  );
}
