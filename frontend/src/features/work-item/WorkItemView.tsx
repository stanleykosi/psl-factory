'use client';

// SCR-02 work item: header and tabs shared by Overview (/work/[id]) and History (/work/[id]/history).
// Data comes only from E-WORK-ITEM and E-WORK-HISTORY; the backend decides access (INV-ACCESS).
import Link from 'next/link';

import { LoadingState, SignedOutState } from '@/shell/FrameStates';
import { WarningIcon } from '@/shell/icons';
import { SampleLabel } from '@/shell/SampleLabel';

import { formatWat, STATE_TAGS, type WorkItem } from './labels';
import { useWorkItem } from './useWorkItem';
import { WorkItemHistory } from './WorkItemHistory';
import { WorkItemOverview } from './WorkItemOverview';
import { NoAccessState, WorkErrorCard } from './WorkItemStates';

import './work-item.css';

export type WorkItemTab = 'overview' | 'history';

function WorkItemHeader({ item }: { item: WorkItem }) {
  const tag = STATE_TAGS[item.state];
  return (
    <header className="work-header">
      <nav aria-label="Breadcrumb">
        <p className="psl-crumb">
          <Link href="/my-work">My work</Link> / {item.line} / <span className="psl-mono">{item.reference}</span>
        </p>
      </nav>
      <div className="work-titleline">
        <h1 className="shell-title">{item.title}</h1>
        <span className={`psl-tag psl-tag--${tag.tone} work-state`}>{tag.text}</span>
      </div>
      <p className="work-sub">
        <span>revision {item.revision}</span>
        {/* INV-SAMPLE: the record says it is sample data, whatever the build's API mode (tag shown only when switched on). */}
        <SampleLabel show={item.sample} />
      </p>
    </header>
  );
}

function WorkItemTabs({ base, tab }: { base: string; tab: WorkItemTab }) {
  const tabs = [
    { key: 'overview', label: 'Overview', href: base },
    { key: 'history', label: 'History', href: `${base}/history` },
  ] as const;
  return (
    <nav aria-label="Work item" className="psl-tabs work-tabs">
      {tabs.map((t) => (
        <Link key={t.key} className="psl-tab" href={t.href} aria-current={t.key === tab ? 'page' : undefined}>
          {t.label}
        </Link>
      ))}
    </nav>
  );
}

export function WorkItemView({ id, tab }: { id: string; tab: WorkItemTab }) {
  const { state, retry } = useWorkItem(id);
  const base = `/work/${encodeURIComponent(id)}`;

  if (state.status === 'loading') return <LoadingState />;
  if (state.status === 'error') {
    const { error } = state;
    if (error.kind === 'unauthenticated') return <SignedOutState pathname={tab === 'history' ? `${base}/history` : base} />;
    if (error.kind === 'forbidden' || error.kind === 'not_found') return <NoAccessState />;
    return (
      <WorkErrorCard
        message="We couldn’t load this work item. Your work is safe; nothing was changed."
        error={error}
        onRetry={() => void retry()}
      />
    );
  }

  const { item, loadedAt, refreshFailed } = state;
  return (
    <>
      <WorkItemHeader item={item} />
      {refreshFailed && (
        <div className="psl-callout psl-callout--warning">
          <WarningIcon />
          <span>
            We couldn&rsquo;t refresh this item. Showing what we had at {formatWat(loadedAt)}.
          </span>
        </div>
      )}
      <WorkItemTabs base={base} tab={tab} />
      {tab === 'overview' ? <WorkItemOverview id={id} item={item} /> : <WorkItemHistory id={id} revision={item.revision} />}
    </>
  );
}
