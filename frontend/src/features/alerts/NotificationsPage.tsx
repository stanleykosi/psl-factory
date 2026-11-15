'use client';

import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { Suspense, useCallback, useEffect, useMemo, useRef, useState, type FormEvent } from 'react';

import { api, call } from '@/api/client';
import { ApiError, networkError } from '@/api/errors';
import { FilterIcon, SearchIcon } from '@/features/my-work/icons';
import { LoadingState, SignedOutState } from '@/shell/FrameStates';

import { AlertAvatar, AlertBody, AlertsLoadError, useOpenAlert, type OpenAlert } from './AlertParts';
import { AlertsFilterPanel, type AlertFilters } from './AlertsFilterPanel';
import type { Alert } from './types';
import { buildAlertQuery, countLine, filterCount, isNarrowed, parseView, viewSearch, workHref, type View } from './model';
import { useIsPhone } from './useIsPhone';
import './alerts.css';

const SEARCH_DEBOUNCE_MS = 300;

// `now` is when page 1 arrived: "10:42", "yesterday" and "12 Nov" are read against it.
type Loaded = { items: Alert[]; nextCursor?: string; total?: number; now: number };
type ListState = { status: 'loading' } | ({ status: 'ready' } & Loaded) | { status: 'error'; error: ApiError };

const asApiError = (error: unknown) => (error instanceof ApiError ? error : networkError());
const fetchPage = (v: View, cursor?: string) => call(api.GET('/api/v1/notifications', { params: { query: buildAlertQuery(v, cursor) } }));

/** /notifications (SCR-15): the person's own alerts. useSearchParams needs a Suspense boundary for `next build`. */
export function NotificationsPage() {
  return (
    <Suspense fallback={null}>
      <Notifications />
    </Suspense>
  );
}

