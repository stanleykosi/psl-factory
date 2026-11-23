'use client';

// SCR-07 project page: breadcrumb, title, the project tab bar, then the tab. Journey shows the PM and route line, the
// facts strip and every piece of work in the order returned. Data comes only from the live GET /projects/{case_id}
// (see model.ts); the backend decides access and which tabs and figures a person gets.
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { createContext, useContext, useEffect, useRef, type ReactNode } from 'react';

import { Breadcrumb, EmptyState, formatDayMonth, PageTitle, Panel, Tag, VisuallyHidden } from '@/components';
import { WorkErrorCard } from '@/features/work-item/WorkItemStates';
import { useMe, usePhoneBack } from '@/shell/AppShell';
import { hasDestination, visibleDestinations } from '@/shell/destinations';
import { LoadingState, NotOpenState, SignedOutState } from '@/shell/FrameStates';
import { SampleLabel } from '@/shell/SampleLabel';

import { clientOf, factText, piecesText, projectCounts, PROJECT_TABS, type Journey, type JourneyItem, type ProjectTab } from './model';
import { DeliveryTab } from './DeliveryTab';
import { MoneyTab } from './MoneyTab';
import { MoreFooter } from './MoreFooter';
import { ProjectNoAccess } from './ProjectStates';
import { ProjectTabContent } from './ProjectTabContent';
import { PANEL_ID, ProjectTabs } from './ProjectTabs';
import { hasTabContent } from './tabsModel';
import { useProject, type MoreState } from './useProject';

import './projects.css';

/** The four facts SCR-07 draws from live; a figure the response does not carry reads "Not available", never 0. */
function ProjectFacts({ journey }: { journey: Journey }) {
  const { facts } = journey;
  const cells: { label: string; value: number | string | null | undefined; current?: boolean }[] = [
    { label: 'CONTRACT STAGES', value: facts.finance?.stages },
    { label: 'WAITING ON PEOPLE', value: facts.waiting, current: facts.waiting > 0 },
    { label: 'STOPPED', value: facts.stopped, current: facts.stopped > 0 },
    { label: 'NEXT MILESTONE', value: facts.finance?.next },
  ];
  return (
    <>
      <section aria-label="Facts earned" className="psl-facts projects__facts">
        {cells.map((cell) => {
          const value = factText(cell.value);
          const tone = value === 'Not available' ? 'psl-fact--unknown' : cell.current ? 'psl-fact--current' : undefined;
          return (
            <div key={cell.label} className={tone ? `psl-fact ${tone}` : 'psl-fact'}>
              <b>{cell.label}</b>
              <strong>{value}</strong>
            </div>
          );
        })}
      </section>
      {facts.finance?.limited && <p className="projects__partial">Figures may be partial.</p>}
    </>
  );
}

/** One piece of work: its line, the reference when there is one, when it started and last changed, and its state words as given. */
function JourneyLines({ items }: { items: JourneyItem[] }) {
  return (
    <ol className="projects__lines">
      {items.map((item) => {
        // Two rows with the same title get their reference or state in the link name (UX-1-1).
        const repeated = items.filter((other) => other.line === item.line).length > 1;
        return (
          <li key={item.id} className="projects__line">
            <span aria-hidden="true" className="projects__dot projects__dot--neutral" />
            <span className="projects__linemain">
              <Link href={`/work/${item.id}`} className="projects__linename">
                {item.line}
                {repeated && <VisuallyHidden>, {item.reference ?? item.state}</VisuallyHidden>}
              </Link>
              {item.reference && <span className="projects__ref"> {item.reference}</span>}
              <span className="projects__detail">
                Started {formatDayMonth(item.started)} · Updated {formatDayMonth(item.updated)}
              </span>
            </span>
            <Tag tone="neutral" className="projects__state">
              {item.state}
            </Tag>
          </li>
        );
      })}
    </ol>
  );
}

/** The right-hand panel: only the link to the Assistant, and only when live offers an Assistant for this project and the person has it. */
function AskPanel({ journey }: { journey: Journey }) {
  const me = useMe();
  if (journey.assistant.length === 0 || !hasDestination(me, 'assistant')) return null;
  return (
    <Panel kind="agent" as="aside" aria-label="Assistant" className="projects__agent">
      <p className="projects__plain">
        <Link href="/assistant">Ask me about this project</Link>
      </p>
    </Panel>
  );
}

