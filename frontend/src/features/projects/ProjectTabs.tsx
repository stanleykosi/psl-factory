'use client';

import { Tabs } from '@/components';

import { countOf, PROJECT_TABS, type JourneyView, type ProjectTab } from './model';

export const PANEL_ID = 'project-tabpanel';

/** The project's tabs are links (each has its own address); Tabs gives them arrows, Home and End. */
export function ProjectTabs({ base, current, counts }: { base: string; current: ProjectTab; counts?: JourneyView['tab_counts'] }) {
  return (
    <Tabs
      label="Project"
      className="projects__tabs"
      tabs={PROJECT_TABS.map((t) => ({ key: t.key, label: t.label, href: `${base}${t.path}`, count: t.count ? countOf(counts?.[t.count]) : undefined }))}
      selected={current}
      panelId={PANEL_ID}
    />
  );
}
