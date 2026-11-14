'use client';

// SCR-07 project journey: breadcrumb, title, project tabs, what is next and every line's work in the order returned.
// Data comes only from E-PROJECT; the backend decides access (INV-ACCESS).
import Link from 'next/link';

import { STATE_TAGS } from '@/features/work-item/labels';
import { WorkErrorCard } from '@/features/work-item/WorkItemStates';
import { useMe } from '@/shell/AppShell';
import { visibleDestinations } from '@/shell/destinations';
import { LoadingState, NotOpenState, SignedOutState } from '@/shell/FrameStates';

import type { Journey, JourneyLine } from './model';
import { ProjectNoAccess } from './ProjectStates';
import { ProjectTabs } from './ProjectTabs';
import { useProject } from './useProject';

import './projects.css';

/** CMP-05 tag for a line; a state outside the enum (only if the contract changes) shows its raw value as neutral. */
function StateTag({ state }: { state: JourneyLine['state'] }) {
  const tag = Object.hasOwn(STATE_TAGS, state) ? STATE_TAGS[state] : { text: state, tone: 'neutral' };
  return <span className={`psl-tag psl-tag--${tag.tone} projects__state`}>{tag.text}</span>;
}

function JourneyView({ journey, base }: { journey: Journey; base: string }) {
  return (
    <>
      <header className="projects__header">
        <nav aria-label="Breadcrumb" className="projects__crumb">
          <p className="psl-crumb">
            <Link href="/projects">Projects</Link> / <span aria-current="page">{journey.title}</span>
          </p>
        </nav>
        <Link href="/projects" className="projects__back">
          &larr; Projects
        </Link>
        <h1 className="shell-title">{journey.title}</h1>
      </header>
      <ProjectTabs base={base} current="journey" />
      <div className="psl-callout psl-callout--info projects__next">
        <span>
          <strong>What is next</strong>
          <span className="projects__nexttext">{journey.next}</span>
        </span>
      </div>
      <section className="projects__journey" aria-labelledby="project-journey-title">
        <h2 id="project-journey-title" className="projects__h2">
          The whole journey
        </h2>
        {journey.lines.length === 0 ? (
          <div className="psl-empty">
            <p>No work on this project yet.</p>
          </div>
        ) : (
          <ol className="psl-list projects__lines">
            {journey.lines.map((line, i) => (
              <li key={`${line.work_id}-${i}`}>
                <Link href={`/work/${encodeURIComponent(line.work_id)}`} className="projects__line">
                  <span className="projects__linename">{line.line}</span>
                  <StateTag state={line.state} />
                </Link>
              </li>
            ))}
          </ol>
        )}
      </section>
    </>
  );
}

function ProjectJourney({ caseId }: { caseId: string }) {
  const { state, retry } = useProject(caseId);
  const base = `/projects/${encodeURIComponent(caseId)}`;

  if (state.status === 'loading') return <LoadingState />;
  if (state.status === 'error') {
    const { error } = state;
    if (error.kind === 'unauthenticated') return <SignedOutState pathname={base} />;
    if (error.kind === 'forbidden' || error.kind === 'not_found') return <ProjectNoAccess />;
    return (
      <WorkErrorCard
        message="We couldn’t load this project. Your work is safe; nothing was changed."
        error={error}
        onRetry={() => void retry()}
      />
    );
  }
  return <JourneyView journey={state.journey} base={base} />;
}

/** /projects/<case_id>: one project's journey, for anyone whose /me lists Projects. Without it no request is made. */
export function ProjectJourneyPage({ caseId }: { caseId: string }) {
  const me = useMe();
  if (!me.destinations.includes('projects')) {
    return <NotOpenState first={visibleDestinations(me.destinations)[0]} />;
  }
  return <ProjectJourney caseId={caseId} />;
}
