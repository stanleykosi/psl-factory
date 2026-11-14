'use client';

// E-SETUP-RULES for one view: the first page with its counts, then "Show more" pages appended in order.
// Counts always come from the first page's count fields; rows never change them.
import { useCallback, useEffect, useState } from 'react';

import { ApiError, networkError } from '@/api/errors';

import { readRules, type RulesArea } from './api';
import type { RulesPage, RuleRow } from './contract-proposal';

export type RulesState =
  | { status: 'loading' }
  | { status: 'error'; error: ApiError }
  | { status: 'ready'; page: RulesPage; items: RuleRow[]; nextCursor?: string; more: 'idle' | 'loading' | 'failed' };

export const asApiError = (error: unknown) => (error instanceof ApiError ? error : networkError());
const ACCESS_LOST = new Set<ApiError['kind']>(['unauthenticated', 'forbidden', 'not_found']);
const ready = (page: RulesPage): RulesState => ({ status: 'ready', page, items: page.items, nextCursor: page.next_cursor, more: 'idle' });

export function useSetupRules(area?: RulesArea) {
  const [state, setState] = useState<RulesState>({ status: 'loading' });

  const load = useCallback(async () => {
    setState({ status: 'loading' });
    try {
      setState(ready(await readRules(area)));
    } catch (error) {
      setState({ status: 'error', error: asApiError(error) });
    }
  }, [area]);

  useEffect(() => {
    // One read per opened view; the effect only starts the request.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, [load]);

  /** Re-reads the first page after a write. A failed read keeps the rows on screen unless access was lost. */
  const refresh = useCallback(async (): Promise<RulesPage | ApiError> => {
    try {
      const page = await readRules(area);
      setState(ready(page));
      return page;
    } catch (error) {
      const apiError = asApiError(error);
      if (ACCESS_LOST.has(apiError.kind)) setState({ status: 'error', error: apiError });
      return apiError;
    }
  }, [area]);

  const cursor = state.status === 'ready' && state.more !== 'loading' ? state.nextCursor : undefined;
  const loadMore = useCallback(async () => {
    if (!cursor) return;
    setState((s) => (s.status === 'ready' ? { ...s, more: 'loading' } : s));
    try {
      const next = await readRules(area, cursor);
      setState((s) => (s.status === 'ready' ? { ...s, items: [...s.items, ...next.items], nextCursor: next.next_cursor, more: 'idle' } : s));
    } catch (error) {
      const apiError = asApiError(error);
      if (apiError.kind === 'unauthenticated') setState({ status: 'error', error: apiError });
      else setState((s) => (s.status === 'ready' ? { ...s, more: 'failed' } : s));
    }
  }, [area, cursor]);

  /** A write found the person signed out: the page becomes the signed-out state. */
  const signOut = useCallback((error: ApiError) => setState({ status: 'error', error }), []);

  return { state, retry: load, refresh, loadMore, signOut };
}
