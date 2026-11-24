'use client';

import NextLink from 'next/link';
import { useCallback, useEffect, useRef, useState } from 'react';

import { readInbox } from '@/api/alerts';
import { ApiError, networkError } from '@/api/errors';
import { Button, EmptyState, formatTime, Link, Loading, PageTitle, Skeleton, Tag, useIsPhone, VisuallyHidden } from '@/components';
import { SignedOutState } from '@/shell/FrameStates';

import { AlertAvatar, AlertBody, AlertsLoadError, RowTail, useAlertActions, type OpenAlert, type RowNotice } from './AlertParts';
import type { Alert, DailySummary } from './types';
import { alertHref, loadedLine, needsYou, summaryLine } from './model';
import './alerts.css';

// `now` is when page 1 arrived: "10:42", "yesterday" and "12 Nov" are read against it.
type Loaded = { items: Alert[]; nextPage: number | null; unread: number; summary?: DailySummary; now: number };
type ListState = { status: 'loading' } | ({ status: 'ready' } & Loaded) | { status: 'error'; error: ApiError };

const asApiError = (error: unknown) => (error instanceof ApiError ? error : networkError());
const fetchPage = async (page: number) => {
  const list = await readInbox(page);
  // A body without an items list is not an alerts list: shown as a load error, never as "no alerts".
  if (!Array.isArray(list?.items) || typeof list.unread !== 'number') throw networkError();
  return list;
};

/** /notifications (SCR-15): the person's own alerts, 25 to a page, "Load more" while the server has another page. */
export function NotificationsPage() {
  const phone = useIsPhone();
  const [list, setList] = useState<ListState>({ status: 'loading' });
  const [asOf, setAsOf] = useState<string>();
  const [more, setMore] = useState<'idle' | 'loading' | 'error'>('idle');
  const [signedOut, setSignedOut] = useState(false);
  const loading = useRef(false);

  /** Page 1 replaces the list. */
  const load = useCallback(async () => {
    if (loading.current) return;
    loading.current = true;
    setList((prev) => (prev.status === 'ready' ? prev : { status: 'loading' }));
    setMore('idle');
    try {
      const data = await fetchPage(1);
      setAsOf(data.as_of);
      setList({ status: 'ready', items: data.items, nextPage: data.next_page ?? null, unread: data.unread, summary: data.daily_summary, now: Date.now() });
    } catch (error) {
      const e = asApiError(error);
      if (e.kind === 'unauthenticated') setSignedOut(true);
      else setList({ status: 'error', error: e });
    }
    loading.current = false;
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, [load]);

  const showMore = async () => {
    if (list.status !== 'ready' || list.nextPage === null || more === 'loading') return;
    setMore('loading');
    try {
      const data = await fetchPage(list.nextPage);
      setAsOf(data.as_of);
      setList((prev) => {
        if (prev.status !== 'ready') return prev;
        const seen = new Set(prev.items.map((alert) => alert.id));
        return { ...prev, items: [...prev.items, ...data.items.filter((alert) => !seen.has(alert.id))], nextPage: data.next_page ?? null };
      });
      setMore('idle');
    } catch (error) {
      if (asApiError(error).kind === 'unauthenticated') setSignedOut(true);
      else setMore('error');
    }
  };

  const actions = useAlertActions({
    onRead: (alert) =>
      setList((prev) =>
        prev.status !== 'ready'
          ? prev
          : { ...prev, unread: Math.max(0, prev.unread - 1), items: prev.items.map((item) => (item.id === alert.id ? { ...item, read: true } : item)) },
      ),
    onGone: () => void load(),
    onSignedOut: () => setSignedOut(true),
  });

  if (signedOut) return <SignedOutState pathname="/notifications" />;

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
    body = <AlertsLoadError error={list.error} asOf={asOf} onRetry={() => void load()} />;
  } else {
    const { items, now, unread, nextPage } = list;
    const summary = summaryLine(list.summary);
    const rows = { now, onOpen: actions.open, onMark: (alert: Alert) => void actions.markRead(alert), notices: actions.notices };
    body = (
      <>
        {summary && <p className="alerts-summary">{summary}</p>}
        {items.length === 0 ? (
          <EmptyState title="No alerts">Alerts for your work will appear here.</EmptyState>
        ) : (
          <>
            <Group id="need" title="Needs you" items={items.filter(needsYou)} primary {...rows} />
            <Group id="info" title="For information" items={items.filter((alert) => !needsYou(alert))} {...rows} />
            <p className="alerts-asof">
              {asOf && `As of ${formatTime(asOf)}. `}
              {loadedLine(items.length, unread)}.
            </p>
          </>
        )}
        {more === 'error' && (
          <p className="alerts-rownote" role="status">
            Couldn’t load more alerts. Try again.
          </p>
        )}
        {nextPage !== null && (
          <div className="alerts-more">
            <Button kind="secondary" busy={more === 'loading'} busyLabel="Loading…" onClick={() => void showMore()}>
              {more === 'error' ? 'Try again' : 'Load more'}
            </Button>
          </div>
        )}
      </>
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

      {body}
      {phone && settingsLink}
    </div>
  );
}

type GroupProps = { id: string; title: string; items: Alert[]; primary?: boolean; now: number; onOpen: OpenAlert; onMark: (alert: Alert) => void; notices: Record<string, RowNotice> };

/** A group heading with its loaded count over its rows; an empty group is not drawn. */
function Group({ id, title, items, primary, now, onOpen, onMark, notices }: GroupProps) {
  if (items.length === 0) return null;
  return (
    <section aria-labelledby={`alerts-page-${id}`} className="alerts-listwrap">
      <h2 id={`alerts-page-${id}`} className={`alerts-grp alerts-grp--page${primary ? ' alerts-grp--need' : ''}`}>
        <span>{title}</span>
        <span>
          <VisuallyHidden>, </VisuallyHidden>
          {items.length}
        </span>
      </h2>
      <ul aria-label={title} className="alerts-list">
        {items.map((alert) => (
          <AlertRow key={alert.id} alert={alert} now={now} onOpen={onOpen} onMark={onMark} notice={notices[alert.id]} />
        ))}
      </ul>
    </section>
  );
}

type RowProps = { alert: Alert; now: number; onOpen: OpenAlert; onMark: (alert: Alert) => void; notice?: RowNotice };

/** One alert: avatar, title over subject and meta, NEW while unread. A row with a link is one link to it. */
function AlertRow({ alert, now, onOpen, onMark, notice }: RowProps) {
  const unread = !alert.read;
  const href = alertHref(alert);
  const content = (
    <>
      <AlertAvatar agent={alert.agent} />
      <AlertBody alert={alert} now={now} />
      {unread && (
        <Tag tone="neutral" className="alerts-new">
          <VisuallyHidden>, </VisuallyHidden>NEW
        </Tag>
      )}
    </>
  );
  return (
    <li className={unread ? 'alerts-row alerts-row--unread' : 'alerts-row'}>
      {href ? (
        <NextLink href={href} className="alerts-link" onClick={(event) => void onOpen(event, alert)}>
          {content}
        </NextLink>
      ) : (
        <div className="alerts-link alerts-link--plain">{content}</div>
      )}
      {(notice || (unread && !href)) && (
        <div className="alerts-rowtail">
          <RowTail alert={alert} notice={notice} onMark={onMark} />
        </div>
      )}
    </li>
  );
}
