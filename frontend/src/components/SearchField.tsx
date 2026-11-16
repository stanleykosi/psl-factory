'use client';

// SearchField (design/system/project/components/SearchField): a search box with a leading magnifier. The
// placeholder names what can be searched; the accessible name is the label. `onSearch` fires after a 200ms pause
// once there are 2 characters (and when the box is cleared). A clear button appears once there is text.
import { useEffect, useRef, type ComponentPropsWithRef } from 'react';

import { Icon } from './Icon';
import { IconButton } from './IconButton';
import { cx } from './internal';

export const SEARCH_PAUSE_MS = 200;
export const SEARCH_MIN_CHARS = 2;

export type SearchFieldProps = Omit<ComponentPropsWithRef<'input'>, 'value' | 'onChange' | 'type'> & {
  /** The accessible name ("Search work"). */
  label: string;
  value: string;
  onChange: (value: string) => void;
  /** The settled search: 2+ characters after the pause, or '' when cleared. */
  onSearch?: (query: string) => void;
  fieldClassName?: string;
};

export function SearchField({ label, value, onChange, onSearch, className, fieldClassName, disabled, ...rest }: SearchFieldProps) {
  const input = useRef<HTMLInputElement>(null);
  const search = useRef(onSearch);
  const last = useRef(value.trim());
  useEffect(() => {
    search.current = onSearch;
  });

  useEffect(() => {
    const query = value.trim();
    if (query === last.current || (query.length > 0 && query.length < SEARCH_MIN_CHARS)) return undefined;
    const timer = setTimeout(
      () => {
        last.current = query;
        search.current?.(query);
      },
      query.length === 0 ? 0 : SEARCH_PAUSE_MS,
    );
    return () => clearTimeout(timer);
  }, [value]);

  return (
    <div className={cx('psl-search', fieldClassName)}>
      <Icon name="search" />
      <input
        {...rest}
        ref={input}
        type="search"
        className={cx('psl-input cmp-search', className)}
        aria-label={label}
        value={value}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === 'Escape' && value) {
            event.preventDefault();
            event.stopPropagation();
            onChange('');
          }
          rest.onKeyDown?.(event);
        }}
      />
      {value && !disabled && (
        <IconButton
          bare
          icon="close"
          label="Clear search"
          className="psl-search__clear"
          onClick={() => {
            onChange('');
            input.current?.focus();
          }}
        />
      )}
    </div>
  );
}
