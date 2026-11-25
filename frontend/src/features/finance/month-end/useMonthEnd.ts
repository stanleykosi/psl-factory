'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

import { call, liveApi } from '@/api/client';
import { ApiError, networkError, UNEXPECTED_MESSAGE } from '@/api/errors';

import type { MonthEnd } from './types';

export type MonthEndState = { status: 'loading' } | { status: 'error'; error: ApiError } | { status: 'ready'; body: MonthEnd };

const asApiError = (error: unknown) => (error instanceof ApiError ? error : networkError());

/** A 200 missing a field the page reads is not a month-end body. */
function checked(data: MonthEnd) {
  if (!Array.isArray(data?.work) || !Array.isArray(data.cash) || !Array.isArray(data.workspaces) || typeof data.counts !== 'object' || data.counts === null) {
    throw new ApiError(200, 'server', 'unexpected_response', UNEXPECTED_MESSAGE);
  }
  return data;
}

const fetchPage = (month: string, page?: number): Promise<MonthEnd> =>
  call(liveApi.GET('/api/v1/month-end', { params: { query: { month, ...(page ? { page } : {}) } } }));

/** One read of GET /month-end per page open (no polling); Try again re-reads, "Show more" appends the next page. */
export function useMonthEnd(period: string) {
  const [state, setState] = useState<MonthEndState>({ status: 'loading' });
  const [more, setMore] = useState<'idle' | 'loading' | 'error'>('idle');
  // Answers to a superseded period or an earlier try are dropped.
  const request = useRef(0);
  const pressed = useRef(false);

  const load = useCallback(async () => {
    const n = ++request.current;
    setState({ status: 'loading' });
    setMore('idle');
    try {
      const body = checked(await fetchPage(period));
      if (n === request.current) setState({ status: 'ready', body });
    } catch (error) {
      if (n === request.current) setState({ status: 'error', error: asApiError(error) });
    }
  }, [period]);

  useEffect(() => {
    // The effect only starts the request.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, [load]);

  /** Appends the next page's rows; the counts, cash and time stay as page 1 returned them. */
  const showMore = async () => {
    if (state.status !== 'ready' || state.body.next_page === null || pressed.current) return;
    pressed.current = true;
    const n = request.current;
    setMore('loading');
    try {
      const page = checked(await fetchPage(period, state.body.next_page));
      if (n !== request.current) return;
      setState((prev) => (prev.status !== 'ready' ? prev : { status: 'ready', body: { ...prev.body, work: [...prev.body.work, ...page.work], page: page.page, next_page: page.next_page } }));
      setMore('idle');
    } catch (error) {
      if (n !== request.current) return;
      const e = asApiError(error);
      if (e.kind === 'unauthenticated') setState({ status: 'error', error: e });
      else setMore('error');
    } finally {
      pressed.current = false;
    }
  };

  return { state, more, retry: load, showMore };
}
