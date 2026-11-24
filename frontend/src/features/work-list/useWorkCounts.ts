'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

import { call, liveApi } from '@/api/client';
import { ApiError, networkError } from '@/api/errors';

import type { WorkCounts } from './types';

export type WorkCountsState = { status: 'loading' } | { status: 'error'; error: ApiError } | { status: 'ready'; counts: WorkCounts };

/**
 * The person's whole queues and per-line summaries (GET /api/v1/work/counts), read with no filter so a tab keeps
 * showing its queue while the list is narrowed. `refresh()` re-reads in place: numbers already shown stay when a
 * refresh fails, and the answer says whether it could be read. A first read that fails leaves `error`.
 *
 *   const { state, refresh } = useWorkCounts();
 */
export function useWorkCounts() {
  const [state, setState] = useState<WorkCountsState>({ status: 'loading' });
  const live = useRef(true);

  const refresh = useCallback(async () => {
    try {
      const counts = await call(liveApi.GET('/api/v1/work/counts', { params: { query: {} } }));
      if (live.current) setState({ status: 'ready', counts });
      return true;
    } catch (error) {
      if (live.current) setState((s) => (s.status === 'ready' ? s : { status: 'error', error: error instanceof ApiError ? error : networkError() }));
      return false;
    }
  }, []);

  useEffect(() => {
    live.current = true;
    void refresh();
    return () => {
      live.current = false;
    };
  }, [refresh]);

  return { state, refresh };
}
