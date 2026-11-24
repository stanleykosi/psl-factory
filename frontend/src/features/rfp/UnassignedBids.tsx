'use client';

// SCR-24 list (F-88): the received RFPs still waiting for an accountable PM, from `GET /received-bids/assignments` (not the work queue).
// Rows are keyed by `case_id`; 12 a page, "Load more" while the server gives a cursor. A row whose owner access is missing says so and
// has no Assign button. The Assign PM drawer opens over it from the page's own address (`?assign=<case_id>`); after a write the first
// page is read again and the row leaves only if the server no longer lists it.
import Link from 'next/link';
import { useCallback, useEffect, useRef, useState } from 'react';

import { ApiError, networkError } from '@/api/errors';
import { Button, buttonClass, EmptyState, ErrorState, formatDateTime, Loading, Skeleton } from '@/components';
import { SignedOutState } from '@/shell/FrameStates';

import { AssignPmDrawer } from './AssignPmDrawer';
import { fetchBids, type BidRow } from './receivedBids';

import './rfp.css';

export const NEEDS_ACCESS = 'You need access to this RFP’s owner first';

type State = { status: 'loading' } | { status: 'error'; error: ApiError } | { status: 'ready'; rows: BidRow[]; cursor: string | null };

/** The deadline as the row says it: the date when there is one, else the status in words. */
export function deadlineText(row: Pick<BidRow, 'deadline' | 'deadline_status'>): string {
  if (row.deadline) return `Deadline ${formatDateTime(row.deadline)}`;
  if (row.deadline_status === 'unknown') return 'Deadline not known';
  if (row.deadline_status === 'not_stated') return 'No deadline stated';
  return `Deadline ${row.deadline_status.replace(/_/g, ' ')}`;
}

type Props = {
  /** The case whose drawer is open (from the address), if any. */
  openId?: string;
  /** Where a row's Assign button goes. */
  hrefFor: (caseId: string) => string;
  /** The drawer was closed. */
  onClose: () => void;
  pathname: string;
};

export function UnassignedBids({ openId, hrefFor, onClose, pathname }: Props) {
  const [state, setState] = useState<State>({ status: 'loading' });
  const [more, setMore] = useState<'idle' | 'loading' | 'error'>('idle');
  const seq = useRef(0);

  /** Page 1 again. Resolves to whether `openId` is still listed (null when the read failed). */
  const load = useCallback(async (): Promise<BidRow[] | null> => {
    const mine = ++seq.current;
    try {
      const page = await fetchBids();
      if (mine !== seq.current) return null;
      setState({ status: 'ready', rows: page.items, cursor: page.cursor });
      setMore('idle');
      return page.items;
    } catch (error) {
      if (mine === seq.current) setState({ status: 'error', error: error instanceof ApiError ? error : networkError() });
      return null;
    }
  }, []);
  useEffect(() => {
    // One read per opening; the effect only starts the request.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, [load]);

  const loadMore = async () => {
    if (state.status !== 'ready' || !state.cursor) return;
    setMore('loading');
    try {
      const page = await fetchBids(state.cursor);
      setState((prev) => (prev.status === 'ready' ? { status: 'ready', rows: [...prev.rows, ...page.items.filter((i) => !prev.rows.some((r) => r.case_id === i.case_id))], cursor: page.cursor } : prev));
      setMore('idle');
    } catch (error) {
      if (error instanceof ApiError && error.kind === 'unauthenticated') setState({ status: 'error', error });
      else setMore('error');
    }
  };

  const reloadList = useCallback(async () => {
    const rows = await load();
    return rows === null ? null : rows.some((row) => row.case_id === openId);
  }, [load, openId]);

  let body;
  if (state.status === 'loading') {
    body = (
      <div className="shell-loading">
        <Skeleton widths={[90, 70, 80]} />
        <Loading>Loading…</Loading>
      </div>
    );
  } else if (state.status === 'error' && state.error.kind === 'unauthenticated') {
    body = <SignedOutState pathname={pathname} />;
  } else if (state.status === 'error' && state.error.kind === 'forbidden') {
    body = (
      <EmptyState title="This queue isn’t open to your role.">
        {state.error.message}
        <br />
        <Link href="/my-work">Go to Needs me</Link>
      </EmptyState>
    );
  } else if (state.status === 'error') {
    body = <ErrorState title="We couldn’t load the RFPs waiting for a PM. Nothing was changed." onRetry={() => void load()} />;
  } else if (state.rows.length === 0) {
    body = <EmptyState title="Nothing is waiting for a PM.">New received RFPs will appear here.</EmptyState>;
  } else {
    body = (
      <>
        <ul className="rfp-bids">
          {state.rows.map((row) => (
            <li key={row.case_id} className="rfp-bids__row" data-case={row.case_id}>
              <span className="rfp-bids__what">
                <strong>{row.reference}</strong>
                <span className="psl-hint">
                  Received {formatDateTime(row.received_at)} · {deadlineText(row)}
                </span>
              </span>
              {row.owner_access_required ? (
                <span className="psl-hint">{NEEDS_ACCESS}</span>
              ) : (
                <Link href={hrefFor(row.case_id)} className={buttonClass('secondary', 'sm')} data-assign-link="">
                  Assign PM
                </Link>
              )}
            </li>
          ))}
        </ul>
        {state.cursor && (
          <Button kind="secondary" busy={more === 'loading'} busyLabel="Loading…" onClick={() => void loadMore()}>
            Load more
          </Button>
        )}
        {more === 'error' && <p className="psl-hint">We couldn’t load more. Try again.</p>}
      </>
    );
  }

  return (
    <>
      {body}
      {openId && <AssignPmDrawer key={openId} caseId={openId} reloadList={reloadList} onClose={onClose} pathname={pathname} />}
    </>
  );
}
