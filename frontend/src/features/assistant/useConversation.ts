'use client';

// E-CONVERSATION for one conversation, read again every 5 s while status = working (D-UPDATES). The timer waits while
// the tab is hidden and a read follows when it is visible again; it stops on any other status. A failed poll keeps the
// last good data. Opening or reloading only reads: nothing here writes.
import { useCallback, useEffect, useRef, useState } from 'react';

import { ApiError, networkError } from '@/api/errors';

import { fetchConversation } from './api';
import type { Conversation } from './types';

export const POLL_MS = 5000;

export type ConversationState =
  | { status: 'loading' }
  | { status: 'ready'; data: Conversation; refreshFailed: boolean }
  | { status: 'missing' }
  | { status: 'signed_out' }
  | { status: 'error'; error: ApiError };

export function useConversation(id: string, onSettled?: () => void) {
  const [state, setState] = useState<ConversationState>({ status: 'loading' });
  const data = useRef<Conversation | null>(null);
  const reading = useRef(false);
  const settled = useRef(onSettled);
  useEffect(() => {
    settled.current = onSettled;
  });

  /** Reads once; answers the conversation read, or nothing when a read is already running or this one failed. */
  const read = useCallback(async (): Promise<Conversation | undefined> => {
    if (reading.current) return undefined;
    reading.current = true;
    try {
      const next = await fetchConversation(id);
      const was = data.current?.status;
      data.current = next;
      setState({ status: 'ready', data: next, refreshFailed: false });
      if (was === 'working' && next.status !== 'working') settled.current?.();
      return next;
    } catch (thrown) {
      const error = thrown instanceof ApiError ? thrown : networkError();
      if (error.kind === 'unauthenticated') setState({ status: 'signed_out' });
      else if (error.kind === 'not_found' || error.kind === 'forbidden') setState({ status: 'missing' });
      else if (data.current) setState({ status: 'ready', data: data.current, refreshFailed: true });
      else setState({ status: 'error', error });
      return undefined;
    } finally {
      reading.current = false;
    }
  }, [id]);

  useEffect(() => {
    // One read per opening; the effect only starts the request.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void read();
  }, [read]);

  const working = state.status === 'ready' && state.data.status === 'working';
  useEffect(() => {
    if (!working) return undefined;
    const timer = setInterval(() => {
      if (document.visibilityState !== 'hidden') void read();
    }, POLL_MS);
    const onVisible = () => {
      if (document.visibilityState === 'visible') void read();
    };
    document.addEventListener('visibilitychange', onVisible);
    return () => {
      clearInterval(timer);
      document.removeEventListener('visibilitychange', onVisible);
    };
  }, [working, read]);

  const retry = useCallback(() => {
    setState({ status: 'loading' });
    void read();
  }, [read]);

  return { state, reload: read, retry };
}
