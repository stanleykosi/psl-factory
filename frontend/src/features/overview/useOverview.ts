'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

import { api, call } from '@/api/client';
import { ApiError, networkError } from '@/api/errors';

import type { Overview } from './types';

export const POLL_MS = 15_000;

export type OverviewState =
  | { status: 'loading' }
  | { status: 'ready'; data: Overview }
  | { status: 'signed_out' }
  | { status: 'not_open'; error: ApiError }
  | { status: 'error'; error: ApiError; lastAsOf?: string };

const asApiError = (error: unknown) => (error instanceof ApiError ? error : networkError());

/** E-OVERVIEW as returned, kept current by D-UPDATES r2 polling. 401, 403 and 404 stop the polling. */
export function useOverview() {
  const [state, setState] = useState<OverviewState>({ status: 'loading' });
  const seq = useRef(0);
  const applied = useRef(0);
  const inFlight = useRef(0);
  const lastSuccess = useRef(0);
  const lastAsOf = useRef<string>(undefined);
  const stopped = useRef(false);

  /** One read. A response older than one already shown is dropped. */
  const load = useCallback(async () => {
    const mine = ++seq.current;
    inFlight.current += 1;
    try {
      const data = await call(api.GET('/api/v1/overview'));
      if (mine < applied.current || stopped.current) return;
      applied.current = mine;
      lastSuccess.current = Date.now();
      lastAsOf.current = data.as_of;
      setState({ status: 'ready', data });
    } catch (error) {
      if (mine < applied.current || stopped.current) return;
      applied.current = mine;
      const e = asApiError(error);
      if (e.kind === 'unauthenticated') {
        stopped.current = true;
        setState({ status: 'signed_out' });
      } else if (e.kind === 'forbidden' || e.kind === 'not_found') {
        stopped.current = true;
        setState({ status: 'not_open', error: e });
      } else {
        setState({ status: 'error', error: e, lastAsOf: lastAsOf.current });
      }
    } finally {
      inFlight.current -= 1;
    }
  }, []);

  useEffect(() => {
    // The effect only starts the first request.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, [load]);

  // D-UPDATES: every 15 s while the tab is visible; on return, at once if the figures are older than 15 s.
  useEffect(() => {
    let timer: ReturnType<typeof setInterval> | undefined;
    const tick = () => {
      if (!stopped.current && inFlight.current === 0) void load();
    };
    const start = () => {
      clearInterval(timer);
      timer = setInterval(tick, POLL_MS);
    };
    const onVisibility = () => {
      if (document.visibilityState === 'visible') {
        if (Date.now() - lastSuccess.current > POLL_MS) tick();
        start();
      } else {
        clearInterval(timer);
      }
    };
    if (document.visibilityState === 'visible') start();
    document.addEventListener('visibilitychange', onVisibility);
    return () => {
      clearInterval(timer);
      document.removeEventListener('visibilitychange', onVisibility);
    };
  }, [load]);

  return { state, retry: load };
}
