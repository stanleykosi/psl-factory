'use client';

// SCR-04 record and records fields: a select-only combobox that opens a searchable listbox of E-LINE-OPTIONS.
// Options are only ever those returned for this line, field and parent; an option with a disabled_reason shows
// the reason and can't be chosen. Search waits 250 ms. D-157: no paging footer; the search finds a record, and the next page
// appends when the end of the list scrolls into view or the keyboard reaches the last option, while next_cursor is present.
import { useCallback, useEffect, useId, useRef, useState, type KeyboardEvent } from 'react';

import { Button, DEFAULT_PAGE_SIZE, Loading, SearchField, type PageSize } from '@/components';

import { isNew, type NewValue } from './intake';
import { allowsNew } from './showWhen';
import { fetchOptions } from './useStartWork';
import type { Field, LineOption } from './types';

export const SEARCH_DEBOUNCE_MS = 250;
/** The last row of a list whose line carries the mock overlay `allow_new` (F-49, G-23-1). */
export const NEW_CLIENT = 'New client';

/** Where the options come from when it is not E-LINE-OPTIONS (the live project list): one page by search and cursor. */
export type OptionSource = (q: string, cursor: string | undefined) => Promise<{ items: LineOption[]; next_cursor?: string }>;

type Props = {
  lineKey: string;
  field: Field;
  parent: string | undefined;
  value: LineOption | LineOption[] | NewValue | undefined;
  onChange: (value: LineOption | LineOption[] | NewValue | undefined) => void;
  disabled: boolean;
  labelId: string;
  describedBy: string | undefined;
  invalid: boolean;
  /** Replaces E-LINE-OPTIONS as the data source; the list UI is the same. */
  source?: OptionSource;
  /** The empty list's line, where "Nothing to choose from." is not the line's words. */
  emptyText?: string;
};

type ListState =
  | { status: 'loading'; items: LineOption[] }
  | { status: 'ready'; items: LineOption[]; next?: string; more: boolean }
  | { status: 'error'; items: LineOption[] };

