'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

import { api, call } from '@/api/client';
import { ApiError, networkError } from '@/api/errors';

import type { MonthEnd } from './proposal';

export type MonthEndState = { status: 'loading' } | { status: 'error'; error: ApiError } | { status: 'ready'; body: MonthEnd };

/** One read of E-MONTH-END per page open (no polling); Try again re-reads. */
export function useMonthEnd(period: string) {
  const [state, setState] = useState<MonthEndState>({ status: 'loading' });
  // Answers to a superseded period or an earlier try are dropped.
  const request = useRef(0);

  const load = useCallback(async () => {
    const n = ++request.current;
    setState({ status: 'loading' });
    try {
      const body = (await call(api.GET('/api/v1/finance/month-end', { params: { query: { period } } }))) as MonthEnd;
      if (n === request.current) setState({ status: 'ready', body });
    } catch (error) {
      if (n === request.current) setState({ status: 'error', error: error instanceof ApiError ? error : networkError() });
    }
  }, [period]);

  useEffect(() => {
    // The effect only starts the request.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, [load]);

  return { state, retry: load };
}
