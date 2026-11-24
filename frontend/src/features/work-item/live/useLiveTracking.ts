'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

import { call, liveApi } from '@/api/client';
import { ApiError, networkError } from '@/api/errors';
import type { LiveTracking } from '@/api/types';

const ACCESS_LOST = new Set<ApiError['kind']>(['unauthenticated', 'forbidden', 'not_found']);

export type LiveTrackingState = { tracking: LiveTracking | null; error: ApiError | null };

/** GET /work/{id}/tracking, read again on every item read (`readAt` changes with each one, so the item's polling rule is the only one).
 *  Nothing is read when the item has no tracking_url. A failed read keeps the last good tracking; lost access goes to `onAccessLost`. */
export function useLiveTracking(id: number, hasTracking: boolean, readAt: Date | null, onAccessLost: (error: ApiError) => void) {
  const [state, setState] = useState<LiveTrackingState>({ tracking: null, error: null });
  // An answer to an earlier read is dropped.
  const request = useRef(0);

  const load = useCallback(async () => {
    const n = ++request.current;
    try {
      const tracking = await call(liveApi.GET('/api/v1/work/{work_id}/tracking', { params: { path: { work_id: id } } }));
      if (n === request.current) setState({ tracking, error: null });
    } catch (caught) {
      if (n !== request.current) return;
      const error = caught instanceof ApiError ? caught : networkError();
      if (ACCESS_LOST.has(error.kind)) onAccessLost(error);
      else setState((s) => ({ ...s, error }));
    }
  }, [id, onAccessLost]);

  useEffect(() => {
    if (!hasTracking || readAt === null) return;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, [load, hasTracking, readAt]);

  return { ...state, retry: load };
}
