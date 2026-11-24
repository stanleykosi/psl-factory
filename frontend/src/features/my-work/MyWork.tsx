'use client';

import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { call, liveApi } from '@/api/client';
import { Button, EmptyState, ListToolbar, ShowMore, Tabs, useIsPhone, type FilterChip, type ShowMoreProps } from '@/components';
import { coverageNotes, useWorkCounts, useWorkList, WorkListLoading, type LineKey } from '@/features/work-list';
import { SignedOutState } from '@/shell/FrameStates';

import { CaughtUp } from './CaughtUp';
import { MyWorkFilter, useProjects, type Filters, type Preview } from './FilterPanel';
import { filterCount as countFilters, formatTime, isNarrowed, parseView, QUEUES, recordsText, resultCount, showUnassigned, stateWords, tabCount, viewSearch, type View } from './model';
import { StartedCards, WorkCards, WorkTable } from './WorkRows';

export const POLL_MS = 15_000;
const PANEL_ID = 'my-work-panel';

/** SCR-01 My work: a person's queues from the live work list, with counts, search, filters, paging and live refresh. */
export function MyWork() {
  const params = useSearchParams();
  const router = useRouter();
  const view = useMemo(() => parseView(new URLSearchParams(params?.toString() ?? '')), [params]);
  const phone = useIsPhone();
  const unassigned = view.queue === 'unassigned';

  // The list reads page 1 again whenever one of these changes; the Unassigned tab's body is not this list.
  const { state: list, loadMore, retry, refresh: refreshList } = useWorkList({ queue: view.queue, line: view.line, q: view.q, project: view.project, state: view.state, limit: view.limit, enabled: !unassigned });
  const { state: countsState, refresh: refreshCounts } = useWorkCounts();
  const counts = countsState.status === 'ready' ? countsState.counts : undefined;
  const projects = useProjects();
  // The view whose last refresh failed; a new view starts clean.
  const [failedView, setFailedView] = useState<string>();
  const [filterOpen, setFilterOpen] = useState(false);

  const lastSuccess = useRef(0);
  const [lastLoaded, setLastLoaded] = useState<string>();
  const focusRow = useRef<number | null>(null);
  const viewRef = useRef(view);
  const panel = useRef<HTMLDivElement>(null);
  const pollable = useRef(false);

  const navigate = useCallback(
    (next: Partial<View>) => router.replace(`/my-work${viewSearch({ ...viewRef.current, ...next })}`, { scroll: false }),
    [router],
  );

  const ready = list.status === 'ready' && !unassigned ? list : undefined;
  useEffect(() => {
    viewRef.current = view;
  }, [view]);
  useEffect(() => {
    if (ready) {
      lastSuccess.current = Date.now();
      /* eslint-disable react-hooks/set-state-in-effect */
      setLastLoaded(ready.asOf);
      /* eslint-enable react-hooks/set-state-in-effect */
    }
  }, [ready?.asOf]); // eslint-disable-line react-hooks/exhaustive-deps
  const rowCount = ready?.items.length ?? 0;
  useEffect(() => {
    pollable.current = !unassigned && list.status === 'ready';
    // Show more: the keyboard moves to the first row it added.
    if (focusRow.current !== null && rowCount > focusRow.current) {
      panel.current?.querySelectorAll<HTMLElement>('[data-work-link]')[focusRow.current]?.focus();
      focusRow.current = null;
    }
  }, [list.status, rowCount, unassigned]);

  // D-UPDATES: every 15 s while the tab is visible; on return, at once if the data is older than 15 s. A failed refresh keeps what is shown.
  const refresh = useCallback(async () => {
    const [listed, counted] = await Promise.all([refreshList(), refreshCounts()]);
    setFailedView(listed && counted ? undefined : viewSearch(viewRef.current));
    if (listed && counted) lastSuccess.current = Date.now();
  }, [refreshList, refreshCounts]);
  const refreshRef = useRef(refresh);
  useEffect(() => {
    refreshRef.current = refresh;
  }, [refresh]);
  useEffect(() => {
    let timer: ReturnType<typeof setInterval> | undefined;
    const tick = () => {
      if (pollable.current) void refreshRef.current();
    };
    const start = () => {
      clearInterval(timer);
      timer = setInterval(tick, POLL_MS);
    };
    const onVisibility = () => {
      if (document.visibilityState === 'visible') {
        if (Date.now() - lastSuccess.current > POLL_MS) tick();
        start();
      } else {
        clearInterval(timer);
      }
    };
    if (document.visibilityState === 'visible') start();
    document.addEventListener('visibilitychange', onVisibility);
    return () => {
      clearInterval(timer);
      document.removeEventListener('visibilitychange', onVisibility);
    };
  }, []);

  // Search: the box keeps what the person typed; the URL takes it once the search field settles (2+ characters, or cleared).
  const [text, setText] = useState(view.q ?? '');
  const [syncedQ, setSyncedQ] = useState(view.q);
  if (view.q !== syncedQ) {
    setSyncedQ(view.q);
    if ((text.trim() || undefined) !== view.q) setText(view.q ?? '');
  }
  const applySearch = (value: string) => {
    const q = value.trim() || undefined;
    if (q !== viewRef.current.q) navigate({ q });
  };

  const toolbar = useRef<HTMLFormElement>(null);
  // The bottom sheet does not hand focus back to the Filter button on its own; the popover does.
  const filterButton = useRef<HTMLElement | null>(null);
  const filterWasOpen = useRef(false);
  const closeFilter = useCallback(() => setFilterOpen(false), []);
  useEffect(() => {
    filterButton.current = toolbar.current?.querySelector<HTMLElement>('.cmp-anchor button') ?? null;
    if (filterOpen) filterWasOpen.current = true;
    else if (filterWasOpen.current) {
      filterWasOpen.current = false;
      filterButton.current?.focus();
    }
  }, [filterOpen]);
  const applyFilters = (filters: Filters) => {
    closeFilter();
    navigate({ line: filters.line, project: filters.project, state: filters.state });
  };
  // "Show N items" in the filter panel: a one-page preview of the same list with the draft filters; the count is used only when the server marks it complete.
  const preview = useCallback(async (filters: Filters): Promise<Preview> => {
    const { queue, q } = viewRef.current;
    const data = await call(liveApi.GET('/api/v1/work', { params: { query: { queue, page: 1, limit: 8, ...(q && { q }), ...filters } } }));
    return data.total_coverage === 'complete' && data.total !== null ? { count: data.total } : undefined;
  }, []);
  const removeFilter = (filters: Filters) => navigate(filters);

  if (list.status === 'error' && !unassigned && list.error.kind === 'unauthenticated') return <SignedOutState pathname="/my-work" />;
  if (countsState.status === 'error' && countsState.error.kind === 'unauthenticated') return <SignedOutState pathname="/my-work" />;

  const shownTabs = QUEUES.filter((x) => x.key !== 'unassigned' || showUnassigned(counts, view.queue));
  const current = QUEUES.find((x) => x.key === view.queue)!;
  const filterCount = countFilters(view);
  const narrowed = isNarrowed(view);
  const lines = ready?.lineOptions ?? [];
  const startedTab = tabCount(counts, 'mine');
  // SCR-01-*-empty: an empty Needs me shows the caught-up view without the search bar.
  const caughtUp = ready !== undefined && ready.items.length === 0 && ready.more === 'done' && !narrowed && view.queue === 'needs_me';
  const records = recordsText(counts);
  const asOf = ready?.asOf ?? counts?.as_of;
  const refreshFailed = failedView === viewSearch(view);

  const noFilters = { line: undefined, project: undefined, state: undefined };
  type ChipDef = Omit<FilterChip, 'onRemove'> & { patch: Filters };
  const chipDefs: (ChipDef | undefined)[] = [
    view.line ? { key: 'line', name: 'Line', value: lines.find((l) => l.key === view.line)?.title ?? view.line, patch: { line: undefined } } : undefined,
    view.project ? { key: 'project', name: 'Project', value: projects.find((p) => p.case_id === view.project)?.title ?? 'Selected project', patch: { project: undefined } } : undefined,
    view.state ? { key: 'state', name: 'State', value: stateWords(view.state), patch: { state: undefined } } : undefined,
  ];
  const chipList = chipDefs.filter((chip): chip is ChipDef => chip !== undefined);
  const filterPanel = <MyWorkFilter lines={lines} projects={projects} applied={{ line: view.line as LineKey | undefined, project: view.project, state: view.state }} preview={preview} onApply={applyFilters} onClose={closeFilter} />;

  const paging: ShowMoreProps | undefined = ready && {
    shown: ready.items.length,
    total: ready.totalComplete && ready.total !== null ? ready.total : undefined,
    hasMore: ready.more !== 'done',
    busy: ready.more === 'loading',
    failed: ready.more === 'failed',
    onMore: () => {
      if (ready.more !== 'failed') focusRow.current = ready.items.length;
      void loadMore();
    },
    size: view.limit,
    onSize: (limit) => navigate({ limit: limit as View['limit'] }),
    moreLabel: ready.more === 'keep-looking' ? 'Keep looking' : undefined,
  };

  let body;
  if (unassigned) {
    // F-88 puts received bids here; until it lands the tab says so rather than asking the work list.
    body = (
      <EmptyState title="Unassigned work">
        Work that still needs an owner opens here once this list is connected to received bids.
      </EmptyState>
    );
  } else if (list.status === 'loading') {
    body = <WorkListLoading>Loading your queue…</WorkListLoading>;
  } else if (list.status === 'error' && list.error.kind === 'forbidden') {
    body = (
      <EmptyState title="This queue isn&rsquo;t open to your role.">
        {list.error.message}
        {view.queue !== 'needs_me' && (
          <>
            <br />
            <Link href="/my-work">Go to Needs me</Link>
          </>
        )}
      </EmptyState>
    );
  } else if (list.status === 'error') {
    body = (
      <div className="shell-errorcard" role="alert">
        <span className="shell-eyebrow">ERROR · COULDN&rsquo;T LOAD</span>
        <span>We couldn&rsquo;t load your queue. Your work is safe; nothing was changed.</span>
        <span className="shell-reference">
          {lastLoaded && `Last loaded ${formatTime(lastLoaded)}. `}Reference {list.error.code} for support.
        </span>
        <div className="shell-errorcard__action">
          <Button kind="secondary" size="lg" block onClick={() => void retry()}>
            Try again
          </Button>
        </div>
      </div>
    );
  } else if (list.items.length === 0 && list.more === 'done' && narrowed) {
    body = (
      <EmptyState
        title="No work matches"
        action={
          <Button kind="link" onClick={() => navigate({ q: undefined, ...noFilters })}>
            Clear filters
          </Button>
        }
      >
        Nothing in {current.label} matches your search and filters.
      </EmptyState>
    );
  } else if (caughtUp) {
    body = <CaughtUp started={startedTab && !startedTab.atLeast ? startedTab.count : undefined} onSeeStarted={() => navigate({ queue: 'mine' })} />;
  } else if (list.items.length === 0 && list.more === 'done') {
    body = <EmptyState title={current.empty}>New work will appear here.</EmptyState>;
  } else if (list.items.length === 0) {
    // Pages came back empty but the server says there are more: no empty state until it says there is nothing.
    body = <ShowMore solo {...paging!} />;
  } else {
    const context = { lines: list.lines, asOf: list.asOf };
    body = (
      <>
        {!phone ? (
          <WorkTable rows={list.items} context={context} paging={paging!} />
        ) : (
          <>
            {view.queue === 'waiting' ? <StartedCards rows={list.items} /> : <WorkCards rows={list.items} context={context} />}
            <ShowMore solo {...paging!} />
          </>
        )}
        {coverageNotes(list.coverage, list.asOf).map((note) => (
          <p key={note} className="wl-note">
            {note}
          </p>
        ))}
      </>
    );
  }

  return (
    <>
      <div className="my-work__head">
        <h1 className="shell-title">My work</h1>
        {asOf &&
          (refreshFailed ? (
            <p className="my-work__updated" role="status">
              {records && `${records} · `}Couldn&rsquo;t refresh · updated {formatTime(asOf)}
            </p>
          ) : (
            <p className="my-work__updated">{records ? `${records} · updated ${formatTime(asOf)}` : `Updated ${formatTime(asOf)}`}</p>
          ))}
      </div>

      <div className="my-work__tabs">
        <Tabs
          label="My work"
          panelId={PANEL_ID}
          strip={phone}
          selected={view.queue}
          onSelect={(queue) => navigate({ queue })}
          tabs={shownTabs.map((tab) => {
            const count = tabCount(counts, tab.key);
            return { key: tab.key, label: tab.label, count: count?.count, atLeast: count?.atLeast };
          })}
        />
        {countsState.status === 'error' && <span className="my-work__nocount">Count unavailable</span>}
      </div>

      {!unassigned && (
        <form
          ref={toolbar}
          role="search"
          className="my-work__toolbar"
          hidden={caughtUp}
          onSubmit={(event) => {
            event.preventDefault();
            applySearch(text);
          }}
        >
          <ListToolbar
            search={{ label: 'Search', placeholder: phone ? 'Search work' : 'Search work, client or reference', value: text, onChange: setText, onSearch: applySearch, maxLength: 120 }}
            filterCount={filterCount}
            filterOpen={filterOpen}
            onFilterToggle={() => (filterOpen ? closeFilter() : setFilterOpen(true))}
            filterPanel={filterPanel}
            resultText={ready ? resultCount(ready.items.length, ready.more !== 'done', ready.total, ready.totalComplete) : ''}
            // removeFilter only runs from the chip's button; the navigate it calls reads a ref then, not during render
            // eslint-disable-next-line react-hooks/refs
            chips={chipList.map((chip): FilterChip => ({ key: chip.key, name: chip.name, value: chip.value, onRemove: () => removeFilter(chip.patch) }))}
            onClearAll={() => removeFilter(noFilters)}
          />
        </form>
      )}

      <div ref={panel} id={PANEL_ID} role="tabpanel" className="my-work__panel" aria-label={current.label}>
        {body}
      </div>
    </>
  );
}
