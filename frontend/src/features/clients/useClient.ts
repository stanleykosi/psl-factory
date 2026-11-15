'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

import { ApiError, networkError, UNEXPECTED_MESSAGE } from '@/api/errors';

import { fetchClient, type ClientDetail } from './api';

export type ClientState = { status: 'loading' } | { status: 'error'; error: ApiError } | { status: 'ready'; client: ClientDetail };
export type RefreshResult = { client: ClientDetail; error?: never } | { client?: never; error: ApiError };

const asApiError = (error: unknown) => (error instanceof ApiError ? error : networkError());

async function read(clientId: string) {
  const data = await fetchClient(clientId);
  if (typeof data.client_id !== 'string' || typeof data.revision !== 'number' || !Array.isArray(data.projects)) {
    throw new ApiError(200, 'server', 'unexpected_response', UNEXPECTED_MESSAGE);
  }
  return data;
}

/** E-CLIENT: one read per opened client. `refresh` reads again without clearing the screen (after a save or a conflict). */
export function useClient(clientId: string) {
  const [state, setState] = useState<ClientState>({ status: 'loading' });
  const seq = useRef(0);

  const load = useCallback(async () => {
    const mine = ++seq.current;
    setState({ status: 'loading' });
    try {
      const client = await read(clientId);
      if (mine === seq.current) setState({ status: 'ready', client });
    } catch (error) {
      if (mine === seq.current) setState({ status: 'error', error: asApiError(error) });
    }
  }, [clientId]);

  useEffect(() => {
    // The effect only starts the request.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, [load]);

  const refresh = useCallback(async (): Promise<RefreshResult> => {
    const mine = ++seq.current;
    try {
      const client = await read(clientId);
      if (mine === seq.current) setState({ status: 'ready', client });
      return { client };
    } catch (error) {
      return { error: asApiError(error) };
    }
  }, [clientId]);

  return { state, retry: load, refresh };
}
