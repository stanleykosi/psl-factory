'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

import { ApiError, networkError, UNEXPECTED_MESSAGE } from '@/api/errors';

import { fetchGroup, fetchHistory, fetchWorkspace, type Contact, type Group, type Workspace } from './api';

const asApiError = (error: unknown) => (error instanceof ApiError ? error : networkError());
const unexpected = () => new ApiError(200, 'server', 'unexpected_response', UNEXPECTED_MESSAGE);

export type GroupState = { status: 'loading' } | { status: 'error'; error: ApiError } | { status: 'ready'; group: Group };
export type WorkspaceState = { status: 'loading' } | { status: 'error'; error: ApiError } | { status: 'ready'; workspace: Workspace };

/** clients_group: page 1 on open; "Show more" appends the next page of projects (a project already shown is not added twice). */
export function useGroup(key: string) {
  const [state, setState] = useState<GroupState>({ status: 'loading' });
  const [more, setMore] = useState<'idle' | 'loading' | 'error'>('idle');
  const seq = useRef(0);
  const pressed = useRef(false);

  const load = useCallback(async () => {
    const mine = ++seq.current;
    setState({ status: 'loading' });
    setMore('idle');
    try {
      const group = await fetchGroup(key);
      if (!Array.isArray(group.projects) || group.debt === undefined) throw unexpected();
      if (mine === seq.current) setState({ status: 'ready', group });
    } catch (error) {
      if (mine === seq.current) setState({ status: 'error', error: asApiError(error) });
    }
  }, [key]);

  useEffect(() => {
    // The effect only starts the request.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, [load]);

  const showMore = async () => {
    if (state.status !== 'ready' || state.group.next_page === null || pressed.current) return;
    pressed.current = true;
    const mine = seq.current;
    setMore('loading');
    try {
      const next = await fetchGroup(key, state.group.next_page);
      if (!Array.isArray(next.projects)) throw unexpected();
      if (mine !== seq.current) return;
      setState((prev) => {
        if (prev.status !== 'ready') return prev;
        const seen = new Set(prev.group.projects.map((p) => p.case_id));
        return { status: 'ready', group: { ...prev.group, projects: [...prev.group.projects, ...next.projects.filter((p) => !seen.has(p.case_id))], next_page: next.next_page } };
      });
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

/** workspaces_client: one read per opened project's contacts. */
export function useWorkspace(caseId: string) {
  const [state, setState] = useState<WorkspaceState>({ status: 'loading' });
  const seq = useRef(0);

  const load = useCallback(async () => {
    const mine = ++seq.current;
    setState({ status: 'loading' });
    try {
      const workspace = await fetchWorkspace(caseId);
      if (typeof workspace.case_id !== 'string' || typeof workspace.title !== 'string' || !Array.isArray(workspace.contacts)) throw unexpected();
      if (mine === seq.current) setState({ status: 'ready', workspace });
    } catch (error) {
      if (mine === seq.current) setState({ status: 'error', error: asApiError(error) });
    }
  }, [caseId]);

  useEffect(() => {
    // The effect only starts the request.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, [load]);

  return { state, retry: load };
}

export type HistoryState = { status: 'closed' } | { status: 'loading' } | { status: 'error' } | { status: 'ready'; items: Contact[]; next: number | null; more: 'idle' | 'loading' | 'error' };

/** clients_contact_history (billing): opened on demand, newest first; a failure is inline and leaves the page alone. */
export function useHistory(caseId: string, customer?: string) {
  const [state, setState] = useState<HistoryState>({ status: 'closed' });
  const pressed = useRef(false);

  const open = useCallback(async () => {
    setState({ status: 'loading' });
    try {
      const data = await fetchHistory(caseId, customer);
      if (!Array.isArray(data.items)) throw unexpected();
      setState({ status: 'ready', items: data.items, next: data.next_page, more: 'idle' });
    } catch {
      setState({ status: 'error' });
    }
  }, [caseId, customer]);

  const showMore = async () => {
    if (state.status !== 'ready' || state.next === null || pressed.current) return;
    pressed.current = true;
    const { next } = state;
    setState({ ...state, more: 'loading' });
    try {
      const data = await fetchHistory(caseId, customer, next);
      if (!Array.isArray(data.items)) throw unexpected();
      setState((prev) => (prev.status !== 'ready' ? prev : { status: 'ready', items: [...prev.items, ...data.items], next: data.next_page, more: 'idle' }));
    } catch {
      setState((prev) => (prev.status !== 'ready' ? prev : { ...prev, more: 'error' }));
    } finally {
      pressed.current = false;
    }
  };

  return { state, open, showMore };
}
