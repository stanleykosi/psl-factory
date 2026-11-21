'use client';

// SCR-02 work item: header and tabs shared by Overview (/work/[id]) and History (/work/[id]/history).
// Data comes only from E-WORK-ITEM and E-WORK-HISTORY; the backend decides access (INV-ACCESS).
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { createContext, useContext, type ReactNode } from 'react';

import { Breadcrumb, Callout, formatDayTime, Tabs, Tag, useIsPhone } from '@/components';
import { PROJECT_TABS } from '@/features/projects/model';
import { usePhoneBack } from '@/shell/AppShell';
import { LoadingState, SignedOutState } from '@/shell/FrameStates';
import { SampleLabel } from '@/shell/SampleLabel';
import { useWorkspacePage, type WorkspacePage } from '@/features/workspace/usePageReload';

import { RfpFrame } from '@/features/rfp/RfpFrame';
import { rememberedRfpFrame } from '@/features/rfp/frameMemory';
import { statusTone } from '@/features/rfp/labels';
import { SEVERITY_WORDS, tagTone } from '@/features/workspace/labels';
import { screenHeading } from '@/features/workspace/Workspace';

import { startedLine, STATE_TAGS, type WorkItem } from './labels';
import { presentationOf, viewFor } from './presentation';
import { useWorkItem } from './useWorkItem';
import { WorkItemHistory } from './WorkItemHistory';
import { boardLayout, WorkItemOverview } from './WorkItemOverview';
import { NoAccessState, WorkErrorCard } from './WorkItemStates';

import './work-item.css';

export type WorkItemTab = 'overview' | 'history';

type HeaderProps = { item: WorkItem; phone: boolean; tabs: ReactNode };

/**
 * Desktop: the breadcrumb or, on the state boards, the reference and client line; then the title line with the
 * state tag; the Overview / History tabs close the crumb line; then the started line. Without a started line the revision stays in the page for screen readers only.
 * Phones: the title, then the tag with the tabs at the end of its line; the reference sits at the end of the frame's bar, as the boards draw it.
 * History draws this same header on every width, so switching tabs does not move it.
 */
