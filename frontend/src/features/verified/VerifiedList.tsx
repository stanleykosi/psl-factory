'use client';

// SCR-14 Verified outputs, from the live work list (queue=verified) only. Read-only: search, the line filter and
// Show more narrow or page the list; each title links to its work item, and "Open output" reads that one item on
// press. The server filters by access (INV-ACCESS); this component shows what it is sent and never reads roles.
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useState } from 'react';

import { call, liveApi } from '@/api/client';
import { Button, EmptyState, formatDayTime, ListToolbar, PageTitle, SampleLabel, Table, useIsPhone, type Column } from '@/components';
import { LineFilter, lineTitle, ownerText, shownText, useWorkList, WorkListError, WorkListFooter, WorkListLoading, workHref, type WorkLine, type WorkListRow } from '@/features/work-list';

import './verified.css';

const CAPTION = 'Verified outputs, in the order the factory reports them';
const NO_OUTPUT = 'No output file is attached to this item yet. Open the item to see its records.';
const OPEN_FAILED = 'We couldn’t open the output. Try again.';

/** Only a web address opens in a new tab. */
function openable(url: string): string | null {
  try {
    const parsed = new URL(url, window.location.origin);
    return parsed.protocol === 'https:' || parsed.protocol === 'http:' ? parsed.href : null;
  } catch {
    return null;
  }
}

/** "Open output": reads this one item when pressed (never ahead of time, never kept) and opens its `output_url`. */
function OpenOutput({ row }: { row: WorkListRow }) {
  const [phase, setPhase] = useState<'idle' | 'reading' | 'none' | 'failed'>('idle');
  const open = async () => {
    setPhase('reading');
    try {
      const item = await call(liveApi.GET('/api/v1/work/{work_id}', { params: { path: { work_id: row.id } } }));
      if (item.output_url === null) return setPhase('none');
      const href = openable(item.output_url);
      if (href === null) return setPhase('failed');
      window.open(href, '_blank', 'noopener,noreferrer');
      setPhase('idle');
    } catch {
      setPhase('failed');
    }
  };
  const noteId = `verified-note-${row.id}`;
  return (
    <div className="ver-open">
      <Button kind="secondary" size="sm" busy={phase === 'reading'} busyLabel="Opening…" aria-describedby={phase === 'none' || phase === 'failed' ? noteId : undefined} onClick={() => void open()}>
        Open output
      </Button>
      {(phase === 'none' || phase === 'failed') && (
        <p id={noteId} className="ver-note" role="status">
          {phase === 'none' ? NO_OUTPUT : OPEN_FAILED}
        </p>
      )}
    </div>
  );
}

/** Desktop (SCR-14-desktop): output, line, owner, last updated, and the Open output action. */
function VerifiedTable({ rows, lines }: { rows: WorkListRow[]; lines: WorkLine[] }) {
  const columns: Column<WorkListRow>[] = [
    {
      key: 'output',
      header: 'OUTPUT',
      cell: (row) => (
        <>
          <Link className="ver-title" href={workHref(row.id)}>
            {row.title}
          </Link>
          {row.sample && <SampleLabel />}
        </>
      ),
    },
    { key: 'line', header: 'LINE', cell: (row) => lineTitle(lines, row.line) },
    { key: 'owner', header: 'OWNER', cell: (row) => ownerText(row.owner) },
    {
      key: 'updated',
      header: 'LAST UPDATED',
      cell: (row) => <time dateTime={row.updated_at}>{formatDayTime(row.updated_at)}</time>,
    },
    { key: 'action', header: 'Actions', hideHeader: true, cell: (row) => <OpenOutput row={row} /> },
  ];
  return <Table className="ver-tablewrap" caption={CAPTION} columns={columns} rows={rows} rowKey={(row) => String(row.id)} empty="Nothing has been verified yet." />;
}

/** Phone (SCR-14-mobile): separate outlined cards; the title link covers the card, Open output sits above it. */
function VerifiedCards({ rows, lines }: { rows: WorkListRow[]; lines: WorkLine[] }) {
  return (
    <ul className="ver-cards" aria-label={CAPTION}>
      {rows.map((row) => (
        <li key={row.id} className="ver-card">
          <Link className="ver-title" href={workHref(row.id)}>
            {row.title}
          </Link>
          {row.sample && <SampleLabel />}
          <span className="ver-meta">
            {lineTitle(lines, row.line)} · {ownerText(row.owner)}
          </span>
          <span className="ver-meta">
            Last updated <time dateTime={row.updated_at}>{formatDayTime(row.updated_at)}</time>
          </span>
          <OpenOutput row={row} />
        </li>
      ))}
    </ul>
  );
}

export function VerifiedList() {
  const { state, filters, setFilters, retry, loadMore } = useWorkList({ queue: 'verified' });
  const pathname = usePathname() ?? '/verified';
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
    body = <WorkListError error={state.error} pathname={pathname} what="the verified outputs" onRetry={() => void retry()} />;
  } else if (state.status === 'loading') {
    body = <WorkListLoading>Loading verified outputs…</WorkListLoading>;
  } else if (state.items.length === 0 && state.more === 'done') {
    body = narrowed ? (
      <EmptyState level={2} title="No verified outputs match your search." className="wl-empty" action={<p><Button kind="secondary" onClick={clearAll}>Clear search</Button></p>}>
        Try other words, or clear them to see every verified output.
      </EmptyState>
    ) : (
      <EmptyState level={2} title="Nothing has been verified yet." className="wl-empty">
        Outputs appear here once the factory has verified them.
      </EmptyState>
    );
  } else {
    body = (
      <>
        {state.items.length > 0 && (phone ? <VerifiedCards rows={state.items} lines={state.lines} /> : <VerifiedTable rows={state.items} lines={state.lines} />)}
        <WorkListFooter more={state.more} onMore={() => void loadMore()} coverage={state.coverage} asOf={state.asOf} />
      </>
    );
  }

  const ready = state.status === 'ready' ? state : null;
  const lineChip = ready?.lineOptions.find((line) => line.key === filters.line);
  return (
    <div className="ver-page">
      <header className="ver-header">
        <PageTitle>Verified outputs</PageTitle>
      </header>
      {state.status !== 'error' && (
        <div role="search">
          <ListToolbar
            className="ver-toolbar"
            search={{ label: 'Search', placeholder: 'Search verified outputs', value: text, onChange: setText, onSearch: applySearch }}
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
