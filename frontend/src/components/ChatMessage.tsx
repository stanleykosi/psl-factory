'use client';

// ChatMessage (design/system/project/components/ChatMessage): the pieces of the assistant page. Your message is an
// ink box on the right. An agent's message has the avatar and "Name · Team agent", the hand-off note, the steps it
// took, its answer, source tags and a draft. Text is plain: `children` is rendered as text with its line breaks kept,
// never as HTML or markdown. The agent never carries a decision control here.
import type { ReactNode } from 'react';

import { AGENTS, AgentAvatar, type AgentKey } from './Avatar';
import { cx, usePhone } from './internal';

export type ChatMessageProps =
  | { from: 'person'; children: ReactNode; className?: string }
  | {
      from: 'agent';
      agent: AgentKey;
      /** The answer, plain text. */
      children?: ReactNode;
      /** "Invoices are prepared by Chidi, so Tola passed this to him." */
      handoff?: string;
      /** The step list (an AgentChecklist). */
      steps?: ReactNode;
      /** Source tags. */
      sources?: ReactNode;
      /** Why it cannot answer, a plain line. */
      cannot?: string;
      /** A DraftCard. */
      draft?: ReactNode;
      className?: string;
    };

export function ChatMessage(props: ChatMessageProps) {
  const phone = usePhone();
  if (props.from === 'person') {
    return (
      <div className={cx('cmp-chat cmp-chat--person', props.className)}>
        <p className="cmp-chat__text">{props.children}</p>
      </div>
    );
  }
  const { agent, children, handoff, steps, sources, cannot, draft, className } = props;
  const who = AGENTS[agent];
  return (
    <article className={cx('cmp-chat cmp-chat--agent', className)} aria-label={`${who.name}, ${who.role}`}>
      <AgentAvatar agent={agent} size={phone ? 32 : 40} className="cmp-chat__avatar" />
      <span className="cmp-chat__who">
        <strong>{who.name}</strong> <span>· {who.role}</span>
      </span>
      <div className="cmp-chat__body">
        {handoff && <p className="cmp-chat__handoff">{handoff}</p>}
        {steps}
        {children && <p className="cmp-chat__answer cmp-chat__text">{children}</p>}
        {cannot && <p className="cmp-chat__cannot cmp-chat__text">{cannot}</p>}
        {sources && <div className="cmp-chat__sources">{sources}</div>}
        {draft}
      </div>
    </article>
  );
}
