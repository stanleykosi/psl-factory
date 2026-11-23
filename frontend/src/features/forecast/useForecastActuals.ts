'use client';

// F-103: GET /work/{id}/forecast/actuals/{month}, read once per selected month. Reads only; no paging parameter exists.
import { useEffect, useState } from 'react';

import { call, liveApi } from '@/api/client';
import { ApiError } from '@/api/errors';
import type { LiveForecastMonth } from '@/api/types';

export type ActualsState = { status: 'idle' } | { status: 'loading' } | { status: 'ready'; month: LiveForecastMonth } | { status: 'error'; error: ApiError };

export function useForecastActuals(workId: number, month: string | null): ActualsState {
  const [state, setState] = useState<{ key: string | null; value: ActualsState }>({ key: null, value: { status: 'idle' } });
  const key = month === null ? null : `${workId}:${month}`;

  useEffect(() => {
    if (month === null) return;
    let active = true;
    call(liveApi.GET('/api/v1/work/{work_id}/forecast/actuals/{month}', { params: { path: { work_id: workId, month } } }))
      .then((data) => active && setState({ key, value: { status: 'ready', month: data } }))
      .catch((e: unknown) => active && setState({ key, value: { status: 'error', error: e instanceof ApiError ? e : new ApiError(0, 'server', 'unexpected', 'Something went wrong.') } }));
    return () => {
      active = false;
    };
  }, [workId, month, key]);

  if (key === null) return { status: 'idle' };
  return state.key === key ? state.value : { status: 'loading' };
}
