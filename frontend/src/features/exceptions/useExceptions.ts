'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

import { api, call } from '@/api/client';
import { ApiError, networkError } from '@/api/errors';

import type { ExceptionRow, ExceptionsLimit } from './types';

export type ExceptionsState =
  | { status: 'loading' }
  | { status: 'error'; error: ApiError }
  | { status: 'ready'; items: ExceptionRow[]; nextCursor?: string; asOf: string; more: 'idle' | 'loading' | 'failed' };

/** E-EXCEPTIONS (D-PAGING): rows in the order returned; cursor "Show more" appends. The backend filters by grants. */
export function useExceptions({ limit: initialLimit = 20 }: { limit?: ExceptionsLimit } = {}) {
  const [limit, setLimit] = useState<ExceptionsLimit>(initialLimit);
  const [state, setState] = useState<ExceptionsState>({ status: 'loading' });
  // Answers to an earlier limit or an earlier Try again are dropped.
  const request = useRef(0);

  const fetchPage = useCallback(
    (cursor?: string) =>
      call(api.GET('/api/v1/exceptions', { params: { query: cursor ? { limit, cursor } : { limit } } })),
    [limit],
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
    // First page on open and whenever the limit changes.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, [load]);

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
    } catch (error) {
      if (n !== request.current) return;
      // A sign-out on Show more replaces the list with the signed-out state; anything else keeps the rows.
      if (error instanceof ApiError && error.kind === 'unauthenticated') setState({ status: 'error', error });
      else setState((s) => (s.status === 'ready' ? { ...s, more: 'failed' } : s));
    }
  }, [cursor, fetchPage]);

  return { state, limit, setLimit, retry: load, showMore };
}
