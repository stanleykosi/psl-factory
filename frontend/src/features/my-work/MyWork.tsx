'use client';

import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { api, call } from '@/api/client';
import { ApiError, networkError } from '@/api/errors';
import { Button, Callout, EmptyState, ListToolbar, Loading, Segmented, Skeleton, Tabs, useIsPhone, type FilterChip } from '@/components';
import { SignedOutState } from '@/shell/FrameStates';

import { CaughtUp } from './CaughtUp';
import { MyWorkFilter, type Filters, type Preview } from './FilterPanel';
import {
  appendPage,
  buildWorkQuery,
  filterCount as countFilters,
  isNarrowed,
  LIMITS,
  lineOptions,
  mergeRefresh,
  parseView,
  QUEUES,
  recordsText,
  resultCount,
  shownText,
  showMoreLabel,
  stateTag,
  formatTime,
  viewSearch,
  WAITING_ON,
  type Counts,
  type Limit,
  type View,
  type WorkItem,
  type Suggestion,
  type WorkList,
  type WorkListWithSuggestions,
} from './model';
import { StartedCards, WorkCards, WorkTable } from './WorkRows';

export const POLL_MS = 15_000;
const PANEL_ID = 'my-work-panel';

type Loaded = { items: WorkItem[]; firstCount: number; pages: number; nextCursor?: string };
type ListState = { status: 'loading' } | ({ status: 'ready' } & Loaded) | { status: 'error'; error: ApiError };

const asApiError = (error: unknown) => (error instanceof ApiError ? error : networkError());

