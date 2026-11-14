'use client';

// The bell's feed (F-15): page 1 of E-NOTIFICATIONS with the server's default page. One request when the frame is
// ready, one each time the drawer opens, and one when the tab comes back after more than 5 minutes; never a timer,
// never two at once, and nothing more after a 401. Marking read changes the held list only.
import { useCallback, useEffect, useRef, useState } from 'react';

import { api, call } from '@/api/client';
import { ApiError, networkError } from '@/api/errors';

import type { AlertWithNeed } from './types';

const STALE_MS = 5 * 60_000;

/** The latest successful list; `now` is when it arrived, for the meta line's "10:42" and "yesterday". */
export type FeedData = { items: AlertWithNeed[]; unreadCount?: number; asOf: string; now: number };
export type AlertsFeed = {
  data?: FeedData;
  /** The latest attempt failed; cleared by the next success. */
  error?: ApiError;
  loading: boolean;
  refresh: () => Promise<void>;
  markRead: (id: string) => void;
};

export function useAlertsFeed(enabled: boolean): AlertsFeed {
  const [data, setData] = useState<FeedData>();
  const [error, setError] = useState<ApiError>();
  const [loading, setLoading] = useState(false);
  const inFlight = useRef(false);
  const stopped = useRef(false);
  const loadedAt = useRef(0);

  const refresh = useCallback(async () => {
    if (inFlight.current || stopped.current) return;
    inFlight.current = true;
    setLoading(true);
    try {
      const list = await call(api.GET('/api/v1/notifications'));
      // A body without an items list is not an alerts list: shown as a load error, never as "no alerts".
      if (!Array.isArray(list?.items)) throw networkError();
      loadedAt.current = Date.now();
      setData({ items: list.items, unreadCount: list.unread_count, asOf: list.as_of, now: loadedAt.current });
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
    setData((prev) => {
      const item = prev?.items.find((alert) => alert.id === id);
      if (!prev || !item || item.read) return prev;
      const unreadCount = prev.unreadCount === undefined ? undefined : Math.max(0, prev.unreadCount - 1);
      return { ...prev, unreadCount, items: prev.items.map((alert) => (alert.id === id ? { ...alert, read: true } : alert)) };
    });
  }, []);

  return { data, error, loading, refresh, markRead };
}
