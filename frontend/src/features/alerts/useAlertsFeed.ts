'use client';

// The bell's feed (F-15, F-61): page 1 of GET /api/v1/notifications. One request when the frame is
// ready, one each time the drawer opens, and one when the tab comes back after more than 5 minutes; never a timer,
// never two at once, and nothing more after a 401. Marking read changes the held list only.
import { useCallback, useEffect, useRef, useState } from 'react';

import { readInboxFirstPage } from '@/api/alerts';
import { ApiError, networkError } from '@/api/errors';

import type { Alert, DailySummary } from './types';

const STALE_MS = 5 * 60_000;

/** Dispatched on window with the alert id once the server accepted a mark-read. */
export const ALERT_READ_EVENT = 'psl:alert-read';

/** The latest successful page 1; `unread` is the server's total for the whole inbox; `now` is when it arrived, for the meta line's "10:42" and "yesterday". */
export type FeedData = { items: Alert[]; unread: number; asOf: string; summary?: DailySummary; now: number };
export type AlertsFeed = {
  data?: FeedData;
  /** The latest attempt failed; cleared by the next success. */
  error?: ApiError;
  loading: boolean;
  refresh: () => Promise<void>;
  markRead: (id: string) => void;
  /** A failed request elsewhere (a mark-read): a 401 stops further reads, as it does for the list. */
  stop: (error: ApiError) => void;
};

export function useAlertsFeed(enabled: boolean): AlertsFeed {
  const [data, setData] = useState<FeedData>();
  const [error, setError] = useState<ApiError>();
  const [loading, setLoading] = useState(false);
  const inFlight = useRef(false);
  const stopped = useRef(false);
  const loadedAt = useRef(0);
  const readIds = useRef(new Set<string>());

  const refresh = useCallback(async () => {
    if (inFlight.current || stopped.current) return;
    inFlight.current = true;
    setLoading(true);
    try {
      const list = await readInboxFirstPage();
      // A body without an items list is not an alerts list: shown as a load error, never as "no alerts".
      if (!Array.isArray(list?.items)) throw networkError();
      loadedAt.current = Date.now();
      // A list read before a mark-read can arrive after it: keep what this session marked read.
      const stale = list.items.filter((alert) => alert.read === false && readIds.current.has(alert.id)).length;
      const items = stale ? list.items.map((alert) => (readIds.current.has(alert.id) ? { ...alert, read: true } : alert)) : list.items;
      // The count is the server's; without a number it is unknown, so the list is a load error and the badge stays hidden.
      if (typeof list.unread !== 'number') throw networkError();
      setData({ items, unread: Math.max(0, list.unread - stale), asOf: list.as_of, summary: list.daily_summary, now: loadedAt.current });
      setError(undefined);
    } catch (caught) {
      const e = caught instanceof ApiError ? caught : networkError();
      if (e.kind === 'unauthenticated') stopped.current = true;
      setError(e);
    }
    inFlight.current = false;
    setLoading(false);
  }, []);

  useEffect(() => {
    if (!enabled) return;
    // One request when /me is ready; the effect only starts it.
    void refresh();
  }, [enabled, refresh]);

  useEffect(() => {
    if (!enabled) return undefined;
    function onVisible() {
      if (document.visibilityState === 'visible' && loadedAt.current > 0 && Date.now() - loadedAt.current > STALE_MS) void refresh();
    }
    document.addEventListener('visibilitychange', onVisible);
    return () => document.removeEventListener('visibilitychange', onVisible);
  }, [enabled, refresh]);

  const markRead = useCallback((id: string) => {
    readIds.current.add(id);
    setData((prev) => {
      const item = prev?.items.find((alert) => alert.id === id);
      if (!prev || !item || item.read) return prev;
      return { ...prev, unread: Math.max(0, prev.unread - 1), items: prev.items.map((alert) => (alert.id === id ? { ...alert, read: true } : alert)) };
    });
  }, []);

  // A mark-read made elsewhere (the Notifications page) lowers the badge the same way.
  useEffect(() => {
    if (!enabled) return undefined;
    const onRead = (event: Event) => markRead((event as CustomEvent<string>).detail);
    window.addEventListener(ALERT_READ_EVENT, onRead);
    return () => window.removeEventListener(ALERT_READ_EVENT, onRead);
  }, [enabled, markRead]);

  const stop = useCallback((e: ApiError) => {
    if (e.kind !== 'unauthenticated') return;
    stopped.current = true;
    setError(e);
  }, []);

  return { data, error, loading, refresh, markRead, stop };
}