function Notifications() {
  const params = useSearchParams();
  const router = useRouter();
  const search = params?.toString() ?? '';
  const view = useMemo(() => parseView(new URLSearchParams(search)), [search]);
  const phone = useIsPhone();

  const [list, setList] = useState<ListState>({ status: 'loading' });
  // From the latest successful response: its time, whether it carries total (search and Filter), its unread count.
  const [asOf, setAsOf] = useState<string>();
  const [toolbar, setToolbar] = useState(false);
  const [unreadCount, setUnreadCount] = useState<number>();
  const [more, setMore] = useState<'idle' | 'loading' | 'error'>('idle');
  const [signedOut, setSignedOut] = useState(false);
  const [filterOpen, setFilterOpen] = useState(false);

  const seq = useRef(0);
  const viewRef = useRef(view);
  const filterButton = useRef<HTMLButtonElement>(null);

  const navigate = useCallback(
    (next: Partial<View>) => router.replace(`/notifications${viewSearch({ ...viewRef.current, ...next })}`, { scroll: false }),
    [router],
  );

  /** Page 1 of a view. A response for an older view is ignored. */
  const load = useCallback(
    async (v: View) => {
      const mine = ++seq.current;
      setList({ status: 'loading' });
      setMore('idle');
      try {
        const data = await fetchPage(v);
        if (mine !== seq.current) return;
        setAsOf(data.as_of);
        setToolbar(data.total !== undefined);
        setUnreadCount(data.unread_count);
        // Without total there is no search or Filter to clear them with, so the filters go and the list is re-read.
        if (data.total === undefined && isNarrowed(v)) {
          router.replace('/notifications', { scroll: false });
          return;
        }
        setList({ status: 'ready', items: data.items, nextCursor: data.next_cursor, total: data.total, now: Date.now() });
      } catch (error) {
        if (mine !== seq.current) return;
        const e = asApiError(error);
        if (e.kind === 'unauthenticated') setSignedOut(true);
        else setList({ status: 'error', error: e });
      }
    },
    [router],
  );

  const showMore = async () => {
    if (list.status !== 'ready' || !list.nextCursor || more === 'loading') return;
    const mine = seq.current;
    setMore('loading');
    try {
      const data = await fetchPage(view, list.nextCursor);
      if (mine !== seq.current) return;
      setAsOf(data.as_of);
      setUnreadCount(data.unread_count);
      setList((prev) => (prev.status !== 'ready' ? prev : { ...prev, items: [...prev.items, ...data.items], nextCursor: data.next_cursor, total: data.total }));
      setMore('idle');
    } catch (error) {
      if (mine !== seq.current) return;
      if (asApiError(error).kind === 'unauthenticated') setSignedOut(true);
      else setMore('error');
    }
  };

  useEffect(() => {
    viewRef.current = view;
    // A new search or filter reloads from page 1.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load(view);
  }, [view, load]);

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
  const applyFilters = (filters: AlertFilters) => {
    closeFilter();
    navigate({ agent: filters.agent, unread: filters.unread });
  };

  const openAlert = useOpenAlert();

  if (signedOut) return <SignedOutState pathname={`/notifications${search ? `?${search}` : ''}`} />;

  const count = list.status === 'ready' ? countLine(list.total) : undefined;
  const facets = filterCount(view);
  const filterLabel = facets > 0 ? `Filter · ${facets}` : 'Filter';
  const filterProps = {
    ref: filterButton,
    type: 'button' as const,
    'aria-haspopup': 'dialog' as const,
    'aria-expanded': filterOpen,
    onClick: () => (filterOpen ? closeFilter() : setFilterOpen(true)),
  };
  const filterPanel = filterOpen && (
    <AlertsFilterPanel
      phone={phone}
      applied={{ agent: view.agent, unread: view.unread }}
      unreadCount={unreadCount}
      anchor={filterButton}
      onApply={applyFilters}
      onClose={closeFilter}
    />
  );
  const settingsLink = <Link href="/settings/alerts">Alert settings</Link>;

  let body;
  if (list.status === 'loading') {
    body = <LoadingState />;
  } else if (list.status === 'error') {
    body = <AlertsLoadError error={list.error} asOf={asOf} onRetry={() => void load(view)} />;
  } else if (list.items.length === 0 && isNarrowed(view)) {
    body = (
      <div className="psl-empty">
        <h3>No alerts match</h3>
        <button type="button" className="psl-btn psl-btn--secondary" onClick={() => navigate({ q: undefined, agent: undefined, unread: undefined })}>
          Clear search and filters
        </button>
      </div>
    );
  } else if (list.items.length === 0) {
    body = (
      <div className="psl-empty">
        <h3>No alerts yet.</h3>
      </div>
    );
  } else {
    const { now } = list;
    body = (
      <div className="alerts-listwrap">
        <ul aria-label="Alerts" className="alerts-list">
          {list.items.map((alert) => (
            <AlertRow key={alert.id} alert={alert} now={now} onOpen={openAlert} />
          ))}
        </ul>
        {list.nextCursor && (
          <div className="psl-showmore alerts-showmore">
            <button
              type="button"
              className="psl-btn psl-btn--secondary psl-btn--sm"
              aria-busy={more === 'loading'}
              aria-disabled={more === 'loading' || undefined}
              onClick={() => void showMore()}
            >
              Show more
            </button>
          </div>
        )}
        {more === 'error' && (
          <div className="psl-callout psl-callout--problem alerts-morefail">
            <span>We couldn&rsquo;t load more. Nothing was changed.</span>
            <button type="button" className="psl-btn psl-btn--secondary psl-btn--sm" onClick={() => void showMore()}>
              Try again
            </button>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="alerts-page">
      {!phone && <p className="alerts-eyebrow">NOTIFICATIONS</p>}
      {/* Phone: "← Home" sits level with the heading until the frame's phone bar has a back-link slot (D-19, D-13). */}
      <div className="alerts-head">
        <h1 className="shell-title">Notifications</h1>
        {phone ? (
          <Link href="/" className="alerts-back">
            ← Home
          </Link>
        ) : (
          settingsLink
        )}
      </div>

      {toolbar && (
        <form role="search" className="psl-toolbar alerts-toolbar" onSubmit={onSearchSubmit}>
          <div className="psl-search alerts-search">
            <SearchIcon />
            <label className="alerts-sr" htmlFor="alerts-q">
              Search
            </label>
            <input
              id="alerts-q"
              type="search"
              className="psl-input"
              placeholder="Search notifications"
              value={text}
              onChange={(e) => onSearchInput(e.target.value)}
            />
          </div>
          <div className="alerts-filter">
            {phone ? (
              <button {...filterProps} className="psl-iconbtn" aria-label={filterLabel}>
                <FilterIcon />
              </button>
            ) : (
              <button {...filterProps} className="psl-btn psl-btn--secondary alerts-filterbtn">
                <FilterIcon />
                {filterLabel}
              </button>
            )}
            {!phone && filterPanel}
          </div>
          {!phone && count && <span className="alerts-count">{count}</span>}
          {!phone && count && unreadCount !== undefined && <span className="alerts-sr">, {unreadCount} unread</span>}
        </form>
      )}
      {phone && filterPanel}

      {body}
      {phone && settingsLink}
    </div>
  );
}

type RowProps = { alert: Alert; now: number; onOpen: OpenAlert };

/** One alert: avatar, text over the meta line, NEW while unread. The whole row is one link to its work. */
function AlertRow({ alert, now, onOpen }: RowProps) {
  const unread = alert.read === false;
  return (
    <li className={unread ? 'alerts-row alerts-row--unread' : 'alerts-row'}>
      <Link href={workHref(alert)} className="alerts-link" onClick={(event) => onOpen(event, alert)}>
        <AlertAvatar agent={alert.agent} />
        <AlertBody alert={alert} now={now} />
        {unread && (
          <span className="psl-tag psl-tag--person alerts-new">
            <span className="alerts-sr">, </span>NEW
          </span>
        )}
      </Link>
    </li>
  );
}
