'use client';

// Segmented (design/system/project/components/Segmented): a row of joined options for a short single choice. One
// tab stop; arrows move and choose, Home and End go to the first and last, skipping disabled options. Each option
// stays on one line; a count is the square badge after the label, never "· 4" text.
import { useRef, type KeyboardEvent } from 'react';

import { CountBadge } from './CountBadge';
import { cx } from './internal';

export type SegmentedOption<T extends string> = {
  value: T;
  label: string;
  count?: number;
  /** Shown to assistive technology; the option cannot be chosen. */
  disabled?: boolean;
};

export function Segmented<T extends string>({ label, labelledBy, options, value, onChange, phone = false, className }: {
  /** The group's name, when no visible label names it. */
  label?: string;
  labelledBy?: string;
  options: SegmentedOption<T>[];
  /** undefined: nothing chosen yet. */
  value: T | undefined;
  onChange: (value: T) => void;
  /** 44px options with 15px text. */
  phone?: boolean;
  className?: string;
}) {
  const refs = useRef<(HTMLButtonElement | null)[]>([]);
  const checked = options.findIndex((o) => o.value === value);
  const firstEnabled = options.findIndex((o) => !o.disabled);
  const tabStop = checked >= 0 ? checked : firstEnabled;

  function move(at: number) {
    refs.current[at]?.focus();
    onChange(options[at].value);
  }

  function keys(event: KeyboardEvent<HTMLButtonElement>, at: number) {
    const enabled = options.map((o, i) => (o.disabled ? -1 : i)).filter((i) => i >= 0);
    if (enabled.length === 0) return;
    const pos = enabled.indexOf(at);
    let to: number | undefined;
    if (event.key === 'ArrowRight' || event.key === 'ArrowDown') to = enabled[(pos + 1) % enabled.length];
    else if (event.key === 'ArrowLeft' || event.key === 'ArrowUp') to = enabled[(pos - 1 + enabled.length) % enabled.length];
    else if (event.key === 'Home') to = enabled[0];
    else if (event.key === 'End') to = enabled[enabled.length - 1];
    if (to === undefined) return;
    event.preventDefault();
    move(to);
  }

  return (
    <div role="radiogroup" aria-label={label} aria-labelledby={labelledBy} className={cx('psl-seg', phone && 'psl-seg--phone', className)}>
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
          aria-disabled={option.disabled || undefined}
          tabIndex={at === tabStop ? 0 : -1}
          onClick={() => {
            if (!option.disabled) onChange(option.value);
          }}
          onKeyDown={(event) => keys(event, at)}
        >
          {option.label}
          {option.count !== undefined && <CountBadge count={option.count} />}
        </button>
      ))}
    </div>
  );
}
