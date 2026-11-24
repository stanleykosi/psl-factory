'use client';

// Pieces the three project tabs share: the states of a tab read (loading, signed out, no access, error), the footer
// with "Show more", an amount and a row link. Nothing is computed here; values come from tabsModel.
import Link from 'next/link';
import type { ReactNode } from 'react';

import type { ApiError } from '@/api/errors';
import { EmptyState, usePagedRows, Unknown, When, type PageSize } from '@/components';
import { WorkErrorCard } from '@/features/work-item/WorkItemStates';
import { LoadingState, SignedOutState } from '@/shell/FrameStates';

import { amountText, workHref, type Amount, type ListTab, type TabRows } from './tabsModel';
import type { TabState } from './useProjectTab';

/** What a tab shows until it has rows: null when ready. 403 and 404 look the same and leave no row text behind. */
export function tabStateView(state: { status: 'loading' } | { status: 'ready' } | { status: 'error'; error: ApiError }, { retry, signInPath }: { retry: () => void; signInPath: string }): ReactNode {
  if (state.status === 'ready') return null;
  if (state.status === 'loading') return <LoadingState />;
  const { error } = state;
  if (error.kind === 'unauthenticated') return <SignedOutState pathname={signInPath} />;
  if (error.kind === 'forbidden' || error.kind === 'not_found') return <TabNoAccess />;
  return <WorkErrorCard message="We couldn’t load this tab. Your work is safe; nothing was changed." error={error} onRetry={retry} />;
}

/** One sentence as the heading (no second line repeating it), with an optional action. */
export function TabEmpty({ children, action }: { children: ReactNode; action?: ReactNode }) {
  return (
    <div className="psl-empty">
      <h2>{children}</h2>
      {action}
    </div>
  );
}

export function TabNoAccess() {
  return (
    <EmptyState level={2} title="No access to this tab" className="ptabs__noaccess">
      It holds records you don&rsquo;t have access to. Nothing from it is shown here.
    </EmptyState>
  );
}

/** A row's text that opens its work item only when the row carries a work_id (plain text otherwise). */
export function RowLink({ workId, className, children }: { workId: unknown; className?: string; children: ReactNode }) {
  const href = workHref(workId);
  return href ? (
    <Link href={href} className={className}>
      {children}
    </Link>
  ) : (
    <>{children}</>
  );
}

/** A money value: the amount as the boards write it (plain text), or the amber Unknown tag (never 0 or blank). */
export function AmountValue({ value }: { value: Amount | undefined }) {
  const text = amountText(value);
  return text === undefined ? <Unknown /> : <>{text}</>;
}

export const NONE = <>—</>;

/** "As of 12 Nov 16:40" under the rows. */
export function AsOf({ value }: { value: string }) {
  return (
    <p className="ptabs__asof">
      As of <When value={value} show="daytime" />
    </p>
  );
}

/** The paging window over a tab's loaded rows (10 first, grown in place by the footer). */
export function useTabPaging<T extends ListTab>(state: TabState<T>, more: 'idle' | 'loading' | 'error', showMore: (limit: PageSize) => Promise<void>, resetKey = '') {
  const ready = state.status === 'ready' ? state : undefined;
  const { rows, paging } = usePagedRows({
    items: (ready?.rows ?? []) as TabRows[T][number][],
    next: Boolean(ready?.nextCursor),
    busy: more === 'loading',
    failed: more === 'error',
    loadMore: (limit) => void showMore(limit),
    resetKey,
  });
  return { rows: rows as TabRows[T], paging };
}

