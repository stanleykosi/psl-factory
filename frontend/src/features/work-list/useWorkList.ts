'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

import { call, liveApi } from '@/api/client';
import { ApiError, networkError } from '@/api/errors';

import type { MoreState, WorkCoverage, WorkLine, WorkListFilters, WorkListPage, WorkListRow, WorkQueue } from './types';

/** One click or first load asks at most this many pages while they come back empty. */
export const MAX_EMPTY_PAGES = 10;

export type WorkListState =
  | { status: 'loading' }
  | { status: 'error'; error: ApiError }
  | {
      status: 'ready';
      items: WorkListRow[];
      /** Titles for the keys on the rows: the latest response's `lines[]`. */
      lines: WorkLine[];
      /** The line filter's choices: `lines[]` of the first page of this queue, kept while a filter is applied. */
      lineOptions: WorkLine[];
      asOf: string;
      coverage: WorkCoverage;
      more: MoreState;
    };

export type WorkListQuery = WorkListFilters & { queue: WorkQueue };

const coverageOf = (page: WorkListPage): WorkCoverage => ({ limited: page.limited, evaluated: page.evaluated, deferredCount: page.deferred.length });

/**
 * The live work list, for any queue (GET /api/v1/work). Rows come back in the server's order, 8 to a page, and are
 * never re-sorted. A page with no rows and a `next_page` is skipped: the list keeps asking (up to MAX_EMPTY_PAGES
 * requests, then "keep-looking") until rows arrive or `next_page` is null. Changing the queue, line, search or
 * project restarts from page 1 and drops the answers to earlier requests.
 *
 *   const { state, loadMore, retry, setFilters, filters } = useWorkList({ queue: 'verified' });
 *   state: { status: 'loading' } | { status: 'error', error } | { status: 'ready', items, lines, lineOptions, asOf, coverage, more }
 */
export function useWorkList({ queue, line, q, project }: WorkListQuery) {
  const [filters, setFilters] = useState<WorkListFilters>({ line, q, project });
  const [state, setState] = useState<WorkListState>({ status: 'loading' });
  // The page to ask for next; null when the list is complete.
  const next = useRef<number | null>(1);
  // Answers to an earlier queue, filter or Try again are dropped.
  const request = useRef(0);
  // The line filter's choices, kept across filter changes within one queue so a narrowed list can be widened again.
  const options = useRef<{ queue: WorkQueue; lines: WorkLine[] } | null>(null);

  const fetchPage = useCallback(
    async (page: number) => {
      const query: { queue: WorkQueue; page: number; line?: WorkListFilters['line']; q?: string; project?: string } = { queue, page };
      if (filters.line) query.line = filters.line;
      if (filters.q) query.q = filters.q;
      if (filters.project) query.project = filters.project;
      return call(liveApi.GET('/api/v1/work', { params: { query } }));
    },
    [queue, filters],
  );

  /** Asks from `first` until a page has rows, the list ends, or the cap is reached. */
  const collect = useCallback(
    async (first: number, n: number) => {
      let page = first;
      for (let asked = 1; ; asked += 1) {
        const body = await fetchPage(page);
        if (n !== request.current || body.items.length > 0 || body.next_page === null || asked >= MAX_EMPTY_PAGES) return body;
        page = body.next_page;
      }
    },
    [fetchPage],
  );

  const moreOf = (body: WorkListPage): MoreState => (body.next_page === null ? 'done' : body.items.length === 0 ? 'keep-looking' : 'idle');

  const load = useCallback(async () => {
    const n = ++request.current;
    setState({ status: 'loading' });
    try {
      const body = await collect(1, n);
      if (n !== request.current) return;
      next.current = body.next_page;
      if (!filters.line || options.current?.queue !== queue) options.current = { queue, lines: body.lines };
      setState({ status: 'ready', items: body.items, lines: body.lines, lineOptions: options.current.lines, asOf: body.as_of, coverage: coverageOf(body), more: moreOf(body) });
    } catch (error) {
      if (n === request.current) setState({ status: 'error', error: error instanceof ApiError ? error : networkError() });
    }
  }, [collect, filters.line, queue]);

  useEffect(() => {
    // First page on open and whenever the queue, line, search or project changes.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, [load]);

  const loadMore = useCallback(async () => {
    const page = next.current;
    if (page === null) return;
    const n = request.current;
    setState((s) => (s.status === 'ready' ? { ...s, more: 'loading' } : s));
    try {
      const body = await collect(page, n);
      if (n !== request.current) return;
      next.current = body.next_page;
      setState((s) => {
        if (s.status !== 'ready') return s;
        const seen = new Set(s.items.map((row) => row.id));
        const added = body.items.filter((row) => !seen.has(row.id));
        return {
          ...s,
          items: [...s.items, ...added],
          lines: body.lines,
          lineOptions: s.lineOptions,
          asOf: body.as_of,
          coverage: coverageOf(body),
          more: moreOf(body),
        };
      });
    } catch (error) {
      if (n !== request.current) return;
      // A sign-out while paging replaces the list with the signed-out state; anything else keeps the rows shown.
      if (error instanceof ApiError && error.kind === 'unauthenticated') setState({ status: 'error', error });
      else setState((s) => (s.status === 'ready' ? { ...s, more: 'failed' } : s));
    }
  }, [collect]);

  return { state, loadMore, retry: load, setFilters, filters: { queue, ...filters } };
}
