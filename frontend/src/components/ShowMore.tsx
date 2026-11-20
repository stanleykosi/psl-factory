'use client';

// ShowMore (design/system/project/components/ShowMore): the one paging footer (D-PAGING r2, F-54). Left to right: how
// many are showing ("20 of 74 showing", "All 74 showing", or "20 showing" where the total is not known), "Rows per
// page" as a 10 / 20 / 50 segmented group (never a dropdown), then "Show more" when there is more. No numbered pages.
// Table draws it inside its frame (`paging`); card lists put it under the last card (`solo`).
import { useEffect, useRef, useState } from 'react';

import { Button } from './Button';
import { cx, usePhone } from './internal';
import { Segmented } from './Segmented';

export const PAGE_SIZES = [10, 20, 50] as const;
export type PageSize = (typeof PAGE_SIZES)[number];
/** Every list starts at 10 rows (D-137). */
export const DEFAULT_PAGE_SIZE: PageSize = 10;

/** The rows-per-page choice of a list that keeps it in state; lists that keep it in the URL pass their own. */
export function usePageSize(initial: PageSize = DEFAULT_PAGE_SIZE) {
  return useState<PageSize>(initial);
}

/** The smallest page the server allows that covers `rows` more rows (the contract's limit is 10, 20 or 50). */
export function limitFor(rows: number): PageSize {
  return PAGE_SIZES.find((n) => n >= rows) ?? 50;
}

/**
 * The window over a cursor list's loaded rows (D-137). `items` is what the list has loaded so far and `next` whether
 * the server has more. Choosing a larger size shows more rows: the loaded ones stay in place, and only the missing
 * rows are fetched (`loadMore`, with the list's existing cursor) and appended. A smaller size trims the shown rows
 * back without a fetch; rows already loaded wait unseen. `resetKey` changing (a new filter or search, which reloads the
 * list from the first page) takes the window back to one page. A list that keeps the size in the URL passes
 * `size` and `onSize`.
 */
export function usePagedRows<T>({ items, next, busy, failed = false, loadMore, resetKey, size: controlled, onSize, total: known }: {
  items: T[];
  next: boolean;
  busy: boolean;
  /** The last fetch failed: no further fetch starts until the person presses Show more or Try again. */
  failed?: boolean;
  loadMore: (limit: PageSize) => void;
  resetKey?: unknown;
  size?: PageSize;
  onSize?: (size: PageSize) => void;
  /** A total the list knows beyond its loaded rows (My work's queue count). */
  total?: number;
}) {
  const [own, setOwn] = usePageSize();
  const size = controlled ?? own;
  const [visible, setVisible] = useState<number>(size);
  const [seenKey, setSeenKey] = useState(resetKey);
  if (seenKey !== resetKey) {
    setSeenKey(resetKey);
    setVisible(size);
  }
  const missing = visible - items.length;
  const latest = useRef(loadMore);
  useEffect(() => {
    latest.current = loadMore;
  });
  useEffect(() => {
    if (missing > 0 && next && !busy && !failed) latest.current(limitFor(missing));
  }, [missing, next, busy, failed]);

  const shown = Math.min(visible, items.length);
  const total = next ? known : items.length;
  const hasMore = next || items.length > shown;
  const paging: ShowMoreProps = {
    shown,
    total: total !== undefined && total > shown ? total : hasMore ? undefined : shown,
    hasMore,
    busy,
    onMore: () => {
      if (failed) latest.current(limitFor(Math.max(missing, 1)));
      else setVisible(shown + size);
    },
    size,
    onSize: (n) => {
      setOwn(n);
      onSize?.(n);
      setVisible(n);
    },
  };
  return { rows: items.slice(0, visible), paging };
}

export type ShowMoreProps = {
  shown: number;
  /** undefined where the list only knows whether there is more. */
  total?: number;
  onMore: () => void;
  busy?: boolean;
  /** For a list without a total: whether there is more to load. */
  hasMore?: boolean;
  /** Rows per page now, and the change handler. */
  size: PageSize;
  onSize: (size: PageSize) => void;
  /** Drawn on its own under a list of cards (its own frame), not inside a table. */
  solo?: boolean;
  className?: string;
};

// A list that redraws itself on a new size may remount this footer; the chosen option takes focus again.
let focusSize: PageSize | undefined;

export function ShowMore({ shown, total, onMore, busy = false, hasMore, size, onSize, solo = false, className }: ShowMoreProps) {
  const phone = usePhone();
  const rows = useRef<HTMLSpanElement>(null);
  const more = total !== undefined ? total > shown : Boolean(hasMore);
  const text = total === undefined ? `${shown} showing` : more ? `${shown} of ${total} showing` : `All ${total} showing`;
  const label = total === undefined ? 'Show more' : `Show ${Math.min(size, total - shown)} more`;

  useEffect(() => {
    if (focusSize === undefined) return;
    const option = rows.current?.querySelector<HTMLButtonElement>(`[role="radio"][aria-label="${focusSize}"]`);
    // A copy that is not drawn (the other of a desktop and phone pair) leaves the focus for the one that is.
    if (!option || option.checkVisibility?.() === false) return;
    focusSize = undefined;
    option.focus();
  });

  return (
    <div className={cx('psl-showmore', solo && 'psl-showmore--solo', phone && 'psl-showmore--phone', className)}>
      <span className="psl-showmore__count" aria-live="polite">{text}</span>
      <span className="psl-showmore__rows" ref={rows}>
        <span className="psl-showmore__label" aria-hidden="true">Rows per page</span>
        <Segmented
          label="Rows per page"
          phone={phone}
          value={String(size) as `${PageSize}`}
          options={PAGE_SIZES.map((n, i) => ({ value: String(n) as `${PageSize}`, label: String(n), disabled: total !== undefined && i > 0 && total <= PAGE_SIZES[i - 1] }))}
          onChange={(value) => {
            const next = PAGE_SIZES.find((n) => String(n) === value);
            if (next === undefined || next === size) return;
            focusSize = next;
            onSize(next);
          }}
        />
      </span>
      {more && (
        <Button kind="secondary" size="sm" className="psl-showmore__more" busy={busy} busyLabel="Loading…" onClick={onMore}>
          {label}
        </Button>
      )}
    </div>
  );
}
