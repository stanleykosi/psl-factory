'use client';

// SCR-07 project page: breadcrumb, title, the project tab bar, then the tab. Journey shows the PM and route line, the
// facts strip, every line's work in the order returned, what is next and Tola's summary. Data comes only from
// E-PROJECT (PROPOSAL fields optional, see model.ts); the backend decides access (INV-ACCESS).
import Link from 'next/link';

import { avatarClass, STATE_TAGS } from '@/features/work-item/labels';
import { WorkErrorCard } from '@/features/work-item/WorkItemStates';
import { useMe } from '@/shell/AppShell';
import { visibleDestinations } from '@/shell/destinations';
import { LoadingState, NotOpenState, SignedOutState } from '@/shell/FrameStates';

import {
  clientOf,
  linesText,
  piecesText,
  PROJECT_TABS,
  workCounts,
  type JourneyFacts,
  type JourneyLineView,
  type JourneyView,
  type ProjectTab,
} from './model';
import { ProjectNoAccess } from './ProjectStates';
import { PANEL_ID, ProjectTabs, tabId } from './ProjectTabs';
import { useProject } from './useProject';

import './projects.css';

/** CMP-05 tag for a line; a state outside the enum (only if the contract changes) shows its raw value as neutral. */
const tagFor = (state: JourneyLineView['state']) => (Object.hasOwn(STATE_TAGS, state) ? STATE_TAGS[state] : { text: state, tone: 'neutral' });

const FACTS: readonly { key: keyof JourneyFacts; label: string; tone?: (value: number) => string | undefined }[] = [
  { key: 'contract_stages', label: 'CONTRACT STAGES' },
  { key: 'invoices_verified', label: 'INVOICES VERIFIED', tone: () => 'psl-fact--earned' },
  { key: 'waiting_on_people', label: 'WAITING ON PEOPLE', tone: (n) => (n > 0 ? 'psl-fact--current' : undefined) },
  { key: 'stopped', label: 'STOPPED', tone: (n) => (n > 0 ? 'psl-fact--current' : undefined) },
  { key: 'next_milestone', label: 'NEXT MILESTONE' },
  { key: 'paid', label: 'PAID' },
];

/** The six facts as drawn; a value the response does not carry reads "Not known", never 0. */
function FactsStrip({ facts }: { facts?: JourneyFacts }) {
  return (
    <section aria-label="Facts earned" className="psl-facts projects__facts">
      {FACTS.map((f) => {
        const value = facts?.[f.key];
        const tone = value === undefined ? 'psl-fact--unknown' : typeof value === 'number' ? f.tone?.(value) : undefined;
        return (
          <div key={f.key} className={tone ? `psl-fact ${tone}` : 'psl-fact'}>
            <b>{f.label}</b>
            <strong>{value ?? 'Not known'}</strong>
          </div>
        );
      })}
    </section>
  );
}

function JourneyLines({ lines }: { lines: JourneyLineView[] }) {
  const names = lines.map((l) => l.title ?? l.line);
  return (
    <ol className="projects__lines">
      {lines.map((line, i) => {
        const tag = tagFor(line.state);
        const name = names[i];
        // Two lines with the same name get their reference or state in the link name (UX-1-1).
        const repeated = names.indexOf(name) !== names.lastIndexOf(name);
        return (
          <li key={`${line.work_id}-${i}`} className="projects__line">
            <span aria-hidden="true" className={`projects__dot projects__dot--${tag.tone}`} />
            <span className="projects__linemain">
              <Link href={`/work/${encodeURIComponent(line.work_id)}`} className="projects__linename">
                {name}
                {repeated && <span className="projects__sr">, {line.reference ?? tag.text}</span>}
              </Link>
              {line.reference && <span className="projects__ref"> {line.reference}</span>}
              {line.detail && <span className="projects__detail">{line.detail}</span>}
            </span>
            <span className={`psl-tag psl-tag--${tag.tone} projects__state`}>{tag.text}</span>
          </li>
        );
      })}
    </ol>
  );
}

