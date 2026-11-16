'use client';

import NextLink from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { Suspense, useCallback, useEffect, useMemo, useRef, useState, type FormEvent } from 'react';

import { api, call } from '@/api/client';
import { ApiError, networkError } from '@/api/errors';
import { Button, Callout, EmptyState, Link, ListToolbar, Loading, PageTitle, ShowMore, Skeleton, Tag, useIsPhone, VisuallyHidden } from '@/components';
import { SignedOutState } from '@/shell/FrameStates';

import { AlertAvatar, AlertBody, AlertsLoadError, useOpenAlert, type OpenAlert } from './AlertParts';
import { AlertsFilterPanel, type AlertFilters } from './AlertsFilterPanel';
import type { Alert } from './types';
import { buildAlertQuery, countLine, filterCount, isNarrowed, parseView, viewSearch, workHref, type View } from './model';
import './alerts.css';

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

  // Search: the box keeps what the person typed; the URL takes the settled search (two characters or more, or none).
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
  const onSearchSubmit = (event: FormEvent) => {
    event.preventDefault();
    applySearch(text);
  };

  const closeFilter = useCallback(() => {
    setFilterOpen(false);
  }, []);
  const applyFilters = (filters: AlertFilters) => {
    closeFilter();
    navigate({ agent: filters.agent, unread: filters.unread });
  };

  const openAlert = useOpenAlert();

  if (signedOut) return <SignedOutState pathname={`/notifications${search ? `?${search}` : ''}`} />;

  const count = list.status === 'ready' ? countLine(list.total) : undefined;
  const facets = filterCount(view);
  const filterPanel = (
    <AlertsFilterPanel applied={{ agent: view.agent, unread: view.unread }} unreadCount={unreadCount} onApply={applyFilters} onClose={closeFilter} />
  );
  const settingsLink = (
    <Link href="/settings/alerts" className="cmp-target">
      Alert settings
    </Link>
  );

  let body;
  if (list.status === 'loading') {
    body = (
      <div className="cmp-stack">
        <Skeleton />
        <Loading>Loading…</Loading>
      </div>
    );
  } else if (list.status === 'error') {
    body = <AlertsLoadError error={list.error} asOf={asOf} onRetry={() => void load(view)} />;
  } else if (list.items.length === 0 && isNarrowed(view)) {
    body = (
      <EmptyState
        title="No alerts match"
        action={
          <Button kind="secondary" onClick={() => navigate({ q: undefined, agent: undefined, unread: undefined })}>
            Clear search and filters
          </Button>
        }
      >
        Nothing fits this search and these filters.
      </EmptyState>
    );
  } else if (list.items.length === 0) {
    body = (
      <EmptyState title="No alerts yet.">Alerts for your work will appear here.</EmptyState>
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
        {(list.nextCursor || more === 'loading') && (
          <ShowMore className="alerts-showmore" shown={list.items.length} hasMore busy={more === 'loading'} onMore={() => void showMore()} />
        )}
        {more === 'error' && (
          <Callout kind="problem">
            We couldn&rsquo;t load more. Nothing was changed.{' '}
            <Button kind="secondary" size="sm" onClick={() => void showMore()}>
              Try again
            </Button>
          </Callout>
        )}
      </div>
    );
  }

  return (
    <div className="alerts-page">
      {/* Phone: "← Home" sits level with the heading until the frame's phone bar has a back-link slot (D-19, D-13). */}
      <div className="alerts-head">
        <div className="alerts-titlecol">
          {!phone && <p className="alerts-eyebrow">NOTIFICATIONS</p>}
          <PageTitle size={36}>Notifications</PageTitle>
        </div>
        {phone ? (
          <Link href="/" className="alerts-back">
            ← Home
          </Link>
        ) : (
          settingsLink
        )}
      </div>

      {toolbar && (
        <form role="search" onSubmit={onSearchSubmit}>
          <ListToolbar
            search={{ label: 'Search', placeholder: 'Search notifications', value: text, onChange: setText, onSearch: applySearch }}
            filterCount={facets}
            filterOpen={filterOpen}
            onFilterToggle={() => (filterOpen ? closeFilter() : setFilterOpen(true))}
            filterPanel={filterPanel}
            resultText={count ?? ''}
          />
          {!phone && count && unreadCount !== undefined && <VisuallyHidden>, {unreadCount} unread</VisuallyHidden>}
        </form>
      )}

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
      <NextLink href={workHref(alert)} className="alerts-link" onClick={(event) => onOpen(event, alert)}>
        <AlertAvatar agent={alert.agent} />
        <AlertBody alert={alert} now={now} />
        {unread && (
          <Tag tone="neutral" className="alerts-new">
            <VisuallyHidden>, </VisuallyHidden>NEW
          </Tag>
        )}
      </NextLink>
    </li>
  );
}
