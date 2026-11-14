'use client';

// SCR-10 All exceptions list, from E-EXCEPTIONS only. Read-only: the only controls are rows per page, Show more
// and Try again, and each row links to its work item, where any action lives. The backend filters by grants
// (INV-ACCESS); this component shows exactly the rows it is sent and never reads roles.
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useSyncExternalStore } from 'react';

import { LoadingState, SignedOutState } from '@/shell/FrameStates';
import { WarningIcon } from '@/shell/icons';
import { formatWat } from '@/features/work-item/labels';
import { WorkErrorCard } from '@/features/work-item/WorkItemStates';

import { EXCEPTIONS_LIMITS, KIND_TAGS, sinceText } from './labels';
import type { ExceptionRow, ExceptionsLimit } from './types';
import { useExceptions } from './useExceptions';

import './exceptions.css';

const PHONE_QUERY = '(max-width: 719.98px)';

function subscribePhone(onChange: () => void) {
  if (typeof window.matchMedia !== 'function') return () => {};
  const media = window.matchMedia(PHONE_QUERY);
  media.addEventListener('change', onChange);
  return () => media.removeEventListener('change', onChange);
}
const isPhoneNow = () => typeof window.matchMedia === 'function' && window.matchMedia(PHONE_QUERY).matches;

/** Below 720px the rows are cards. */
function useIsPhone() {
  return useSyncExternalStore(subscribePhone, isPhoneNow, () => false);
}

const workHref = (row: ExceptionRow) => `/work/${encodeURIComponent(row.work_id)}`;

function Since({ row, asOf }: { row: ExceptionRow; asOf: string }) {
  return (
    <time className="exc-since" dateTime={row.since} title={formatWat(row.since)}>
      {sinceText(row.since, asOf)}
    </time>
  );
}

function KindTag({ row }: { row: ExceptionRow }) {
  const tag = KIND_TAGS[row.what];
  return <span className={tag.className}>{tag.text}</span>;
}

function ExceptionsTable({ rows, asOf }: { rows: ExceptionRow[]; asOf: string }) {
  return (
    <table className="psl-table exc-table">
      <caption className="exc-sr">Exceptions, in the order the factory reports them</caption>
      <thead>
        <tr>
          <th scope="col">WHAT HAPPENED</th>
          <th scope="col">WORK</th>
          <th scope="col">WHAT&rsquo;S BEING DONE</th>
          <th scope="col">WHO ACTS</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row, i) => (
          <tr key={i}>
            <td>
              <span className="exc-what">
                <KindTag row={row} />
                <Since row={row} asOf={asOf} />
              </span>
            </td>
            <td>
              <Link className="exc-title" href={workHref(row)}>
                {row.title}
              </Link>
            </td>
            <td>{row.doing}</td>
            <td>{row.who_acts}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function ExceptionsCards({ rows, asOf }: { rows: ExceptionRow[]; asOf: string }) {
  return (
    <ul className="exc-cards" aria-label="Exceptions, in the order the factory reports them">
      {rows.map((row, i) => (
        <li key={i} className="exc-card">
          <span className="exc-what">
            <KindTag row={row} />
            <Since row={row} asOf={asOf} />
          </span>
          <Link className="exc-title" href={workHref(row)}>
            {row.title}
          </Link>
          <span className="exc-doing">{row.doing}</span>
          <span className="exc-who">Who acts: {row.who_acts}</span>
        </li>
      ))}
    </ul>
  );
}

function NoAccess({ compact }: { compact: boolean }) {
  const Heading = compact ? 'h3' : 'h2';
  return (
    <div className="psl-empty exc-empty">
      <Heading>This list is for Leads</Heading>
      <p>Your own exceptions appear in My work, under Needs me.</p>
      <p>
        <Link href="/my-work">Go to My work</Link>
      </p>
    </div>
  );
}

export type ExceptionsListProps = {
  limit?: ExceptionsLimit;
  /** Embedded mode: rows, "As of" and a "See all exceptions" link; no paging chrome or footer. */
  compact?: boolean;
  /** Compact mode only: render the first n rows received (display only; never reorders). */
  maxRows?: number;
  seeAllHref?: string;
};

export function ExceptionsList({ limit: initialLimit = 20, compact = false, maxRows, seeAllHref = '/exceptions' }: ExceptionsListProps) {
  const { state, limit, setLimit, retry, showMore } = useExceptions({ limit: initialLimit });
  const pathname = usePathname() ?? '/exceptions';
  const phone = useIsPhone();

  if (state.status === 'error') {
    const { error } = state;
    if (error.kind === 'unauthenticated') return <SignedOutState pathname={pathname} />;
    if (error.kind === 'forbidden' || error.kind === 'not_found') return <NoAccess compact={compact} />;
    return (
      <WorkErrorCard
        message="We couldn’t load the exceptions. Your work is safe; nothing was changed."
        error={error}
        onRetry={() => void retry()}
      />
    );
  }

  const toolbar = !compact && (state.status === 'loading' || state.items.length > 0) && (
    <div className="exc-toolbar">
      {state.status === 'ready' && <span className="psl-mono exc-count">{state.items.length} shown</span>}
      <label className="exc-limit">
        <span>Rows per page</span>
        <select className="psl-input" value={limit} onChange={(e) => setLimit(Number(e.target.value) as ExceptionsLimit)}>
          {EXCEPTIONS_LIMITS.map((n) => (
            <option key={n} value={n}>
              {n}
            </option>
          ))}
        </select>
      </label>
    </div>
  );

  if (state.status === 'loading') {
    return (
      <div className="exc-list">
        {toolbar}
        <LoadingState />
      </div>
    );
  }

  const asOf = <p className="exc-note">As of {formatWat(state.asOf)}</p>;
  const seeAll = compact && (
    <p className="exc-seeall">
      <Link href={seeAllHref}>See all exceptions</Link>
    </p>
  );

  if (state.items.length === 0) {
    const Heading = compact ? 'h3' : 'h2';
    return (
      <div className="exc-list">
        <div className="psl-empty exc-empty">
          <Heading>No exceptions.</Heading>
          <p>Everything is moving or verified.</p>
        </div>
        {asOf}
        {seeAll}
      </div>
    );
  }

  const rows = compact && maxRows !== undefined ? state.items.slice(0, maxRows) : state.items;
  return (
    <div className="exc-list">
      {toolbar}
      <div className="psl-tablewrap exc-wrap">
        {phone ? <ExceptionsCards rows={rows} asOf={state.asOf} /> : <ExceptionsTable rows={rows} asOf={state.asOf} />}
        {!compact && state.nextCursor && (
          <div className="psl-showmore exc-showmore">
            <span>Showing {state.items.length}</span>
            <button
              type="button"
              className={state.more === 'loading' ? 'psl-btn psl-btn--text is-busy' : 'psl-btn psl-btn--text'}
              aria-disabled={state.more === 'loading' || undefined}
              onClick={() => {
                if (state.more !== 'loading') void showMore();
              }}
            >
              Show more
            </button>
          </div>
        )}
      </div>
      {!compact && state.more === 'failed' && (
        <div className="psl-callout psl-callout--warning">
          <WarningIcon />
          <span>We couldn&rsquo;t load more exceptions. Choose Show more to try again.</span>
        </div>
      )}
      {asOf}
      {seeAll}
      {!compact && (
        <p className="exc-footer">
          The factory never resends after an unknown outcome until it has checked for a receipt. Nothing here is lost;
          each item resumes where it stopped.
        </p>
      )}
    </div>
  );
}
