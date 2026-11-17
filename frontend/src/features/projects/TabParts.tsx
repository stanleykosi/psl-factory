'use client';

// Pieces the three project tabs share: the states of a tab read (loading, signed out, no access, error), the footer
// with "Show more", an amount, an owner and a row link. Nothing is computed here; values come from tabsModel.
import Link from 'next/link';
import type { ReactNode } from 'react';

import { Button, Callout, EmptyState, ShowMore, Unknown, When } from '@/components';
import { WorkErrorCard } from '@/features/work-item/WorkItemStates';
import { LoadingState, SignedOutState } from '@/shell/FrameStates';

import { amountText, ownerText, workHref, type Amount, type ListTab, type Owner } from './tabsModel';
import type { TabState } from './useProjectTab';

/** What a tab shows until it has rows: null when ready. 403 and 404 look the same and leave no row text behind. */
export function tabStateView(state: TabState<ListTab>, { retry, signInPath }: { retry: () => void; signInPath: string }): ReactNode {
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
      <h3>{children}</h3>
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

/** The owner as the boards write it; "No owner" in signal ink when the row has none. */
export function OwnerValue({ owner }: { owner: Owner | undefined }) {
  const text = ownerText(owner);
  return text === undefined ? <span className="ptabs__noowner">No owner</span> : <>{text}</>;
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

/** "20 showing · Show more", and the failure of a later page. */
export function RowsFooter({ shown, hasMore, more, onMore }: { shown: number; hasMore: boolean; more: 'idle' | 'loading' | 'error'; onMore: () => void }) {
  if (!hasMore && more !== 'error') return null;
  return (
    <div className="ptabs__foot">
      <ShowMore shown={shown} hasMore={hasMore} busy={more === 'loading'} onMore={onMore} />
      {more === 'error' && (
        <Callout kind="problem">
          We couldn&rsquo;t load more. Nothing was changed.{' '}
          <Button kind="secondary" size="sm" onClick={onMore}>
            Try again
          </Button>
        </Callout>
      )}
    </div>
  );
}