export function RecordPicker({ lineKey, field, parent, value, onChange, disabled, labelId, describedBy, invalid, source, emptyText }: Props) {
  const multiple = field.type === 'records';
  const adding = isNew(value);
  const chosen = multiple ? ((value as LineOption[] | undefined) ?? []) : value && !adding ? [value as LineOption] : [];
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState('');
  const [query, setQuery] = useState('');
  const [list, setList] = useState<ListState>({ status: 'loading', items: [] });
  const buttonRef = useRef<HTMLButtonElement>(null);
  const popupRef = useRef<HTMLDivElement>(null);
  const focusSearch = () => popupRef.current?.querySelector<HTMLElement>('input[type="search"]')?.focus();
  const listRef = useRef<HTMLUListElement>(null);
  const request = useRef(0);
  // The cursor of the page last asked for, so Try again repeats that page.
  const lastCursor = useRef<string | undefined>(undefined);
  const id = useId();
  const popupId = `${id}-popup`;

  const load = useCallback(
    async (cursor?: string, limit: PageSize = DEFAULT_PAGE_SIZE) => {
      const seq = ++request.current;
      lastCursor.current = cursor;
      setList((current) => (cursor ? { status: 'ready', items: current.items, next: cursor, more: true } : { status: 'loading', items: [] }));
      try {
        const page = await (source ? source(query, cursor) : fetchOptions(lineKey, field.name, { parent, q: query, cursor, limit }));
        if (seq !== request.current) return;
        setList((current) => ({ status: 'ready', items: cursor ? [...current.items, ...page.items] : page.items, next: page.next_cursor, more: false }));
      } catch {
        if (seq !== request.current) return;
        setList((current) => ({ status: 'error', items: cursor ? current.items : [] }));
      }
    },
    [field.name, lineKey, parent, query, source],
  );

  const rows = list.items;
  const next = list.status === 'ready' && !list.more ? list.next : undefined;
  const loadMore = useRef<() => void>(() => undefined);
  useEffect(() => {
    loadMore.current = () => {
      if (next) void load(next);
    };
  });
  const sentinel = useRef<HTMLLIElement>(null);
  // The observer is made again after each page, so a list still short of its bottom keeps loading.
  useEffect(() => {
    const node = sentinel.current;
    if (!open || !node || !next || typeof IntersectionObserver === 'undefined') return undefined;
    const observer = new IntersectionObserver((entries) => {
      if (entries.some((e) => e.isIntersecting)) loadMore.current();
    }, { root: listRef.current, rootMargin: '0px 0px 48px 0px' });
    observer.observe(node);
    return () => observer.disconnect();
  }, [open, next, rows.length]);

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
    if (open) popupRef.current?.querySelector<HTMLElement>('input[type="search"]')?.focus();
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

  function optionKeys(event: KeyboardEvent<HTMLLIElement>, option: LineOption | undefined) {
    const items = [...(listRef.current?.querySelectorAll<HTMLElement>('[role="option"]') ?? [])];
    const at = items.indexOf(event.currentTarget);
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault();
      const to = event.key === 'ArrowDown' ? Math.min(at + 1, items.length - 1) : at - 1;
      if (event.key === 'ArrowDown' && at === items.length - 1) loadMore.current();
      if (to < 0) focusSearch();
      else items[to].focus();
    } else if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      if (option) choose(option);
    }
  }

  function popupKeys(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key !== 'Escape') return;
    // Esc closes the listbox only; the drawer stays open.
    event.stopPropagation();
    close();
  }

  const shown = adding ? NEW_CLIENT : chosen.map((c) => c.label).join(', ');
  const placeholder = field.placeholder ?? 'Choose…';

  return (
    <div className="sw-picker">
      <Button
        ref={buttonRef}
        kind="bare"
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
        <span className="psl-chev cmp-selectarrow" aria-hidden="true" />
      </Button>
      {open && (
        // The popup only catches Esc for its own controls; it is not itself interactive.
        // eslint-disable-next-line jsx-a11y/no-static-element-interactions
        <div ref={popupRef} id={popupId} className="psl-pop sw-picker__pop" onKeyDown={popupKeys}>
          <SearchField
            label={`Search ${field.label}`}
            placeholder="Search…"
            value={q}
            onChange={setQ}
            onKeyDown={(event) => {
              if (event.key !== 'ArrowDown') return;
              event.preventDefault();
              listRef.current?.querySelector<HTMLElement>('[role="option"]')?.focus();
            }}
          />
          {list.status === 'loading' && <Loading className="sw-picker__loading">Loading…</Loading>}
          {list.status === 'error' && list.items.length === 0 && (
            <p className="psl-error sw-picker__error">
              We couldn&rsquo;t load these options.{' '}
              <Button kind="text" size="sm" onClick={() => void load()}>
                Try again
              </Button>
            </p>
          )}
          {list.status === 'ready' && list.items.length === 0 && !allowsNew(field) && <p className="psl-hint sw-picker__empty">{emptyText ?? 'Nothing to choose from.'}</p>}
          {(list.items.length > 0 || (list.status === 'ready' && allowsNew(field))) && (
            <ul ref={listRef} className="psl-listbox" role="listbox" aria-labelledby={labelId} aria-multiselectable={multiple || undefined}>
              {rows.map((option) => {
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
              {allowsNew(field) && !multiple && list.status === 'ready' && !list.next && (
                <li
                  role="option"
                  className="psl-option"
                  tabIndex={-1}
                  aria-selected={adding}
                  onClick={() => {
                    onChange({ new: { name: '' } });
                    close();
                  }}
                  onKeyDown={(event) => {
                    if (event.key !== 'Enter' && event.key !== ' ') return optionKeys(event, undefined);
                    event.preventDefault();
                    onChange({ new: { name: '' } });
                    close();
                  }}
                >
                  {NEW_CLIENT}
                </li>
              )}
              {list.status === 'ready' && list.next && <li ref={sentinel} role="presentation" className="sw-picker__end" aria-hidden="true" />}
            </ul>
          )}
          {list.status === 'ready' && list.more && <Loading className="sw-picker__loading">Loading more…</Loading>}
          {list.status === 'error' && list.items.length > 0 && (
            <p className="psl-error sw-picker__error">
              We couldn&rsquo;t load more.{' '}
              <Button kind="text" size="sm" onClick={() => void load(lastCursor.current)}>
                Try again
              </Button>
            </p>
          )}
        </div>
      )}
    </div>
  );
}
