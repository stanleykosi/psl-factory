'use client';

// E-CONVERSATIONS: the person's own conversations, newest first, a page at a time. `refresh` re-reads the first page
// (after a send, a start, or a working conversation ends). `asOf` is when the list was read, the day the labels use.
import { useCallback, useEffect, useRef, useState } from 'react';

import { ApiError, networkError } from '@/api/errors';
import { DEFAULT_PAGE_SIZE, type PageSize } from '@/components';

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
  // How many pages the list holds: a re-read of page 1 keeps the later pages (and their cursor) once there are any.
  const pages = useRef(1);

  const refresh = useCallback(async () => {
    const mine = ++seq.current;
    try {
      const page = await fetchConversations(DEFAULT_PAGE_SIZE);
      if (mine !== seq.current) return;
      setState((current) => {
        if (current.status !== 'ready' || pages.current === 1) {
          pages.current = 1;
          return { status: 'ready', items: page.items, next: page.next_cursor, asOf: page.as_of, more: 'idle' };
        }
        // Page 1 goes to the top; the conversations already loaded after it stay where they are, and so does the cursor.
        const fresh = new Set(page.items.map((row) => row.conversation_id));
        const items = [...page.items, ...current.items.filter((row) => !fresh.has(row.conversation_id))];
        return { status: 'ready', items, next: current.next, asOf: page.as_of, more: current.more === 'loading' ? 'idle' : current.more };
      });
    } catch (thrown) {
      if (mine !== seq.current) return;
      const error = thrown instanceof ApiError ? thrown : networkError();
      // A failed refresh keeps the rows already shown.
      setState((current) => (error.kind === 'unauthenticated' ? { status: 'signed_out' } : current.status === 'ready' ? current : { status: 'error', error }));
    }
  }, []);

  const more = useCallback(async (limit: PageSize) => {
    const current = state;
    if (current.status !== 'ready' || !current.next) return;
    const mine = ++seq.current;
    setState({ ...current, more: 'loading' });
    try {
      const page = await fetchConversations(limit, current.next);
      if (mine === seq.current) pages.current += 1;
      if (mine === seq.current) setState({ status: 'ready', items: [...current.items, ...page.items], next: page.next_cursor, asOf: current.asOf, more: 'idle' });
    } catch {
      if (mine === seq.current) setState({ ...current, more: 'error' });
    }
  }, [state]);

  useEffect(() => {
    // One read when the page opens; the effect only starts the request.
    void refresh();
  }, [refresh]);

  const retry = useCallback(() => {
    setState({ status: 'loading' });
    void refresh();
  }, [refresh]);

  return { state, refresh, more, retry };
}
