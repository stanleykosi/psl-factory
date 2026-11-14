'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

import { api, call } from '@/api/client';
import { ApiError, networkError } from '@/api/errors';

import type { HistoryEntry, HistoryKind, HistoryLimit } from './labels';

export type WorkHistoryState =
  | { status: 'loading' }
  | { status: 'error'; error: ApiError }
  | { status: 'ready'; items: HistoryEntry[]; nextCursor?: string; asOf: string; more: 'idle' | 'loading' | 'failed' };

/** One work item's history (D-PAGING r2): rows in the order returned, cursor "Show more" appends. */
export function useWorkHistory(id: string, revision: number) {
  const [kind, setKind] = useState<HistoryKind>('all');
  const [limit, setLimit] = useState<HistoryLimit>(20);
  const [state, setState] = useState<WorkHistoryState>({ status: 'loading' });
  // Answers to an earlier filter, limit or revision are dropped.
  const request = useRef(0);

  const fetchPage = useCallback(
    (cursor?: string) =>
      call(
        api.GET('/api/v1/work/{work_id}/history', {
          params: { path: { work_id: id }, query: cursor ? { kind, limit, cursor } : { kind, limit } },
        }),
      ),
    [id, kind, limit],
  );

  const load = useCallback(async () => {
    const n = ++request.current;
    setState({ status: 'loading' });
    try {
      const page = await fetchPage();
      if (n === request.current) {
        setState({ status: 'ready', items: page.items, nextCursor: page.next_cursor, asOf: page.as_of, more: 'idle' });
      }
    } catch (error) {
      if (n === request.current) setState({ status: 'error', error: error instanceof ApiError ? error : networkError() });
    }
  }, [fetchPage]);

  useEffect(() => {
    // First page on open, on a new filter or limit, and whenever the item's revision changes.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, [load, revision]);

  const cursor = state.status === 'ready' ? state.nextCursor : undefined;
  const showMore = useCallback(async () => {
    if (!cursor) return;
    const n = request.current;
    setState((s) => (s.status === 'ready' ? { ...s, more: 'loading' } : s));
    try {
      const page = await fetchPage(cursor);
      if (n !== request.current) return;
      setState((s) =>
        s.status === 'ready'
          ? { status: 'ready', items: [...s.items, ...page.items], nextCursor: page.next_cursor, asOf: page.as_of, more: 'idle' }
          : s,
      );
    } catch {
      if (n === request.current) setState((s) => (s.status === 'ready' ? { ...s, more: 'failed' } : s));
    }
  }, [cursor, fetchPage]);

  return { state, kind, setKind, limit, setLimit, retry: load, showMore };
}
