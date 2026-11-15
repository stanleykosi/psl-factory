'use client';

// Tabs (design/system/project/components/Tabs): switch between sections of one thing (a project's Journey,
// Milestones, Documents…). Joined 44px boxes; the selected tab fills ink; counts are square badges and zero shows
// "0". Tabs are links (each section has its own address) or buttons. One tab stop: arrows move focus, Home and End
// go to the first and last, Enter or Space opens the focused tab. On a phone they are a strip that scrolls sideways.
import NextLink from 'next/link';
import { useRef, type KeyboardEvent } from 'react';

import { CountBadge } from './CountBadge';
import { cx } from './internal';

export type TabItem<K extends string> = { key: K; label: string; count?: number; href?: string };

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
    const last = tabs.length - 1;
    const to =
      event.key === 'ArrowRight' ? (at + 1) % tabs.length : event.key === 'ArrowLeft' ? (at - 1 + tabs.length) % tabs.length : event.key === 'Home' ? 0 : event.key === 'End' ? last : -1;
    if (to >= 0) {
      event.preventDefault();
      refs.current[to]?.focus();
    } else if (event.key === ' ' && tabs[at].href) {
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
          tabIndex: isSelected ? 0 : -1,
          onKeyDown: (event: KeyboardEvent<HTMLElement>) => keys(event, at),
        } as const;
        const content = (
          <>
            {tab.label}
            {tab.count !== undefined && <CountBadge count={tab.count} />}
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
            onClick={() => onSelect?.(tab.key)}
          >
            {content}
          </button>
        );
      })}
    </div>
  );
}
