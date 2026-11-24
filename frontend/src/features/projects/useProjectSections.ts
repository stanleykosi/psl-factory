'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

import { call, liveApi } from '@/api/client';
import { ApiError, networkError, UNEXPECTED_MESSAGE } from '@/api/errors';

import { buildSectionQuery, isSectionsBody, mergePage, type Section, type SectionsTab } from './sectionsModel';

export type SectionsState =
  | { status: 'loading' }
  | { status: 'error'; error: ApiError }
  | { status: 'ready'; sections: Section[]; requestedPage: number; asOf: string };
export type MoreState = 'idle' | 'loading' | 'error';

const asApiError = (error: unknown) => (error instanceof ApiError ? error : networkError());

/**
 * One GET /projects/{case_id}/{tab} read per (case, tab, settled search); "Show more" reads the next page for every
 * section and merges it. A late answer for an earlier view is ignored (sequence guard). A failed read drops the rows.
 * No polling, no automatic retry.
 */
export function useProjectSections(caseId: string, tab: SectionsTab, q: string | undefined) {
  const [state, setState] = useState<SectionsState>({ status: 'loading' });
  const [more, setMore] = useState<MoreState>('idle');
  const seq = useRef(0);

  const readPage = useCallback(
    async (page?: number) => {
      const data = await call(liveApi.GET('/api/v1/projects/{case_id}/{tab}', { params: { path: { case_id: caseId, tab }, query: buildSectionQuery(q, page) } }));
      if (!isSectionsBody(data, tab)) throw new ApiError(200, 'server', 'unexpected_response', UNEXPECTED_MESSAGE);
      return data;
    },
    [caseId, tab, q],
  );

  const load = useCallback(async () => {
    const mine = ++seq.current;
    setState({ status: 'loading' });
    setMore('idle');
    try {
      const data = await readPage();
      if (mine !== seq.current) return;
      setState({ status: 'ready', sections: data.sections, requestedPage: 1, asOf: data.as_of });
    } catch (error) {
      if (mine !== seq.current) return;
      setState({ status: 'error', error: asApiError(error) });
    }
  }, [readPage]);

  const showMore = useCallback(async () => {
    if (state.status !== 'ready') return;
    const mine = seq.current;
    const page = state.requestedPage + 1;
    setMore('loading');
    try {
      const data = await readPage(page);
      if (mine !== seq.current) return;
      setState((prev) => (prev.status !== 'ready' ? prev : { status: 'ready', sections: mergePage(prev.sections, data.sections, page), requestedPage: page, asOf: data.as_of }));
      setMore('idle');
    } catch (error) {
      if (mine !== seq.current) return;
      const e = asApiError(error);
      if (e.kind === 'unauthenticated' || e.kind === 'forbidden' || e.kind === 'not_found') setState({ status: 'error', error: e });
      else setMore('error');
    }
  }, [state, readPage]);

  useEffect(() => {
    // The effect only starts the request.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, [load]);

  return { state, more, showMore, retry: load };
}
