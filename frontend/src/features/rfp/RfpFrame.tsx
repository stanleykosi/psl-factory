// The RFP frame on the SCR-16 desktop boards: reference, title, status tag, PM and the five tabs, each drawn only
// from `rfp` on the work item; a missing field leaves its element out. Phones draw no frame (the page sets the
// bar's "← RFP" instead). Tabs are links in a nav, not a tablist: the screens behind Requirements, Pricing and
// Submission are plain text unless the response says where they are (F-37: the Requirements page; F-38: a Submission tab
// that carries `work_id`), never a dead link or a disabled button.
import Link from 'next/link';
import { useEffect, type ReactNode } from 'react';

import type { WorkItem } from '@/api/types';

import type { Rfp, RfpTab } from './contract';
import { rememberRfpFrame } from './frameMemory';
import { frameHeading, statusTone } from './labels';
import './rfp.css';

const work = (id: string) => `/work/${encodeURIComponent(id)}`;

function Count({ tab }: { tab: RfpTab }) {
  if (tab.count === undefined) return null;
  return <span className="psl-badge">{tab.of === undefined ? tab.count : `${tab.count}/${tab.of}`}</span>;
}

/** F-37: the page that is the Requirements workspace says so; a team-input task this person can act on is the page's own Team input. */
const REQUIREMENTS_LINE = 'rfp_response';

function Tab({ id, tab, outcome, requirements, current, teamTask }: { id: string; tab: RfpTab; outcome: boolean; requirements: boolean; current?: RfpTab['key']; teamTask?: string }) {
  const target = tab.work_id ?? id;
  const isCurrent = current ? tab.key === current : tab.current;
  const href =
    tab.key === 'team_input'
      ? teamTask
        ? `${work(id)}/respond?task=${encodeURIComponent(teamTask)}`
        : current === 'requirements'
          ? undefined
          : work(target)
      : tab.key === 'requirements' && requirements
        ? work(target)
        : tab.key === 'outcome' && outcome
          ? `${work(target)}/outcome`
          : tab.key === 'submission' && tab.work_id
            ? work(tab.work_id)
            : undefined;
  if (isCurrent) {
    return (
      <span className="psl-tab rfp-tab is-current" aria-current="page">
        {tab.label}
        <Count tab={tab} />
      </span>
    );
  }
  if (!href) {
    return (
      <span className="psl-tab rfp-tab is-plain">
        {tab.label}
        <Count tab={tab} />
      </span>
    );
  }
  return (
    <Link className="psl-tab rfp-tab" href={href}>
      {tab.label}
      <Count tab={tab} />
    </Link>
  );
}

/**
 * `item.line` leads the eyebrow as the boards draw it ("PRE-SALE / RFP · TL-RFP-2026-014"). `fallback` is the
 * page's own title, the h1 when `rfp` has neither client nor title.
 */
export function RfpFrame({ id, item, rfp, fallback, current, end }: { id: string; item: Pick<WorkItem, 'line' | 'rfp_outcome'> & Partial<Pick<WorkItem, 'workspace' | 'tasks'>>; rfp: Rfp; fallback: string; current?: RfpTab['key']; end?: ReactNode }) {
  const requirements = item.workspace?.line_key === REQUIREMENTS_LINE;
  // the Requirements page links its Team input tab to the form of a team-input task the response says this person can act on
  const teamTask = current === 'requirements' ? item.tasks?.find((t) => t.you_can_act && (t.response as { variant?: string } | undefined)?.variant === 'team_input')?.id : undefined;
  const heading = frameHeading(rfp) ?? fallback;
  const { line, rfp_outcome: outcome } = item;
  useEffect(() => rememberRfpFrame({ rfp, item: { line, rfp_outcome: outcome }, fallback }), [rfp, line, outcome, fallback]);
  return (
    <header className="rfp-frame">
      <p className="rfp-eyebrow">
        {[item.line, rfp.reference].filter(Boolean).join(' · ')}
        {end}
      </p>
      <div className="rfp-titlerow">
        <h1 className="shell-title rfp-title">{heading}</h1>
        <span className="rfp-tags">
          <span className={`psl-tag ${statusTone(rfp.status.kind)}`}>{rfp.status.label}</span>
          {rfp.pm && <span className="psl-tag psl-tag--neutral rfp-pm">PM {rfp.pm.name}</span>}
        </span>
      </div>
      {rfp.tabs && rfp.tabs.length > 0 && (
        <nav aria-label="RFP" className="psl-tabs rfp-tabs">
          {rfp.tabs.map((tab) => (
            <Tab key={tab.key} id={id} tab={tab} outcome={Boolean(item.rfp_outcome)} requirements={requirements} current={current} teamTask={teamTask} />
          ))}
        </nav>
      )}
    </header>
  );
}