function JourneyTab({ journey, more, showMore }: { journey: Journey; more: MoreState; showMore: () => void }) {
  const counts = projectCounts(journey);
  const engagement = journey.facts.engagement;
  const route = [engagement?.manager && `PM ${engagement.manager}`, engagement?.route, piecesText(counts.pieces)];
  const phoneLine = [piecesText(counts.pieces), `${counts.waiting} waiting on people`, `${counts.stopped} stopped`];
  const rowsRef = useRef<HTMLDivElement>(null);
  // Show more: the keyboard moves to the first row it added.
  const focusRow = useRef<number | null>(null);
  useEffect(() => {
    if (focusRow.current !== null && journey.items.length > focusRow.current) {
      rowsRef.current?.querySelectorAll<HTMLElement>('.projects__linename')[focusRow.current]?.focus();
      focusRow.current = null;
    }
  }, [journey.items.length]);
  return (
    <>
      <p className="projects__route">{route.filter(Boolean).join(' · ')}</p>
      <p className="projects__phoneline">{phoneLine.join(' · ')}</p>
      <ProjectFacts journey={journey} />
      <div className="projects__body">
        <Panel className="projects__journey" head="The whole journey, oldest first" bodyClassName="projects__journeybody">
          {journey.items.length === 0 ? (
            <EmptyState title="No work yet" className="projects__empty">
              No work on this project yet.
            </EmptyState>
          ) : (
            <div ref={rowsRef}>
              <JourneyLines items={journey.items} />
            </div>
          )}
          {journey.items.length > 0 && (
            <MoreFooter
              text={`${journey.items.length} of ${counts.pieces} shown`}
              hasMore={journey.next_page !== null}
              busy={more === 'loading'}
              failed={more === 'error'}
              onMore={() => {
                if (more !== 'error') focusRow.current = journey.items.length;
                showMore();
              }}
            />
          )}
        </Panel>
        <AskPanel journey={journey} />
      </div>
    </>
  );
}

const ProjectContext = createContext<{ journey: Journey; base: string; tab: ProjectTab; more: MoreState; showMore: () => void } | null>(null);

/** The tab's content, drawn inside the frame's tabpanel; the frame has already read the project. */
export function ProjectTabBody() {
  const ctx = useContext(ProjectContext);
  if (!ctx) throw new Error('ProjectTabBody needs the project frame');
  const { journey, base, tab, more, showMore } = ctx;
  return tab === 'journey' ? (
    <JourneyTab journey={journey} more={more} showMore={showMore} />
  ) : tab === 'delivery' ? (
    <DeliveryTab />
  ) : hasTabContent(tab) ? (
    <ProjectTabContent caseId={journey.case_id} journey={journey} base={base} tab={tab} />
  ) : (
    <MoneyTab caseId={journey.case_id} base={base} />
  );
}

function ProjectView({ journey, base, tab, more, showMore, children }: { journey: Journey; base: string; tab: ProjectTab; more: MoreState; showMore: () => void; children: ReactNode }) {
  return (
    <ProjectContext.Provider value={{ journey, base, tab, more, showMore }}>
      <div className="projects__page">
        <header className="projects__header">
          <div className="projects__crumb">
            <Breadcrumb items={[{ label: 'Projects', href: '/projects' }]} current={clientOf(journey.title)} />
          </div>
          <PageTitle size={36} phoneSize={22}>
            {journey.title}
          </PageTitle>
          <SampleLabel show={journey.sample} />
        </header>
        <ProjectTabs base={base} current={tab} tabs={journey.tabs} />
        <div role="tabpanel" id={PANEL_ID} aria-label={PROJECT_TABS.find((t) => t.key === tab)?.label} className="projects__panel">
          {children}
        </div>
      </div>
    </ProjectContext.Provider>
  );
}

function ProjectPage({ caseId, tab, children }: { caseId: string; tab: ProjectTab; children: ReactNode }) {
  const { state, retry, more, showMore } = useProject(caseId);
  const base = `/projects/${encodeURIComponent(caseId)}`;

  if (state.status === 'loading') return <LoadingState />;
  if (state.status === 'error') {
    const { error } = state;
    if (error.kind === 'unauthenticated') return <SignedOutState pathname={`${base}${PROJECT_TABS.find((t) => t.key === tab)?.path ?? ''}`} />;
    if (error.kind === 'forbidden' || error.kind === 'not_found') return <ProjectNoAccess />;
    return (
      <WorkErrorCard
        message="We couldn’t load this project. Your work is safe; nothing was changed."
        error={error}
        onRetry={() => void retry()}
      />
    );
  }
  return (
    <ProjectView journey={state.journey} base={base} tab={tab} more={more} showMore={() => void showMore()}>
      {children}
    </ProjectView>
  );
}

/** The project's frame (breadcrumb, title, tab bar), read once for the project. It is the layout of every tab, so a tab change keeps it and only the panel changes. */
export function ProjectFrame({ caseId, tab, children }: { caseId: string; tab: ProjectTab; children: ReactNode }) {
  const me = useMe();
  usePhoneBack({ label: 'Projects', href: '/projects' });
  if (!hasDestination(me, 'projects')) {
    return <NotOpenState first={visibleDestinations(me.destinations)[0]} />;
  }
  return (
    <ProjectPage caseId={caseId} tab={tab}>
      {children}
    </ProjectPage>
  );
}

/** The tab is the path under /projects/<case_id>/; anything else is the Journey. */
export function ProjectLayoutFrame({ caseId, children }: { caseId: string; children: ReactNode }) {
  const segment = usePathname().split('/')[3] ?? '';
  const tab = PROJECT_TABS.find((t) => t.path === (segment ? `/${segment}` : ''))?.key ?? 'journey';
  return (
    <ProjectFrame caseId={caseId} tab={tab}>
      {children}
    </ProjectFrame>
  );
}

/** One project tab as a single page: the frame and its content (the route files split them across layout and page). */
export function ProjectJourneyPage({ caseId, tab = 'journey' }: { caseId: string; tab?: ProjectTab }) {
  return (
    <ProjectFrame caseId={caseId} tab={tab}>
      <ProjectTabBody />
    </ProjectFrame>
  );
}
