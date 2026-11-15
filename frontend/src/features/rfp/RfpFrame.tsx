// The RFP frame on the SCR-16 desktop boards: reference, title, status tag, PM and the five tabs, each drawn only
// from `rfp` on the work item; a missing field leaves its element out. Phones draw no frame (the page sets the
// bar's "← RFP" instead). Tabs are links in a nav, not a tablist: the screens behind Requirements, Pricing and
// Submission are not built, so those are plain text, never a dead link or a disabled button.
import Link from 'next/link';

import type { WorkItem } from '@/api/types';
import { CountBadge, PageTitle, Tag } from '@/components';

import type { Rfp, RfpTab } from './contract';
import { frameHeading, statusTone } from './labels';

const work = (id: string) => `/work/${encodeURIComponent(id)}`;

function Count({ tab }: { tab: RfpTab }) {
  if (tab.count === undefined) return null;
  return tab.of === undefined ? <CountBadge count={tab.count} /> : <span className="psl-badge">{`${tab.count}/${tab.of}`}</span>;
}

function Tab({ id, tab, outcome }: { id: string; tab: RfpTab; outcome: boolean }) {
  const target = tab.work_id ?? id;
  const href = tab.key === 'team_input' ? work(target) : tab.key === 'outcome' && outcome ? `${work(target)}/outcome` : undefined;
  if (tab.current) {
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
export function RfpFrame({ id, item, rfp, fallback }: { id: string; item: Pick<WorkItem, 'line' | 'rfp_outcome'>; rfp: Rfp; fallback: string }) {
  const heading = frameHeading(rfp) ?? fallback;
  return (
    <header className="rfp-frame">
      <p className="rfp-eyebrow">{[item.line, rfp.reference].filter(Boolean).join(' · ')}</p>
      <div className="rfp-titlerow">
        <PageTitle className="rfp-title">{heading}</PageTitle>
        <span className="rfp-tags">
          <Tag tone={statusTone(rfp.status.kind)}>{rfp.status.label}</Tag>
          {rfp.pm && (
            <Tag tone="neutral" className="rfp-pm">
              PM {rfp.pm.name}
            </Tag>
          )}
        </span>
      </div>
      {rfp.tabs && rfp.tabs.length > 0 && (
        <nav aria-label="RFP" className="psl-tabs rfp-tabs">
          {rfp.tabs.map((tab) => (
            <Tab key={tab.key} id={id} tab={tab} outcome={Boolean(item.rfp_outcome)} />
          ))}
        </nav>
      )}
    </header>
  );
}
