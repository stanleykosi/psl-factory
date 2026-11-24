'use client';

// F-85 SCR-02 on the live API: /work/[id] and /work/[id]/history for an integer work id (GET /work/{id}, GET /work/{id}/history).
// F-91: the station track, six facts, agent card, reference and started line come from GET /work/{id}/tracking (item.tracking_url);
// history pages older events by the next_before cursor. Only what the API serves is drawn: no agent steps, no placeholder where a part is absent.
// Writes: the controls row (ItemControls, F-87) and a line's own `Actions` slot; both send through useWorkCommand. Access is the backend's answer (404 = missing or not yours).
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { Component, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';

import type { ApiError } from '@/api/errors';
import {
  AgentAvatar,
  agentKey,
  Breadcrumb,
  buttonClass,
  Button,
  Callout,
  EmptyState,
  FactsStrip,
  formatDayTime,
  PersonAvatar,
  Segmented,
  StationTrack,
  Tabs,
  Tag,
  useIsPhone,
} from '@/components';
import { adapterFor, type LineContext, type PanelRef } from '@/features/workspace/adapter';
import type { Section } from '@/features/workspace/labels';
import { SectionView } from '@/features/workspace/Sections';
import '@/features/workspace/lines';
import { usePhoneBack } from '@/shell/AppShell';
import { LoadingState, SignedOutState } from '@/shell/FrameStates';
import { SampleLabel } from '@/shell/SampleLabel';
import type { LiveTracking, LiveWorkItem } from '@/api/types';

import { ACTOR_TAGS, nextStepKind, STATE_TAGS } from '../labels';
import { NoAccessState, WorkErrorCard } from '../WorkItemStates';
import { ItemControls } from './ItemControls';
import { decisionHref, activityOf, factsOf, historyCaption, historyLine, HISTORY_FILTERS, lineName, safeHref, stationsOf, words } from './model';
import { useLiveHistory } from './useLiveHistory';
import { useLiveTracking } from './useLiveTracking';
import { useLiveWorkItem } from './useLiveWorkItem';

import '../work-item.css';

const UNAVAILABLE = 'This record is unavailable.';

/** The page's error words (spec): 404 and 403 say one thing; a 403 that is a stale session token is not "no access". */
function ErrorState({ error, pathname, onRetry, what }: { error: ApiError; pathname: string; onRetry: () => void; what: string }) {
  if (error.kind === 'unauthenticated') return <SignedOutState pathname={pathname} />;
  if (error.kind === 'not_found') {
    return (
      <section className="psl-panel work-noaccess" aria-labelledby="work-unavailable">
        <div className="psl-panel__body">
          <Tag tone="neutral" className="work-noaccess__tag">
            NO ACCESS
          </Tag>
          <h1 id="work-unavailable" className="shell-title">
            {UNAVAILABLE}
          </h1>
          <p>
            <Link className={buttonClass('dark', 'lg')} href="/my-work">
              Back to my queue
            </Link>
          </p>
        </div>
      </section>
    );
  }
  if (error.kind === 'forbidden') return <NoAccessState />;
  const message =
    error.kind === 'csrf'
      ? 'Refresh your session and try again.'
      : error.kind === 'rate_limited' || error.kind === 'read_limited' || error.status === 503
        ? 'Try again shortly.'
        : error.kind === 'network'
          ? error.message
          : `We couldn’t load ${what}. Your work is safe; nothing was changed.`;
  return <WorkErrorCard message={message} error={error} onRetry={onRetry} />;
}

function Tabs2({ base, tab }: { base: string; tab: 'overview' | 'history' }) {
  return (
    <Tabs
      label="Work item"
      className="work-tabs"
      selected={tab}
      tabs={[
        { key: 'overview', label: 'Overview', href: base },
        { key: 'history', label: 'History', href: `${base}/history` },
      ]}
    />
  );
}

function Header({ item, tracking, base, tab }: { item: LiveWorkItem; tracking: LiveTracking | null; base: string; tab: 'overview' | 'history' }) {
  const phone = useIsPhone();
  const tag = STATE_TAGS[item.state];
  const tagEl = (
    <Tag tone={tag.tone} className="work-state">
      {tag.text}
    </Tag>
  );
  const sub = (
    <div className="work-sub">
      <span>{item.status_label}</span>
      {item.owner !== null && <span>With {item.owner}</span>}
      {tracking && (
        <span>
          Started by {tracking.started_by} · <time dateTime={tracking.started_at}>{formatDayTime(tracking.started_at)}</time>
        </span>
      )}
      <span>
        Updated <time dateTime={item.updated_at}>{formatDayTime(item.updated_at)}</time>
      </span>
      {/* INV-SAMPLE: the record says it is sample data (tag shown only when switched on) */}
      <SampleLabel show={item.sample} />
    </div>
  );
  const tabs = <Tabs2 base={base} tab={tab} />;
  return (
    <header className="work-header work-header--end">
      {!phone && (
        <div className="work-crumbrow">
          <Breadcrumb items={[{ label: 'My work', href: '/my-work' }, { label: lineName(item.line) }]} current={<span>Work {item.id}{item.reference ? ` · ${item.reference}` : ''}</span>} />
          <div className="work-crumbright">{tabs}</div>
        </div>
      )}
      <div className="work-titleline">
        <h1 className="shell-title">{item.title}</h1>
        {!phone && tagEl}
      </div>
      {phone && (
        <div className="work-tagline">
          {tagEl}
          {tabs}
        </div>
      )}
      {sub}
    </header>
  );
}

/** One panel through its adapter; a key with no adapter has nothing to draw and is left out.
 *  A failed re-read keeps the last good readback on screen with a warning above it: the line's `Actions` stays mounted, so a
 *  command lock it holds (an uncertain result at this revision) survives the failed read and Try again. */
function PanelView({ panel, ctx, version, reloadItem, onAccessLost }: { panel: PanelRef; ctx: LineContext; version: string; reloadItem: () => Promise<LiveWorkItem | null>; onAccessLost: (error: ApiError) => void }) {
  const adapter = adapterFor(panel.key);
  const [ready, setReady] = useState<{ sections: Section[]; readback: unknown } | null>(null);
  const [failed, setFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const { workId, caseId, revision, caseRevision, state: itemState } = ctx;
  const commands = useMemo(() => (adapter && ready ? (adapter.commands?.(ready.readback, ctx) ?? []) : []), [adapter, ready, ctx]);

  useEffect(() => {
    if (!adapter) return;
    let active = true;
    adapter
      .read(panel, { workId, caseId, revision, caseRevision, state: itemState })
      .then((readback) => {
        if (!active) return;
        setReady({ sections: adapter.sections(readback, { workId, caseId, revision, caseRevision, state: itemState }), readback });
        setFailed(false);
      })
      .catch(() => {
        if (active) setFailed(true);
      });
    return () => {
      active = false;
    };
    // a new item revision (poll) or a Try again reads the panel again
  }, [adapter, panel, workId, caseId, revision, caseRevision, itemState, version, attempt]);

  if (!adapter) return null;
  const { Actions } = adapter;
  return (
    <>
      {failed && (
        <Callout kind="warning">
          We couldn’t load this part of the page.{' '}
          <Button
            kind="secondary"
            size="sm"
            onClick={() => {
              setFailed(false);
              setAttempt((n) => n + 1);
            }}
          >
            Try again
          </Button>
        </Callout>
      )}
      {ready?.sections.map((section) => (
        <SectionView key={section.key} section={section} level={2} />
      ))}
      {ready && Actions && (
        <PanelBoundary>
          <Actions
            readback={ready.readback}
            ctx={ctx}
            commands={commands}
            onAccessLost={onAccessLost}
            reload={() => {
              setAttempt((n) => n + 1);
              return reloadItem();
            }}
          />
        </PanelBoundary>
      )}
    </>
  );
}

/** A line's write form that fails to draw takes only itself down: the page and the panel's sections stay. */
class PanelBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  render() {
    return this.state.failed ? <Callout kind="warning">We couldn’t show these controls. Reload the page to try again.</Callout> : this.props.children;
  }
}

const BUSY = new Set<ApiError['kind']>(['rate_limited', 'read_limited']);
const isBusy = (error: ApiError) => BUSY.has(error.kind) || error.status === 503;

/** The station track with who holds each station, and the six facts. Nothing when the item has no tracking_url; one callout when the read failed and there is no earlier read. */
function TrackingBlock({ item, tracking, error, onRetry }: { item: LiveWorkItem; tracking: LiveTracking | null; error: ApiError | null; onRetry: () => void }) {
  if (item.tracking_url === null) return null;
  if (!tracking) {
    return error ? (
      <Callout kind="warning">
        We couldn’t load where this work is held.{isBusy(error) && ' Try again shortly.'}{' '}
        <Button kind="secondary" size="sm" onClick={onRetry}>
          Try again
        </Button>
      </Callout>
    ) : null;
  }
  const stations = stationsOf(tracking, item);
  return (
    <>
      {stations.length > 0 && (
        <section className="work-track" aria-label="Stations">
          <StationTrack stations={stations} />
        </section>
      )}
      <FactsStrip facts={factsOf(tracking)} label="Facts" className="work-facts" paidNote={null} />
    </>
  );
}

/** The agent on this item: its name and picture, what it is doing (the activity line, else progress) and its last recorded activity. No steps. */
function AgentCard({ item, tracking }: { item: LiveWorkItem; tracking: LiveTracking | null }) {
  const activity = activityOf(item);
  const last = tracking?.last_activity ?? null;
  if (!item.agent && !activity && !last) return null;
  const key = agentKey(item.agent);
  return (
    <section className="psl-agent work-agent" aria-label="Agent at work">
      {item.agent && (
        <div className="psl-agent__head">
          {key ? <AgentAvatar agent={key} working={item.current_activity?.watching === true} /> : <PersonAvatar name={item.agent} />}
          <span>
            <strong>{item.agent}</strong>
          </span>
        </div>
      )}
      {(activity || last) && (
        <div className="work-agent__body">
          {activity && (
            <p className="work-plain">
              {activity.text}
              {activity.updatedAt && (
                <>
                  {' '}
                  <span className="work-note">
                    Updated <time dateTime={activity.updatedAt}>{formatDayTime(activity.updatedAt)}</time>
                  </span>
                </>
              )}
            </p>
          )}
          {last && (
            <p className="work-note">
              Last activity: {words(last.kind)} · {words(last.status)} · <time dateTime={last.at}>{formatDayTime(last.at)}</time>
            </p>
          )}
        </div>
      )}
    </section>
  );
}

function Overview({
  item,
  ctx,
  reload,
  lose,
  tracking,
  trackingError,
  retryTracking,
}: {
  item: LiveWorkItem;
  ctx: LineContext;
  reload: () => Promise<LiveWorkItem | null>;
  lose: (error: ApiError) => void;
  tracking: LiveTracking | null;
  trackingError: ApiError | null;
  retryTracking: () => void;
}) {
  const outputHref = safeHref(item.output_url);
  return (
    <div className="work-columns work-columns--lone">
      <div className="work-column">
        <TrackingBlock item={item} tracking={tracking} error={trackingError} onRetry={retryTracking} />
        <AgentCard item={item} tracking={tracking} />
        <ItemControls item={item} reload={reload} onAccessLost={lose} />
        {item.blocker && (
          <Callout kind="warning" announce={false} className="work-next">
            <strong>Why it is stuck.</strong> {item.blocker}
          </Callout>
        )}
        {item.next_step && (
          <Callout kind={nextStepKind(item.state)} announce={false} icon={false} className="work-next">
            <strong>Next step.</strong> {item.next_step}
          </Callout>
        )}
        {item.tasks.length > 0 && (
          <section className="psl-panel" aria-labelledby="live-decisions">
            <h2 id="live-decisions" className="psl-panel__head">
              Decisions waiting
            </h2>
            <div className="psl-panel__body ws-section__body">
              <ul className="ws-rows">
              {item.tasks.map((task) => {
                const href = decisionHref(item.id, task);
                return (
                  <li key={task.id} className="ws-row">
                    <span>
                      {words(task.kind)} · {task.role} · {words(task.status)}
                    </span>{' '}
                    {href && (
                      <Link className="psl-link cmp-target" href={href}>
                        Open decision
                      </Link>
                    )}
                  </li>
                );
              })}
              </ul>
            </div>
          </section>
        )}
        {outputHref && (
          <p>
            <a className="psl-link cmp-target" href={outputHref}>
              Open the output
            </a>
          </p>
        )}
        {item.panels.map((panel) => (
          <PanelView key={panel.key} panel={panel} ctx={ctx} version={item.updated_at} reloadItem={reload} onAccessLost={lose} />
        ))}
      </div>
    </div>
  );
}

function History({ id }: { id: number }) {
  const { state, kind, setKind, retry, loadOlder } = useLiveHistory(id);
  const list = useRef<HTMLOListElement>(null);
  // the row to focus once older events arrive: the first new one
  const focusFrom = useRef<number | null>(null);
  const count = state.status === 'ready' ? state.items.length : 0;
  useEffect(() => {
    if (focusFrom.current === null || count <= focusFrom.current) return;
    (list.current?.children[focusFrom.current] as HTMLElement | undefined)?.focus();
    focusFrom.current = null;
  }, [count]);

  let body: ReactNode;
  if (state.status === 'loading') body = <LoadingState />;
  else if (state.status === 'error') body = <ErrorState error={state.error} pathname={`/work/${id}/history`} onRetry={() => void retry()} what="this item’s history" />;
  else if (state.items.length === 0) body = <EmptyState title="No changes recorded yet.">Changes appear here as the work moves.</EmptyState>;
  else {
    const failed = typeof state.older === 'object' ? state.older.error : null;
    body = (
      <>
        <ol ref={list} className="work-hcards" aria-label="History, newest first">
          {state.items.map((row) => {
            const line = historyLine(row);
            const tag = ACTOR_TAGS[line.actorKind === 'worker' ? 'agent' : 'person'];
            return (
              <li key={line.entryId} className="work-hcard" tabIndex={-1}>
                <span className="work-hcard__when">
                  <time dateTime={line.at}>{formatDayTime(line.at)}</time>
                </span>
                <span className="work-who">
                  <Tag tone={tag.tone}>{tag.text}</Tag>
                  {line.actor && <span>{line.actor}</span>}
                </span>
                <span className="work-eventline">
                  <strong className="work-event">{line.station}</strong> {line.status}
                </span>
                {line.reason && <span className="work-line">{line.reason}</span>}
                {line.evidenceId !== null && <span className="work-line">Evidence {line.evidenceId}</span>}
              </li>
            );
          })}
        </ol>
        {failed && (
          <Callout kind="warning">{isBusy(failed) ? 'Try again shortly.' : 'We couldn’t load older events. Your work is safe; nothing was changed.'}</Callout>
        )}
        {state.nextBefore !== null && (
          <p>
            <Button
              kind="secondary"
              busy={state.older === 'loading'}
              busyLabel="Loading…"
              onClick={() => {
                focusFrom.current = state.items.length;
                void loadOlder();
              }}
            >
              {failed ? 'Try again' : 'Older events'}
            </Button>
          </p>
        )}
        <p className="work-note">
          {historyCaption(state.items.length, state.nextBefore !== null)} As of <time dateTime={state.asOf}>{formatDayTime(state.asOf)}</time>.
        </p>
      </>
    );
  }
  return (
    <div className="work-column">
      <div className="work-historybar">
        <Segmented label="Show" className="work-filter" value={kind} onChange={setKind} options={HISTORY_FILTERS.map((f) => ({ value: f.kind, label: f.label }))} />
      </div>
      {body}
    </div>
  );
}

/** The frame and the tab's content for a live work id (one item read for both tabs). */
export function LiveWorkItemView({ id, tab }: { id: string; tab: 'overview' | 'history' }) {
  const workId = Number.parseInt(id, 10);
  const { state, retry, reload, lose } = useLiveWorkItem(workId);
  // a new object per read, made here (the frame outlives the tab) so a line's unread lock still matches after History and back
  const readItem = state.status === 'ready' ? state.item : null;
  const ctx: LineContext | null = useMemo(
    () => (readItem ? { workId: readItem.id, caseId: readItem.case_id, revision: readItem.revision, caseRevision: readItem.case_revision, state: readItem.state } : null),
    [readItem],
  );
  const tracking = useLiveTracking(workId, readItem !== null && readItem.tracking_url !== null, state.status === 'ready' ? state.loadedAt : null, lose);
  const base = `/work/${workId}`;
  usePhoneBack(tab === 'history' ? { label: 'Work item', href: base } : { label: 'Queue', href: '/my-work' });

  if (state.status === 'loading') return <LoadingState />;
  if (state.status === 'error') return <ErrorState error={state.error} pathname={tab === 'history' ? `${base}/history` : base} onRetry={() => void retry()} what="this work item" />;
  const { item, loadedAt, refreshFailed } = state;
  return (
    <>
      <Header item={item} tracking={tracking.tracking} base={base} tab={tab} />
      {refreshFailed && <Callout kind="warning">We couldn’t refresh this item. Showing what we had at {formatDayTime(loadedAt)}.</Callout>}
      {tab === 'overview' ? ctx && <Overview item={item} ctx={ctx} reload={reload} lose={lose} tracking={tracking.tracking} trackingError={tracking.error} retryTracking={() => void tracking.retry()} /> : <History id={workId} />}
    </>
  );
}

/** The tab is the path under /work/<id>/: History, else the Overview. */
export function LiveWorkItemLayoutFrame({ id }: { id: string }) {
  const tab = usePathname().split('/')[3] === 'history' ? 'history' : 'overview';
  return <LiveWorkItemView id={id} tab={tab} />;
}
