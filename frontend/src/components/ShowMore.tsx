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
export const DEFAULT_PAGE_SIZE: PageSize = 20;

/** The rows-per-page choice of a list that keeps it in state; lists that keep it in the URL pass their own. */
export function usePageSize(initial: PageSize = DEFAULT_PAGE_SIZE) {
  return useState<PageSize>(initial);
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
    focusSize = undefined;
    option?.focus();
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
          options={PAGE_SIZES.map((n) => ({ value: String(n) as `${PageSize}`, label: String(n) }))}
          onChange={(value) => {
            const next = Number(value) as PageSize;
            if (next === size) return;
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
