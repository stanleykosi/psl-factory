'use client';

// SCR-07 project page: breadcrumb, title, the project tab bar, then the tab. Journey shows the PM and route line, the
// facts strip, every line's work in the order returned, what is next and Tola's summary. Data comes only from
// E-PROJECT (v7 optional fields, see model.ts); the backend decides access (INV-ACCESS).
import Link from 'next/link';

import { AgentAvatar, agentKey, Breadcrumb, EmptyState, PageTitle, Panel, STATE_TAGS, Tag, VisuallyHidden, type FactoryState, type TagTone } from '@/components';
import { WorkErrorCard } from '@/features/work-item/WorkItemStates';
import { useMe, usePhoneBack } from '@/shell/AppShell';
import { visibleDestinations } from '@/shell/destinations';
import { LoadingState, NotOpenState, SignedOutState } from '@/shell/FrameStates';

import {
  agentSummaryOf,
  clientOf,
  factsOf,
  factText,
  findFact,
  lineDetail,
  linesText,
  pmNameOf,
  piecesText,
  PROJECT_TABS,
  textOf,
  workCounts,
  type JourneyFact,
  type JourneyLineView,
  type JourneyView,
  type ProjectTab,
} from './model';
import { MoneyTab } from './MoneyTab';
import { ProjectNoAccess } from './ProjectStates';
import { PANEL_ID, ProjectTabs } from './ProjectTabs';
import { useProject } from './useProject';

import './projects.css';

/** CMP-05 tag for a line; a state outside the enum (only if the contract changes) shows its raw value as neutral. */
const tagFor = (state: JourneyLineView['state']): { text: string; tone: TagTone } => (Object.hasOwn(STATE_TAGS, state) ? STATE_TAGS[state as FactoryState] : { text: state, tone: 'neutral' });

// The six facts SCR-07 draws, shown "Unknown" when the response sends no facts. Their tones are presentation only.
const BOARD_FACTS = ['CONTRACT STAGES', 'INVOICES VERIFIED', 'WAITING ON PEOPLE', 'STOPPED', 'NEXT MILESTONE', 'PAID'];
const FACT_TONES: Record<string, (value: string) => string | undefined> = {
  'invoices verified': () => 'psl-fact--earned',
  'waiting on people': (v) => (v !== '0' ? 'psl-fact--current' : undefined),
  stopped: (v) => (v !== '0' ? 'psl-fact--current' : undefined),
};

/** The facts in the response's order; a value it does not know reads "Unknown", never 0. */
function ProjectFacts({ facts }: { facts?: JourneyFact[] }) {
  const shown = facts ?? BOARD_FACTS.map((label) => ({ label, unknown: true }));
  return (
    <section aria-label="Facts earned" className="psl-facts projects__facts">
      {shown.map((fact, i) => {
        const value = factText(fact);
        const tone = value === undefined ? 'psl-fact--unknown' : FACT_TONES[fact.label.toLowerCase()]?.(value);
        return (
          <div key={`${fact.label}-${i}`} className={tone ? `psl-fact ${tone}` : 'psl-fact'}>
            <b>{fact.label}</b>
            <strong>{value ?? 'Unknown'}</strong>
          </div>
        );
      })}
    </section>
  );
}

function JourneyLines({ lines }: { lines: JourneyLineView[] }) {
  const names = lines.map((l) => textOf(l.title) ?? l.line);
  return (
    <ol className="projects__lines">
      {lines.map((line, i) => {
        const tag = tagFor(line.state);
        const name = names[i];
        // Two lines with the same name get their reference or state in the link name (UX-1-1).
        const repeated = names.indexOf(name) !== names.lastIndexOf(name);
        const reference = textOf(line.reference);
        const detail = lineDetail(line);
        return (
          <li key={`${line.work_id}-${i}`} className="projects__line">
            <span aria-hidden="true" className={`projects__dot projects__dot--${tag.tone}`} />
            <span className="projects__linemain">
              <Link href={`/work/${encodeURIComponent(line.work_id)}`} className="projects__linename">
                {name}
                {repeated && <VisuallyHidden>, {reference ?? tag.text}</VisuallyHidden>}
              </Link>
              {reference && <span className="projects__ref"> {reference}</span>}
              {detail && <span className="projects__detail">{detail}</span>}
            </span>
            <Tag tone={tag.tone} className="projects__state">
              {tag.text}
            </Tag>
          </li>
        );
      })}
    </ol>
  );
}

