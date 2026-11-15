'use client';

// E-TEMPLATES: the first page, then "Show more" pages appended in order. A refresh (after an upload) always re-reads
// the first page and drops the later ones.
import { useCallback, useEffect, useState } from 'react';

import type { ApiError } from '@/api/errors';

import { readTemplates, type TemplateRow, type TemplatesPage } from './api';
import { asApiError } from './useSetupRules';

export type TemplatesState =
  | { status: 'loading' }
  | { status: 'error'; error: ApiError }
  | { status: 'ready'; items: TemplateRow[]; nextCursor?: string; asOf: string; more: 'idle' | 'loading' | 'failed' };

const ACCESS_LOST = new Set<ApiError['kind']>(['unauthenticated', 'forbidden', 'not_found']);
const ready = (page: TemplatesPage): TemplatesState => ({ status: 'ready', items: page.items, nextCursor: page.next_cursor, asOf: page.as_of, more: 'idle' });

export function useTemplates() {
  const [state, setState] = useState<TemplatesState>({ status: 'loading' });

  const load = useCallback(async () => {
    setState({ status: 'loading' });
    try {
      setState(ready(await readTemplates()));
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
  const refresh = useCallback(async (): Promise<TemplatesPage | ApiError> => {
    try {
      const page = await readTemplates();
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
      const next = await readTemplates(cursor);
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
