'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

import { call, liveApi } from '@/api/client';
import { ApiError, networkError, UNEXPECTED_MESSAGE } from '@/api/errors';

import { isDocument, publicationOf, type LiveDocument, type Publication } from './documentModel';

export type DocumentState =
  | { status: 'loading' }
  | { status: 'error'; error: ApiError }
  /** `publication` is null when its read failed; `refreshFailed`: the last re-read failed, so what is shown may be older than the record. */
  | { status: 'ready'; doc: LiveDocument; publication: Publication | null; refreshFailed: boolean };

const asApiError = (error: unknown) => (error instanceof ApiError ? error : networkError());
// The live path takes a 64-bit id; a string is passed through so no digit is lost to a JS number.
const asId = (versionId: string) => versionId as unknown as number;

/**
 * One document-review read pair per opened version: the preview (required) and the publication read (status word and
 * findings; its failure is not fatal). A late answer for an earlier one is ignored. `refresh` re-reads without
 * clearing the page and never sends anything; it says whether the re-read worked. No polling, no automatic retry.
 */
export function useDocument(caseId: string, versionId: string) {
  const [state, setState] = useState<DocumentState>({ status: 'loading' });
  const seq = useRef(0);

  const read = useCallback(async () => {
    const path = { case_id: caseId, version_id: asId(versionId) };
    const [doc, publication] = await Promise.all([
      call(liveApi.GET('/api/v1/projects/{case_id}/document-reviews/{version_id}', { params: { path } })),
      call(liveApi.GET('/api/v1/projects/{case_id}/document-reviews/{version_id}/publication', { params: { path } })).then(publicationOf, () => null),
    ]);
    if (!isDocument(doc)) throw new ApiError(200, 'server', 'unexpected_response', UNEXPECTED_MESSAGE);
    return { doc, publication };
  }, [caseId, versionId]);

  const load = useCallback(async () => {
    const mine = ++seq.current;
    setState({ status: 'loading' });
    try {
      const result = await read();
      if (mine === seq.current) setState({ status: 'ready', ...result, refreshFailed: false });
    } catch (error) {
      if (mine === seq.current) setState({ status: 'error', error: asApiError(error) });
    }
  }, [read]);

  const refresh = useCallback(async (): Promise<boolean> => {
    const mine = ++seq.current;
    try {
      const result = await read();
      if (mine === seq.current) setState({ status: 'ready', ...result, refreshFailed: false });
      return true;
    } catch (error) {
      const e = asApiError(error);
      if (mine !== seq.current) return false;
      // Access lost since the page opened: nothing of the document stays on screen.
      if (e.kind === 'unauthenticated' || e.kind === 'forbidden' || e.kind === 'not_found') setState({ status: 'error', error: e });
      else setState((s) => (s.status === 'ready' ? { ...s, refreshFailed: true } : s));
      return false;
    }
  }, [read]);

  useEffect(() => {
    // The effect only starts the request.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, [load]);

  return { state, retry: load, refresh };
}
