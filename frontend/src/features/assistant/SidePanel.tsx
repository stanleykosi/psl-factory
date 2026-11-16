'use client';

// The agent and its context: the pose that matches the conversation, one sentence on where it stands, the project and
// "Your access" lines as the record states them, and the standing note on what agents cannot do.
/* eslint-disable @next/next/no-img-element -- fixed mascot assets from public/agents, as the other features use */
import { AGENTS } from '@/components';

import { CANNOT_NOTE } from './labels';
import type { AgentName, Conversation } from './types';

export type Pose = 'idle' | 'working' | 'done';

export function poseFor(conversation: Pick<Conversation, 'status'>): Pose {
  if (conversation.status === 'working') return 'working';
  return conversation.status === 'drafted' ? 'done' : 'idle';
}

export function SidePanel({ agent, pose, status, project, access }: {
  agent: AgentName;
  pose: Pose;
  status: string | undefined;
  project: string | undefined;
  access: string[] | undefined;
}) {
  const who = AGENTS[agent];
  return (
    <aside className="as__side" aria-label="Agent and context">
      <div className={`as__pose as__pose--${agent}`}>
        <img src={`/agents/${agent}-${pose}.png`} alt={`${who.name} pose`} />
      </div>
      <p className="as__status" aria-live="polite">
        {status}
      </p>
      <div className="as__fact">
        <span>Project</span>
        <span>{project ?? 'Pick a project with @'}</span>
      </div>
      <div className="as__fact">
        <span>Your access</span>
        <span>{access && access.length > 0 ? access.join(', ') : 'Records you can see'}</span>
      </div>
      <p className="as__cannot">{CANNOT_NOTE}</p>
    </aside>
  );
}
