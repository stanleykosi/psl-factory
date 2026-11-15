'use client';

// TextArea (design/system/project/components/TextArea): notes, reasons and descriptions. At least 88px, grows with
// its content to 240px and then scrolls. With a limit, the count sits under the box on the right in mono and turns
// signal-ink when over; the text is never cut.
import { useLayoutEffect, useRef, type ComponentPropsWithRef } from 'react';

import { FieldLabel, FieldMessage, useFieldIds, type FieldText } from './Field';
import { assignRef, cx } from './internal';

// The TextArea page: grows with content up to 240px, then scrolls.
const MAX_HEIGHT = 240;

export type TextAreaProps = Omit<ComponentPropsWithRef<'textarea'>, 'children' | 'value'> &
  FieldText & {
    value: string;
    /** The most characters allowed; shows "38 / 500". */
    limit?: number;
    fieldClassName?: string;
  };

export function TextArea({ label, optional, hint, error, limit, id, className, fieldClassName, value, ref: outer, ...rest }: TextAreaProps) {
  const ids = useFieldIds(id, { hint, error });
  const ref = useRef<HTMLTextAreaElement | null>(null);
  const over = limit !== undefined && value.length > limit;
  const countId = `${ids.control}-count`;

  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = 'auto';
    if (el.scrollHeight === 0) return;
    el.style.height = `${Math.min(el.scrollHeight + 4, MAX_HEIGHT)}px`;
    el.style.overflowY = el.scrollHeight + 4 > MAX_HEIGHT ? 'auto' : 'hidden';
  }, [value]);

  return (
    <div className={cx('psl-field', fieldClassName)}>
      <FieldLabel htmlFor={ids.control} id={ids.label} label={label} optional={optional} />
      <textarea
        {...rest}
        ref={(el) => {
          ref.current = el;
          assignRef(outer, el);
        }}
        id={ids.control}
        value={value}
        className={cx('psl-input psl-input--area', (error || over) && 'is-error', className)}
        aria-invalid={error || over ? true : undefined}
        aria-describedby={cx(ids.describedBy, limit !== undefined && countId, rest['aria-describedby']) || undefined}
      />
      <FieldMessage id={ids.message} hint={hint} error={error} />
      {limit !== undefined && (
        <span className={cx('psl-count', over && 'is-over')} id={countId}>
          {value.length} / {limit}
        </span>
      )}
    </div>
  );
}
