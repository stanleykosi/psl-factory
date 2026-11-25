'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

import { ApiError, networkError, UNEXPECTED_MESSAGE } from '@/api/errors';

import { fetchDirectory, type Directory, type DirectoryQuery, type GroupRow, type ProjectRow } from './api';

export type ClientsState =
  | { status: 'loading' }
  | { status: 'error'; error: ApiError }
  | { status: 'ready'; groups: GroupRow[]; projects: ProjectRow[]; groupNext: number | null; projectNext: number | null; readAt: string };

const asApiError = (error: unknown) => (error instanceof ApiError ? error : networkError());

function checked(data: Directory) {
  if (!Array.isArray(data.groups) || !Array.isArray(data.projects)) throw new ApiError(200, 'server', 'unexpected_response', UNEXPECTED_MESSAGE);
  return data;
}

/** Rows already shown stay; a row the server sends again (both lists come back on every call) is not added twice. */
const added = <T>(have: T[], more: T[], keyOf: (row: T) => string) => {
  const seen = new Set(have.map(keyOf));
  return [...have, ...more.filter((row) => !seen.has(keyOf(row)))];
};

/** clients_directory: page 1 on open, then "Show more" asks for the next group page, and when none is left the next project page. */
export function useClients(query: DirectoryQuery) {
  const { q, billing } = query;
  const [state, setState] = useState<ClientsState>({ status: 'loading' });
  const [more, setMore] = useState<'idle' | 'loading' | 'error'>('idle');
  const seq = useRef(0);
  const pressed = useRef(false);

  const load = useCallback(async () => {
    const mine = ++seq.current;
    setState({ status: 'loading' });
    setMore('idle');
    try {
      const data = checked(await fetchDirectory({ q, billing }));
      if (mine !== seq.current) return;
      setState({ status: 'ready', groups: data.groups, projects: data.projects, groupNext: data.next_group_page, projectNext: data.next_page, readAt: new Date().toISOString() });
    } catch (error) {
      if (mine !== seq.current) return;
      setState({ status: 'error', error: asApiError(error) });
    }
  }, [q, billing]);

  useEffect(() => {
    // The effect only starts the request.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, [load]);

  const showMore = async () => {
    if (state.status !== 'ready' || pressed.current) return;
    const { groupNext, projectNext } = state;
    if (groupNext === null && projectNext === null) return;
    pressed.current = true;
    const mine = seq.current;
    setMore('loading');
    try {
      const data = checked(await fetchDirectory(groupNext !== null ? { q, billing, clients_page: groupNext } : { q, billing, page: projectNext ?? undefined }));
      if (mine !== seq.current) return;
      setState((prev) =>
        prev.status !== 'ready'
          ? prev
          : groupNext !== null
            ? { ...prev, groups: added(prev.groups, data.groups, (g) => g.key), groupNext: data.next_group_page, readAt: new Date().toISOString() }
            : { ...prev, projects: added(prev.projects, data.projects, (p) => p.case_id), projectNext: data.next_page, readAt: new Date().toISOString() },
      );
      setMore('idle');
    } catch (error) {
      if (mine !== seq.current) return;
      const e = asApiError(error);
      if (e.kind === 'unauthenticated') setState({ status: 'error', error: e });
      else setMore('error');
    } finally {
      pressed.current = false;
    }
  };

  return { state, more, retry: load, showMore };
}
