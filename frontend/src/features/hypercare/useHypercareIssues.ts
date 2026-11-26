'use client';

// F-115: the project's open issues for the hypercare page, read from the issues register (GET /projects/{case_id}/issues). A failure here is
// this block's own: it never takes the rest of the page down, and Try again repeats only this read. Reads only; no write.
import { useCallback, useEffect, useState } from 'react';

import { call, liveApi } from '@/api/client';

import { readOpenIssues, type OpenIssues } from './hypercareModel';

export type IssuesState = { status: 'loading' } | { status: 'failed' } | { status: 'ready'; open: OpenIssues };

/** `refresh` changes when the stability read says something new (a new assessment), so the list is read again then and not on every poll. */
export function useHypercareIssues(caseId: string, refresh: unknown): { state: IssuesState; retry: () => void } {
  const [state, setState] = useState<IssuesState>({ status: 'loading' });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let active = true;
    readOpenIssues((before) => call(liveApi.GET('/api/v1/projects/{case_id}/issues', { params: { path: { case_id: caseId }, query: before === null ? {} : { before } } })))
      .then((open) => active && setState({ status: 'ready', open }))
      // keep the last good list on screen when a later read fails
      .catch(() => active && setState((was) => (was.status === 'ready' ? was : { status: 'failed' })));
    return () => {
      active = false;
    };
  }, [caseId, refresh, attempt]);

  const retry = useCallback(() => {
    setState({ status: 'loading' });
    setAttempt((n) => n + 1);
  }, []);
  return { state, retry };
}