/** SCR-01 My work: a person's queues from E-WORK-LIST, with search, filters, paging and live refresh. */
export function MyWork() {
  const params = useSearchParams();
  const router = useRouter();
  const view = useMemo(() => parseView(new URLSearchParams(params?.toString() ?? '')), [params]);
  const phone = useIsPhone();

  const [list, setList] = useState<ListState>({ status: 'loading' });
  const [counts, setCounts] = useState<Counts | null | undefined>(undefined);
  const [asOf, setAsOf] = useState<string>();
  const [lineFilters, setLineFilters] = useState<WorkList['filters']>();
  const [suggestions, setSuggestions] = useState<Suggestion[]>();
  const [refreshFailed, setRefreshFailed] = useState(false);
  const [more, setMore] = useState<'idle' | 'loading' | 'error'>('idle');
  const [signedOut, setSignedOut] = useState(false);
  const [filterOpen, setFilterOpen] = useState(false);

  const seq = useRef(0);
  const inFlight = useRef(0);
  const lastSuccess = useRef(0);
  const pollable = useRef(false);
  const focusRow = useRef<number | null>(null);
  const viewRef = useRef(view);
  const panel = useRef<HTMLDivElement>(null);

  const navigate = useCallback(
    (next: Partial<View>) => router.replace(`/my-work${viewSearch({ ...viewRef.current, ...next })}`, { scroll: false }),
    [router],
  );

  const fetchPage = useCallback(async (v: View, cursor?: string) => {
    inFlight.current += 1;
    try {
      return await call(api.GET('/api/v1/work', { params: { query: buildWorkQuery(v, cursor) } }));
    } finally {
      inFlight.current -= 1;
    }
  }, []);

  const took = useCallback((data: WorkList) => {
    setCounts(data.counts ?? null);
    setAsOf(data.as_of);
    setLineFilters(data.filters);
    setSuggestions((data as WorkListWithSuggestions).suggestions);
    setRefreshFailed(false);
    lastSuccess.current = Date.now();
  }, []);

  /** Page 1 of a view. A response for an older view is ignored. */
  const load = useCallback(
    async (v: View) => {
      const mine = ++seq.current;
      setList({ status: 'loading' });
      setMore('idle');
      try {
        const data = await fetchPage(v);
        if (mine !== seq.current) return;
        took(data);
        setList({ status: 'ready', items: data.items, firstCount: data.items.length, pages: 1, nextCursor: data.next_cursor });
      } catch (error) {
        if (mine !== seq.current) return;
        const e = asApiError(error);
        if (e.kind === 'unauthenticated') setSignedOut(true);
        else setList({ status: 'error', error: e });
      }
    },
    [fetchPage, took],
  );

  /** Re-reads page 1 in place: rows loaded with Show more stay, nothing else on screen moves. */
  const refresh = useCallback(async () => {
    if (inFlight.current > 0) return;
    const mine = seq.current;
    try {
      const data = await fetchPage(viewRef.current);
      if (mine !== seq.current) return;
      took(data);
      setList((prev) =>
        prev.status !== 'ready'
          ? prev
          : {
              ...prev,
              items: mergeRefresh(prev.items, prev.firstCount, data.items),
              firstCount: data.items.length,
              nextCursor: prev.pages === 1 ? data.next_cursor : prev.nextCursor,
            },
      );
    } catch (error) {
      if (mine !== seq.current) return;
      if (asApiError(error).kind === 'unauthenticated') setSignedOut(true);
      else setRefreshFailed(true);
    }
  }, [fetchPage, took]);

  const showMore = async () => {
    if (list.status !== 'ready' || !list.nextCursor) return;
    const mine = seq.current;
    const before = list.items.length;
    setMore('loading');
    try {
      const data = await fetchPage(view, list.nextCursor);
      if (mine !== seq.current) return;
      took(data);
      focusRow.current = before;
      setList((prev) =>
        prev.status !== 'ready' ? prev : { ...prev, items: appendPage(prev.items, data.items), pages: prev.pages + 1, nextCursor: data.next_cursor },
      );
      setMore('idle');
    } catch (error) {
      if (mine !== seq.current) return;
      if (asApiError(error).kind === 'unauthenticated') setSignedOut(true);
      else setMore('error');
    }
  };

  useEffect(() => {
    viewRef.current = view;
    // A new view (queue, search, filters or rows per page) reloads from page 1.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load(view);
  }, [view, load]);

  useEffect(() => {
    pollable.current = list.status === 'ready' && !signedOut;
    if (focusRow.current !== null && list.status === 'ready') {
      panel.current?.querySelectorAll<HTMLElement>('[data-work-link]')[focusRow.current]?.focus();
      focusRow.current = null;
    }
  }, [list, signedOut]);

  // D-UPDATES: every 15 s while the tab is visible; on return, at once if the data is older than 15 s.
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
    navigate({ line: filters.line, project: filters.project, state: filters.state, waiting: filters.waiting });
  };
  // "Show N items" in the filter panel: the same list request with the draft filters, one page of 50.
  const preview = useCallback(async (filters: Filters): Promise<Preview> => {
    const data = await call(api.GET('/api/v1/work', { params: { query: buildWorkQuery({ ...viewRef.current, ...filters, limit: 50 }) } }));
    return { count: data.items.length, more: Boolean(data.next_cursor) };
  }, []);
  const removeFilter = (filters: Filters) => navigate(filters);

  if (signedOut) return <SignedOutState pathname="/my-work" />;

  const ready = list.status === 'ready' ? list : null;
  const tabs = QUEUES.filter((x) => x.key !== 'unassigned' || counts?.unassigned !== undefined);
  const current = QUEUES.find((x) => x.key === view.queue)!;
  const selectedShown = tabs.some((x) => x.key === view.queue);
  const filterCount = countFilters(view);
  const narrowed = isNarrowed(view);
  const lines = lineOptions(lineFilters, ready?.items ?? [], view.line);
  const lineTitle = lines.find((l) => l.key === view.line)?.title ?? view.line;
  // SCR-01-*-empty: an empty Needs me shows the caught-up view without the search bar.
  const caughtUp = ready !== null && ready.items.length === 0 && !narrowed && view.queue === 'needs_me';
  const records = recordsText(counts);

  const noFilters = { line: undefined, project: undefined, state: undefined, waiting: undefined };
  type ChipDef = Omit<FilterChip, 'onRemove'> & { patch: Filters };
  const chipDefs: (ChipDef | undefined)[] = [
    view.line ? { key: 'line', name: 'Line', value: lineTitle ?? view.line, patch: { line: undefined } } : undefined,
    view.project ? { key: 'project', name: 'Project', value: view.project, patch: { project: undefined } } : undefined,
    view.state ? { key: 'state', name: 'State', value: stateTag(view.state).words, patch: { state: undefined } } : undefined,
    view.waiting ? { key: 'waiting', name: 'Waiting on', value: WAITING_ON[view.waiting], patch: { waiting: undefined } } : undefined,
  ];
  const chipList = chipDefs.filter((chip): chip is ChipDef => chip !== undefined);
  const filterPanel = (
    <MyWorkFilter
      lines={lines}
      applied={{ line: view.line, project: view.project, state: view.state, waiting: view.waiting }}
      preview={preview}
      onApply={applyFilters}
      onClose={closeFilter}
    />
  );

  let body;
  if (list.status === 'loading') {
    body = (
      <div className="shell-loading">
        <Skeleton widths={[90, 70, 80]} />
        <Loading>Loading your queue…</Loading>
      </div>
    );
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
          {asOf && `Last loaded ${formatTime(asOf)}. `}Reference {list.error.code} for support.
        </span>
        <div className="shell-errorcard__action">
          <Button kind="secondary" size="lg" block onClick={() => void load(view)}>
            Try again
          </Button>
        </div>
      </div>
    );
  } else if (list.items.length === 0 && narrowed) {
    body = (
      <EmptyState
        title="No work matches"
        action={
          <button type="button" className="psl-link cmp-linkbutton" onClick={() => navigate({ q: undefined, ...noFilters })}>
            Clear filters
          </button>
        }
      >
        Nothing in {current.label} matches your search and filters.
      </EmptyState>
    );
  } else if (caughtUp) {
    body = <CaughtUp counts={counts} phone={phone} suggestions={suggestions} onSeeStarted={() => navigate({ queue: 'waiting_on_others' })} />;
  } else if (list.items.length === 0) {
    body = <EmptyState title={current.empty}>New work will appear here.</EmptyState>;
  } else {
    body = (
      <>
        {!phone ? (
          <WorkTable items={list.items} />
        ) : view.queue === 'waiting_on_others' ? (
          <StartedCards items={list.items} />
        ) : (
          <WorkCards items={list.items} />
        )}
        <div className="my-work__foot">
          <div className="psl-showmore my-work__showmore">
            <span>{shownText(view, counts, list.items.length, Boolean(list.nextCursor))}</span>
            <span className="my-work__rows">
              <span className="my-work__rowslabel" aria-hidden="true">
                ROWS PER PAGE
              </span>
              <Segmented label="Rows per page" phone={phone} value={String(view.limit) as `${Limit}`} options={LIMITS.map((n) => ({ value: String(n) as `${Limit}`, label: String(n) }))} onChange={(n) => navigate({ limit: Number(n) as Limit })} />
            </span>
            {list.nextCursor && (
              <Button kind="secondary" size="sm" className="my-work__more" busy={more === 'loading'} busyLabel="Loading…" onClick={() => void showMore()}>
                {showMoreLabel(view, counts, list.items.length)}
              </Button>
            )}
          </div>
          {more === 'error' && (
            <Callout kind="problem" className="my-work__morefail">
              We couldn&rsquo;t load more. Your work is safe; nothing was changed.{' '}
              <Button kind="secondary" size="sm" onClick={() => void showMore()}>
                Try again
              </Button>
            </Callout>
          )}
        </div>
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
          selected={selectedShown ? view.queue : tabs[0].key}
          onSelect={(queue) => navigate({ queue })}
          tabs={tabs.map((tab) => ({ key: tab.key, label: tab.label, count: counts?.[tab.key] }))}
        />
        {counts === null && <span className="my-work__nocount">Count unavailable</span>}
      </div>

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
          search={{ label: 'Search', placeholder: phone ? 'Search work' : 'Search work, client or reference', value: text, onChange: setText, onSearch: applySearch }}
          filterCount={filterCount}
          filterOpen={filterOpen}
          onFilterToggle={() => (filterOpen ? closeFilter() : setFilterOpen(true))}
          filterPanel={filterPanel}
          resultText={ready ? resultCount(view, counts, ready.items.length, Boolean(ready.nextCursor)) : ''}
          // removeFilter only runs from the chip's button; the navigate it calls reads a ref then, not during render
          // eslint-disable-next-line react-hooks/refs
          chips={chipList.map((chip): FilterChip => ({ key: chip.key, name: chip.name, value: chip.value, onRemove: () => removeFilter(chip.patch) }))}
          onClearAll={() => removeFilter(noFilters)}
        />
      </form>

      <div
        ref={panel}
        id={PANEL_ID}
        role="tabpanel"
        className="my-work__panel"
        aria-label={current.label}
      >
        {body}
      </div>
    </>
  );
}
