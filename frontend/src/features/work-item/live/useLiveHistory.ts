'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

import { call, liveApi } from '@/api/client';
import { ApiError, networkError } from '@/api/errors';
import type { LiveHistoryRow } from '@/api/types';

import { mergeHistory, type LiveHistoryKind } from './model';

export type LiveHistoryState =
  | { status: 'loading' }
  | { status: 'error'; error: ApiError }
  | { status: 'ready'; items: LiveHistoryRow[]; asOf: string; nextBefore: number | null; older: 'idle' | 'loading' | { error: ApiError } };

/** GET /work/{id}/history?kind=&before=: the latest 30 changes, then older ones by the `next_before` cursor. The chosen tab is kept through an error.
 *  Changing the tab starts again at the first page; an answer to an earlier tab or page is dropped. */
export function useLiveHistory(id: number) {
  const [kind, setKind] = useState<LiveHistoryKind>('all');
  const [state, setState] = useState<LiveHistoryState>({ status: 'loading' });
  const request = useRef(0);

  const read = useCallback(
    (before?: number) =>
      call(
        liveApi.GET('/api/v1/work/{work_id}/history', {
          params: { path: { work_id: id }, query: { ...(kind === 'all' ? {} : { kind }), ...(before === undefined ? {} : { before }) } },
        }),
      ),
    [id, kind],
  );

  const load = useCallback(async () => {
    const n = ++request.current;
    setState({ status: 'loading' });
    try {
      const page = await read();
      if (n === request.current) setState({ status: 'ready', items: page.items, asOf: page.as_of, nextBefore: page.next_before, older: 'idle' });
    } catch (error) {
      if (n === request.current) setState({ status: 'error', error: error instanceof ApiError ? error : networkError() });
    }
  }, [read]);

  useEffect(() => {
    void load();
  }, [load]);

  /** Older events: the same tab with `before` set to the cursor. A failure keeps the rows and says why; nothing retries by itself. */
  const loadOlder = useCallback(async () => {
    if (state.status !== 'ready' || state.nextBefore === null || state.older === 'loading') return;
    const n = ++request.current;
    const { nextBefore } = state;
    setState({ ...state, older: 'loading' });
    try {
      const page = await read(nextBefore);
      if (n === request.current) setState((s) => (s.status === 'ready' ? { ...s, items: mergeHistory(s.items, page.items), nextBefore: page.next_before, older: 'idle' } : s));
    } catch (error) {
      if (n === request.current) setState((s) => (s.status === 'ready' ? { ...s, older: { error: error instanceof ApiError ? error : networkError() } } : s));
    }
  }, [read, state]);

  return { state, kind, setKind, retry: load, loadOlder };
}
