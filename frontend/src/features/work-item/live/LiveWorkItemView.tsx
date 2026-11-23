'use client';

// F-85 SCR-02 on the live API: /work/[id] and /work/[id]/history for an integer work id (GET /work/{id}, GET /work/{id}/history).
// Only what the response carries is drawn: no station track, facts strip or agent steps, and no placeholder where they were.
// Reads only; every write (resume, cancel, release, decide, ...) is a later feature. Access is the backend's answer (404 = missing or not yours).
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useEffect, useState, type ReactNode } from 'react';

import type { ApiError } from '@/api/errors';
import { Breadcrumb, buttonClass, Button, Callout, EmptyState, formatDayTime, Segmented, Tabs, Tag, useIsPhone } from '@/components';
import { adapterFor, type LineContext, type PanelRef } from '@/features/workspace/adapter';
import type { Section } from '@/features/workspace/labels';
import { SectionView } from '@/features/workspace/Sections';
import '@/features/forecast/forecastAdapter';
import '@/features/workspace/weeklyReportAdapter';
import { usePhoneBack } from '@/shell/AppShell';
import { LoadingState, SignedOutState } from '@/shell/FrameStates';
import { SampleLabel } from '@/shell/SampleLabel';
import type { LiveWorkItem } from '@/api/types';

import { nextStepKind, STATE_TAGS } from '../labels';
import { NoAccessState, WorkErrorCard } from '../WorkItemStates';
import { decisionHref, activityOf, historyCaption, historyLine, HISTORY_FILTERS } from './model';
import { useLiveHistory } from './useLiveHistory';
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

function Header({ item, base, tab }: { item: LiveWorkItem; base: string; tab: 'overview' | 'history' }) {
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
      <span>
        Updated <time dateTime={item.updated_at}>{formatDayTime(item.updated_at)}</time>
      </span>
      {/* INV-SAMPLE: the record says it is sample data (tag shown only when switched on) */}
      <SampleLabel show={item.sample} />
    </div>
  );
  const tabs = <Tabs2 base={base} tab={tab} />;
  return (
    <header className="work-header">
      {!phone && (
        <div className="work-crumbrow">
          <Breadcrumb items={[{ label: 'My work', href: '/my-work' }, { label: item.line }]} current={<span>Work {item.id}</span>} />
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

/** One panel through its adapter; a key with no adapter has nothing to draw and is left out. */
function PanelView({ panel, ctx, version }: { panel: PanelRef; ctx: LineContext; version: string }) {
  const adapter = adapterFor(panel.key);
  const [state, setState] = useState<{ status: 'loading' } | { status: 'error' } | { status: 'ready'; sections: Section[]; readback: unknown }>({ status: 'loading' });
  const [attempt, setAttempt] = useState(0);
  const { workId, caseId, revision, caseRevision } = ctx;

  useEffect(() => {
    if (!adapter) return;
    let active = true;
    adapter
      .read(panel)
      .then((readback) => {
        if (active) setState({ status: 'ready', sections: adapter.sections(readback, { workId, caseId, revision, caseRevision }), readback });
      })
      .catch(() => {
        if (active) setState({ status: 'error' });
      });
    return () => {
      active = false;
    };
    // a new item revision (poll) or a Try again reads the panel again
  }, [adapter, panel, workId, caseId, revision, caseRevision, version, attempt]);

  if (!adapter) return null;
  if (state.status === 'loading') return null;
  if (state.status === 'error') {
    return (
      <Callout kind="warning">
        We couldn’t load this part of the page.{' '}
        <Button
          kind="secondary"
          size="sm"
          onClick={() => {
            setState({ status: 'loading' });
            setAttempt((n) => n + 1);
          }}
        >
          Try again
        </Button>
      </Callout>
    );
  }
  return (
    <>
      {state.sections.map((section) => (
        <SectionView key={section.key} section={section} level={2} />
      ))}
      {adapter.Extra && <adapter.Extra readback={state.readback} ctx={ctx} />}
    </>
  );
}

function Overview({ item }: { item: LiveWorkItem }) {
  const activity = activityOf(item);
  const ctx: LineContext = { workId: item.id, caseId: item.case_id, revision: item.revision, caseRevision: item.case_revision };
  return (
    <div className="work-columns work-columns--lone">
      <div className="work-column">
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
                      {task.kind} · {task.role} · {task.status}
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
        {item.output_url && (
          <p>
            <a className="psl-link cmp-target" href={item.output_url}>
              Open the output
            </a>
          </p>
        )}
        {item.panels.map((panel) => (
          <PanelView key={panel.key} panel={panel} ctx={ctx} version={item.updated_at} />
        ))}
      </div>
    </div>
  );
}

function History({ id }: { id: number }) {
  const { state, kind, setKind, retry } = useLiveHistory(id);
  let body: ReactNode;
  if (state.status === 'loading') body = <LoadingState />;
  else if (state.status === 'error') body = <ErrorState error={state.error} pathname={`/work/${id}/history`} onRetry={() => void retry()} what="this item’s history" />;
  else if (state.items.length === 0) body = <EmptyState title="No changes recorded yet.">Changes appear here as the work moves.</EmptyState>;
  else {
    body = (
      <>
        <ol className="work-hcards" aria-label="History, newest first">
          {state.items.map((row, i) => {
            const line = historyLine(row);
            return (
              <li key={i} className="work-hcard">
                <span className="work-hcard__when">
                  <time dateTime={line.at}>{formatDayTime(line.at)}</time>
                </span>
                <span className="work-eventline">
                  <strong className="work-event">{line.station}</strong> {line.status}
                </span>
                {line.actor && <span className="work-who">{line.actor}</span>}
                {line.reason && <span className="work-line">{line.reason}</span>}
                {line.evidenceId !== null && <span className="work-line">Evidence {line.evidenceId}</span>}
              </li>
            );
          })}
        </ol>
        <p className="work-note">
          {historyCaption(state.items.length)} As of <time dateTime={state.asOf}>{formatDayTime(state.asOf)}</time>.
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
  const { state, retry } = useLiveWorkItem(workId);
  const base = `/work/${workId}`;
  usePhoneBack(tab === 'history' ? { label: 'Work item', href: base } : { label: 'Queue', href: '/my-work' });

  if (state.status === 'loading') return <LoadingState />;
  if (state.status === 'error') return <ErrorState error={state.error} pathname={tab === 'history' ? `${base}/history` : base} onRetry={() => void retry()} what="this work item" />;
  const { item, loadedAt, refreshFailed } = state;
  return (
    <>
      <Header item={item} base={base} tab={tab} />
      {refreshFailed && <Callout kind="warning">We couldn’t refresh this item. Showing what we had at {formatDayTime(loadedAt)}.</Callout>}
      {tab === 'overview' ? <Overview item={item} /> : <History id={workId} />}
    </>
  );
}

/** The tab is the path under /work/<id>/: History, else the Overview. */
export function LiveWorkItemLayoutFrame({ id }: { id: string }) {
  const tab = usePathname().split('/')[3] === 'history' ? 'history' : 'overview';
  return <LiveWorkItemView id={id} tab={tab} />;
}
