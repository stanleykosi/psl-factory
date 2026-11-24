'use client';

// SCR-10 All exceptions list, from the live work list (queue=exceptions) only. Read-only: search, the line filter and
// Show more narrow or page the list, and each row links to its work item, where any action lives. The server
// filters by access (INV-ACCESS); this component shows exactly the rows it is sent and never reads roles.
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useState } from 'react';

import { Button, EmptyState, formatDayTime, ListToolbar, PageTitle, SampleLabel, Table, Tag, useIsPhone, type Column } from '@/components';
import { LineFilter, ownerText, shownText, stateTag, useWorkList, WorkListError, WorkListFooter, WorkListLoading, workHref, type WorkListRow } from '@/features/work-list';

import './exceptions.css';

const CAPTION = 'Exceptions, in the order the factory reports them';

function RowTag({ row }: { row: WorkListRow }) {
  const { text, tone } = stateTag(row.state);
  return <Tag tone={tone}>{text}</Tag>;
}

const Updated = ({ row }: { row: WorkListRow }) => (
  <time className="exc-since" dateTime={row.updated_at}>
    Last updated {formatDayTime(row.updated_at)}
  </time>
);

/** Desktop (SCR-10-desktop): the tag with the last update beneath, the title, what is being done, who acts. */
function ExceptionsTable({ rows }: { rows: WorkListRow[] }) {
  const columns: Column<WorkListRow>[] = [
    {
      key: 'what',
      header: 'WHAT HAPPENED',
      cell: (row) => (
        <>
          <RowTag row={row} />
          <Updated row={row} />
        </>
      ),
    },
    {
      key: 'work',
      header: 'WORK',
      cell: (row) => (
        <>
          <Link className="exc-title" href={workHref(row.id)}>
            {row.title}
          </Link>
          {row.sample && <SampleLabel />}
        </>
      ),
    },
    { key: 'doing', header: 'WHAT’S BEING DONE', cell: (row) => <span className="exc-doing">{row.status_label}</span> },
    { key: 'who', header: 'WHO ACTS', cell: (row) => <span className="exc-who">{ownerText(row.owner)}</span> },
  ];
  return <Table className="exc-tablewrap" caption={CAPTION} columns={columns} rows={rows} rowKey={(row) => String(row.id)} empty="No exceptions right now." />;
}

/** Phone (SCR-10-mobile): separate outlined cards (tag, title, what's being done); the title link covers the whole card. */
function ExceptionsCards({ rows }: { rows: WorkListRow[] }) {
  return (
    <ul className="exc-cards" aria-label={CAPTION}>
      {rows.map((row) => (
        <li key={row.id} className="exc-card">
          <RowTag row={row} />
          <Link className="exc-title" href={workHref(row.id)}>
            {row.title}
          </Link>
          {row.sample && <SampleLabel />}
          <span className="exc-doing">{row.status_label}</span>
          <span className="exc-doing">
            {ownerText(row.owner)} · <time dateTime={row.updated_at}>Last updated {formatDayTime(row.updated_at)}</time>
          </span>
        </li>
      ))}
    </ul>
  );
}

export function ExceptionsList() {
  const { state, filters, setFilters, retry, loadMore } = useWorkList({ queue: 'exceptions' });
  const pathname = usePathname() ?? '/exceptions';
  const phone = useIsPhone();
  const [filterOpen, setFilterOpen] = useState(false);

  // Search: the box keeps what the person typed; the request takes the settled search (SearchField's pause).
  const [text, setText] = useState('');
  const applySearch = (value: string) => {
    const q = value.trim() || undefined;
    setFilters((f) => (f.q === q ? f : { ...f, q }));
  };
  const clearAll = () => {
    setText('');
    setFilters({});
  };
  const narrowed = Boolean(filters.q || filters.line);

  let body;
  if (state.status === 'error') {
    body = <WorkListError error={state.error} pathname={pathname} what="the exceptions" onRetry={() => void retry()} />;
  } else if (state.status === 'loading') {
    body = <WorkListLoading>Loading exceptions…</WorkListLoading>;
  } else if (state.items.length === 0 && state.more === 'done') {
    body = narrowed ? (
      <EmptyState level={2} title="No exceptions match your search." className="wl-empty" action={<p><Button kind="secondary" onClick={clearAll}>Clear search</Button></p>}>
        Try other words, or clear them to see every exception.
      </EmptyState>
    ) : (
      <EmptyState level={2} title="No exceptions right now." className="wl-empty">
        Everything is moving or verified.
      </EmptyState>
    );
  } else {
    body = (
      <>
        {state.items.length > 0 && (phone ? <ExceptionsCards rows={state.items} /> : <ExceptionsTable rows={state.items} />)}
        <WorkListFooter more={state.more} onMore={() => void loadMore()} coverage={state.coverage} asOf={state.asOf} />
        <p className="exc-footer">
          The factory never resends after an unknown outcome until it has checked for a receipt. Nothing here is lost;
          each item resumes where it stopped.
        </p>
      </>
    );
  }

  const ready = state.status === 'ready' ? state : null;
  const lineChip = ready?.lineOptions.find((line) => line.key === filters.line);
  return (
    <div className="exc-page">
      <header className="exc-header">
        <PageTitle>All exceptions</PageTitle>
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
      {state.status !== 'error' && (
        <div role="search">
          <ListToolbar
            className="exc-toolbar"
            search={{ label: 'Search', placeholder: 'Search exceptions', value: text, onChange: setText, onSearch: applySearch }}
            filterCount={filters.line ? 1 : 0}
            filterOpen={filterOpen}
            onFilterToggle={() => setFilterOpen((open) => !open)}
            filterPanel={
              <LineFilter
                lines={ready?.lineOptions ?? []}
                applied={filters.line}
                onApply={(line) => {
                  setFilterOpen(false);
                  setFilters((f) => ({ ...f, line }));
                }}
                onClose={() => setFilterOpen(false)}
              />
            }
            resultText={ready && !(ready.items.length === 0 && ready.more === 'done') ? shownText(ready.items.length, ready.more) : ''}
            chips={filters.line ? [{ key: 'line', name: 'Line', value: lineChip?.title ?? filters.line, onRemove: () => setFilters((f) => ({ ...f, line: undefined })) }] : []}
            onClearAll={clearAll}
          />
        </div>
      )}
      {body}
    </div>
  );
}
