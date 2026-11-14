'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

import { api, call } from '@/api/client';
import { ApiError, networkError, UNEXPECTED_MESSAGE } from '@/api/errors';

import { isJourney, type Journey } from './model';

export type JourneyState = { status: 'loading' } | { status: 'error'; error: ApiError } | { status: 'ready'; journey: Journey };

/** One E-PROJECT read per opened project; a late response for an earlier project is ignored. No polling. */
export function useProject(caseId: string) {
  const [state, setState] = useState<JourneyState>({ status: 'loading' });
  const seq = useRef(0);

  const load = useCallback(async () => {
    const mine = ++seq.current;
    setState({ status: 'loading' });
    try {
      const data = await call(api.GET('/api/v1/projects/{case_id}', { params: { path: { case_id: caseId } } }));
      if (mine !== seq.current) return;
      if (!isJourney(data)) throw new ApiError(200, 'server', 'unexpected_response', UNEXPECTED_MESSAGE);
      setState({ status: 'ready', journey: data });
    } catch (error) {
      if (mine !== seq.current) return;
      setState({ status: 'error', error: error instanceof ApiError ? error : networkError() });
    }
  }, [caseId]);

  useEffect(() => {
    // The effect only starts the request.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, [load]);

  return { state, retry: load };
}
