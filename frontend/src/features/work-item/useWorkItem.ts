'use client';

import { useCallback, useEffect, useState } from 'react';

import { api, call } from '@/api/client';
import { ApiError, networkError } from '@/api/errors';

import type { WorkItem } from './labels';

/** D-UPDATES r2: the open item is re-read every 5 s while its agent works and the page is visible. */
export const POLL_MS = 5000;
const ACCESS_LOST = new Set<ApiError['kind']>(['unauthenticated', 'forbidden', 'not_found']);

export type WorkItemState =
  | { status: 'loading' }
  | { status: 'error'; error: ApiError }
  | { status: 'ready'; item: WorkItem; loadedAt: Date; refreshFailed: boolean };

export function useWorkItem(id: string) {
  const [state, setState] = useState<WorkItemState>({ status: 'loading' });

  const fetchItem = useCallback(() => call(api.GET('/api/v1/work/{work_id}', { params: { path: { work_id: id } } })), [id]);

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

  const working = state.status === 'ready' && state.item.agent.status === 'working';

  useEffect(() => {
    if (!working) return;
    let active = true;
    let timer: ReturnType<typeof setTimeout> | undefined;

    const schedule = () => {
      clearTimeout(timer);
      timer = document.visibilityState === 'visible' ? setTimeout(() => void poll(), POLL_MS) : undefined;
    };
    // A failed poll keeps the last good item on screen and the next poll tries again, unless access was lost:
    // then the signed-out or no-access state replaces the item and polling stops.
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
  }, [working, fetchItem]);

  return { state, retry: load };
}
