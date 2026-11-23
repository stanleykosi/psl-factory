'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

import { call, liveApi } from '@/api/client';
import { ApiError, networkError } from '@/api/errors';
import type { LiveHistoryRow } from '@/api/types';

import type { LiveHistoryKind } from './model';

export type LiveHistoryState =
  | { status: 'loading' }
  | { status: 'error'; error: ApiError }
  | { status: 'ready'; items: LiveHistoryRow[]; asOf: string };

/** GET /work/{id}/history?kind=: the latest changes the API returns (no paging, no counts). The chosen tab is kept through an error. */
export function useLiveHistory(id: number) {
  const [kind, setKind] = useState<LiveHistoryKind>('all');
  const [state, setState] = useState<LiveHistoryState>({ status: 'loading' });
  // An answer to an earlier tab is dropped.
  const request = useRef(0);

  const load = useCallback(async () => {
    const n = ++request.current;
    setState({ status: 'loading' });
    try {
      const page = await call(
        liveApi.GET('/api/v1/work/{work_id}/history', { params: { path: { work_id: id }, query: kind === 'all' ? {} : { kind } } }),
      );
      if (n === request.current) setState({ status: 'ready', items: page.items, asOf: page.as_of });
    } catch (error) {
      if (n === request.current) setState({ status: 'error', error: error instanceof ApiError ? error : networkError() });
    }
  }, [id, kind]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, [load]);

  return { state, kind, setKind, retry: load };
}
