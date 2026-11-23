'use client';

import { useCallback, useEffect, useState } from 'react';

import { call, liveApi } from '@/api/client';
import { ApiError, networkError } from '@/api/errors';
import type { LiveWorkItem } from '@/api/types';
import { POLL_MS } from '../useWorkItem';

import { needsPolling } from './model';

const ACCESS_LOST = new Set<ApiError['kind']>(['unauthenticated', 'forbidden', 'not_found']);

export type LiveWorkItemState =
  | { status: 'loading' }
  | { status: 'error'; error: ApiError }
  | { status: 'ready'; item: LiveWorkItem; loadedAt: Date; refreshFailed: boolean };

/** GET /work/{id}. Re-read every 5 s while the item is being watched or processing and the tab is visible; otherwise one read.
 *  A failed poll keeps the last good item; lost access replaces it and stops polling. */
export function useLiveWorkItem(id: number) {
  const [state, setState] = useState<LiveWorkItemState>({ status: 'loading' });

  const fetchItem = useCallback(() => call(liveApi.GET('/api/v1/work/{work_id}', { params: { path: { work_id: id } } })), [id]);

  const load = useCallback(async () => {
    setState({ status: 'loading' });
    try {
      setState({ status: 'ready', item: await fetchItem(), loadedAt: new Date(), refreshFailed: false });
    } catch (error) {
      setState({ status: 'error', error: error instanceof ApiError ? error : networkError() });
    }
  }, [fetchItem]);

  useEffect(() => {
    // One read per opened item; the effect only starts the request.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, [load]);

  /** A quiet re-read after a write: the page stays as it is while it loads. Resolves to the new item, or null when the read failed
   *  (the page then says it couldn't refresh); lost access replaces the page. */
  const reload = useCallback(async (): Promise<LiveWorkItem | null> => {
    try {
      const item = await fetchItem();
      setState({ status: 'ready', item, loadedAt: new Date(), refreshFailed: false });
      return item;
    } catch (error) {
      if (error instanceof ApiError && ACCESS_LOST.has(error.kind)) setState({ status: 'error', error });
      else setState((s) => (s.status === 'ready' ? { ...s, refreshFailed: true } : s));
      return null;
    }
  }, [fetchItem]);

  /** A write answered 401 or 404: the page shows the signed-out or unavailable state. */
  const lose = useCallback((error: ApiError) => setState({ status: 'error', error }), []);

  const polling = state.status === 'ready' && needsPolling(state.item);

  useEffect(() => {
    if (!polling) return;
    let active = true;
    let timer: ReturnType<typeof setTimeout> | undefined;

    const schedule = () => {
      clearTimeout(timer);
      timer = document.visibilityState === 'visible' ? setTimeout(() => void poll(), POLL_MS) : undefined;
    };
    const poll = async () => {
      try {
        const item = await fetchItem();
        if (active) setState({ status: 'ready', item, loadedAt: new Date(), refreshFailed: false });
      } catch (error) {
        if (error instanceof ApiError && ACCESS_LOST.has(error.kind)) {
          if (active) setState({ status: 'error', error });
          return;
        }
        if (active) setState((s) => (s.status === 'ready' ? { ...s, refreshFailed: true } : s));
      }
      if (active) schedule();
    };

    schedule();
    document.addEventListener('visibilitychange', schedule);
    return () => {
      active = false;
      clearTimeout(timer);
      document.removeEventListener('visibilitychange', schedule);
    };
  }, [polling, fetchItem]);

  return { state, retry: load, reload, lose };
}
