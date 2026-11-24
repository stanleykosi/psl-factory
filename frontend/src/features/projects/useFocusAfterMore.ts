'use client';

import { useEffect, useRef, type RefObject } from 'react';

/**
 * After "Show more" appends rows, focus stays where the person was. When the control goes (the last page), focus would
 * fall to the page, so it moves to the first new row's link; a row without a link takes focus itself (tabindex -1).
 */
export function useFocusAfterMore(rows: RefObject<HTMLElement | null>, count: number) {
  const before = useRef(count);
  useEffect(() => {
    const previous = before.current;
    before.current = count;
    if (count <= previous || previous === 0) return;
    const active = document.activeElement;
    if (active && active !== document.body && active.isConnected) return;
    const rowEls = rows.current?.querySelectorAll<HTMLElement>('tbody tr, [role="listitem"]');
    const first = rowEls?.[previous];
    if (first && !first.querySelector('a')) first.tabIndex = -1;
    (first?.querySelector<HTMLElement>('a') ?? first ?? rows.current?.querySelector<HTMLElement>('.psl-tablewrap'))?.focus();
  }, [rows, count]);
}
