'use client';

// E-CONVERSATIONS: the person's own conversations, newest first, a page at a time. `refresh` re-reads the first page
// (after a send, a start, or a working conversation ends). `asOf` is when the list was read, the day the labels use.
import { useCallback, useEffect, useRef, useState } from 'react';

import { ApiError, networkError } from '@/api/errors';

import { fetchConversations } from './api';
import type { ConversationRow } from './types';

export type ListState =
  | { status: 'loading' }
  | { status: 'ready'; items: ConversationRow[]; next?: string; asOf: string; more: 'idle' | 'loading' | 'error' }
  | { status: 'signed_out' }
  | { status: 'error'; error: ApiError };

export function useConversationList() {
  const [state, setState] = useState<ListState>({ status: 'loading' });
  const seq = useRef(0);

  const refresh = useCallback(async () => {
    const mine = ++seq.current;
    try {
      const page = await fetchConversations();
      if (mine === seq.current) setState({ status: 'ready', items: page.items, next: page.next_cursor, asOf: page.as_of, more: 'idle' });
    } catch (thrown) {
      if (mine !== seq.current) return;
      const error = thrown instanceof ApiError ? thrown : networkError();
      // A failed refresh keeps the rows already shown.
      setState((current) => (error.kind === 'unauthenticated' ? { status: 'signed_out' } : current.status === 'ready' ? current : { status: 'error', error }));
    }
  }, []);

  const more = useCallback(async () => {
    const current = state;
    if (current.status !== 'ready' || !current.next) return;
    const mine = ++seq.current;
    setState({ ...current, more: 'loading' });
    try {
      const page = await fetchConversations(current.next);
      if (mine === seq.current) setState({ status: 'ready', items: [...current.items, ...page.items], next: page.next_cursor, asOf: current.asOf, more: 'idle' });
    } catch {
      if (mine === seq.current) setState({ ...current, more: 'error' });
    }
  }, [state]);

  useEffect(() => {
    // One read when the page opens; the effect only starts the request.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void refresh();
  }, [refresh]);

  const retry = useCallback(() => {
    setState({ status: 'loading' });
    void refresh();
  }, [refresh]);

  return { state, refresh, more, retry };
}
