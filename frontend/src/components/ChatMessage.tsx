'use client';

// ChatMessage (design/system/project/components/ChatMessage): the pieces of the assistant page. Your message is an
// ink box on the right. An agent's message has the avatar and "Name · Team agent", the hand-off note, the steps it
// took, its answer, source tags and a draft. Text is plain: `children` is rendered as text with its line breaks kept,
// never as HTML or markdown. The agent never carries a decision control here.
import type { ReactNode } from 'react';

import { AGENTS, AgentAvatar, type AgentKey } from './Avatar';
import { cx, usePhone } from './internal';

export type ChatMessageProps =
  | { from: 'person'; children: ReactNode; /** Thumbnails of the images sent with it (an `ImageList`-style list of links). */ images?: { id: string; name: string; src: string; href: string }[]; /** The @/# marks the person added, shown under the words. */ chips?: string[]; /** A muted line under it ("Sending…"). */ note?: ReactNode; className?: string }
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
      /** The agent is named by the steps card just below (the phone working card), so no byline. */
      hideWho?: boolean;
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
        {props.children !== '' && <p className="cmp-chat__text">{props.children}</p>}
        {props.chips && props.chips.length > 0 && (
          <ul className="cmp-chat__chips" aria-label="Mentions">
            {props.chips.map((chip) => (
              <li key={chip}>{chip}</li>
            ))}
          </ul>
        )}
        {props.images && props.images.length > 0 && (
          <ul className="cmp-chat__images" aria-label="Images">
            {props.images.map((image) => (
              <li key={image.id}>
                <a href={image.href} target="_blank" rel="noopener noreferrer" aria-label={`Open ${image.name}`}>
                  {/* eslint-disable-next-line @next/next/no-img-element -- the person's own upload; its size is not known here */}
                  <img src={image.src} alt={image.name} />
                </a>
              </li>
            ))}
          </ul>
        )}
        {props.note && <p className="cmp-chat__note">{props.note}</p>}
      </div>
    );
  }
  const { agent, children, handoff, steps, sources, cannot, draft, hideWho, className } = props;
  const who = AGENTS[agent];
  return (
    <article className={cx('cmp-chat cmp-chat--agent', hideWho && 'cmp-chat--nowho', className)} aria-label={`${who.name}, ${who.role}`}>
      {!hideWho && <AgentAvatar agent={agent} size={phone ? 32 : 40} className="cmp-chat__avatar" />}
      {!hideWho && (
        <span className="cmp-chat__who">
          <strong>{who.name}</strong> <span>· {who.role}</span>
        </span>
      )}
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
