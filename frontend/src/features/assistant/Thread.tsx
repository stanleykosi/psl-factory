'use client';

// The messages of one conversation, in the order returned: the person's ask in an ink box, each agent message with its
// hand-off note, steps, answer, sources and draft. Every string from the API is rendered as text.
import { Fragment } from 'react';

import { AGENTS, AgentChecklist, ChatMessage, formatClock, Link, SourceTag, useIsPhone, type AgentStep } from '@/components';

import { uploadHref } from './api';
import { DraftStart } from './DraftStart';
import { SENDING } from './labels';
import { runStatus, sourcesOf, stepsOf, workHref } from './model';
import type { Message, ThreadConversation } from './types';

type Ref = NonNullable<NonNullable<Message['step_details']>[number]['reference']>;

/** A step's record: a link only when the record names a work item. */
function stepRecord(ref: Ref, words: string): AgentStep['source'] {
  return ref.work_id ? <Link href={workHref(ref.work_id)}>{words}</Link> : words;
}

export function Thread({ conversation, reread }: { conversation: ThreadConversation; reread: () => Promise<unknown> }) {
  const phone = useIsPhone();
  const agent = conversation.agent;
  return (
    <section className="as__thread" aria-label="Conversation">
      {conversation.messages.map((message, at) => {
        if (message.role === 'person') {
          // A message not yet on the server shows its local previews; one that is shows the uploads' own address.
          const images = message.local
            ? message.local.images.map(({ id, name, src }) => ({ id, name, src, href: src }))
            : (message.attachments ?? []).map((a) => ({ id: a.file_id, name: a.name, src: uploadHref(a.file_id), href: uploadHref(a.file_id) }));
          return (
            <ChatMessage key={at} from="person" images={images} chips={message.local?.chips} note={message.local?.sending ? SENDING : undefined}>
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
        // The phone's inline pose, above the agent's first line; only for a refusal.
        const pose = phone && conversation.status === 'cannot_answer' && conversation.messages.findIndex((m) => m.role === 'agent') === at;
        return (
          <Fragment key={at}>
            {pose && (
              <div className={`as__pose as__pose--${agent} as__pose--inline`}>
                {/* eslint-disable-next-line @next/next/no-img-element -- fixed mascot asset from public/agents, as SidePanel does */}
                <img src={`/agents/${agent}-cant.png`} alt={`${AGENTS[agent].name}, can’t do this`} />
              </div>
            )}
            <ChatMessage
              from="agent"
              agent={agent}
              hideWho={card}
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
          </Fragment>
        );
      })}
    </section>
  );
}

