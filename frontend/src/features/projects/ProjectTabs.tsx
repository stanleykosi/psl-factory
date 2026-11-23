'use client';

import { Tabs } from '@/components';

import { visibleTabs, type JourneyTabInfo, type ProjectTab } from './model';

export const PANEL_ID = 'project-tabpanel';

/** The project's tabs are links (each has its own address); Tabs gives them arrows, Home and End. Built from live `tabs[]`, with no counts. */
export function ProjectTabs({ base, current, tabs }: { base: string; current: ProjectTab; tabs?: JourneyTabInfo[] }) {
  if (!tabs) return null;
  return (
    <Tabs
      label="Project"
      className="projects__tabs"
      tabs={visibleTabs(tabs).map((t) => ({ key: t.key, label: t.label, href: `${base}${t.path}` }))}
      selected={current}
      panelId={PANEL_ID}
    />
  );
}
