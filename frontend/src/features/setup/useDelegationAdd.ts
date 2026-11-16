'use client';

// One E-DELEGATION at a time, never resent. Every outcome except a 422 and a 401 re-reads the list once and hands it
// to the form. A network or server error is an uncertain effect: the list is read once, and the form compares its
// revision with the one sent to tell "not added" from "the list changed".
import { useCallback, useRef, useState } from 'react';

import { ApiError } from '@/api/errors';

import { addDelegation, type FieldProblem, type UploadError } from './api';
import type { DelegationBody, DelegationResult, DelegationsPage } from './contract-proposal';
import { asApiError } from './useSetupRules';

export type AddOutcome =
  | { kind: 'added'; result: DelegationResult; page: DelegationsPage | ApiError }
  /** 409, 403 or 404: the message, and the list as re-read. */
  | { kind: 'rejected'; error: ApiError; page: DelegationsPage | ApiError }
  | { kind: 'invalid'; message: string; fields: FieldProblem[] }
  | { kind: 'signed_out'; error: ApiError }
  /** Uncertain effect, list re-read. */
  | { kind: 'unconfirmed'; page: DelegationsPage }
  /** Uncertain effect and the re-read failed too. */
  | { kind: 'unchecked' };

export function useDelegationAdd(refresh: () => Promise<DelegationsPage | ApiError>) {
  // Checked synchronously so a double click, or the desktop panel and the phone sheet together, cannot send two.
  const writing = useRef(false);
  const [busy, setBusy] = useState(false);

  const add = useCallback(
    async (body: DelegationBody, onChecking: () => void): Promise<AddOutcome | null> => {
      if (writing.current) return null;
      writing.current = true;
      setBusy(true);
      try {
        const result = await addDelegation(body);
        return { kind: 'added', result, page: await refresh() };
      } catch (error) {
        const apiError = asApiError(error);
        if (apiError.kind === 'unauthenticated') return { kind: 'signed_out', error: apiError };
        if (apiError.kind === 'invalid') return { kind: 'invalid', message: apiError.message, fields: (apiError as UploadError).fields ?? [] };
        if (apiError.kind === 'stale' || apiError.kind === 'forbidden' || apiError.kind === 'not_found') {
          return { kind: 'rejected', error: apiError, page: await refresh() };
        }
        onChecking();
        const page = await refresh();
        return page instanceof ApiError ? { kind: 'unchecked' } : { kind: 'unconfirmed', page };
      } finally {
        writing.current = false;
        setBusy(false);
      }
    },
    [refresh],
  );

  return { busy, add };
}
