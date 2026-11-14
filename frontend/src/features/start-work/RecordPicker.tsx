'use client';

// SCR-04 record and records fields: a select-only combobox that opens a searchable listbox of E-LINE-OPTIONS.
// Options are only ever those returned for this line, field and parent; an option with a disabled_reason shows
// the reason and can't be chosen. Search waits 250 ms; "Show more" appends the next page while next_cursor is present.
import { useCallback, useEffect, useId, useRef, useState, type KeyboardEvent } from 'react';

import { fetchOptions } from './useStartWork';
import type { Field, LineOption } from './types';

export const SEARCH_DEBOUNCE_MS = 250;

type Props = {
  lineKey: string;
  field: Field;
  parent: string | undefined;
  value: LineOption | LineOption[] | undefined;
  onChange: (value: LineOption | LineOption[] | undefined) => void;
  disabled: boolean;
  labelId: string;
  describedBy: string | undefined;
  invalid: boolean;
};

type ListState =
  | { status: 'loading'; items: LineOption[] }
  | { status: 'ready'; items: LineOption[]; next?: string; more: boolean }
  | { status: 'error'; items: LineOption[] };

export function RecordPicker({ lineKey, field, parent, value, onChange, disabled, labelId, describedBy, invalid }: Props) {
  const multiple = field.type === 'records';
  const chosen = multiple ? ((value as LineOption[] | undefined) ?? []) : value ? [value as LineOption] : [];
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState('');
  const [query, setQuery] = useState('');
  const [list, setList] = useState<ListState>({ status: 'loading', items: [] });
  const buttonRef = useRef<HTMLButtonElement>(null);
  const searchRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLUListElement>(null);
  const request = useRef(0);
  // The cursor of the page last asked for, so Try again repeats that page.
  const lastCursor = useRef<string | undefined>(undefined);
  const id = useId();
  const popupId = `${id}-popup`;

  const load = useCallback(
    async (cursor?: string) => {
      const seq = ++request.current;
      lastCursor.current = cursor;
      setList((current) => (cursor ? { status: 'ready', items: current.items, next: cursor, more: true } : { status: 'loading', items: [] }));
      try {
        const page = await fetchOptions(lineKey, field.name, { parent, q: query, cursor });
        if (seq !== request.current) return;
        setList((current) => ({ status: 'ready', items: cursor ? [...current.items, ...page.items] : page.items, next: page.next_cursor, more: false }));
      } catch {
        if (seq !== request.current) return;
        setList((current) => ({ status: 'error', items: cursor ? current.items : [] }));
      }
    },
    [field.name, lineKey, parent, query],
  );

  useEffect(() => {
    if (!open) return;
    // Reads when the listbox opens and when the search settles; the effect only starts the request.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, [load, open]);

  useEffect(() => {
    if (q === query) return undefined;
    const timer = setTimeout(() => setQuery(q), SEARCH_DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [q, query]);

  useEffect(() => {
    if (open) searchRef.current?.focus();
  }, [open]);

  function close() {
    setOpen(false);
    setQ('');
    setQuery('');
    buttonRef.current?.focus();
  }

  function choose(option: LineOption) {
    if (option.disabled_reason) return;
    if (!multiple) {
      onChange(option);
      close();
      return;
    }
    const has = chosen.some((c) => c.value === option.value);
    const next = has ? chosen.filter((c) => c.value !== option.value) : [...chosen, option];
    onChange(next.length > 0 ? next : undefined);
  }

  function optionKeys(event: KeyboardEvent<HTMLLIElement>, option: LineOption) {
    const items = [...(listRef.current?.querySelectorAll<HTMLElement>('[role="option"]') ?? [])];
    const at = items.indexOf(event.currentTarget);
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault();
      const to = event.key === 'ArrowDown' ? Math.min(at + 1, items.length - 1) : at - 1;
      if (to < 0) searchRef.current?.focus();
      else items[to].focus();
    } else if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      choose(option);
    }
  }

  function popupKeys(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key !== 'Escape') return;
    // Esc closes the listbox only; the drawer stays open.
    event.stopPropagation();
    close();
  }

  const shown = chosen.map((c) => c.label).join(', ');
  const placeholder = field.placeholder ?? 'Choose…';

  return (
    <div className="sw-picker">
      <button
        ref={buttonRef}
        type="button"
        role="combobox"
        className={`psl-input psl-select${open ? ' is-open' : ''}${shown ? '' : ' is-placeholder'}`}
        aria-labelledby={labelId}
        aria-describedby={describedBy}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={open ? popupId : undefined}
        aria-required={field.required}
        aria-invalid={invalid || undefined}
        disabled={disabled}
        onClick={() => (open ? close() : setOpen(true))}
      >
        <span className="sw-picker__value">{shown || placeholder}</span>
        <span className="psl-chev" aria-hidden="true">
          ▾
        </span>
      </button>
      {open && (
        // The popup only catches Esc for its own controls; it is not itself interactive.
        // eslint-disable-next-line jsx-a11y/no-static-element-interactions
        <div id={popupId} className="psl-pop sw-picker__pop" onKeyDown={popupKeys}>
          <div className="psl-search">
            <svg className="psl-icon" aria-hidden="true" width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="7.5" cy="7.5" r="5.5" />
              <path d="M11.5 11.5L16 16" />
            </svg>
            <input
              ref={searchRef}
              type="search"
              className="psl-input"
              aria-label={`Search ${field.label}`}
              placeholder="Search…"
              value={q}
              onChange={(event) => setQ(event.target.value)}
              onKeyDown={(event) => {
                if (event.key !== 'ArrowDown') return;
                event.preventDefault();
                listRef.current?.querySelector<HTMLElement>('[role="option"]')?.focus();
              }}
            />
          </div>
          {list.status === 'loading' && (
            <span className="psl-loading" role="status">
              Loading…
            </span>
          )}
          {list.status === 'error' && list.items.length === 0 && (
            <p className="psl-error sw-picker__error">
              We couldn&rsquo;t load these options.{' '}
              <button type="button" className="psl-btn psl-btn--text psl-btn--sm" onClick={() => void load()}>
                Try again
              </button>
            </p>
          )}
          {list.status === 'ready' && list.items.length === 0 && <p className="psl-hint sw-picker__empty">Nothing to choose from.</p>}
          {list.items.length > 0 && (
            <ul ref={listRef} className="psl-listbox" role="listbox" aria-labelledby={labelId} aria-multiselectable={multiple || undefined}>
              {list.items.map((option) => {
                const selected = chosen.some((c) => c.value === option.value);
                return (
                  <li
                    key={option.value}
                    role="option"
                    className="psl-option"
                    tabIndex={-1}
                    aria-selected={selected}
                    aria-disabled={option.disabled_reason ? true : undefined}
                    onClick={() => choose(option)}
                    onKeyDown={(event) => optionKeys(event, option)}
                  >
                    {option.label}
                    {(option.disabled_reason ?? option.hint) && <small>{option.disabled_reason ?? option.hint}</small>}
                  </li>
                );
              })}
            </ul>
          )}
          {list.status === 'error' && list.items.length > 0 && (
            <p className="psl-error sw-picker__error">
              We couldn&rsquo;t load these options.{' '}
              <button type="button" className="psl-btn psl-btn--text psl-btn--sm" onClick={() => void load(lastCursor.current)}>
                Try again
              </button>
            </p>
          )}
          {list.status === 'ready' && list.next && (
            <div className="psl-showmore">
              <span>{list.items.length} shown</span>
              <button
                type="button"
                className="psl-btn psl-btn--text psl-btn--sm"
                disabled={list.more}
                onClick={() => void load(list.next)}
              >
                Show more
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
