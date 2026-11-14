'use client';

// SCR-10 All exceptions list, from E-EXCEPTIONS only. Read-only: the controls narrow or page the list (search, Filter,
// rows per page, Show more, Try again), and each row links to its work item, where any action lives. The backend
// filters by grants (INV-ACCESS); this component shows exactly the rows it is sent and never reads roles.
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useCallback, useEffect, useRef, useState, useSyncExternalStore, type FormEvent, type KeyboardEvent } from 'react';

import { LoadingState, SignedOutState } from '@/shell/FrameStates';
import { WarningIcon } from '@/shell/icons';
import { FilterIcon, SearchIcon } from '@/features/my-work/icons';
import { formatWat } from '@/features/work-item/labels';
import { WorkErrorCard } from '@/features/work-item/WorkItemStates';

import { ExceptionsFilter } from './ExceptionsFilter';
import { EXCEPTIONS_LIMITS, KIND_TAGS, sinceText } from './labels';
import type { ExceptionKind, ExceptionRow, ExceptionsLimit } from './types';
import { useExceptions } from './useExceptions';

import './exceptions.css';

const PHONE_QUERY = '(max-width: 719.98px)';
const SEARCH_DEBOUNCE_MS = 300;
const CAPTION = 'Exceptions, in the order the factory reports them';

function subscribePhone(onChange: () => void) {
  if (typeof window.matchMedia !== 'function') return () => {};
  const media = window.matchMedia(PHONE_QUERY);
  media.addEventListener('change', onChange);
  return () => media.removeEventListener('change', onChange);
}
const isPhoneNow = () => typeof window.matchMedia === 'function' && window.matchMedia(PHONE_QUERY).matches;

/** Below 720px the rows are cards and Filter is an icon button with a bottom sheet. */
function useIsPhone() {
  return useSyncExternalStore(subscribePhone, isPhoneNow, () => false);
}

const workHref = (row: ExceptionRow) => `/work/${encodeURIComponent(row.work_id)}`;

function KindTag({ row }: { row: ExceptionRow }) {
  const tag = KIND_TAGS[row.what];
  return <span className={tag.className}>{tag.text}</span>;
}

