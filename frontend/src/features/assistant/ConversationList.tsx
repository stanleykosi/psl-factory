'use client';

// The person's conversations, grouped by day. Rows are links; the open one is marked. Used in the left column and, on
// phones, in the "earlier" sheet.
import NextLink from 'next/link';
import { useEffect, useRef } from 'react';

import { AgentAvatar, DEFAULT_PAGE_SIZE, ErrorState, Loading, Skeleton, Button, type PageSize } from '@/components';
import { SignedOutState } from '@/shell/FrameStates';

import { groupByDay, NO_CONVERSATIONS, statusLine } from './labels';
import type { ConversationRow } from './types';
import type { ListState } from './useConversationList';

function Row({ row, current, onOpen, onFocus }: { row: ConversationRow; current: boolean; onOpen?: () => void; onFocus?: () => void }) {
  return (
    <NextLink href={`/assistant/${encodeURIComponent(row.conversation_id)}`} className="as-row" aria-current={current ? 'page' : undefined} onClick={onOpen} onFocus={onFocus}>
      <AgentAvatar agent={row.agent} />
      <span className="as-row__text">
        <span className="as-row__title">{row.title}</span>
        <span className="as-row__sub">{statusLine(row)}</span>
      </span>
    </NextLink>
  );
}

export function ConversationList({ state, currentId, onMore, onRetry, pathname, onOpen }: {
  state: ListState;
  currentId?: string;
  onMore: (limit: PageSize) => void;
  onRetry: () => void;
  pathname: string;
  onOpen?: () => void;
}) {
  const ready = state.status === 'ready' ? state : undefined;
  const sentinel = useRef<HTMLDivElement>(null);
  const hasNext = Boolean(ready?.next);
  const idle = ready?.more === 'idle';
  const count = ready?.items.length ?? 0;
  const latest = useRef(onMore);
  useEffect(() => {
    latest.current = onMore;
  });
  // Infinite scroll: the next page loads when the end of the list comes into view. The observer is made again after each
  // page, so a list still short of the bottom keeps loading; rows already shown are never reloaded.
  useEffect(() => {
    const node = sentinel.current;
    if (!node || !hasNext || !idle || typeof IntersectionObserver === 'undefined') return undefined;
    // The list scrolls inside its own column on desktop, so that column is the observer's root (the page on a phone sheet).
    const root = node.closest('.as__listscroll');
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) latest.current(DEFAULT_PAGE_SIZE);
      },
      { root },
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, [hasNext, idle, count]);
  if (state.status === 'loading') return <Skeleton widths={[90, 70, 80]} />;
  if (state.status === 'signed_out') return <SignedOutState pathname={pathname} />;
  if (state.status === 'error') {
    return (
      <ErrorState title="Couldn’t load your conversations" onRetry={onRetry} retryLabel="Try again">
        Nothing was changed.
      </ErrorState>
    );
  }
  if (state.items.length === 0) return <p className="as-list__empty">{NO_CONVERSATIONS}</p>;
  return (
    <>
      {groupByDay(state.items, state.asOf).map((group) => (
        <section key={group.label} className="as-list__group" aria-label={`Conversations, ${group.label.toLowerCase()}`}>
          <p className="as-list__day">{group.label}</p>
          {group.rows.map((row) => (
            <Row
              key={row.conversation_id}
              row={row}
              current={row.conversation_id === currentId}
              onOpen={onOpen}
              onFocus={row === state.items[state.items.length - 1] && state.next && state.more === 'idle' ? () => onMore(DEFAULT_PAGE_SIZE) : undefined}
            />
          ))}
        </section>
      ))}
      <div ref={sentinel} aria-hidden="true" />
      {state.more === 'loading' && <Loading className="as-list__more">Loading…</Loading>}
      {state.more === 'error' && (
        <p className="psl-hint as-list__more" role="alert">
          Couldn’t load more.{' '}
          <Button kind="text" size="sm" onClick={() => onMore(DEFAULT_PAGE_SIZE)}>
            Try again
          </Button>
        </p>
      )}
    </>
  );
}
