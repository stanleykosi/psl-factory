'use client';

// SCR-10 All exceptions list, from E-EXCEPTIONS only. Read-only: the controls narrow or page the list (search, Filter,
// rows per page, Show more, Try again), and each row links to its work item, where any action lives. The backend
// filters by grants (INV-ACCESS); this component shows exactly the rows it is sent and never reads roles.
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useState } from 'react';

import { Button, Callout, EmptyState, formatDayTime, ListToolbar, PageTitle, Segmented, ShowMore, Table, Tag, useIsPhone, type Column } from '@/components';
import { LoadingState, SignedOutState } from '@/shell/FrameStates';
import { WorkErrorCard } from '@/features/work-item/WorkItemStates';

import { ExceptionsFilter } from './ExceptionsFilter';
import { EXCEPTIONS_LIMITS, KIND_TAGS, sinceText } from './labels';
import type { ExceptionKind, ExceptionRow, ExceptionsLimit } from './types';
import { useExceptions } from './useExceptions';

import './exceptions.css';

const CAPTION = 'Exceptions, in the order the factory reports them';

const workHref = (row: ExceptionRow) => `/work/${encodeURIComponent(row.work_id)}`;

function KindTag({ row }: { row: ExceptionRow }) {
  const tag = KIND_TAGS[row.what];
  return <Tag tone={tag.tone}>{tag.words}</Tag>;
}

/** Desktop (SCR-10-desktop): the tag with "since" beneath, the title with its reference beneath, doing, who acts. */
function ExceptionsTable({ rows, asOf }: { rows: ExceptionRow[]; asOf: string }) {
  const columns: Column<ExceptionRow>[] = [
    {
      key: 'what',
      header: 'WHAT HAPPENED',
      cell: (row) => (
        <>
          <KindTag row={row} />
          <time className="exc-since" dateTime={row.since} title={formatDayTime(row.since)}>
            {sinceText(row.since, asOf)}
          </time>
        </>
      ),
    },
    {
      key: 'work',
      header: 'WORK',
      cell: (row) => (
        <>
          <Link className="exc-title" href={workHref(row)}>
            {row.title}
          </Link>
          {row.ref && <span className="exc-ref">{row.ref}</span>}
        </>
      ),
    },
    { key: 'doing', header: 'WHAT’S BEING DONE', cell: (row) => <span className="exc-doing">{row.doing}</span> },
    { key: 'who', header: 'WHO ACTS', cell: (row) => <span className="exc-who">{row.who_acts}</span> },
  ];
  return <Table className="exc-tablewrap" caption={CAPTION} columns={columns} rows={rows} rowKey={(row) => `${row.work_id}:${row.what}:${row.since}`} empty="No exceptions." />;
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

function NoAccess() {
  return (
    <EmptyState level={2} title="This list is for Leads" className="exc-empty" action={<Link href="/my-work">Go to My work</Link>}>
      Your own exceptions appear in My work, under Needs me.
    </EmptyState>
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

  // Search: the box keeps what the person typed; the request takes the settled search (SearchField's pause).
  const [text, setText] = useState('');
  const applySearch = (value: string) => {
    const q = value.trim() || undefined;
    setFilters((f) => (f.q === q ? f : { ...f, q }));
  };

  const applyKind = (what: ExceptionKind | undefined) => {
    setFilterOpen(false);
    setFilters((f) => ({ ...f, what }));
  };
  const clearAll = () => {
    setText('');
    setFilters({});
  };

  const narrowed = Boolean(filters.q || filters.what);
  const ready = state.status === 'ready' ? state : null;

  let body;
  if (state.status === 'error') {
    const { error } = state;
    if (error.kind === 'unauthenticated') body = <SignedOutState pathname={pathname} />;
    else if (error.kind === 'forbidden' || error.kind === 'not_found') body = <NoAccess />;
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
    const asOf = <p className="exc-note">As of {formatDayTime(state.asOf)}</p>;
    const seeAll = compact && (
      <p className="exc-seeall">
        <Link href={seeAllHref} className="cmp-target">
          See all exceptions
        </Link>
      </p>
    );
    if (state.items.length === 0) {
      body = (
        <>
          {narrowed && !compact ? (
            <EmptyState level={2}
              title="No exceptions match your search and filter."
              className="exc-empty"
              action={
                <p>
                  <Button kind="secondary" onClick={clearAll}>
                    Clear search and filter
                  </Button>
                </p>
              }
            >
              Try other words, or clear them to see every exception.
            </EmptyState>
          ) : (
            <EmptyState level={2} title="No exceptions." className="exc-empty">
              Everything is moving or verified.
            </EmptyState>
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
              <ShowMore className="exc-shown" shown={state.items.length} hasMore={Boolean(state.nextCursor)} busy={state.more === 'loading'} onMore={() => void showMore()} />
              <span className="exc-note">As of {formatDayTime(state.asOf)}</span>
              <span className="exc-rows">
                <span className="exc-rowslabel" aria-hidden="true">
                  ROWS PER PAGE
                </span>
                <Segmented
                  label="Rows per page"
                  phone={phone}
                  options={EXCEPTIONS_LIMITS.map((n) => ({ value: String(n), label: String(n) }))}
                  value={String(limit)}
                  onChange={(value) => setLimit(Number(value) as ExceptionsLimit)}
                />
              </span>
            </div>
          )}
          {!compact && state.more === 'failed' && <Callout kind="problem">We couldn’t load more exceptions. Choose Show more to try again.</Callout>}
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

  return (
    <div className="exc-page">
      <header className="exc-header">
        <PageTitle>{phone ? (openCount === undefined ? 'Exceptions' : `Exceptions · ${openCount}`) : 'All exceptions'}</PageTitle>
        {phone && (
          // The board draws "← Queue" in the phone top bar, which the app frame owns; until it does, it sits here.
          <Link className="exc-back" href="/my-work">
            ← Queue
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
        <div role="search">
          <ListToolbar
            className="exc-toolbar"
            search={{ label: 'Search', placeholder: 'Search exceptions', value: text, onChange: setText, onSearch: applySearch }}
            filterCount={filters.what ? 1 : 0}
            filterOpen={filterOpen}
            onFilterToggle={() => setFilterOpen((open) => !open)}
            filterPanel={<ExceptionsFilter applied={filters.what} onApply={applyKind} onClose={() => setFilterOpen(false)} />}
            resultText={!phone && openCount !== undefined ? `${openCount} OPEN` : ''}
            chips={filters.what ? [{ key: 'what', name: 'What happened', value: KIND_TAGS[filters.what].words, onRemove: () => applyKind(undefined) }] : []}
            onClearAll={clearAll}
          />
        </div>
      )}
      {body}
    </div>
  );
}
