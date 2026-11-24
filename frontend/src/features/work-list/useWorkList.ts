'use client';

import { useCallback, useEffect, useMemo, useRef, useState, type SetStateAction } from 'react';

import { call, liveApi } from '@/api/client';
import { ApiError, networkError } from '@/api/errors';

import type { MoreState, WorkCoverage, WorkLimit, WorkLine, WorkListFilters, WorkListPage, WorkListRow, WorkQueue, WorkState } from './types';

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
      /** The server's count for the narrowed list. Exact only when `totalComplete`; otherwise unknown, never 0. */
      total: number | null;
      totalComplete: boolean;
      pageSize: number;
    };

/** `enabled` false keeps the list from asking at all (a tab whose body is not this list). */
export type WorkListQuery = WorkListFilters & { queue: WorkQueue; enabled?: boolean };

const coverageOf = (page: WorkListPage): WorkCoverage => ({ limited: page.limited, evaluated: page.evaluated, deferredCount: page.deferred.length });
const totalsOf = (page: WorkListPage) => ({ total: page.total, totalComplete: page.total_coverage === 'complete' && page.total !== null, pageSize: page.page_size });

/** A refresh replaces page 1 and keeps the rows loaded after it, minus any id now on page 1. */
export function mergeRefresh(items: WorkListRow[], firstCount: number, page: WorkListRow[]): WorkListRow[] {
  const fresh = new Set(page.map((row) => row.id));
  return [...page, ...items.slice(firstCount).filter((row) => !fresh.has(row.id))];
}

/**
 * The live work list, for any queue (GET /api/v1/work). Rows come back in the server's order, 8 to a page, and are
 * never re-sorted. A page with no rows and a `next_page` is skipped: the list keeps asking (up to MAX_EMPTY_PAGES
 * requests, then "keep-looking") until rows arrive or `next_page` is null. Changing the queue, line, search or
 * project, state or rows per page (`limit`) restarts from page 1 and drops the answers to earlier requests. A screen
 * either calls `setFilters` (Verified, Exceptions) or passes the filters as props from its URL (My work).
 * `refresh()` re-reads page 1 in place and answers whether it could.
 *
 *   const { state, loadMore, retry, refresh, setFilters, filters } = useWorkList({ queue: 'verified' });
 *   state: { status: 'loading' } | { status: 'error', error } | { status: 'ready', items, lines, lineOptions, asOf, coverage, more, total, totalComplete, pageSize }
 */
export function useWorkList({ queue, line, q, project, state: rowState, limit, enabled = true }: WorkListQuery) {
  const [chosen, setChosen] = useState<WorkListFilters | null>(null);
  const given = useMemo<WorkListFilters>(() => ({ line, q, project, state: rowState, limit }), [line, q, project, rowState, limit]);
  const filters = chosen ?? given;
  const setFilters = useCallback((next: SetStateAction<WorkListFilters>) => setChosen((c) => (typeof next === 'function' ? next(c ?? given) : next)), [given]);
  const [state, setState] = useState<WorkListState>({ status: 'loading' });
  // The page to ask for next; null when the list is complete.
  const next = useRef<number | null>(1);
  // Answers to an earlier queue, filter or Try again are dropped.
  const request = useRef(0);
  // The line filter's choices, kept across filter changes within one queue so a narrowed list can be widened again.
  const options = useRef<{ queue: WorkQueue; lines: WorkLine[] } | null>(null);
  // The page the latest answer came from, and how many rows the first page gave (what a refresh replaces).
  const reached = useRef(1);
  const firstCount = useRef(0);
  const inFlight = useRef(0);

  const fetchPage = useCallback(
    async (page: number) => {
      const query: { queue: WorkQueue; page: number; line?: WorkListFilters['line']; q?: string; project?: string; state?: WorkState; limit?: WorkLimit } = { queue, page };
      if (filters.line) query.line = filters.line;
      if (filters.q) query.q = filters.q;
      if (filters.project) query.project = filters.project;
      if (filters.state) query.state = filters.state;
      if (filters.limit) query.limit = filters.limit;
      inFlight.current += 1;
      try {
        return await call(liveApi.GET('/api/v1/work', { params: { query } }));
      } finally {
        inFlight.current -= 1;
      }
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
    if (!enabled) return;
    setState({ status: 'loading' });
    try {
      const body = await collect(1, n);
      if (n !== request.current) return;
      next.current = body.next_page;
      reached.current = body.page;
      firstCount.current = body.items.length;
      if (!filters.line || options.current?.queue !== queue) options.current = { queue, lines: body.lines };
      setState({ status: 'ready', items: body.items, lines: body.lines, lineOptions: options.current.lines, asOf: body.as_of, coverage: coverageOf(body), more: moreOf(body), ...totalsOf(body) });
    } catch (error) {
      if (n === request.current) setState({ status: 'error', error: error instanceof ApiError ? error : networkError() });
    }
  }, [collect, enabled, filters.line, queue]);

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
      reached.current = body.page;
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
          ...totalsOf(body),
        };
      });
    } catch (error) {
      if (n !== request.current) return;
      // A sign-out while paging replaces the list with the signed-out state; anything else keeps the rows shown.
      if (error instanceof ApiError && error.kind === 'unauthenticated') setState({ status: 'error', error });
      else setState((s) => (s.status === 'ready' ? { ...s, more: 'failed' } : s));
    }
  }, [collect]);

  /** Re-reads page 1 in place: rows loaded with Show more stay and nothing else moves. True when it could be read. */
  const refresh = useCallback(async () => {
    if (!enabled || inFlight.current > 0) return true;
    const n = request.current;
    try {
      const body = await fetchPage(1);
      if (n !== request.current) return true;
      // Only a list still on its first page takes the new next page; one that has paged on keeps its own.
      const onFirstPage = reached.current === 1;
      if (onFirstPage) next.current = body.next_page;
      const first = firstCount.current;
      firstCount.current = body.items.length;
      setState((s) =>
        s.status !== 'ready'
          ? s
          : { ...s, items: mergeRefresh(s.items, first, body.items), lines: body.lines, asOf: body.as_of, coverage: coverageOf(body), ...totalsOf(body), more: onFirstPage ? moreOf(body) : s.more },
      );
      return true;
    } catch (error) {
      if (n !== request.current) return true;
      if (error instanceof ApiError && error.kind === 'unauthenticated') setState({ status: 'error', error });
      return false;
    }
  }, [enabled, fetchPage]);

  return { state, loadMore, retry: load, refresh, setFilters, filters: { queue, ...filters } };
}