function WorkItemHeader({ item, phone, tabs }: HeaderProps) {
  const tag = STATE_TAGS[item.state];
  const base = presentationOf(item);
  const view = viewFor(base, phone);
  // The state boards set the tag at the far end of the title line; the default board beside it. History draws the same header.
  const end = boardLayout(item)?.tag === 'end';
  const started = item.started_by !== undefined;
  const boardTitle = phone ? view?.phone?.title : undefined;
  const sub = (
    <div className={`work-sub${base && (!started || phone) ? ' cmp-sr' : ''}`}>
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
  const tagEl = (
    <Tag tone={tag.tone} className="work-state">
      {tag.text}
    </Tag>
  );
  const crumb = base?.eyebrow ? (
    <p className="psl-crumb work-eyebrowline">{base.eyebrow}</p>
  ) : (
    <Breadcrumb
      items={[{ label: 'My work', href: '/my-work' }, { label: item.line }]}
      current={<span className="psl-mono">{item.reference}</span>}
    />
  );
  return (
    <>
      <header className={`work-header${end ? ' work-header--end' : ''}`}>
        {!phone && (
          <div className="work-crumbrow">
            {crumb}
            <div className="work-crumbright">
              {!started && sub}
              {tabs}
            </div>
          </div>
        )}
        {phone && base && <span className="work-barref psl-mono">{item.reference}</span>}
        <div className="work-titleline">
          <h1 className="shell-title">
            {boardTitle ? (
              // the phone board's shorter title is what is drawn; the contract title stays as the heading's name
              <>
                <span aria-hidden="true">{boardTitle}</span>
                <span className="cmp-sr">{item.title}</span>
              </>
            ) : (
              item.title
            )}
          </h1>
          {!phone && tagEl}
        </div>
        {phone && (
          <div className="work-tagline">
            {tagEl}
            {sub}
            {tabs}
          </div>
        )}
        {!phone && started && sub}
      </header>
    </>
  );
}

/**
 * A work item with a line workspace is laid out as the LINE boards draw it (D-73): the crumb line from the workspace
 * context, the title with the workspace status at the far end of its line, the subtitle as the one meta line, then the
 * workspace. The started line, the Overview / History tabs and the revision are not drawn; History stays one link in
 * the crumb line (desktop) or the meta line (phone), and the reference sits at the end of the phone bar and the status tag shares the meta line.
 */
/**
 * The project tab bar the line boards draw under the title (desktop), from the project the workspace names. Every tab
 * with a page is a link to it (F-30); none is marked current, since the response does not say which tab the item
 * belongs to and the frontend does not read that from the crumbs.
 */
function ProjectBar({ caseId }: { caseId: string }) {
  return (
    <nav aria-label="Project" className="psl-tabs work-projecttabs">
      {PROJECT_TABS.map((t) => (
        <Link key={t.key} className="psl-tab" href={`/projects/${encodeURIComponent(caseId)}${t.path}`}>
          {t.label}
        </Link>
      ))}
    </nav>
  );
}

/** F-37: the line key of the RFP requirements workspace; read only to draw the RFP frame and its status tag. */
const RFP_RESPONSE_LINE = 'rfp_response';
/** F-38: the line key of the RFP submission workspace; read only to draw the RFP frame, its status and the phone's way back. */
const RFP_SUBMISSION_LINE = 'rfp_submission';

function LineHeader({ item, phone, historyHref }: { item: WorkItem; phone: boolean; historyHref: string }) {
  const ws = item.workspace;
  const state = STATE_TAGS[item.state];
  const crumbs = ws?.context?.crumbs ?? [];
  const status = ws?.status;
  const history = (
    <nav aria-label="Work item" className="work-linehistory">
      <Link href={historyHref}>History</Link>
    </nav>
  );
  // F-30: a severity the workspace's facts carry is drawn beside the status, as the issue boards do
  const severity = ws?.sections.flatMap((section) => (section.kind === 'facts' && !section.restricted ? section.items : [])).find((i) => i.severity !== undefined)?.severity;
  // F-37: an RFP's requirements page reads the RFP's own status (the frame's tag), as the RFP pages do
  const tag = ws?.line_key === RFP_SUBMISSION_LINE ? (
    // F-38: the submission boards draw only the status the workspace returns; no state tag stands in for a missing one
    status ? (
      <Tag tone={tagTone(status.tone)} className="work-state">
        {status.label}
      </Tag>
    ) : null
  ) : item.rfp && ws?.line_key === RFP_RESPONSE_LINE ? (
    <span className={`psl-tag ${statusTone(item.rfp.status.kind)} work-state`}>{item.rfp.status.label}</span>
  ) : status ? (
    <Tag tone={tagTone(status.tone)} className="work-state">
      {status.label}
    </Tag>
  ) : (
    <Tag tone={state.tone} className="work-state">
      {state.text}
    </Tag>
  );
  return (
    <header className="work-header work-header--end work-header--line">
      {/* F-38: the submission boards put the state in the phone bar (the verified status, or the version label), not the reference */}
      {phone && <span className="work-barref work-barref--line psl-mono">{ws?.line_key === RFP_SUBMISSION_LINE ? (status?.tone === 'verified' ? status.label : ws.version?.label) ?? item.reference : item.reference}</span>}
      {!phone && (
        <div className="work-crumbrow">
          {crumbs.length > 0 ? (
            <nav aria-label="Where this sits">
              <ol className="psl-crumb ws-crumbs">
                {crumbs.map((c, i) => (
                  <li key={`${c.value}-${i}`} aria-current={i === crumbs.length - 1 ? 'location' : undefined}>
                    {c.label}
                  </li>
                ))}
              </ol>
            </nav>
          ) : (
            <Breadcrumb items={[{ label: 'My work', href: '/my-work' }, { label: item.line }]} current={<span className="psl-mono">{item.reference}</span>} />
          )}
          {history}
        </div>
      )}
      <div className="work-titleline">
        <h1 className="shell-title">{phone && ws ? screenHeading(ws) ?? item.title : item.title}</h1>
        {!phone && (
          <span className="work-lineend">
            {/* INV-SAMPLE: the record says it is sample data, whatever the build's API mode */}
            <SampleLabel show={item.sample} />
            {severity && <Tag tone="neutral">{SEVERITY_WORDS[severity]}</Tag>}
            {tag}
          </span>
        )}
      </div>
      {!phone && ws?.context?.project && <ProjectBar caseId={ws.context.project.case_id} />}
      {(phone || ws?.subtitle) && (
        <div className="work-linemeta">
          {ws?.subtitle && <p className="work-sub">{ws.subtitle}</p>}
          {phone && (
            <>
              <SampleLabel show={item.sample} />
              {/* F-38: the RFP's own status (its deadline) is drawn under the title on a phone, where the frame is not */}
              {ws?.line_key === RFP_SUBMISSION_LINE && item.rfp?.status.label && <span className="psl-mono">{item.rfp.status.label}</span>}
              {ws?.line_key === RFP_SUBMISSION_LINE && status?.tone === 'verified' ? null : tag}
              {history}
            </>
          )}
        </div>
      )}
      <div className="cmp-sr">
        <span>{startedLine(item)}</span>
      </div>
    </header>
  );
}

function WorkItemTabs({ base, tab, count }: { base: string; tab: WorkItemTab; count?: number }) {
  return (
    <Tabs
      label="Work item"
      className="work-tabs"
      selected={tab}
      tabs={[
        { key: 'overview', label: 'Overview', href: base },
        { key: 'history', label: 'History', href: `${base}/history`, count },
      ]}
    />
  );
}

type WorkItemContextValue = { id: string; item: WorkItem; workspace: WorkspacePage; counts?: Parameters<typeof WorkItemHistory>[0]['counts'] };
const WorkItemContext = createContext<WorkItemContextValue | null>(null);
function useWorkItemContext() {
  const ctx = useContext(WorkItemContext);
  if (!ctx) throw new Error('A work item tab needs the work item frame');
  return ctx;
}

/** The Overview tab's content, drawn under the frame's header. */
export function WorkItemOverviewPane() {
  const { id, item, workspace } = useWorkItemContext();
  return <WorkItemOverview id={id} item={item} workspace={workspace} />;
}

/** The History tab's content; it reads its own list, so only this area shows a skeleton while that loads. */
export function WorkItemHistoryPane() {
  const { id, item, counts } = useWorkItemContext();
  const phone = useIsPhone();
  return <WorkItemHistory id={id} revision={item.revision} counts={counts} phone={phone} />;
}

/**
 * The work item's frame: the header (with the tabs) and the refresh notice, around the tab's content. It is the layout
 * of Overview and History, so changing tab keeps it and reads the item once. An RFP item that follows another item of
 * the same RFP keeps that RFP's frame on screen while it loads (the item's own read still decides what it shows).
 */
export function WorkItemFrame({ id, tab, children }: { id: string; tab: WorkItemTab; children: ReactNode }) {
  const { state, retry } = useWorkItem(id);
  // F-17: the line workspace's quiet re-read after a step; the newer of the two reads is drawn.
  const workspace = useWorkspacePage(id);
  const phone = useIsPhone();
  const base = `/work/${encodeURIComponent(id)}`;
  const item = state.status === 'ready' ? state.item : undefined;
  const view = item && presentationOf(item);
  // The phone bar's way back: the queue from the overview (and while loading or without access); the item from history.
  // F-30: an issue's work item goes back to its project (D-111 item 9); every other work item keeps the queue.
  // F-31: the planning item does the same (D-113 item 9). F-39: so does the escalation.
  const projectId = item?.workspace?.line_key === 'issue_followup' || item?.workspace?.line_key === 'planning' || item?.workspace?.line_key === 'escalation' ? item.workspace.context?.project?.case_id : undefined;
  // F-38: the submission item goes back to the RFP, its first other tab that has a page of its own
  const rfpBack = item?.workspace?.line_key === RFP_SUBMISSION_LINE ? item.rfp?.tabs?.find((t) => t.work_id && !t.current) : undefined;
  // F-40: the handover goes back to the Delivery tab it was opened from (UX-1-1)
  const deliveryId = item?.workspace?.line_key === 'delivery_handover' ? item.workspace.context?.project?.case_id : undefined;
  usePhoneBack(tab === 'history' ? { label: view?.back_label ?? 'Work item', href: base } : deliveryId ? { label: 'Delivery', href: `/projects/${encodeURIComponent(deliveryId)}/delivery` } : projectId ? { label: 'Project', href: `/projects/${encodeURIComponent(projectId)}` } : rfpBack?.work_id ? { label: 'RFP', href: `/work/${encodeURIComponent(rfpBack.work_id)}` } : { label: 'Queue', href: '/my-work' });

  if (state.status === 'loading') {
    const kept = !phone && tab === 'overview' ? rememberedRfpFrame(id) : undefined;
    if (!kept) return <LoadingState />;
    return (
      <>
        <RfpFrame id={id} item={kept.item} rfp={kept.rfp} fallback={kept.fallback} current={kept.current} end={
            <Link className="psl-link rfp-history" href={`${base}/history`}>
              History
            </Link>
          } />
        <LoadingState />
      </>
    );
  }
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
  // The line boards draw neither the tabs nor the started line; the history page keeps the item header.
  const line = tab === 'overview' && shown.workspace !== undefined;
  const tabs = <WorkItemTabs base={base} tab={tab} count={view?.history_counts?.all} />;
  return (
    <>
      {line && !phone && shown.rfp && (shown.workspace?.line_key === RFP_RESPONSE_LINE || shown.workspace?.line_key === RFP_SUBMISSION_LINE) ? (
        <RfpFrame
          id={id}
          item={shown}
          rfp={shown.rfp}
          fallback={shown.title}
          current={shown.workspace?.line_key === RFP_SUBMISSION_LINE ? 'submission' : 'requirements'}
          end={
            <Link className="psl-link rfp-history" href={`${base}/history`}>
              History
            </Link>
          }
        />
      ) : line ? (
        <LineHeader item={shown} phone={phone} historyHref={`${base}/history`} />
      ) : (
        <WorkItemHeader item={shown} phone={phone} tabs={tabs} />
      )}
      {refreshFailed && (
        <Callout kind="warning">We couldn&rsquo;t refresh this item. Showing what we had at {formatDayTime(loadedAt)}.</Callout>
      )}
      <WorkItemContext.Provider value={{ id, item: shown, workspace: workspace.page, counts: view?.history_counts }}>{children}</WorkItemContext.Provider>
    </>
  );
}

/** The tab is the path under /work/<id>/: History, else the Overview. */
export function WorkItemLayoutFrame({ id, children }: { id: string; children: ReactNode }) {
  const tab = usePathname().split('/')[3] === 'history' ? 'history' : 'overview';
  return (
    <WorkItemFrame id={id} tab={tab}>
      {children}
    </WorkItemFrame>
  );
}

/** One work item tab as a single page: the frame and its content (the route files split them across layout and page). */
export function WorkItemView({ id, tab }: { id: string; tab: WorkItemTab }) {
  return <WorkItemFrame id={id} tab={tab}>{tab === 'overview' ? <WorkItemOverviewPane /> : <WorkItemHistoryPane />}</WorkItemFrame>;
}
