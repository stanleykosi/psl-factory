// SCR-02 Overview: the six facts, the station track, the agent at work, the current human task and the
// next step. Read-only; the only link that leads to an action is "Open the decision" when you_can_act.
import Link from 'next/link';

import {
  AGENT_TAGS,
  avatarClass,
  currentStationIndex,
  FACTS,
  formatWat,
  nextStepKind,
  STATIONS,
  STEP_WORDS,
  stepKind,
  type Fact,
  type WorkItem,
} from './labels';

function FactValue({ fact }: { fact: Fact | undefined }) {
  // INV-UNKNOWN: a fact the payload does not carry reads Unknown, never blank, zero or "No".
  const status = fact?.status ?? 'unknown';
  if (status === 'earned') {
    return (
      <>
        <strong>Earned</strong>
        {fact?.at && <time dateTime={fact.at}>{formatWat(fact.at)}</time>}
      </>
    );
  }
  if (status === 'current') return <strong>In progress</strong>;
  if (status === 'not_yet') {
    return (
      <strong>
        <span aria-hidden="true">—</span>
        <span className="work-sr">Not yet</span>
      </strong>
    );
  }
  return <strong>Unknown</strong>;
}

function factClass(fact: Fact | undefined): string {
  const status = fact?.status ?? 'unknown';
  if (status === 'earned') return fact?.name === 'verified' ? 'psl-fact psl-fact--verified' : 'psl-fact psl-fact--earned';
  if (status === 'current') return 'psl-fact psl-fact--current';
  if (status === 'unknown') return 'psl-fact psl-fact--unknown';
  return 'psl-fact';
}

export function FactsStrip({ facts }: { facts: WorkItem['facts'] }) {
  return (
    <div className="work-facts">
      <ul className="psl-facts" aria-label="Facts">
        {FACTS.map(({ name, label }) => {
          const fact = facts.find((f) => f.name === name);
          return (
            <li key={name} className={factClass(fact)}>
              <b>{label}</b>
              <FactValue fact={fact} />
            </li>
          );
        })}
      </ul>
      <p className="work-note">Paid is a separate Finance fact and is not part of this line.</p>
    </div>
  );
}

export function StationTrack({ stations }: { stations: WorkItem['stations'] }) {
  const current = currentStationIndex(stations);
  return (
    // From 720px a narrow column can scroll the row sideways inside this focusable region; below 720px it is a list.
    // eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex
    <section className="work-track" aria-label="Stations" tabIndex={0}>
      <ol className="psl-track">
        {stations.map((station, i) => {
          const { text, modifier } = STATIONS[station.status];
          return (
            <li key={i} className={`psl-station psl-station--${modifier}`} aria-current={i === current ? 'step' : undefined}>
              <b>{String(i + 1).padStart(2, '0')}</b>
              <strong>{station.name}</strong>
              <span>{text}</span>
            </li>
          );
        })}
      </ol>
    </section>
  );
}

export function AgentCard({ agent }: { agent: WorkItem['agent'] }) {
  if (agent.status === 'none') {
    return (
      <section className="work-agent work-agent--none" aria-label="Agent at work">
        <p>No agent work on this item.</p>
      </section>
    );
  }
  const name = agent.name ?? 'Agent';
  const steps = agent.steps ?? [];
  const tag = AGENT_TAGS[agent.status];
  const now = steps.findIndex((s) => stepKind(s.status) !== 'done');
  return (
    <section className="psl-agent work-agent" aria-label="Agent at work">
      <div className="psl-agent__head">
        <span className={avatarClass(agent.name)} aria-hidden="true">
          {name.charAt(0).toUpperCase()}
        </span>
        <span>
          <strong>{name}</strong>
          <small>Cannot approve, send or pay.</small>
          {agent.status === 'working' && now >= 0 && (
            <small>
              step {now + 1} of {steps.length}
            </small>
          )}
        </span>
        <span className={`psl-tag psl-tag--${tag.tone}`}>{tag.text}</span>
      </div>
      {steps.length > 0 && (
        <ol className="psl-steps">
          {steps.map((step, i) => {
            const kind = stepKind(step.status);
            return (
              <li key={i} className={`psl-step psl-step--${kind}`}>
                <span className={kind === 'now' ? 'psl-step__box psl-now' : 'psl-step__box'} aria-hidden="true">
                  {kind === 'next' ? i + 1 : kind === 'done' ? '✓' : null}
                </span>
                <span className="psl-step__text">
                  <span>
                    <span className="work-sr">{STEP_WORDS[kind]}: </span>
                    {step.text}
                  </span>
                  {step.source && <span className="psl-step__ref psl-mono">Read: {step.source}</span>}
                </span>
              </li>
            );
          })}
        </ol>
      )}
    </section>
  );
}

export function TaskPanels({ id, tasks }: { id: string; tasks: WorkItem['tasks'] }) {
  return tasks.map((task) => (
    <section key={task.id} className={task.you_can_act ? 'psl-panel psl-panel--decide' : 'psl-panel'} aria-label="Current human task">
      <h2 className={task.you_can_act ? 'psl-panel__head psl-panel__head--decide' : 'psl-panel__head'}>{task.title}</h2>
      <div className="psl-panel__body">
        <p className="work-plain">Only a {task.required_role} can decide.</p>
        {task.you_can_act && <p className="work-plain">You are {task.required_role}.</p>}
        {task.you_can_act && (
          <Link className="psl-btn" href={`/work/${encodeURIComponent(id)}/decide?task=${encodeURIComponent(task.id)}`}>
            Open the decision
          </Link>
        )}
      </div>
    </section>
  ));
}

export function NextStep({ item }: { item: WorkItem }) {
  return (
    <p className={`psl-callout psl-callout--${nextStepKind(item.state)} work-next`}>
      <span>
        <strong>Next step.</strong> {item.next_step}
      </span>
    </p>
  );
}

export function WorkItemOverview({ id, item }: { id: string; item: WorkItem }) {
  return (
    <>
      <FactsStrip facts={item.facts} />
      <StationTrack stations={item.stations} />
      <div className="work-columns">
        <div className="work-column">
          <AgentCard agent={item.agent} />
          <NextStep item={item} />
        </div>
        {item.tasks.length > 0 && (
          <div className="work-column">
            <TaskPanels id={id} tasks={item.tasks} />
          </div>
        )}
      </div>
    </>
  );
}
