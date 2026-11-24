'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

import { api, call } from '@/api/client';
import { ApiError, networkError, UNEXPECTED_MESSAGE } from '@/api/errors';
import { DEFAULT_PAGE_SIZE, type PageSize } from '@/components';

import { buildTabQuery, isTabResponse, rowsOf, type ReadTab, type TabResponse, type TabRows, type TabView } from './tabsModel';

export type TabState<T extends ReadTab> =
  | { status: 'loading' }
  | { status: 'error'; error: ApiError }
  | { status: 'ready'; rows: TabRows[T]; summary: TabResponse['summary']; asOf: string; nextCursor?: string };

const asApiError = (error: unknown) => (error instanceof ApiError ? error : networkError());

/**
 * One E-PROJECT-TAB read per view (tab, settled search); "Show more" appends the next page. A late answer
 * for an earlier view is ignored (sequence guard). A failed read drops the earlier rows. No polling, no automatic retry.
 */
export function useProjectTab<T extends ReadTab>(caseId: string, tab: T, view: TabView) {
  const [state, setState] = useState<TabState<T>>({ status: 'loading' });
  const [more, setMore] = useState<'idle' | 'loading' | 'error'>('idle');
  const seq = useRef(0);
  const { q } = view;

  const fetchPage = useCallback(
    async (limit: PageSize, cursor?: string) => {
      const query = buildTabQuery({ q }, cursor, limit);
      const data = await call(api.GET('/api/v1/projects/{case_id}/{tab}', { params: { path: { case_id: caseId, tab }, query } }));
      if (!isTabResponse(data, tab)) throw new ApiError(200, 'server', 'unexpected_response', UNEXPECTED_MESSAGE);
      return data;
    },
    [caseId, tab, q],
  );

  const load = useCallback(async () => {
    const mine = ++seq.current;
    setState({ status: 'loading' });
    setMore('idle');
    try {
      const data = await fetchPage(DEFAULT_PAGE_SIZE);
      if (mine !== seq.current) return;
      setState({ status: 'ready', rows: rowsOf(data, tab), summary: data.summary, asOf: data.as_of, nextCursor: data.next_cursor });
    } catch (error) {
      if (mine !== seq.current) return;
      setState({ status: 'error', error: asApiError(error) });
    }
  }, [fetchPage, tab]);

  const showMore = useCallback(async (limit: PageSize) => {
    if (state.status !== 'ready' || !state.nextCursor) return;
    const mine = seq.current;
    setMore('loading');
    try {
      const data = await fetchPage(limit, state.nextCursor);
      if (mine !== seq.current) return;
      setState((prev) =>
        prev.status !== 'ready' ? prev : { ...prev, rows: [...prev.rows, ...rowsOf(data, tab)] as TabRows[T], asOf: data.as_of, nextCursor: data.next_cursor },
      );
      setMore('idle');
    } catch (error) {
      if (mine !== seq.current) return;
      const e = asApiError(error);
      if (e.kind === 'unauthenticated' || e.kind === 'forbidden' || e.kind === 'not_found') setState({ status: 'error', error: e });
      else setMore('error');
    }
  }, [state, fetchPage, tab]);

  useEffect(() => {
    // The effect only starts the request.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, [load]);

  return { state, more, showMore, retry: load };
}
