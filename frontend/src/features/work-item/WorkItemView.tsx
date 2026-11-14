'use client';

// SCR-02 work item: header and tabs shared by Overview (/work/[id]) and History (/work/[id]/history).
// Data comes only from E-WORK-ITEM and E-WORK-HISTORY; the backend decides access (INV-ACCESS).
import Link from 'next/link';
import type { ReactNode } from 'react';

import { usePhoneBack } from '@/shell/AppShell';
import { LoadingState, SignedOutState } from '@/shell/FrameStates';
import { WarningIcon } from '@/shell/icons';
import { SampleLabel } from '@/shell/SampleLabel';

import { formatWat, startedLine, STATE_TAGS, type WorkItem } from './labels';
import { presentationOf } from './presentation';
import { useIsPhone } from './usePhone';
import { useWorkItem } from './useWorkItem';
import { WorkItemHistory } from './WorkItemHistory';
import { boardLayout, WorkItemOverview } from './WorkItemOverview';
import { NoAccessState, WorkErrorCard } from './WorkItemStates';

import './work-item.css';

export type WorkItemTab = 'overview' | 'history';

type HeaderProps = { item: WorkItem; tab: WorkItemTab; phone: boolean; tabs: ReactNode };

/**
 * Desktop: the breadcrumb (with "revision N" at its end when the item does not say who started it), then the title
 * line with the state tag and the Overview / History tabs; history keeps its tabs under the title, as drawn.
 * Phones: the title, then the tag with the reference and revision (the boards put the reference in the bar, which
 * the frame owns); the tabs close the page. History on phones reads "History · <ref>" under a HISTORY eyebrow.
 */
function WorkItemHeader({ item, tab, phone, tabs }: HeaderProps) {
  const tag = STATE_TAGS[item.state];
  // The state boards and history set the tag at the far end of the title line; the default board beside it.
  const end = tab === 'history' || boardLayout(item)?.tag === 'end';
  const history = tab === 'history';
  const started = item.started_by !== undefined;
  const sub = (
    <div className="work-sub">
      {/* phones: the reference and revision only (the phone boards draw no started line) */}
      {phone ? (
        <span>
          <span className="psl-mono">{item.reference}</span> · revision {item.revision}
        </span>
      ) : (
        <span>{startedLine(item)}</span>
      )}
      {/* INV-SAMPLE: the record says it is sample data, whatever the build's API mode (tag shown only when switched on). */}
      <SampleLabel show={item.sample} />
    </div>
  );
  const tagEl = <span className={`psl-tag psl-tag--${tag.tone} work-state`}>{tag.text}</span>;
  return (
    <>
      <header className={`work-header${end ? ' work-header--end' : ''}${history ? ' work-header--history' : ''}`}>
        {!phone && (
          <div className="work-crumbrow">
            <nav aria-label="Breadcrumb">
              <p className="psl-crumb">
                <Link href="/my-work">My work</Link> / {item.line} / <span className="psl-mono">{item.reference}</span>
              </p>
            </nav>
            {!started && sub}
          </div>
        )}
        {phone && history && <p className="work-eyebrow psl-mono">HISTORY</p>}
        <div className="work-titleline">
          <h1 className="shell-title">{phone && history ? `History · ${item.reference}` : item.title}</h1>
          {!phone && tagEl}
          {!phone && !history && tabs}
        </div>
        {phone && (
          <div className="work-tagline">
            {tagEl}
            {sub}
          </div>
        )}
        {!phone && started && sub}
      </header>
      {!phone && history && tabs}
    </>
  );
}

function WorkItemTabs({ base, tab, count }: { base: string; tab: WorkItemTab; count?: number }) {
  const tabs = [
    { key: 'overview', label: 'Overview', href: base },
    { key: 'history', label: 'History', href: `${base}/history` },
  ] as const;
  return (
    <nav aria-label="Work item" className="psl-tabs work-tabs">
      {tabs.map((t) => (
        <Link key={t.key} className="psl-tab" href={t.href} aria-current={t.key === tab ? 'page' : undefined}>
          {t.label}
          {t.key === 'history' && count !== undefined && (
            <>
              {' '}
              <span className="psl-badge">{count}</span>
            </>
          )}
        </Link>
      ))}
    </nav>
  );
}

export function WorkItemView({ id, tab }: { id: string; tab: WorkItemTab }) {
  const { state, retry } = useWorkItem(id);
  const phone = useIsPhone();
  const base = `/work/${encodeURIComponent(id)}`;
  const item = state.status === 'ready' ? state.item : undefined;
  const view = item && presentationOf(item);
  // The phone bar's way back: the queue from the overview (and while loading or without access); the item from history.
  usePhoneBack(tab === 'history' ? { label: view?.back_label ?? 'Work item', href: base } : { label: 'Queue', href: '/my-work' });

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

  const { loadedAt, refreshFailed } = state;
  const tabs = <WorkItemTabs base={base} tab={tab} count={view?.history_counts?.all} />;
  return (
    <>
      <WorkItemHeader item={state.item} tab={tab} phone={phone} tabs={tabs} />
      {refreshFailed && (
        <div className="psl-callout psl-callout--warning">
          <WarningIcon />
          <span>
            We couldn&rsquo;t refresh this item. Showing what we had at {formatWat(loadedAt)}.
          </span>
        </div>
      )}
      {tab === 'overview' ? (
        <WorkItemOverview id={id} item={state.item} />
      ) : (
        <WorkItemHistory id={id} revision={state.item.revision} counts={view?.history_counts} phone={phone} />
      )}
      {phone && tabs}
    </>
  );
}
