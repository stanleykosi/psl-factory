'use client';

// The person's conversations, grouped by day. Rows are links; the open one is marked. Used in the left column and, on
// phones, in the "earlier" sheet.
import NextLink from 'next/link';

import { AgentAvatar, ErrorState, ShowMore, Skeleton, usePagedRows, type PageSize } from '@/components';
import { SignedOutState } from '@/shell/FrameStates';

import { groupByDay, NO_CONVERSATIONS, statusLine } from './labels';
import type { ConversationRow } from './types';
import type { ListState } from './useConversationList';

function Row({ row, current, onOpen }: { row: ConversationRow; current: boolean; onOpen?: () => void }) {
  return (
    <NextLink href={`/assistant/${encodeURIComponent(row.conversation_id)}`} className="as-row" aria-current={current ? 'page' : undefined} onClick={onOpen}>
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
  const { rows, paging } = usePagedRows({
    items: ready?.items ?? [],
    next: Boolean(ready?.next),
    busy: ready?.more === 'loading',
    failed: ready?.more === 'error',
    loadMore: onMore,
  });
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
      {groupByDay(rows, state.asOf).map((group) => (
        <section key={group.label} className="as-list__group" aria-label={`Conversations, ${group.label.toLowerCase()}`}>
          <p className="as-list__day">{group.label}</p>
          {group.rows.map((row) => (
            <Row key={row.conversation_id} row={row} current={row.conversation_id === currentId} onOpen={onOpen} />
          ))}
        </section>
      ))}
      <ShowMore solo {...paging} />
      {state.more === 'error' && (
        <p className="psl-hint" role="alert">
          Couldn’t load more.
        </p>
      )}
    </>
  );
}