/** Tola's summary of the project (PROPOSAL `agent_summary`); without one the panel says so. */
function AgentSummary({ journey }: { journey: JourneyView }) {
  const me = useMe();
  const summary = agentSummaryOf(journey.agent_summary);
  const agent = summary?.name ?? 'Tola';
  const role = summary ? summary.role : 'PMO agent';
  const paragraphs = summary?.paragraphs ?? [];
  const key = agentKey(agent);
  return (
    <Panel
      kind="agent"
      as="aside"
      aria-label={`${agent}'s summary`}
      className="projects__agent"
      head={
        <span className="projects__agenthead">
          {key && <AgentAvatar agent={key} size={40} />}
          <span className="projects__agentname">
            {agent} {role && <span className="projects__agentrole">· {role}</span>}
          </span>
        </span>
      }
    >
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
    </Panel>
  );
}

function JourneyTab({ journey }: { journey: JourneyView }) {
  const counts = workCounts(journey);
  const facts = factsOf(journey.facts);
  const pm = pmNameOf(journey.pm);
  const waiting = factText(findFact(facts, 'waiting on people'));
  const stopped = factText(findFact(facts, 'stopped'));
  const route = [pm && `PM ${pm}`, textOf(journey.route), `${piecesText(counts.pieces)} across ${linesText(counts.lines)}`];
  const phoneLine = [piecesText(counts.pieces), waiting && `${waiting} waiting on people`, stopped && `${stopped} stopped`];
  return (
    <>
      <p className="projects__route">{route.filter(Boolean).join(' · ')}</p>
      <p className="projects__phoneline">{phoneLine.filter(Boolean).join(' · ')}</p>
      <ProjectFacts facts={facts} />
      <div className="projects__body">
        <Panel className="projects__journey" head="The whole journey, oldest first" bodyClassName="projects__journeybody">
          {journey.lines.length === 0 ? (
            <EmptyState title="No work yet" className="projects__empty">
              No work on this project yet.
            </EmptyState>
          ) : (
            <JourneyLines lines={journey.lines} />
          )}
          <p className="projects__next">
            <strong>What is next</strong> <span className="projects__nexttext">{journey.next}</span>
          </p>
        </Panel>
        <AgentSummary journey={journey} />
      </div>
    </>
  );
}

/** A tab whose contents FE-M3-PROJECT-TABS builds: a plain "coming next" panel with the way back to the journey. */
function ComingNext({ tab, base }: { tab: ProjectTab; base: string }) {
  const label = PROJECT_TABS.find((t) => t.key === tab)?.label ?? '';
  return (
    <EmptyState
      level={2}
      title={`${label} ${label.endsWith('s') ? 'come' : 'comes'} next`}
      className="projects__coming"
      action={<Link href={base}>Open the journey</Link>}
    >
      This tab is not built yet. The journey shows every line&rsquo;s work on this project now.
    </EmptyState>
  );
}

function ProjectView({ journey, base, tab }: { journey: JourneyView; base: string; tab: ProjectTab }) {
  return (
    <div className="projects__page">
      <header className="projects__header">
        <div className="projects__crumb">
          <Breadcrumb items={[{ label: 'Projects', href: '/projects' }]} current={clientOf(journey)} />
        </div>
        <PageTitle size={36} phoneSize={22}>
          {journey.title}
        </PageTitle>
      </header>
      <ProjectTabs base={base} current={tab} counts={journey.tab_counts} />
      <div role="tabpanel" id={PANEL_ID} aria-label={PROJECT_TABS.find((t) => t.key === tab)?.label} className="projects__panel">
        {tab === 'journey' ? <JourneyTab journey={journey} /> : tab === 'money' ? <MoneyTab caseId={journey.case_id} base={base} /> : <ComingNext tab={tab} base={base} />}
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
  usePhoneBack({ label: 'Projects', href: '/projects' });
  if (!me.destinations.includes('projects')) {
    return <NotOpenState first={visibleDestinations(me.destinations)[0]} />;
  }
  return <ProjectPage caseId={caseId} tab={tab} />;
}
