'use client';

import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { useCallback, useEffect, useMemo, useRef, useState, useSyncExternalStore, type FormEvent, type KeyboardEvent } from 'react';

import { api, call } from '@/api/client';
import { ApiError, networkError } from '@/api/errors';
import { SignedOutState } from '@/shell/FrameStates';

import { CaughtUp } from './CaughtUp';
import { FilterPanel, type Filters, type Preview } from './FilterPanel';
import { FilterIcon, SearchIcon } from './icons';
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
  type Queue,
  type View,
  type WorkItem,
  type WorkList,
} from './model';
import { StartedCards, WorkCards, WorkTable } from './WorkRows';

export const POLL_MS = 15_000;
const SEARCH_DEBOUNCE_MS = 300;
const PHONE_QUERY = '(max-width: 719.98px)';
const PANEL_ID = 'my-work-panel';

type Loaded = { items: WorkItem[]; firstCount: number; pages: number; nextCursor?: string };
type ListState = { status: 'loading' } | ({ status: 'ready' } & Loaded) | { status: 'error'; error: ApiError };

const asApiError = (error: unknown) => (error instanceof ApiError ? error : networkError());

function subscribePhone(onChange: () => void) {
  if (typeof window.matchMedia !== 'function') return () => {};
  const media = window.matchMedia(PHONE_QUERY);
  media.addEventListener('change', onChange);
  return () => media.removeEventListener('change', onChange);
}
const isPhoneNow = () => typeof window.matchMedia === 'function' && window.matchMedia(PHONE_QUERY).matches;

/** Below 720px the list is cards, the filter is an icon button and the panel a bottom sheet. */
function useIsPhone() {
  return useSyncExternalStore(subscribePhone, isPhoneNow, () => false);
}