/** Tola's summary of the project (PROPOSAL `summary`); without one the panel says so. */
function AgentSummary({ journey }: { journey: JourneyView }) {
  const me = useMe();
  const agent = journey.summary?.agent ?? 'Tola';
  const role = journey.summary?.role ?? 'PMO agent';
  const paragraphs = journey.summary?.paragraphs ?? [];
  return (
    <aside className="projects__agent" aria-label={`${agent}'s summary`}>
      <div className="projects__agenthead">
        <span className={`${avatarClass(agent)} projects__avatar`} aria-hidden="true">
          {agent.charAt(0).toUpperCase()}
        </span>
        <span className="projects__agentname">
          {agent} <span className="projects__agentrole">· {role}</span>
        </span>
      </div>
      <div className="projects__agentbody">
        {paragraphs.length === 0 && <p>{agent} has not summarised this project yet.</p>}
        {paragraphs.map((text, i) => (
          <p key={i}>{text}</p>
        ))}
        {me.destinations.includes('assistant') && (
          <p>
            <Link href="/assistant">Ask me about this project</Link>
          </p>
        )}
      </div>
    </aside>
  );
}

function JourneyTab({ journey }: { journey: JourneyView }) {
  const counts = workCounts(journey.lines);
  const facts = journey.facts;
  const route = [journey.pm && `PM ${journey.pm}`, journey.route, `${piecesText(counts.pieces)} across ${linesText(counts.lines)}`];
  const phoneLine = [
    piecesText(counts.pieces),
    facts?.waiting_on_people !== undefined && `${facts.waiting_on_people} waiting on people`,
    facts?.stopped !== undefined && `${facts.stopped} stopped`,
  ];
  return (
    <>
      <p className="projects__route">{route.filter(Boolean).join(' · ')}</p>
      <p className="projects__phoneline">{phoneLine.filter(Boolean).join(' · ')}</p>
      <FactsStrip facts={facts} />
      <div className="projects__body">
        <section className="projects__journey" aria-labelledby="project-journey-title">
          <h2 id="project-journey-title" className="projects__h2">
            The whole journey, oldest first
          </h2>
          {journey.lines.length === 0 ? (
            <div className="psl-empty projects__empty">
              <p>No work on this project yet.</p>
            </div>
          ) : (
            <JourneyLines lines={journey.lines} />
          )}
          <p className="projects__next">
            <strong>What is next</strong> <span className="projects__nexttext">{journey.next}</span>
          </p>
        </section>
        <AgentSummary journey={journey} />
      </div>
    </>
  );
}

/** A tab whose contents FE-M3-PROJECT-TABS builds: a plain "coming next" panel with the way back to the journey. */
function ComingNext({ tab, base }: { tab: ProjectTab; base: string }) {
  const label = PROJECT_TABS.find((t) => t.key === tab)?.label ?? '';
  return (
    <section className="psl-empty projects__coming" aria-labelledby="project-coming-title">
      <h2 id="project-coming-title" className="projects__h2">
        {label} {label.endsWith('s') ? 'come' : 'comes'} next
      </h2>
      <p>This tab is not built yet. The journey shows every line&rsquo;s work on this project now.</p>
      <Link href={base}>Open the journey</Link>
    </section>
  );
}

function ProjectView({ journey, base, tab }: { journey: JourneyView; base: string; tab: ProjectTab }) {
  return (
    <div className="projects__page">
      <header className="projects__header">
        <nav aria-label="Breadcrumb" className="projects__crumb">
          <p className="psl-crumb">
            <Link href="/projects">Projects</Link> / <span aria-current="page">{clientOf(journey)}</span>
          </p>
        </nav>
        <Link href="/projects" className="projects__back">
          &larr; Projects
        </Link>
        <h1 className="shell-title">{journey.title}</h1>
      </header>
      <ProjectTabs base={base} current={tab} counts={journey.tab_counts} />
      <div role="tabpanel" id={PANEL_ID} aria-labelledby={tabId(tab)} className="projects__panel">
        {tab === 'journey' ? <JourneyTab journey={journey} /> : <ComingNext tab={tab} base={base} />}
      </div>
    </div>
  );
}

function ProjectPage({ caseId, tab }: { caseId: string; tab: ProjectTab }) {
  const { state, retry } = useProject(caseId);
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
  return <ProjectView journey={state.journey} base={base} tab={tab} />;
}

/** /projects/<case_id>[/<tab>]: one project, for anyone whose /me lists Projects. Without it no request is made. */
export function ProjectJourneyPage({ caseId, tab = 'journey' }: { caseId: string; tab?: ProjectTab }) {
  const me = useMe();
  if (!me.destinations.includes('projects')) {
    return <NotOpenState first={visibleDestinations(me.destinations)[0]} />;
  }
  return <ProjectPage caseId={caseId} tab={tab} />;
}
