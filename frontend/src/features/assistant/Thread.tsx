'use client';

// The messages of one conversation, in the order returned: the person's ask in an ink box, each agent message with its
// hand-off note, steps, answer, sources and draft. Every string from the API is rendered as text.
import { AGENTS, AgentChecklist, ChatMessage, formatClock, Link, SourceTag, useIsPhone, type AgentStep } from '@/components';

import { DraftStart } from './DraftStart';
import { runStatus, sourcesOf, stepsOf, workHref } from './model';
import type { Conversation, Message } from './types';

type Ref = NonNullable<NonNullable<Message['step_details']>[number]['reference']>;

/** A step's record: a link only when the record names a work item. */
function stepRecord(ref: Ref, words: string): AgentStep['source'] {
  return ref.work_id ? <Link href={workHref(ref.work_id)}>{words}</Link> : words;
}

export function Thread({ conversation, reread }: { conversation: Conversation; reread: () => Promise<unknown> }) {
  const phone = useIsPhone();
  const agent = conversation.agent;
  return (
    <section className="as__thread" aria-label="Conversation">
      {conversation.messages.map((message, at) => {
        if (message.role === 'person') {
          return (
            <ChatMessage key={at} from="person">
              {message.text}
            </ChatMessage>
          );
        }
        if (!agent) return null;
        const steps = stepsOf(message, stepRecord);
        const status = runStatus(steps);
        const sources = sourcesOf(message);
        // Phones draw the full card for a working run (the task, its step and when it started), the plain header otherwise.
        const asked = [...conversation.messages.slice(0, at)].reverse().find((m) => m.role === 'person')?.at;
        const card = phone && status === 'working';
        return (
          <ChatMessage
            key={at}
            from="agent"
            agent={agent}
            handoff={message.handoff?.note}
            cannot={message.cannot_reason}
            steps={
              steps.length > 0 && (
                <AgentChecklist
                  agent={card ? agent : undefined}
                  task={conversation.title ?? AGENTS[agent].name}
                  status={status}
                  steps={steps}
                  foot={card && asked ? `Started ${formatClock(asked)}` : undefined}
                  label={`${AGENTS[agent].name}’s steps`}
                  inline={!card}
                />
              )
            }
            sources={sources.length === 0 ? undefined : sources.map((source) => (source.restricted ? <SourceTag key={source.key} restricted /> : <SourceTag key={source.key} label={source.label!} href={source.href} />))}
            draft={message.draft && <DraftStart draft={message.draft} reread={reread} />}
          >
            {message.text}
          </ChatMessage>
        );
      })}
    </section>
  );
}

