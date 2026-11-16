'use client';

// TextField (design/system/project/components/TextField): one line, label always visible above, hint or error
// below. The placeholder is an example, never the label. Read-only is for values the factory set.
import type { ComponentPropsWithRef } from 'react';

import { FieldLabel, FieldMessage, useFieldIds, type FieldText } from './Field';
import { cx } from './internal';

export type TextFieldProps = Omit<ComponentPropsWithRef<'input'>, 'children'> &
  FieldText & {
    /** 48px with 15px text, for phone screens. */
    phone?: boolean;
    fieldClassName?: string;
  };

export function TextField({ label, optional, hint, error, phone = false, id, className, fieldClassName, type = 'text', ...rest }: TextFieldProps) {
  const ids = useFieldIds(id, { hint, error });
  return (
    <div className={cx('psl-field', fieldClassName)}>
      <FieldLabel htmlFor={ids.control} id={ids.label} label={label} optional={optional} />
      <input
        {...rest}
        id={ids.control}
        type={type}
        className={cx('psl-input', phone && 'psl-input--phone', error && 'is-error', className)}
        aria-invalid={error ? true : undefined}
        aria-describedby={cx(ids.describedBy, rest['aria-describedby']) || undefined}
      />
      <FieldMessage id={ids.message} hint={hint} error={error} />
    </div>
  );
}
