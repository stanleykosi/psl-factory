'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

import { ApiError, networkError, UNEXPECTED_MESSAGE } from '@/api/errors';

import { fetchClients, type ClientList, type ClientRow } from './api';

export type ClientsState =
  | { status: 'loading' }
  | { status: 'error'; error: ApiError }
  | { status: 'ready'; items: ClientRow[]; nextCursor?: string; asOf: string };

const asApiError = (error: unknown) => (error instanceof ApiError ? error : networkError());

function checked(data: ClientList) {
  if (!Array.isArray(data.items) || typeof data.as_of !== 'string') throw new ApiError(200, 'server', 'unexpected_response', UNEXPECTED_MESSAGE);
  return data;
}

/** E-CLIENTS: page 1 on open, then "Show more" appends the next page by the cursor the backend returned. */
export function useClients() {
  const [state, setState] = useState<ClientsState>({ status: 'loading' });
  const [more, setMore] = useState<'idle' | 'loading' | 'error'>('idle');
  const seq = useRef(0);
  const pressed = useRef(false);

  const load = useCallback(async () => {
    const mine = ++seq.current;
    setState({ status: 'loading' });
    setMore('idle');
    try {
      const data = checked(await fetchClients());
      if (mine !== seq.current) return;
      setState({ status: 'ready', items: data.items, nextCursor: data.next_cursor, asOf: data.as_of });
    } catch (error) {
      if (mine !== seq.current) return;
      setState({ status: 'error', error: asApiError(error) });
    }
  }, []);

  useEffect(() => {
    // The effect only starts the request.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, [load]);

  /** Appends the next page; resolves with the number of rows before it, so the caller can move focus to the first new row. */
  const showMore = async () => {
    if (state.status !== 'ready' || !state.nextCursor || pressed.current) return undefined;
    pressed.current = true;
    const mine = seq.current;
    const before = state.items.length;
    setMore('loading');
    try {
      const data = checked(await fetchClients(state.nextCursor));
      if (mine !== seq.current) return undefined;
      setState((prev) => (prev.status !== 'ready' ? prev : { ...prev, items: [...prev.items, ...data.items], nextCursor: data.next_cursor, asOf: data.as_of }));
      setMore('idle');
      return before;
    } catch (error) {
      if (mine !== seq.current) return undefined;
      const e = asApiError(error);
      if (e.kind === 'unauthenticated') setState({ status: 'error', error: e });
      else setMore('error');
      return undefined;
    } finally {
      pressed.current = false;
    }
  };

  return { state, more, retry: load, showMore };
}