const tabId = (queue: Queue) => `my-work-tab-${queue}`;

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
  const filterButton = useRef<HTMLButtonElement>(null);

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

  // Search: the box keeps what the person typed; the URL takes it 300 ms after the last keystroke.
  const [text, setText] = useState(view.q ?? '');
  const [syncedQ, setSyncedQ] = useState(view.q);
  if (view.q !== syncedQ) {
    setSyncedQ(view.q);
    if ((text.trim() || undefined) !== view.q) setText(view.q ?? '');
  }
  const debounce = useRef<ReturnType<typeof setTimeout>>(undefined);
  useEffect(() => () => clearTimeout(debounce.current), []);
  const applySearch = (value: string) => {
    clearTimeout(debounce.current);
    const q = value.trim() || undefined;
    if (q !== viewRef.current.q) navigate({ q });
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
  const applyFilters = (filters: Filters) => {
    closeFilter();
    navigate({ line: filters.line, project: filters.project, state: filters.state, waiting: filters.waiting });
  };
  // "Show N items" in the filter panel: the same list request with the draft filters, one page of 50.
  const preview = useCallback(async (filters: Filters): Promise<Preview> => {
    const data = await call(api.GET('/api/v1/work', { params: { query: buildWorkQuery({ ...viewRef.current, ...filters, limit: 50 }) } }));
    return { count: data.items.length, more: Boolean(data.next_cursor) };
  }, []);
  const removeFilter = (filters: Filters) => {
    navigate(filters);
    filterButton.current?.focus();
  };

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

  const onTabKey = (event: KeyboardEvent<HTMLButtonElement>, index: number) => {
    const last = tabs.length - 1;
    const next = { ArrowRight: index === last ? 0 : index + 1, ArrowLeft: index === 0 ? last : index - 1, Home: 0, End: last }[event.key];
    if (next === undefined) return;
    event.preventDefault();
    document.getElementById(tabId(tabs[next].key))?.focus();
    navigate({ queue: tabs[next].key });
  };

  const onLimitKey = (event: KeyboardEvent<HTMLButtonElement>, index: number) => {
    const step = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }[event.key];
    if (step === undefined) return;
    event.preventDefault();
    const next = LIMITS[(index + step + LIMITS.length) % LIMITS.length];
    event.currentTarget.parentElement?.querySelectorAll<HTMLElement>('[role="radio"]')[LIMITS.indexOf(next)]?.focus();
    navigate({ limit: next });
  };

  // SCR-01-*-filter: while the panel is open the Filter button is dark and its count badge light.
  const filterBadge = filterCount > 0 && <span className={filterOpen ? 'psl-badge my-work__badge-open' : 'psl-badge psl-badge--signal'}>{filterCount}</span>;
  const filterProps = {
    ref: filterButton,
    type: 'button' as const,
    'aria-haspopup': 'dialog' as const,
    'aria-expanded': filterOpen,
    onClick: () => (filterOpen ? closeFilter() : setFilterOpen(true)),
  };
  const filterPanel = filterOpen && (
    <FilterPanel
      phone={phone}
      lines={lines}
      applied={{ line: view.line, project: view.project, state: view.state, waiting: view.waiting }}
      anchor={filterButton}
      preview={preview}
      onApply={applyFilters}
      onClose={closeFilter}
    />
  );

  let body;
  if (list.status === 'loading') {
    body = (
      <div className="psl-panel shell-loading">
        <div className="shell-skel" aria-hidden="true">
          <span className="psl-skel" style={{ width: '90%' }} />
          <span className="psl-skel" style={{ width: '70%' }} />
          <span className="psl-skel" style={{ width: '80%' }} />
        </div>
        <span className="psl-loading" role="status">
          <span className="psl-busy" aria-hidden="true">
            <i />
            <i />
            <i />
          </span>
          Loading your queue…
        </span>
      </div>
    );
  } else if (list.status === 'error' && list.error.kind === 'forbidden') {
    body = (
      <div className="psl-empty">
        <h3>This queue isn&rsquo;t open to your role.</h3>
        <p>{list.error.message}</p>
        {view.queue !== 'needs_me' && (
          <p>
            <Link href="/my-work">Go to Needs me</Link>
          </p>
        )}
      </div>
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
          <button type="button" className="psl-btn psl-btn--secondary psl-btn--lg psl-btn--block" onClick={() => void load(view)}>
            Try again
          </button>
        </div>
      </div>
    );
  } else if (list.items.length === 0 && narrowed) {
    body = (
      <div className="psl-empty">
        <h3>No work matches</h3>
        <p>Nothing in {current.label} matches your search and filters.</p>
        <button
          type="button"
          className="psl-link my-work__linkbutton"
          onClick={() => navigate({ q: undefined, line: undefined, project: undefined, state: undefined, waiting: undefined })}
        >
          Clear filters
        </button>
      </div>
    );
  } else if (caughtUp) {
    body = <CaughtUp counts={counts} phone={phone} onSeeStarted={() => navigate({ queue: 'waiting_on_others' })} />;
  } else if (list.items.length === 0) {
    body = (
      <div className="psl-empty">
        <h3>{current.empty}</h3>
        <p>New work will appear here.</p>
      </div>
    );
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
              <span role="radiogroup" aria-label="Rows per page" className={phone ? 'psl-seg psl-seg--phone' : 'psl-seg'}>
                {LIMITS.map((n: Limit, i) => (
                  <button
                    key={n}
                    type="button"
                    role="radio"
                    aria-checked={n === view.limit}
                    tabIndex={n === view.limit ? 0 : -1}
                    className="psl-seg__opt"
                    onClick={() => navigate({ limit: n })}
                    onKeyDown={(e) => onLimitKey(e, i)}
                  >
                    {n}
                  </button>
                ))}
              </span>
            </span>
            {list.nextCursor && (
              <button
                type="button"
                className="psl-btn psl-btn--secondary psl-btn--sm my-work__more"
                disabled={more === 'loading'}
                aria-busy={more === 'loading'}
                onClick={() => void showMore()}
              >
                {showMoreLabel(view, counts, list.items.length)}
              </button>
            )}
          </div>
          {more === 'error' && (
            <div className="psl-callout psl-callout--problem my-work__morefail">
              <span>We couldn&rsquo;t load more. Your work is safe; nothing was changed.</span>
              <button type="button" className="psl-btn psl-btn--secondary psl-btn--sm" onClick={() => void showMore()}>
                Try again
              </button>
            </div>
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
        <div role="tablist" aria-label="My work" className="psl-tabs">
          {tabs.map((tab, i) => {
            const selected = tab.key === view.queue;
            const count = counts?.[tab.key];
            return (
              <button
                key={tab.key}
                id={tabId(tab.key)}
                type="button"
                role="tab"
                className="psl-tab my-work__tab"
                aria-selected={selected}
                aria-controls={selected ? PANEL_ID : undefined}
                tabIndex={selected || (!selectedShown && i === 0) ? 0 : -1}
                onClick={() => navigate({ queue: tab.key })}
                onKeyDown={(e) => onTabKey(e, i)}
              >
                {tab.label}
                <span className="psl-badge">{count === undefined ? '–' : count}</span>
              </button>
            );
          })}
        </div>
        {counts === null && <span className="my-work__nocount">Count unavailable</span>}
      </div>

      <div className="my-work__toolbar" hidden={caughtUp}>
        <form role="search" className="psl-toolbar" onSubmit={onSearchSubmit}>
          <div className="psl-search my-work__search">
            <SearchIcon />
            <label className="my-work__sr" htmlFor="my-work-q">
              Search
            </label>
            <input
              id="my-work-q"
              type="search"
              className="psl-input"
              placeholder={phone ? 'Search work' : 'Search work, client or reference'}
              value={text}
              onChange={(e) => onSearchInput(e.target.value)}
            />
          </div>
          <div className="my-work__filter">
            {phone ? (
              <button {...filterProps} className="psl-iconbtn my-work__iconbtn" aria-label={filterCount ? `Filter, ${filterCount} on` : 'Filter'}>
                <FilterIcon />
                {filterBadge}
              </button>
            ) : (
              <button {...filterProps} className={filterOpen ? 'psl-btn psl-btn--dark' : 'psl-btn psl-btn--secondary'}>
                <FilterIcon />
                Filter
                {filterBadge}
              </button>
            )}
            {!phone && filterPanel}
          </div>
          {ready && <span className="psl-resultcount">{resultCount(view, counts, ready.items.length, Boolean(ready.nextCursor))}</span>}
        </form>
        {filterCount > 0 && (
          <div className="my-work__chips">
            {view.line && (
              <span className="psl-chip">
                <span>Line</span>
                <strong>{lineTitle}</strong>
                <button type="button" aria-label="Remove Line filter" onClick={() => removeFilter({ line: undefined })}>
                  ×
                </button>
              </span>
            )}
            {view.project && (
              <span className="psl-chip">
                <span>Project</span>
                <strong>{view.project}</strong>
                <button type="button" aria-label="Remove Project filter" onClick={() => removeFilter({ project: undefined })}>
                  ×
                </button>
              </span>
            )}
            {view.state && (
              <span className="psl-chip">
                <span>State</span>
                <strong>{stateTag(view.state).words}</strong>
                <button type="button" aria-label="Remove State filter" onClick={() => removeFilter({ state: undefined })}>
                  ×
                </button>
              </span>
            )}
            {view.waiting && (
              <span className="psl-chip">
                <span>Waiting on</span>
                <strong>{WAITING_ON[view.waiting]}</strong>
                <button type="button" aria-label="Remove Waiting on filter" onClick={() => removeFilter({ waiting: undefined })}>
                  ×
                </button>
              </span>
            )}
            <button
              type="button"
              className="psl-btn psl-btn--text"
              onClick={() => removeFilter({ line: undefined, project: undefined, state: undefined, waiting: undefined })}
            >
              Clear all
            </button>
          </div>
        )}
      </div>
      {phone && filterPanel}

      <div
        ref={panel}
        id={PANEL_ID}
        role="tabpanel"
        className="my-work__panel"
        aria-labelledby={selectedShown ? tabId(view.queue) : undefined}
        aria-label={selectedShown ? undefined : current.label}
      >
        {body}
      </div>
    </>
  );
}
