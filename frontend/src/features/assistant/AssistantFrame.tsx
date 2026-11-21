'use client';

// /assistant (SCR-05): the conversation list on the left, the home or thread in the middle, the agent and its context
// on the right. It lives in the route layout, so the list is read once and kept while the person moves between
// conversations. On phones the list is the "earlier" sheet.
import NextLink from 'next/link';
import { usePathname } from 'next/navigation';
import { useCallback, useMemo, useState, type ReactNode } from 'react';

import { BottomSheet, buttonClass, useIsPhone } from '@/components';
import { useMe } from '@/shell/AppShell';
import { visibleDestinations } from '@/shell/destinations';
import { NotOpenState } from '@/shell/FrameStates';

import { AssistantContext } from './AssistantContext';
import type { Pending } from './pending';
import { ConversationList } from './ConversationList';
import { LIST_NOTE } from './labels';
import { useConversationList } from './useConversationList';
import './assistant.css';

export function AssistantFrame({ children }: { children: ReactNode }) {
  const me = useMe();
  const pathname = usePathname() ?? '/assistant';
  const phone = useIsPhone();
  const list = useConversationList();
  const [sheet, setSheet] = useState(false);
  const [pending, setPending] = useState<Pending>();
  const showList = useCallback(() => setSheet(true), []);
  const agents = me.assistant_agents;
  const value = useMemo(() => ({ me, agents: agents ?? [], list, pending, setPending, showList }), [me, agents, list, pending, showList]);

  if (!me.destinations.includes('assistant')) return <NotOpenState first={visibleDestinations(me.destinations)[0]} />;
  const current = /^\/assistant\/([^/]+)/.exec(pathname)?.[1];
  const currentId = current ? decodeURIComponent(current) : undefined;
  const rows = (
    <ConversationList state={list.state} currentId={currentId} onMore={(limit) => void list.more(limit)} onRetry={list.retry} pathname={pathname} onOpen={() => setSheet(false)} />
  );

  return (
    <AssistantContext.Provider value={value}>
      <div className="as">
        {!phone && (
          <aside className="as__list" aria-label="Conversations">
            <NextLink href="/assistant" className={`${buttonClass('secondary', 'lg')} as__new`}>
              + New request
            </NextLink>
            <div className="as__listscroll">{rows}</div>
            <p className="as__note">{LIST_NOTE}</p>
          </aside>
        )}
        {children}
        {phone && sheet && (
          <BottomSheet title="Earlier conversations" onClose={() => setSheet(false)}>
            {rows}
          </BottomSheet>
        )}
      </div>
    </AssistantContext.Provider>
  );
}
