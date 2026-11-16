'use client';

// "Talk to" chips: the agents E-ME names, in the order returned. The pressed one is the agent on the home; in a
// thread none is pressed, because the thread belongs to the agent that answered.
import { AGENTS, AgentAvatar } from '@/components';

import type { AgentName } from './types';

export function TalkTo({ agents, selected, onPick }: { agents: AgentName[]; selected?: AgentName; onPick: (agent: AgentName) => void }) {
  return (
    <div role="group" aria-label="Talk to" className="as__talk">
      <span className="as__eyebrow" aria-hidden="true">
        TALK TO
      </span>
      {agents.map((agent) => (
        <button key={agent} type="button" className={`as-chip as-chip--${agent}`} aria-pressed={selected === agent} onClick={() => onPick(agent)}>
          <AgentAvatar agent={agent} />
          {AGENTS[agent].name}
          <span className="as-chip__team"> · {AGENTS[agent].team}</span>
        </button>
      ))}
    </div>
  );
}

/** Phones: "3 earlier" opens the conversation list as a sheet ("20+ earlier" when the list has another page). */
export function Earlier({ count, more, onOpen }: { count: number; more: boolean; onOpen: () => void }) {
  return (
    <button type="button" className="as-earlier" onClick={onOpen}>
      {`${count}${more ? '+' : ''} earlier`}
    </button>
  );
}
