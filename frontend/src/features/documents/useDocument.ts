'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

import { api, call } from '@/api/client';
import { ApiError, networkError, UNEXPECTED_MESSAGE } from '@/api/errors';

import { isDocument, type DocumentView } from './documentModel';

export type DocumentState =
  | { status: 'loading' }
  | { status: 'error'; error: ApiError }
  /** `refreshFailed`: the last re-read failed, so what is shown may be older than the record. */
  | { status: 'ready'; doc: DocumentView; refreshFailed: boolean };

const asApiError = (error: unknown) => (error instanceof ApiError ? error : networkError());

/**
 * One E-DOCUMENT read per opened document version; a late answer for an earlier one is ignored. `refresh` re-reads
 * without clearing the page (after a decision) and never sends anything. No polling, no automatic retry.
 */
export function useDocument(documentId: string, version: string) {
  const [state, setState] = useState<DocumentState>({ status: 'loading' });
  const seq = useRef(0);

  const read = useCallback(async () => {
    const data = await call(api.GET('/api/v1/documents/{document_id}/versions/{version}', { params: { path: { document_id: documentId, version } } }));
    if (!isDocument(data)) throw new ApiError(200, 'server', 'unexpected_response', UNEXPECTED_MESSAGE);
    return data;
  }, [documentId, version]);

  const load = useCallback(async () => {
    const mine = ++seq.current;
    setState({ status: 'loading' });
    try {
      const doc = await read();
      if (mine === seq.current) setState({ status: 'ready', doc, refreshFailed: false });
    } catch (error) {
      if (mine === seq.current) setState({ status: 'error', error: asApiError(error) });
    }
  }, [read]);

  const refresh = useCallback(async () => {
    const mine = ++seq.current;
    try {
      const doc = await read();
      if (mine === seq.current) setState({ status: 'ready', doc, refreshFailed: false });
    } catch (error) {
      if (mine !== seq.current) return;
      const e = asApiError(error);
      // Access lost since the page opened: nothing of the document stays on screen.
      if (e.kind === 'unauthenticated' || e.kind === 'forbidden' || e.kind === 'not_found') setState({ status: 'error', error: e });
      else setState((s) => (s.status === 'ready' ? { ...s, refreshFailed: true } : s));
    }
  }, [read]);

  useEffect(() => {
    // The effect only starts the request.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, [load]);

  return { state, retry: load, refresh };
}
