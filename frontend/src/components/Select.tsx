'use client';

// Select (design/system/project/components/Select): pick one of up to about 15 values. A select-only combobox:
// focus stays on the control and the active option is aria-activedescendant. Arrows move, Home/End jump, Enter or
// Space chooses, Esc closes and keeps focus on the control, typing jumps to the first match. The list opens below
// the control, above it when there is no room. A disabled option stays readable with its reason as its second line.
import { useEffect, useId, useRef, useState, type KeyboardEvent, type ReactNode } from 'react';

import { FieldLabel, FieldMessage, useFieldIds, type FieldText } from './Field';
import { Icon } from './Icon';
import { cx, isTypeaheadKey, useOutsidePress, useTypeahead } from './internal';

export type SelectOption = {
  value: string;
  label: string;
  /** A second line ("Finance Lead"). */
  hint?: ReactNode;
  /** Why this option cannot be chosen; shown as its second line. */
  disabledReason?: string;
  /** A group label in mono caps, shown above the first option of the group. */
  group?: string;
};

export type SelectProps = FieldText & {
  options: SelectOption[];
  value: string | undefined;
  onChange: (value: string) => void;
  placeholder: string;
  disabled?: boolean;
  id?: string;
  fieldClassName?: string;
};

// The listbox's max-height in psl-bundle.css, plus the 4px gap: below this much room it opens upwards.
const LIST_ROOM = 284;

export function Select({ label, optional, hint, error, options, value, onChange, placeholder, disabled = false, id, fieldClassName }: SelectProps) {
  const ids = useFieldIds(id, { hint, error });
  const listId = useId();
  const [open, setOpen] = useState(false);
  const [up, setUp] = useState(false);
  const [active, setActive] = useState(-1);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const listRef = useRef<HTMLUListElement>(null);
  const typeahead = useTypeahead();
  const chosen = options.findIndex((o) => o.value === value);

  useOutsidePress([buttonRef, listRef], open, () => setOpen(false));

  useEffect(() => {
    if (!open || active < 0) return;
    listRef.current?.querySelector<HTMLElement>(`[data-index="${active}"]`)?.scrollIntoView?.({ block: 'nearest' });
  }, [open, active]);

  function show(at: number) {
    const rect = buttonRef.current?.getBoundingClientRect();
    setUp(rect ? window.innerHeight - rect.bottom < LIST_ROOM && rect.top > window.innerHeight - rect.bottom : false);
    setActive(at);
    setOpen(true);
  }

  function choose(at: number) {
    const option = options[at];
    if (!option || option.disabledReason) return;
    onChange(option.value);
    setOpen(false);
  }

  function keys(event: KeyboardEvent<HTMLButtonElement>) {
    const last = options.length - 1;
    if (!open) {
      if (['ArrowDown', 'ArrowUp', 'Enter', ' '].includes(event.key)) {
        event.preventDefault();
        show(event.key === 'ArrowUp' && chosen < 0 ? last : Math.max(chosen, 0));
      } else if (event.key === 'Home' || event.key === 'End') {
        event.preventDefault();
        show(event.key === 'Home' ? 0 : last);
      } else if (isTypeaheadKey(event)) {
        const at = typeahead(event.key, options.map((o) => o.label), Math.max(chosen, 0));
        if (at >= 0) show(at);
      }
      return;
    }
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault();
      setActive((at) => Math.min(Math.max(at + (event.key === 'ArrowDown' ? 1 : -1), 0), last));
    } else if (event.key === 'Home' || event.key === 'End') {
      event.preventDefault();
      setActive(event.key === 'Home' ? 0 : last);
    } else if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      choose(active);
    } else if (event.key === 'Escape') {
      event.preventDefault();
      event.stopPropagation();
      setOpen(false);
    } else if (event.key === 'Tab') {
      setOpen(false);
    } else if (isTypeaheadKey(event)) {
      const at = typeahead(event.key, options.map((o) => o.label), active + 1);
      if (at >= 0) setActive(at);
    }
  }

  const optionId = (at: number) => `${listId}-${at}`;
  return (
    <div className={cx('psl-field', fieldClassName)}>
      <FieldLabel id={ids.label} label={label} optional={optional} />
      <div className="cmp-anchor">
        <button
          ref={buttonRef}
          id={ids.control}
          type="button"
          role="combobox"
          className={cx('psl-input psl-select', open && 'is-open', chosen < 0 && 'is-placeholder', error && 'is-error')}
          aria-labelledby={ids.label}
          aria-describedby={ids.describedBy}
          aria-haspopup="listbox"
          aria-expanded={open}
          aria-controls={open ? listId : undefined}
          aria-activedescendant={open && active >= 0 ? optionId(active) : undefined}
          aria-invalid={error ? true : undefined}
          disabled={disabled}
          onClick={() => (open ? setOpen(false) : show(Math.max(chosen, 0)))}
          onKeyDown={keys}
        >
          <span>{chosen >= 0 ? options[chosen].label : placeholder}</span>
          <Icon name="chev" className="psl-chev" />
        </button>
        {open && (
          <ul ref={listRef} id={listId} className={cx('psl-pop psl-listbox cmp-pop cmp-pop--fill', up && 'cmp-pop--up')} role="listbox" aria-labelledby={ids.label}>
            {options.map((option, at) => (
              <SelectRow
                key={option.value}
                option={option}
                id={optionId(at)}
                index={at}
                groupStart={option.group !== undefined && option.group !== options[at - 1]?.group}
                selected={at === chosen}
                active={at === active}
                onChoose={() => choose(at)}
              />
            ))}
          </ul>
        )}
      </div>
      <FieldMessage id={ids.message} hint={hint} error={error} />
    </div>
  );
}

function SelectRow({ option, id, index, groupStart, selected, active, onChoose }: {
  option: SelectOption;
  id: string;
  index: number;
  groupStart: boolean;
  selected: boolean;
  active: boolean;
  onChoose: () => void;
}) {
  const second = option.disabledReason ?? option.hint;
  return (
    <>
      {groupStart && (
        <li className="psl-optgroup" role="presentation">
          {option.group?.toUpperCase()}
        </li>
      )}
      {/* Keyboard choice is on the combobox (aria-activedescendant); the pointer chooses here. */}
      {/* eslint-disable-next-line jsx-a11y/click-events-have-key-events */}
      <li
        id={id}
        data-index={index}
        role="option"
        tabIndex={-1}
        className={cx('psl-option', active && 'is-active')}
        aria-selected={selected}
        aria-disabled={option.disabledReason ? true : undefined}
        onMouseDown={(event) => event.preventDefault()}
        onClick={onChoose}
      >
        {option.label}
        {second && <small>{second}</small>}
      </li>
    </>
  );
}
