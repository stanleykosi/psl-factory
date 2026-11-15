'use client';

// A psl-seg radio group (SCR-16 team and result choices): one tab stop, arrow keys move and choose, as the
// Start work choice fields do. Nothing is chosen until the person chooses.
import { useId, useRef, type KeyboardEvent } from 'react';

export type SegOption<T extends string> = { value: T; text: string; /** The accessible name when it differs from the text. */ name?: string; className?: string };

export function Segmented<T extends string>({ label, options, value, onChange, className }: {
  label: string;
  options: SegOption<T>[];
  value: string;
  onChange: (value: T) => void;
  className?: string;
}) {
  const labelId = useId();
  const refs = useRef<(HTMLButtonElement | null)[]>([]);
  const checked = options.findIndex((o) => o.value === value);

  function keys(event: KeyboardEvent<HTMLButtonElement>, at: number) {
    const step = event.key === 'ArrowRight' || event.key === 'ArrowDown' ? 1 : event.key === 'ArrowLeft' || event.key === 'ArrowUp' ? -1 : 0;
    if (step === 0) return;
    event.preventDefault();
    const to = (at + step + options.length) % options.length;
    onChange(options[to].value);
    refs.current[to]?.focus();
  }

  return (
    <div className="resp-field">
      <span id={labelId} className="resp-label">
        {label}
      </span>
      <div role="radiogroup" aria-labelledby={labelId} className={`psl-seg resp-segbar${className ? ` ${className}` : ''}`}>
        {options.map((o, at) => (
          <button
            key={o.value}
            ref={(el) => {
              refs.current[at] = el;
            }}
            type="button"
            role="radio"
            className={`psl-seg__opt${o.className ? ` ${o.className}` : ''}`}
            aria-checked={at === checked}
            aria-label={o.name}
            tabIndex={at === (checked < 0 ? 0 : checked) ? 0 : -1}
            onClick={() => onChange(o.value)}
            onKeyDown={(event) => keys(event, at)}
          >
            {o.text}
          </button>
        ))}
      </div>
    </div>
  );
}
