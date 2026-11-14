'use client';

import Link from 'next/link';
import type { KeyboardEvent } from 'react';

import { countOf, PROJECT_TABS, type JourneyView, type ProjectTab } from './model';

export const tabId = (key: ProjectTab) => `project-tab-${key}`;
export const PANEL_ID = 'project-tabpanel';

/** Arrow keys, Home and End move focus between the tabs; Enter follows the focused tab's link. */
function onTabKey(event: KeyboardEvent<HTMLAnchorElement>, index: number) {
  const last = PROJECT_TABS.length - 1;
  const next = { ArrowRight: index === last ? 0 : index + 1, ArrowLeft: index === 0 ? last : index - 1, Home: 0, End: last }[event.key];
  if (next === undefined) return;
  event.preventDefault();
  document.getElementById(tabId(PROJECT_TABS[next].key))?.focus();
}

export function ProjectTabs({ base, current, counts }: { base: string; current: ProjectTab; counts?: JourneyView['tab_counts'] }) {
  return (
    <div role="tablist" aria-label="Project" className="psl-tabs projects__tabs">
      {PROJECT_TABS.map((t, i) => {
        const selected = t.key === current;
        const count = t.count ? countOf(counts?.[t.count]) : undefined;
        return (
          <Link
            key={t.key}
            id={tabId(t.key)}
            role="tab"
            className="psl-tab"
            href={`${base}${t.path}`}
            aria-selected={selected}
            aria-controls={selected ? PANEL_ID : undefined}
            tabIndex={selected ? 0 : -1}
            onKeyDown={(e) => onTabKey(e, i)}
          >
            {t.label}
            {count !== undefined && <span className="psl-badge">{count}</span>}
          </Link>
        );
      })}
    </div>
  );
}
