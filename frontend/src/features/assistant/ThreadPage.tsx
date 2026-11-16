'use client';

// /assistant/[conversationId]: one conversation. Reads E-CONVERSATION, polls while it is working, and holds the
// composer for the agent that answered. A conversation that is not the person's, or unknown, shows nothing of it.
import { usePathname, useRouter } from 'next/navigation';
import NextLink from 'next/link';
import { useCallback } from 'react';

import { AGENTS, buttonClass, EmptyState, ErrorState, Loading, Skeleton, useIsPhone, VisuallyHidden } from '@/components';
import { usePhoneBack } from '@/shell/AppShell';
import { SignedOutState } from '@/shell/FrameStates';

import { useAssistant } from './AssistantContext';
import { TalkTo } from './Chrome';
import { ComposerBar } from './ComposerBar';
import { workHref } from './model';
import { NOT_FOUND, REFRESH_FAILED, sideSentence } from './labels';
import { poseFor, SidePanel } from './SidePanel';
import { Thread } from './Thread';
import { useConversation } from './useConversation';
import { useSend } from './useSend';
import type { Conversation } from './types';

function PhoneHeader({ title }: { title: string }) {
  usePhoneBack({ label: 'Assistant', href: '/assistant', note: title });
  return null;
}

function Open({ id, conversation, refreshFailed, reload }: { id: string; conversation: Conversation; refreshFailed: boolean; reload: () => Promise<Conversation | undefined> }) {
  const { agents, list } = useAssistant();
  const router = useRouter();
  const phone = useIsPhone();
  const pathname = usePathname() ?? '/assistant';
  const agent = conversation.agent;
  const send = useSend({ agent: agent ?? 'tola', conversationId: id, personCount: conversation.messages.filter((m) => m.role === 'person').length, reload, listChanged: list.refresh });
  // After a start the thread and the list both change ("Started · INV-0415").
  const afterStart = useCallback(async () => {
    await reload();
    void list.refresh();
  }, [reload, list]);
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
        <Thread conversation={conversation} reread={afterStart} />
        {refreshFailed && (
          <p className="psl-hint as__refresh" role="status">
            {REFRESH_FAILED}
          </p>
        )}
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
  const { state, reload, retry } = useConversation(id, list.refresh);

  if (state.status === 'ready') return <Open id={id} conversation={state.data} refreshFailed={state.refreshFailed} reload={reload} />;
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
