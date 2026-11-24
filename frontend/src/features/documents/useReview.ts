'use client';

import { useCallback, useRef, useState } from 'react';

import { call, csrfHeader, liveApi } from '@/api/client';
import { ApiError, networkError } from '@/api/errors';

import type { Verdict } from './documentModel';

export type Submit =
  | { status: 'idle' }
  | { status: 'busy'; verdict: Verdict }
  /** The server refused the note (422 on the field); the note stays. */
  | { status: 'note'; message: string }
  /** Nothing was recorded: the callout says why. */
  | { status: 'refused'; message: string }
  /** Recorded, but the re-read that confirms it failed. */
  | { status: 'unconfirmed'; checking: boolean }
  /** A network failure or 5xx: the decision may or may not be recorded; the buttons stay off until a re-read answers. */
  | { status: 'uncertain'; checking: boolean }
  | { status: 'signed_out' };

const asApiError = (error: unknown) => (error instanceof ApiError ? error : networkError());

/**
 * The one decision write: POST .../document-reviews/{version_id}. `refresh` re-reads the document and says whether it
 * worked; the result is shown from that re-read, never from the 200. One write at a time; nothing is sent twice.
 * `delegated` is always false: an ordinary reviewer (B-11, best reading).
 */
export function useReview({ caseId, versionId, revision, refresh, onRecorded }: {
  caseId: string;
  versionId: string;
  revision: number;
  refresh: () => Promise<boolean>;
  onRecorded: (verdict: Verdict) => void;
}) {
  const [submit, setSubmit] = useState<Submit>({ status: 'idle' });
  const inFlight = useRef(false);
  const recorded = useRef<Verdict | null>(null);

  const decide = useCallback(
    async (verdict: Verdict, note: string) => {
      if (inFlight.current) return;
      inFlight.current = true;
      setSubmit({ status: 'busy', verdict });
      try {
        await call(
          liveApi.POST('/api/v1/projects/{case_id}/document-reviews/{version_id}', {
            params: { path: { case_id: caseId, version_id: versionId as unknown as number }, ...csrfHeader },
            body: { expected_revision: revision, verdict, delegated: false, note },
          }),
        );
      } catch (error) {
        const e = asApiError(error);
        if (e.kind === 'unauthenticated') setSubmit({ status: 'signed_out' });
        else if (e.kind === 'stale') {
          setSubmit({ status: 'refused', message: 'This document changed while you were reading it, so nothing was recorded. We’ve loaded the latest; check it and press again.' });
          void refresh();
        } else if (e.kind === 'invalid') {
          const field = e.fields.find((f) => f.name === 'note');
          if (field) setSubmit({ status: 'note', message: field.message });
          else {
            setSubmit({ status: 'refused', message: e.message });
            if (e.code === 'action_unavailable') void refresh();
          }
        } else if (e.kind === 'forbidden') {
          setSubmit({ status: 'refused', message: 'You can’t record a decision on this document.' });
          void refresh();
        } else if (e.kind === 'csrf' || e.kind === 'rate_limited' || e.kind === 'bad_request' || e.kind === 'too_large' || e.kind === 'unsupported') {
          setSubmit({ status: 'refused', message: e.message });
        } else {
          setSubmit({ status: 'uncertain', checking: false });
        }
        inFlight.current = false;
        return;
      }
      // Recorded: say so only once the re-read has confirmed it.
      if (await refresh()) {
        setSubmit({ status: 'idle' });
        onRecorded(verdict);
      } else {
        recorded.current = verdict;
        setSubmit({ status: 'unconfirmed', checking: false });
      }
      inFlight.current = false;
    },
    [caseId, versionId, revision, refresh, onRecorded],
  );

  /** Try again after an unconfirmed or uncertain write: a re-read only, never a second write. */
  const recheck = useCallback(async () => {
    setSubmit((s) => (s.status === 'unconfirmed' || s.status === 'uncertain' ? { ...s, checking: true } : s));
    const ok = await refresh();
    setSubmit((s) => {
      if (s.status === 'unconfirmed' || s.status === 'uncertain') return ok ? { status: 'idle' } : { ...s, checking: false };
      return s;
    });
    if (ok && recorded.current) onRecorded(recorded.current);
    recorded.current = null;
  }, [refresh, onRecorded]);

  return { submit, decide, recheck };
}
