'use client';

// ListToolbar (design/system/project/components/ListToolbar, CMP-22): the same way to find and narrow records on
// every list. Search, a Filter button showing how many filters are on, the result count in mono on the right, and
// the applied filters as removable chips with Clear all. The filter panel (FilterPanel) opens below the button and
// applies on "Show N results"; on a phone the button is a 44px icon button and the panel a bottom sheet.
// No results is an EmptyState ("No work matches") with Clear filters, drawn by the list.
import { useEffect, useRef, type ReactNode } from 'react';

import { BottomSheet } from './BottomSheet';
import { Button } from './Button';
import { CountBadge } from './CountBadge';
import { Icon } from './Icon';
import { IconButton } from './IconButton';
import { cx, useOutsidePress, usePhone } from './internal';
import { SearchField } from './SearchField';

export type FilterChip = { key: string; name: string; value: string; onRemove: () => void };

export function ListToolbar({ search, filterCount, filterOpen, onFilterToggle, filterPanel, resultText, chips = [], onClearAll, className }: {
  search: { label: string; placeholder: string; value: string; onChange: (value: string) => void; onSearch?: (query: string) => void };
  /** How many filters are on. */
  filterCount: number;
  filterOpen: boolean;
  onFilterToggle: () => void;
  /** The FilterPanel, drawn while `filterOpen`. */
  filterPanel?: ReactNode;
  /** "32 items", "4 of 32". */
  resultText: string;
  chips?: FilterChip[];
  onClearAll?: () => void;
  className?: string;
}) {
  const phone = usePhone();
  return (
    <div className={cx('cmp-listtools', className)}>
      <div className="psl-toolbar">
        <SearchField {...search} fieldClassName="cmp-toolsearch" />
        <span className="cmp-anchor cmp-anchor--inline">
          {phone ? (
            <IconButton icon="filter" label="Filter" count={filterCount > 0 ? filterCount : undefined} aria-expanded={filterOpen} onClick={onFilterToggle} />
          ) : (
            <Button kind="secondary" aria-expanded={filterOpen} onClick={onFilterToggle}>
              <Icon name="filter" />
              Filter
              {filterCount > 0 && (
                <>
                  {' '}
                  <CountBadge count={filterCount} tone="signal" />
                  <span className="cmp-sr"> on</span>
                </>
              )}
            </Button>
          )}
          {filterOpen && filterPanel}
        </span>
        <span className="psl-resultcount" role="status">
          {resultText}
        </span>
      </div>
      {chips.length > 0 && (
        <div className="cmp-chips">
          {chips.map((chip) => (
            <span key={chip.key} className="psl-chip">
              <span>{chip.name}</span>
              <strong>{chip.value}</strong>
              <button type="button" aria-label={`Remove ${chip.name} filter`} onClick={chip.onRemove}>
                ×
              </button>
            </span>
          ))}
          {onClearAll && (
            <button type="button" className="psl-link cmp-linkbutton cmp-linkbutton--small" onClick={onClearAll}>
              Clear all
            </button>
          )}
        </div>
      )}
    </div>
  );
}

/** The filter panel: a popover below the Filter button from 720px, a bottom sheet below. */
export function FilterPanel({ title = 'Filter', children, applyLabel, onApply, onClear, onClose }: {
  title?: string;
  children: ReactNode;
  /** "Show 4 results": says how many will show. */
  applyLabel: string;
  onApply: () => void;
  onClear: () => void;
  onClose: () => void;
}) {
  const phone = usePhone();
  const ref = useRef<HTMLDivElement>(null);
  // The anchor holds the Filter button too, so pressing it toggles rather than closing and reopening.
  const anchor = useRef<HTMLElement | null>(null);
  useOutsidePress([anchor], !phone, onClose);

  useEffect(() => {
    if (phone) return undefined;
    anchor.current = ref.current?.parentElement ?? null;
    // Focus returns to the Filter button (the anchor's first button), which a click does not focus in every browser.
    const back = anchor.current?.querySelector<HTMLElement>('button');
    ref.current?.focus();
    return () => back?.focus();
  }, [phone]);

  if (phone) {
    return (
      <BottomSheet
        title={title}
        onClose={onClose}
        footer={
          <>
            <Button size="xl" block onClick={onApply}>
              {applyLabel}
            </Button>
            <Button kind="text" onClick={onClear}>
              Clear all
            </Button>
          </>
        }
      >
        {children}
      </BottomSheet>
    );
  }
  return (
    // Esc is handled for the whole panel.
    // eslint-disable-next-line jsx-a11y/no-noninteractive-element-interactions
    <div
      ref={ref}
      className="psl-pop cmp-pop cmp-filter"
      role="dialog"
      aria-label={title}
      tabIndex={-1}
      onKeyDown={(event) => {
        if (event.key !== 'Escape') return;
        event.stopPropagation();
        onClose();
      }}
    >
      <div className="cmp-filter__head">{title}</div>
      <div className="cmp-filter__body">{children}</div>
      <div className="cmp-filter__foot">
        <button type="button" className="psl-link cmp-linkbutton" onClick={onClear}>
          Clear all
        </button>
        <Button size="sm" onClick={onApply}>
          {applyLabel}
        </Button>
      </div>
    </div>
  );
}
