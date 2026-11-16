'use client';

// E-DELEGATIONS: the first page, then "Show more" pages appended in order. The options, can_add and the revision a
// write is sent against come from the latest first-page read only. A refresh (after a write) re-reads the first page
// and drops the later ones.
import { useCallback, useEffect, useState } from 'react';

import type { ApiError } from '@/api/errors';

import { readDelegations } from './api';
import type { DelegationRow, DelegationsPage } from './contract-proposal';
import { asApiError } from './useSetupRules';

export type DelegationsState =
  | { status: 'loading' }
  | { status: 'error'; error: ApiError }
  | { status: 'ready'; page: DelegationsPage; items: DelegationRow[]; nextCursor?: string; more: 'idle' | 'loading' | 'failed' };

const ACCESS_LOST = new Set<ApiError['kind']>(['unauthenticated', 'forbidden', 'not_found']);
const ready = (page: DelegationsPage): DelegationsState => ({ status: 'ready', page, items: page.items, nextCursor: page.next_cursor, more: 'idle' });

export function useDelegations() {
  const [state, setState] = useState<DelegationsState>({ status: 'loading' });

  const load = useCallback(async () => {
    setState({ status: 'loading' });
    try {
      setState(ready(await readDelegations()));
    } catch (error) {
      setState({ status: 'error', error: asApiError(error) });
    }
  }, []);

  useEffect(() => {
    // One read per opened view; the effect only starts the request.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, [load]);

  /** Re-reads the first page. A failed read keeps the rows on screen unless access was lost. */
  const refresh = useCallback(async (): Promise<DelegationsPage | ApiError> => {
    try {
      const page = await readDelegations();
      setState(ready(page));
      return page;
    } catch (error) {
      const apiError = asApiError(error);
      if (ACCESS_LOST.has(apiError.kind)) setState({ status: 'error', error: apiError });
      return apiError;
    }
  }, []);

  const cursor = state.status === 'ready' && state.more !== 'loading' ? state.nextCursor : undefined;
  const loadMore = useCallback(async () => {
    if (!cursor) return;
    setState((s) => (s.status === 'ready' ? { ...s, more: 'loading' } : s));
    try {
      const next = await readDelegations(cursor);
      setState((s) => (s.status === 'ready' ? { ...s, items: [...s.items, ...next.items], nextCursor: next.next_cursor, more: 'idle' } : s));
    } catch (error) {
      const apiError = asApiError(error);
      if (apiError.kind === 'unauthenticated') setState({ status: 'error', error: apiError });
      else setState((s) => (s.status === 'ready' ? { ...s, more: 'failed' } : s));
    }
  }, [cursor]);

  /** A write found the person signed out: the page becomes the signed-out state. */
  const signOut = useCallback((error: ApiError) => setState({ status: 'error', error }), []);

  return { state, retry: load, refresh, loadMore, signOut };
}
