'use client';

// Tabs (design/system/project/components/Tabs): switch between sections of one thing (a project's Journey,
// Milestones, Documents…). Joined 44px boxes; the selected tab fills ink; counts are square badges and zero shows
// "0". Tabs are links (each section has its own address) or buttons. One tab stop: arrows move focus, Home and End
// go to the first and last, Enter or Space opens the focused tab; a disabled tab is skipped and cannot open. The
// label and count read "History 7". On a phone they are a strip that scrolls sideways.
import NextLink from 'next/link';
import { useRef, type KeyboardEvent } from 'react';

import { CountBadge } from './CountBadge';
import { cx } from './internal';

export type TabItem<K extends string> = { key: K; label: string; count?: number; href?: string; /** Shown, but cannot be opened. */ disabled?: boolean };

export function Tabs<K extends string>({ label, tabs, selected, onSelect, panelId, strip = false, className }: {
  label: string;
  tabs: TabItem<K>[];
  selected: K;
  /** For button tabs; link tabs navigate. */
  onSelect?: (key: K) => void;
  /** The id of the tab panel the selected tab controls. */
  panelId?: string;
  /** The phone strip. */
  strip?: boolean;
  className?: string;
}) {
  const refs = useRef<(HTMLElement | null)[]>([]);

  function keys(event: KeyboardEvent<HTMLElement>, at: number) {
    const enabled = tabs.map((t, i) => (t.disabled ? -1 : i)).filter((i) => i >= 0);
    const pos = enabled.indexOf(at);
    const n = enabled.length;
    const to =
      n === 0
        ? undefined
        : event.key === 'ArrowRight'
          ? enabled[(pos + 1) % n]
          : event.key === 'ArrowLeft'
            ? enabled[(pos - 1 + n) % n]
            : event.key === 'Home'
              ? enabled[0]
              : event.key === 'End'
                ? enabled[n - 1]
                : undefined;
    if (to !== undefined) {
      event.preventDefault();
      refs.current[to]?.focus();
    } else if (event.key === ' ' && tabs[at].href && !tabs[at].disabled) {
      event.preventDefault();
      event.currentTarget.click();
    }
  }

  return (
    <div role="tablist" aria-label={label} className={cx('psl-tabs', strip && 'psl-tabs--strip', className)}>
      {tabs.map((tab, at) => {
        const isSelected = tab.key === selected;
        const common = {
          role: 'tab',
          className: 'psl-tab',
          'aria-selected': isSelected,
          'aria-controls': isSelected ? panelId : undefined,
          'aria-disabled': tab.disabled || undefined,
          tabIndex: isSelected ? 0 : -1,
          onKeyDown: (event: KeyboardEvent<HTMLElement>) => keys(event, at),
        } as const;
        const content = (
          <>
            {tab.label}
            {tab.count !== undefined && (
              <>
                {' '}
                <CountBadge count={tab.count} />
              </>
            )}
          </>
        );
        return tab.href ? (
          <NextLink
            key={tab.key}
            {...common}
            ref={(el) => {
              refs.current[at] = el;
            }}
            href={tab.href}
            onClick={(event) => {
              if (tab.disabled) event.preventDefault();
            }}
          >
            {content}
          </NextLink>
        ) : (
          <button
            key={tab.key}
            {...common}
            ref={(el) => {
              refs.current[at] = el;
            }}
            type="button"
            className="psl-tab cmp-tabbutton"
            onClick={() => {
              if (!tab.disabled) onSelect?.(tab.key);
            }}
          >
            {content}
          </button>
        );
      })}
    </div>
  );
}
