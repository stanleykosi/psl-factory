// AgentChecklist (design/system/project/components/AgentChecklist, CMP-09): an agent doing the work step by step,
// with the record each step read, so people can follow it and never mistake it for a decision. Blue-bordered card:
// avatar, task, "step n of m", and the WORKING, DONE, Waiting or Action needed tag. Steps: done (filled blue
// square with a tick, record in mono), now (pulsing outlined square, bold), next (numbered grey square), waiting
// for a person (dashed amber square, naming who), stopped ("!" with the reason). Each step's state is also in
// words for screen readers. The footer has when it started and "Ask <name>"; never Approve, Send or Pay.
import NextLink from 'next/link';
import type { ReactNode } from 'react';

import { AGENTS, AgentAvatar, type AgentKey } from './Avatar';
import { Icon } from './Icon';
import { Tag, type TagTone } from './Tag';

export type StepStatus = 'done' | 'now' | 'next' | 'wait' | 'stopped';
export type AgentStep = { text: string; status: StepStatus; /** The record it read ("MIN-0091"). */ source?: string };
export type AgentRunStatus = 'working' | 'done' | 'waiting' | 'stopped';

const STEP_WORDS: Record<StepStatus, string> = { done: 'Done', now: 'In progress', next: 'To do', wait: 'Waiting', stopped: 'Stopped' };

const TAGS: Record<AgentRunStatus, { text: string; tone: TagTone }> = {
  working: { text: 'WORKING', tone: 'agent' },
  done: { text: 'DONE', tone: 'agent' },
  waiting: { text: 'Waiting', tone: 'waiting' },
  stopped: { text: 'Action needed', tone: 'person' },
};

export function AgentChecklist({ agent, task, status, steps, foot, ask, label = 'Agent at work' }: {
  agent: AgentKey;
  /** What it is doing ("Assembling the weekly client report"). */
  task: string;
  status: AgentRunStatus;
  steps: AgentStep[];
  /** "Started 14:02 WAT", "A person must choose". */
  foot?: ReactNode;
  /** Where "Ask Tola" goes (the assistant). */
  ask?: string;
  label?: string;
}) {
  const { name, role } = AGENTS[agent];
  const at = steps.findIndex((s) => s.status !== 'done');
  const progress =
    status === 'done' ? 'done' : status === 'stopped' && at >= 0 ? `stopped at step ${at + 1}` : at >= 0 ? `step ${at + 1} of ${steps.length}` : `step ${steps.length} of ${steps.length}`;
  const tag = TAGS[status];
  return (
    <section className="psl-agent" aria-label={label}>
      <div className="psl-agent__head">
        <AgentAvatar agent={agent} working={status === 'working'} />
        <span>
          <strong>{task}</strong>
          <small>
            {name} · {role} · {progress}
          </small>
        </span>
        <Tag tone={tag.tone} pulse={status === 'working'}>
          {tag.text}
        </Tag>
      </div>
      {steps.length > 0 && (
        <ol className="psl-steps">
          {steps.map((step, i) => (
            <li key={i} className={`psl-step psl-step--${step.status}`}>
              <span className={step.status === 'now' ? 'psl-step__box psl-now' : 'psl-step__box'} aria-hidden="true">
                {step.status === 'done' && <Icon name="check" className="cmp-steptick" />}
                {step.status === 'next' && i + 1}
                {step.status === 'stopped' && '!'}
              </span>
              <span className="psl-step__text">
                <span>
                  <span className="cmp-sr">{STEP_WORDS[step.status]}: </span>
                  {step.text}
                </span>
                {step.source && (
                  <span className="psl-step__ref">
                    <span className="cmp-sr">Read: </span>
                    {step.source}
                  </span>
                )}
              </span>
            </li>
          ))}
        </ol>
      )}
      {(foot || ask) && (
        <div className="psl-agent__foot">
          <span>{foot}</span>
          {ask && (
            <NextLink href={ask} className="psl-link">
              Ask {name}
            </NextLink>
          )}
        </div>
      )}
    </section>
  );
}
