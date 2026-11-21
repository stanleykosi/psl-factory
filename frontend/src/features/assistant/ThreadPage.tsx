'use client';

// /assistant/[conversationId]: one conversation. Reads E-CONVERSATION, polls while it is working, and holds the
// composer for the agent that answered. A conversation that is not the person's, or unknown, shows nothing of it.
import { usePathname, useRouter } from 'next/navigation';
import NextLink from 'next/link';
import { useCallback, useEffect, useMemo, useRef } from 'react';

import { AGENTS, buttonClass, EmptyState, ErrorState, Loading, Skeleton, useIsPhone, VisuallyHidden } from '@/components';
import { usePhoneBack } from '@/shell/AppShell';
import { SignedOutState } from '@/shell/FrameStates';

import { useAssistant } from './AssistantContext';
import { TalkTo } from './Chrome';
import { ComposerBar } from './ComposerBar';
import { personMessages, replied, startedConversation, withPending, type Pending } from './pending';
import { workHref } from './model';
import { NOT_FOUND, REFRESH_FAILED, sideSentence } from './labels';
import { poseFor, SidePanel } from './SidePanel';
import { Thread } from './Thread';
import { useConversation } from './useConversation';
import { useSend } from './useSend';
import type { ThreadConversation } from './types';

function PhoneHeader({ title }: { title: string }) {
  usePhoneBack({ label: 'Assistant', href: '/assistant', note: title });
  return null;
}

function Open({ id, conversation, refreshFailed, reload }: { id: string; conversation: ThreadConversation; refreshFailed: boolean; reload: ReturnType<typeof useConversation>['reload'] }) {
  const { agents, list } = useAssistant();
  const router = useRouter();
  const phone = useIsPhone();
  const pathname = usePathname() ?? '/assistant';
  const agent = conversation.agent;
  const send = useSend({ agent: agent ?? 'tola', conversationId: id, personCount: personMessages(conversation), reload, listChanged: list.refresh });
  // After a start the thread and the list both change ("Started · INV-0415").
  const afterStart = useCallback(async () => {
    await reload();
    void list.refresh();
  }, [reload, list]);
  // Only the thread scrolls on desktop: a conversation that opens, or a reply that arrives, shows the latest message.
  const scroller = useRef<HTMLDivElement>(null);
  const messageCount = conversation.messages.length;
  const shownCount = useRef(messageCount);
  useEffect(() => {
    const el = scroller.current;
    if (el) el.scrollTop = el.scrollHeight;
    // On phones the page scrolls, not the thread: a message added now (the person's own, or the reply) is brought into view (D-160).
    if (messageCount > shownCount.current) el?.querySelector('.as__thread')?.lastElementChild?.scrollIntoView?.({ block: 'nearest' });
    shownCount.current = messageCount;
  }, [messageCount, id]);
  const started = conversation.messages.find((m) => m.draft?.started)?.draft?.started;
  const name = agent ? AGENTS[agent].name : '';
  return (
    <>
      <div className="as__center">
        {conversation.title && <PhoneHeader title={conversation.title} />}
        {!phone && <TalkTo agents={agents} onPick={(next) => router.push(`/assistant?agent=${next}`)} />}
        <VisuallyHidden>
          <h1>{conversation.title ?? 'Conversation'}</h1>
        </VisuallyHidden>
        <div className="as__scroll" ref={scroller}>
          <Thread conversation={conversation} reread={afterStart} />
          {refreshFailed && (
            <p className="psl-hint as__refresh" role="status">
              {REFRESH_FAILED}
            </p>
          )}
        </div>
        {agent && phone && started ? (
          // Phones: once the draft is started the footer action is the way to the work item, as the board draws it.
          <div className="as__open">
            <NextLink href={workHref(started.work_id)} className={buttonClass('primary', 'lg', true)}>
              {started.reference ? `Open ${started.reference}` : 'Open the work item'}
            </NextLink>
          </div>
        ) : (
          agent && <ComposerBar agent={agent} send={send} pathname={pathname} />
        )}
      </div>
      {agent && !phone && (
        <SidePanel
          agent={agent}
          pose={poseFor(conversation)}
          status={sideSentence(name, conversation)}
          project={conversation.context?.project?.title}
          access={conversation.context?.access}
        />
      )}
    </>
  );
}

export function ThreadPage({ id }: { id: string }) {
  const { agents, list } = useAssistant();
  const router = useRouter();
  const pathname = usePathname() ?? '/assistant';
  const { pending, setPending } = useAssistant();
  // The person's message in this conversation, until the agent has replied (D-160): shown before the server has it, and never behind a skeleton.
  const sent: Pending | undefined = pending?.conversationId === id ? pending : undefined;
  const { state, reload, retry } = useConversation(id, list.refresh, Boolean(sent));
  const read = state.status === 'ready' ? state.data : undefined;
  useEffect(() => {
    if (sent?.phase === 'waiting' && read && replied(sent, read)) setPending(undefined);
  }, [sent, read, setPending]);
  const shown = useMemo(() => (read ? withPending(read, sent) : sent && state.status === 'loading' ? startedConversation(id, sent) : undefined), [read, sent, id, state.status]);

  if (shown) return <Open id={id} conversation={shown} refreshFailed={state.status === 'ready' && state.refreshFailed} reload={reload} />;
  let body;
  if (state.status === 'loading') {
    body = (
      <>
        <Skeleton widths={[60, 80, 50]} />
        <Loading>Loading…</Loading>
      </>
    );
  } else if (state.status === 'signed_out') body = <SignedOutState pathname={pathname} />;
  else if (state.status === 'missing') body = <EmptyState title={NOT_FOUND} level={2}>It may belong to someone else, or it may be gone.</EmptyState>;
  else
    body = (
      <ErrorState title="Couldn’t load this conversation" onRetry={retry} retryLabel="Try again">
        Nothing was changed.
      </ErrorState>
    );
  return (
    <div className="as__center">
      <TalkTo agents={agents} onPick={(next) => router.push(`/assistant?agent=${next}`)} />
      <VisuallyHidden>
        <h1>Conversation</h1>
      </VisuallyHidden>
      <div className="as__state">{body}</div>
    </div>
  );
}
