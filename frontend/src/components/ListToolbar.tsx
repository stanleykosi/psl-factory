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

/**
 * The filter panel as the SCR-01 filter boards draw it (D-93): a popover below the Filter button from 720px, with
 * the title in its head and Clear and the dark "Show N items" side by side in its foot; below 720px a bottom sheet
 * with Clear in its head and the dark full-width "Show N items" in thumb reach. Focus moves to the first field on
 * opening and back to the Filter button on closing; Esc and a press outside (or the scrim) close it unapplied.
 */
export function FilterPanel({ title = 'Filter', children, applyLabel, onApply, onClear, onClose, clearLabel = 'Clear', className }: {
  title?: string;
  children: ReactNode;
  /** "Show 4 items": says how many will show. */
  applyLabel: string;
  onApply: () => void;
  onClear: () => void;
  onClose: () => void;
  clearLabel?: string;
  className?: string;
}) {
  const phone = usePhone();
  const ref = useRef<HTMLDivElement>(null);
  // The anchor holds the Filter button too, so pressing it toggles rather than closing and reopening.
  const anchor = useRef<HTMLElement | null>(null);
  const opener = useRef<HTMLElement | null>(null);
  const closeRef = useRef(onClose);
  useEffect(() => {
    closeRef.current = onClose;
  });
  useOutsidePress([anchor], !phone, onClose);

  useEffect(() => {
    // The Filter button: the anchor's first button on desktop; on phones the sheet is portalled, so the button that
    // had focus when it opened (a tap does not focus a button in every browser, so the anchor's is preferred).
    opener.current = document.activeElement instanceof HTMLElement && document.activeElement !== document.body ? document.activeElement : null;
    if (phone) return undefined;
    anchor.current = ref.current?.parentElement ?? null;
    const back = anchor.current?.querySelector<HTMLElement>('button') ?? opener.current;
    (ref.current?.querySelector<HTMLElement>('input:not([disabled]), select:not([disabled]), button:not([disabled])') ?? ref.current)?.focus();
    // Esc closes it wherever focus is on the page (a click may have left focus outside the panel).
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') closeRef.current();
    };
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('keydown', onKey);
      back?.focus();
    };
  }, [phone]);

  if (phone) {
    return (
      <BottomSheet
        title={title}
        onClose={onClose}
        returnFocus={opener}
        grab={false}
        closeButton={false}
        titleClassName="cmp-filter__title"
        className={cx('cmp-filtersheet', className)}
        headAction={
          <button type="button" className="psl-link cmp-linkbutton" onClick={onClear}>
            {clearLabel}
          </button>
        }
        footer={
          <Button kind="dark" size="xl" block onClick={onApply}>
            {applyLabel}
          </Button>
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
      className={cx('psl-pop cmp-pop cmp-filter', className)}
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
        <Button kind="secondary" size="lg" block onClick={onClear}>
          {clearLabel}
        </Button>
        <Button kind="dark" size="lg" block onClick={onApply}>
          {applyLabel}
        </Button>
      </div>
    </div>
  );
}
