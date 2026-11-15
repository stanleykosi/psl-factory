'use client';

// SCR-02 work item: header and tabs shared by Overview (/work/[id]) and History (/work/[id]/history).
// Data comes only from E-WORK-ITEM and E-WORK-HISTORY; the backend decides access (INV-ACCESS).
import Link from 'next/link';
import type { ReactNode } from 'react';

import { usePhoneBack } from '@/shell/AppShell';
import { LoadingState, SignedOutState } from '@/shell/FrameStates';
import { WarningIcon } from '@/shell/icons';
import { SampleLabel } from '@/shell/SampleLabel';
import { useWorkspacePage } from '@/features/workspace/usePageReload';

import { formatWat, startedLine, STATE_TAGS, type WorkItem } from './labels';
import { presentationOf, viewFor } from './presentation';
import { useIsPhone } from './usePhone';
import { useWorkItem } from './useWorkItem';
import { WorkItemHistory } from './WorkItemHistory';
import { boardLayout, WorkItemOverview } from './WorkItemOverview';
import { NoAccessState, WorkErrorCard } from './WorkItemStates';

import './work-item.css';

export type WorkItemTab = 'overview' | 'history';

type HeaderProps = { item: WorkItem; tab: WorkItemTab; phone: boolean; tabs: ReactNode };

/**
 * Desktop: the breadcrumb or, on the state boards, the reference and client line; then the title line with the
 * state tag; the Overview / History tabs close the crumb line (after the header on history); then the started line. Without a started line the revision stays in the page for screen readers only.
 * Phones: the title, then the tag with the tabs at the end of its line (beside the title on history); the reference sits at the end of the frame's bar, as the boards draw it.
 * History on phones reads "History · <ref>" with HISTORY in the bar.
 */
function WorkItemHeader({ item, tab, phone, tabs }: HeaderProps) {
  const tag = STATE_TAGS[item.state];
  const base = presentationOf(item);
  const view = viewFor(base, phone);
  // The state boards and history set the tag at the far end of the title line; the default board beside it.
  const end = tab === 'history' || boardLayout(item)?.tag === 'end';
  const history = tab === 'history';
  const started = item.started_by !== undefined;
  const boardTitle = phone ? view?.phone?.title : undefined;
  const sub = (
    <div className={`work-sub${base && (!started || phone) ? ' work-sr' : ''}`}>
      {/* phones: the reference and the started line (the bar draws the reference on the boards) */}
      {phone ? (
        <span>
          <span className="psl-mono">{item.reference}</span> · {startedLine(item)}
        </span>
      ) : (
        <span>{startedLine(item)}</span>
      )}
      {/* INV-SAMPLE: the record says it is sample data, whatever the build's API mode (tag shown only when switched on). */}
      <SampleLabel show={item.sample} />
    </div>
  );
  const tagEl = <span className={`psl-tag psl-tag--${tag.tone} work-state`}>{tag.text}</span>;
  const crumb = base?.eyebrow ? (
    <p className="psl-crumb work-eyebrowline">{base.eyebrow}</p>
  ) : (
    <nav aria-label="Breadcrumb">
      <p className="psl-crumb">
        <Link href="/my-work">My work</Link> / {history && base?.back_label ? `${base.back_label} ·` : `${item.line} /`}{' '}
        <span className="psl-mono">{item.reference}</span>
      </p>
    </nav>
  );
  return (
    <>
      <header className={`work-header${end ? ' work-header--end' : ''}${history ? ' work-header--history' : ''}`}>
        {!phone && (
          <div className="work-crumbrow">
            {crumb}
            <div className="work-crumbright">
              {!started && sub}
              {!history && tabs}
            </div>
          </div>
        )}
        {phone && base && <span className="work-barref psl-mono">{history ? 'HISTORY' : item.reference}</span>}
        {phone && !base && history && <p className="work-eyebrow psl-mono">HISTORY</p>}
        <div className="work-titleline">
          <h1 className="shell-title">
            {phone && history ? (
              `History · ${item.reference}`
            ) : boardTitle ? (
              // the phone board's shorter title is what is drawn; the contract title stays as the heading's name
              <>
                <span aria-hidden="true">{boardTitle}</span>
                <span className="work-sr">{item.title}</span>
              </>
            ) : (
              item.title
            )}
          </h1>
          {!phone && tagEl}
          {phone && history && tabs}
        </div>
        {phone && !(base && history) && (
          <div className="work-tagline">
            {tagEl}
            {sub}
            {!history && tabs}
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
  // F-17: the line workspace's quiet re-read after a step; the newer of the two reads is drawn.
  const workspace = useWorkspacePage(id);
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

  if (workspace.lost) return workspace.lost.kind === 'unauthenticated' ? <SignedOutState pathname={base} /> : <NoAccessState />;
  const fresh = workspace.fresh && workspace.fresh.at > state.loadedAt ? workspace.fresh : null;
  const shown = fresh?.item ?? state.item;
  const loadedAt = fresh?.at ?? state.loadedAt;
  const refreshFailed = state.refreshFailed || workspace.page.refreshFailed;
  // D-45: the Overview / History strip is on every work item page, boards included, so History is reachable.
  const tabs = <WorkItemTabs base={base} tab={tab} count={view?.history_counts?.all} />;
  return (
    <>
      <WorkItemHeader item={shown} tab={tab} phone={phone} tabs={tabs} />
      {refreshFailed && (
        <div className="psl-callout psl-callout--warning">
          <WarningIcon />
          <span>
            We couldn&rsquo;t refresh this item. Showing what we had at {formatWat(loadedAt)}.
          </span>
        </div>
      )}
      {tab === 'overview' ? (
        <WorkItemOverview id={id} item={shown} workspace={workspace.page} />
      ) : (
        <WorkItemHistory id={id} revision={shown.revision} counts={view?.history_counts} phone={phone} />
      )}
    </>
  );
}
