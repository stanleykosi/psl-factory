'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

import { call, liveApi } from '@/api/client';
import { ApiError, networkError, UNEXPECTED_MESSAGE } from '@/api/errors';

import { isJourney, type Journey } from './model';

export type JourneyState = { status: 'loading' } | { status: 'error'; error: ApiError } | { status: 'ready'; journey: Journey };
export type MoreState = 'idle' | 'loading' | 'error';

const unexpected = () => new ApiError(200, 'server', 'unexpected_response', UNEXPECTED_MESSAGE);

/**
 * One GET /projects/{case_id} read per opened project (page 1); "Show more" reads the next page and appends its rows.
 * A late response for an earlier project is ignored. No polling.
 */
export function useProject(caseId: string) {
  const [state, setState] = useState<JourneyState>({ status: 'loading' });
  const [more, setMore] = useState<MoreState>('idle');
  const seq = useRef(0);
  const readPage = useCallback(
    async (page?: number) => {
      const data = await call(liveApi.GET('/api/v1/projects/{case_id}', { params: { path: { case_id: caseId }, query: page ? { page } : {} } }));
      if (!isJourney(data)) throw unexpected();
      return data;
    },
    [caseId],
  );

  const load = useCallback(async () => {
    const mine = ++seq.current;
    setState({ status: 'loading' });
    setMore('idle');
    try {
      const data = await readPage();
      if (mine !== seq.current) return;
      setState({ status: 'ready', journey: data });
    } catch (error) {
      if (mine !== seq.current) return;
      setState({ status: 'error', error: error instanceof ApiError ? error : networkError() });
    }
  }, [readPage]);

  const showMore = useCallback(async () => {
    if (state.status !== 'ready' || !state.journey.next_page) return;
    const mine = seq.current;
    setMore('loading');
    try {
      const data = await readPage(state.journey.next_page);
      if (mine !== seq.current) return;
      setState((prev) => (prev.status !== 'ready' ? prev : { status: 'ready', journey: { ...prev.journey, items: [...prev.journey.items, ...data.items], page: data.page, next_page: data.next_page } }));
      setMore('idle');
    } catch (error) {
      if (mine !== seq.current) return;
      if (error instanceof ApiError && error.kind === 'unauthenticated') setState({ status: 'error', error });
      else setMore('error');
    }
  }, [state, readPage]);

  useEffect(() => {
    // The effect only starts the request.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, [load]);

  return { state, retry: load, more, showMore };
}