/** Desktop (SCR-10-desktop): the tag with "since" beneath, the title with its reference beneath, doing, who acts. */
function ExceptionsTable({ rows, asOf }: { rows: ExceptionRow[]; asOf: string }) {
  return (
    <div className="psl-tablewrap">
      <table className="psl-table exc-table">
        <caption className="exc-sr">{CAPTION}</caption>
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
                <KindTag row={row} />
                <time className="exc-since" dateTime={row.since} title={formatWat(row.since)}>
                  {sinceText(row.since, asOf)}
                </time>
              </td>
              <td>
                <Link className="exc-title" href={workHref(row)}>
                  {row.title}
                </Link>
                {row.ref && <span className="exc-ref">{row.ref}</span>}
              </td>
              <td className="exc-doing">{row.doing}</td>
              <td className="exc-who">{row.who_acts}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** Phone (SCR-10-mobile): separate outlined cards (tag, title, what's being done); the title link covers the whole card. */
function ExceptionsCards({ rows }: { rows: ExceptionRow[] }) {
  return (
    <ul className="exc-cards" aria-label={CAPTION}>
      {rows.map((row, i) => (
        <li key={i} className="exc-card">
          <KindTag row={row} />
          <Link className="exc-title" href={workHref(row)}>
            {row.title}
          </Link>
          <span className="exc-doing">{row.doing}</span>
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
  /** The page size first requested; later changes to the prop are ignored (the person picks rows per page). */
  limit?: ExceptionsLimit;
  /** Embedded mode: rows, "As of" and a "See all exceptions" link; no header, search, paging chrome or footer. */
  compact?: boolean;
  /** Compact mode only: render the first n rows received (display only; never reorders). */
  maxRows?: number;
  seeAllHref?: string;
};

export function ExceptionsList({ limit: initialLimit = 20, compact = false, maxRows, seeAllHref = '/exceptions' }: ExceptionsListProps) {
  const { state, limit, setLimit, filters, setFilters, retry, showMore } = useExceptions({ limit: initialLimit });
  const pathname = usePathname() ?? '/exceptions';
  const phone = useIsPhone();
  const [filterOpen, setFilterOpen] = useState(false);
  const filterButton = useRef<HTMLButtonElement>(null);

  // Search: the box keeps what the person typed; the request takes it 300 ms after the last keystroke.
  const [text, setText] = useState('');
  const debounce = useRef<ReturnType<typeof setTimeout>>(undefined);
  useEffect(() => () => clearTimeout(debounce.current), []);
  const applySearch = (value: string) => {
    clearTimeout(debounce.current);
    const q = value.trim() || undefined;
    setFilters((f) => (f.q === q ? f : { ...f, q }));
  };
  const onSearchInput = (value: string) => {
    setText(value);
    clearTimeout(debounce.current);
    debounce.current = setTimeout(() => applySearch(value), SEARCH_DEBOUNCE_MS);
  };
  const onSearchSubmit = (event: FormEvent) => {
    event.preventDefault();
    applySearch(text);
  };

  const closeFilter = useCallback(() => {
    setFilterOpen(false);
    filterButton.current?.focus();
  }, []);
  const applyKind = (what: ExceptionKind | undefined) => {
    closeFilter();
    setFilters((f) => ({ ...f, what }));
  };
  const clearAll = () => {
    clearTimeout(debounce.current);
    setText('');
    setFilters({});
  };

  const onLimitKey = (event: KeyboardEvent<HTMLButtonElement>, index: number) => {
    const step = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }[event.key];
    if (step === undefined) return;
    event.preventDefault();
    const next = (index + step + EXCEPTIONS_LIMITS.length) % EXCEPTIONS_LIMITS.length;
    event.currentTarget.parentElement?.querySelectorAll<HTMLElement>('[role="radio"]')[next]?.focus();
    setLimit(EXCEPTIONS_LIMITS[next]);
  };

  const narrowed = Boolean(filters.q || filters.what);
  const ready = state.status === 'ready' ? state : null;

  let body;
  if (state.status === 'error') {
    const { error } = state;
    if (error.kind === 'unauthenticated') body = <SignedOutState pathname={pathname} />;
    else if (error.kind === 'forbidden' || error.kind === 'not_found') body = <NoAccess compact={compact} />;
    else {
      body = (
        <WorkErrorCard
          message="We couldn’t load the exceptions. Your work is safe; nothing was changed."
          error={error}
          onRetry={() => void retry()}
        />
      );
    }
  } else if (state.status === 'loading') {
    body = <LoadingState />;
  } else {
    const asOf = <p className="exc-note">As of {formatWat(state.asOf)}</p>;
    const seeAll = compact && (
      <p className="exc-seeall">
        <Link href={seeAllHref}>See all exceptions</Link>
      </p>
    );
    const Heading = compact ? 'h3' : 'h2';
    if (state.items.length === 0) {
      body = (
        <>
          {narrowed && !compact ? (
            <div className="psl-empty exc-empty">
              <Heading>No exceptions match your search and filter.</Heading>
              <p>Try other words, or clear them to see every exception.</p>
              <p>
                <button type="button" className="psl-btn psl-btn--secondary" onClick={clearAll}>
                  Clear search and filter
                </button>
              </p>
            </div>
          ) : (
            <div className="psl-empty exc-empty">
              <Heading>No exceptions.</Heading>
              <p>Everything is moving or verified.</p>
            </div>
          )}
          {asOf}
          {seeAll}
        </>
      );
    } else {
      const rows = compact && maxRows !== undefined ? state.items.slice(0, maxRows) : state.items;
      body = (
        <>
          {phone ? <ExceptionsCards rows={rows} /> : <ExceptionsTable rows={rows} asOf={state.asOf} />}
          {compact ? (
            asOf
          ) : (
            <div className="exc-foot">
              <span className="exc-shown">Showing {state.items.length}</span>
              <span className="exc-note">As of {formatWat(state.asOf)}</span>
              <span className="exc-rows">
                <span className="exc-rowslabel" aria-hidden="true">
                  ROWS PER PAGE
                </span>
                <span role="radiogroup" aria-label="Rows per page" className={phone ? 'psl-seg psl-seg--phone' : 'psl-seg'}>
                  {EXCEPTIONS_LIMITS.map((n, i) => (
                    <button
                      key={n}
                      type="button"
                      role="radio"
                      aria-checked={n === limit}
                      tabIndex={n === limit ? 0 : -1}
                      className="psl-seg__opt"
                      onClick={() => setLimit(n)}
                      onKeyDown={(e) => onLimitKey(e, i)}
                    >
                      {n}
                    </button>
                  ))}
                </span>
              </span>
              {state.nextCursor && (
                <button
                  type="button"
                  className={state.more === 'loading' ? 'psl-btn psl-btn--secondary psl-btn--sm exc-more is-busy' : 'psl-btn psl-btn--secondary psl-btn--sm exc-more'}
                  aria-disabled={state.more === 'loading' || undefined}
                  onClick={() => {
                    if (state.more !== 'loading') void showMore();
                  }}
                >
                  Show more
                </button>
              )}
            </div>
          )}
          {!compact && state.more === 'failed' && (
            <div className="psl-callout psl-callout--warning">
              <WarningIcon />
              <span>We couldn&rsquo;t load more exceptions. Choose Show more to try again.</span>
            </div>
          )}
          {seeAll}
          {!compact && (
            <p className="exc-footer">
              The factory never resends after an unknown outcome until it has checked for a receipt. Nothing here is lost;
              each item resumes where it stopped.
            </p>
          )}
        </>
      );
    }
  }

  if (compact) return <div className="exc-list">{body}</div>;

  // The open total is a proposal field: drawn only when the backend sends it, never counted from loaded rows.
  const openCount = ready?.openCount;
  const searchable = state.status !== 'error';
  const filterProps = {
    ref: filterButton,
    type: 'button' as const,
    'aria-haspopup': 'dialog' as const,
    'aria-expanded': filterOpen,
    onClick: () => (filterOpen ? closeFilter() : setFilterOpen(true)),
  };
  const filterBadge = filters.what && <span className="psl-badge psl-badge--signal">1</span>;
  const filterPanel = filterOpen && (
    <ExceptionsFilter phone={phone} applied={filters.what} anchor={filterButton} onApply={applyKind} onClose={closeFilter} />
  );

  return (
    <div className="exc-page">
      <header className="exc-header">
        <h1 className="shell-title exc-h1">
          {phone ? (openCount === undefined ? 'Exceptions' : `Exceptions · ${openCount}`) : 'All exceptions'}
        </h1>
        {phone && (
          // The board draws "← Queue" in the phone top bar, which the app frame owns; until it does, it sits here.
          <Link className="exc-back" href="/my-work">
            &larr; Queue
          </Link>
        )}
        {!phone && (
          <p className="exc-intro">
            Everyone&rsquo;s work that can&rsquo;t move on by itself, across every line you can see: an outcome we
            couldn&rsquo;t confirm, a missing owner or rule, or a check that failed.
          </p>
        )}
      </header>
      {searchable && (
        <div className="exc-toolbar">
          <form role="search" className="psl-toolbar" onSubmit={onSearchSubmit}>
            <div className="psl-search exc-search">
              <SearchIcon />
              <label className="exc-sr" htmlFor="exc-q">
                Search
              </label>
              <input
                id="exc-q"
                type="search"
                className="psl-input"
                placeholder="Search exceptions"
                value={text}
                onChange={(e) => onSearchInput(e.target.value)}
              />
            </div>
            <div className="exc-filter">
              {phone ? (
                <button {...filterProps} className="psl-iconbtn exc-iconbtn" aria-label="Filter">
                  <FilterIcon />
                  {filterBadge}
                </button>
              ) : (
                <button {...filterProps} className="psl-btn psl-btn--secondary">
                  <FilterIcon />
                  Filter
                  {filterBadge}
                </button>
              )}
              {!phone && filterPanel}
            </div>
            {!phone && openCount !== undefined && <span className="psl-resultcount">{openCount} OPEN</span>}
          </form>
          {filters.what && (
            <div className="exc-chips">
              <span className="psl-chip">
                <span>What happened</span>
                <strong>{KIND_TAGS[filters.what].words}</strong>
                <button type="button" aria-label="Remove What happened filter" onClick={() => applyKind(undefined)}>
                  ×
                </button>
              </span>
            </div>
          )}
        </div>
      )}
      {phone && filterPanel}
      {body}
    </div>
  );
}
