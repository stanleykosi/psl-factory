'use client';

// Radio (design/system/project/components/Radio): choose exactly one. Plain radios for short options; choice cards
// for decisions where each option says what it does and does not do. Native radios in a fieldset, so arrows move
// and choose. Nothing is chosen until the person chooses: a decision is never preselected.
import { useId, type ReactNode } from 'react';

import { FieldMessage } from './Field';
import { cx } from './internal';

export type RadioOption = {
  value: string;
  label: ReactNode;
  /** The second line: what the choice does (cards), or a short note. */
  detail?: ReactNode;
  /** Why it cannot be chosen; shown as the second line. */
  disabledReason?: string;
};

export function RadioGroup({ legend, options, value, onChange, cards = false, error, name, className, hideLegend = false, disabled: whole = false }: {
  legend: ReactNode;
  options: RadioOption[];
  value: string | undefined;
  onChange: (value: string) => void;
  /** Choice cards: a full-width box per option. */
  cards?: boolean;
  /** Nothing chosen where a choice is required. */
  error?: ReactNode;
  name?: string;
  className?: string;
  /** The legend is read but not drawn, where the screen already names the group. */
  hideLegend?: boolean;
  /** No option can be chosen (a write is in flight, or the choice is locked). */
  disabled?: boolean;
}) {
  const auto = useId();
  const group = name ?? auto;
  const messageId = `${group}-message`;
  return (
    <fieldset className={cx('psl-field cmp-fieldset', className)} aria-describedby={error ? messageId : undefined}>
      <legend className={hideLegend ? 'psl-label cmp-sr' : 'psl-label'}>{legend}</legend>
      <div className={cx('cmp-choices', cards && 'cmp-choices--cards')}>
        {options.map((option) => {
          const checked = option.value === value;
          const disabled = whole || Boolean(option.disabledReason);
          const second = option.disabledReason ?? option.detail;
          return (
            <label
              key={option.value}
              className={cx(cards ? 'psl-choice' : 'psl-radio cmp-check', cards && checked && 'is-selected', error && 'is-error', disabled && 'is-disabled')}
            >
              <input
                type="radio"
                name={group}
                value={option.value}
                checked={checked}
                disabled={disabled}
                onChange={() => onChange(option.value)}
              />
              <span>
                {cards ? <strong>{option.label}</strong> : option.label}
                {second && <small>{second}</small>}
              </span>
            </label>
          );
        })}
      </div>
      <FieldMessage id={messageId} error={error} />
    </fieldset>
  );
}
