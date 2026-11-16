'use client';

// Button (design/system/project/components/Button): seven kinds, four sizes, and the busy and disabled states.
// Busy keeps the button's width, shows the three squares with a label that says what is happening, and ignores
// further presses; disabled always carries its reason beside it.
import { useId, useLayoutEffect, useRef, type ComponentPropsWithRef, type MouseEvent, type ReactNode } from 'react';

import { Icon, type IconName } from './Icon';
import { assignRef, cx } from './internal';

export type ButtonKind = 'primary' | 'start' | 'confirm' | 'dark' | 'secondary' | 'reject' | 'text';
export type ButtonSize = 'sm' | 'md' | 'lg' | 'xl';

export type ButtonProps = Omit<ComponentPropsWithRef<'button'>, 'type'> & {
  kind?: ButtonKind;
  size?: ButtonSize;
  /** Full width (phone footers). */
  block?: boolean;
  /** A leading icon; the label still says what the button does. */
  icon?: IconName;
  busy?: boolean;
  /** What is happening while busy ("Recording…"); the label stays when not given. */
  busyLabel?: ReactNode;
  /** Why the button is disabled, written beside it. */
  reason?: ReactNode;
  type?: 'button' | 'submit' | 'reset';
};

/** The class list for a psl-btn of this kind and size, for links drawn as buttons. */
export function buttonClass(kind: ButtonKind = 'primary', size: ButtonSize = 'md', block = false): string {
  return cx('psl-btn', kind !== 'primary' && `psl-btn--${kind}`, size !== 'md' && `psl-btn--${size}`, block && 'psl-btn--block');
}

export function BusySquares() {
  return (
    <span className="psl-busy" aria-hidden="true">
      <i />
      <i />
      <i />
    </span>
  );
}

export function Button({
  kind = 'primary',
  size = 'md',
  block = false,
  icon,
  busy = false,
  busyLabel,
  reason,
  className,
  children,
  onClick,
  ref,
  type = 'button',
  disabled,
  ...rest
}: ButtonProps) {
  const own = useRef<HTMLButtonElement | null>(null);
  const width = useRef(0);
  const reasonId = useId();

  useLayoutEffect(() => {
    const el = own.current;
    if (!el) return;
    if (busy) {
      if (width.current > 0) el.style.minWidth = `${width.current}px`;
    } else {
      el.style.minWidth = '';
      width.current = el.offsetWidth;
    }
  });

  function press(event: MouseEvent<HTMLButtonElement>) {
    if (busy) {
      event.preventDefault();
      return;
    }
    onClick?.(event);
  }

  const describedBy = cx(rest['aria-describedby'], disabled && reason ? reasonId : undefined) || undefined;
  const button = (
    <button
      {...rest}
      ref={(el) => {
        own.current = el;
        assignRef(ref, el);
      }}
      type={type}
      className={cx(buttonClass(kind, size, block), size === 'sm' && 'cmp-btn-sm', busy && 'is-busy', className)}
      disabled={disabled}
      aria-busy={busy || undefined}
      aria-describedby={describedBy}
      onClick={press}
    >
      {busy ? (
        <>
          <BusySquares />
          {busyLabel ?? children}
        </>
      ) : (
        <>
          {icon && <Icon name={icon} />}
          {children}
        </>
      )}
    </button>
  );
  if (!(disabled && reason)) return button;
  return (
    <>
      {button}
      <span className="psl-reason" id={reasonId}>
        {reason}
      </span>
    </>
  );
}
