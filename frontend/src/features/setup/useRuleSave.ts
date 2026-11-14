'use client';

// One E-SETUP-RULE-SAVE at a time. Nothing resends: every outcome re-reads the list (or not) and hands the result to
// the panel, which decides what the person sees. A network or server error is an uncertain effect: the list is read
// once to see whether the save went through.
import { useCallback, useRef, useState } from 'react';

import { ApiError } from '@/api/errors';

import { saveRule } from './api';
import type { RulesPage, SaveBody } from './contract-proposal';
import { asApiError } from './useSetupRules';

export type SaveOutcome =
  | { kind: 'saved'; revision: number; page: RulesPage | ApiError }
  /** 409, 403 or 404: the message, and the list as re-read. */
  | { kind: 'rejected'; error: ApiError; page: RulesPage | ApiError }
  | { kind: 'invalid'; message: string }
  | { kind: 'signed_out'; error: ApiError }
  /** Uncertain effect, list re-read. */
  | { kind: 'unconfirmed'; page: RulesPage }
  /** Uncertain effect and the re-read failed too. */
  | { kind: 'unchecked' };

export function useRuleSave(refresh: () => Promise<RulesPage | ApiError>) {
  // Checked synchronously so a double click cannot send two saves.
  const writing = useRef(false);
  const [busy, setBusy] = useState(false);

  const save = useCallback(
    async (component: string, body: SaveBody): Promise<SaveOutcome | null> => {
      if (writing.current) return null;
      writing.current = true;
      setBusy(true);
      try {
        const result = await saveRule(component, body);
        return { kind: 'saved', revision: result.revision, page: await refresh() };
      } catch (error) {
        const apiError = asApiError(error);
        if (apiError.kind === 'unauthenticated') return { kind: 'signed_out', error: apiError };
        if (apiError.kind === 'invalid') return { kind: 'invalid', message: apiError.message };
        if (apiError.kind === 'stale' || apiError.kind === 'forbidden' || apiError.kind === 'not_found') {
          return { kind: 'rejected', error: apiError, page: await refresh() };
        }
        const page = await refresh();
        return page instanceof ApiError ? { kind: 'unchecked' } : { kind: 'unconfirmed', page };
      } finally {
        writing.current = false;
        setBusy(false);
      }
    },
    [refresh],
  );

  return { busy, save };
}
