'use client';

// SCR-24 (F-88): the drawer's reads and its one write, `POST /received-bids/{case_id}/assignment`. The write has no idempotency key,
// so it is never repeated here: after a 5xx, a timeout or no answer the assignment is read again first, and the form is offered only
// if it is still null. "Assigned" is said only after the assignment and the list were read again (C-14); a 409 reads the state again
// and shows it. Who may be chosen is whatever the read names.
import { useCallback, useEffect, useRef, useState } from 'react';

import { refreshSession } from '@/api/client';
import { ApiError } from '@/api/errors';

import { assignPm, fetchAssignment, type AssignBody, type AssignmentRead } from './receivedBids';

export const FORBIDDEN = 'You can’t assign a PM for this RFP.';
export const GONE = 'This RFP isn’t available.';
export const CHANGED = 'This changed while you were working.';
export const NOT_CONFIRMED = 'We couldn’t confirm the PM was assigned. Check before trying again.';
export const REFRESH = 'Refresh your session and try again.';
export const TOO_LARGE = 'The file is larger than 5 MB.';
export const WRONG_TYPE = 'Use a Word or PDF file.';
export const RATE_LIMITED = 'Too many tries. Wait a moment.';

export type AssignView =
  | { kind: 'loading' }
  | { kind: 'error' }
  | { kind: 'lost'; why: 'unauthenticated' | 'forbidden' | 'not_found' }
  | { kind: 'ready'; data: AssignmentRead }
  /** Written and read again: the nominee's label as chosen, and whether the re-read list still holds the RFP (null: the list could not be read). */
  | { kind: 'done'; data: AssignmentRead; label: string; listed: boolean | null };

export type AssignNotice =
  | { kind: 'problem'; message: string }
  | { kind: 'invalid'; general: string[] }
  | { kind: 'stale' }
  /** Not confirmed and the read-again did not settle it: only "Check again" (a read) is offered. */
  | { kind: 'unconfirmed' }
  /** Not confirmed at first; the read-again found the assignment. */
  | { kind: 'confirmed' };

export type Proof = { evidence: number } | { uploadId: number };
export type AssignInput = { candidate: number; candidateLabel: string; role: string; reason: string; proof: Proof };

/** The server's field names for the assign body, by the control that draws them. */
const CONTROL: Record<string, string> = { candidate: 'candidate', role: 'role', evidence: 'proof', upload_id: 'proof', checked: 'proof', reason: 'reason' };

const lostOf = (error: unknown): 'unauthenticated' | 'forbidden' | 'not_found' | undefined => {
  if (!(error instanceof ApiError)) return undefined;
  return error.kind === 'unauthenticated' || error.kind === 'forbidden' || error.kind === 'not_found' ? error.kind : undefined;
};

export function useReceivedBidAssign(caseId: string, reloadList: () => Promise<boolean | null>) {
  const [view, setView] = useState<AssignView>({ kind: 'loading' });
  const [notice, setNotice] = useState<AssignNotice | null>(null);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [attempt, setAttempt] = useState(0);
  const [busy, setBusy] = useState(false);
  const writing = useRef(false);

  const load = useCallback(async () => {
    setView({ kind: 'loading' });
    try {
      setView({ kind: 'ready', data: await fetchAssignment(caseId) });
    } catch (error) {
      const why = lostOf(error);
      setView(why ? { kind: 'lost', why } : { kind: 'error' });
    }
  }, [caseId]);
  useEffect(() => {
    // One read per opening; the effect only starts the request.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, [load]);

  /** The read after a write that was not confirmed (or a 409). Returns the read, or null when it failed. */
  const reread = useCallback(async () => {
    try {
      return await fetchAssignment(caseId);
    } catch (error) {
      const why = lostOf(error);
      if (why === 'unauthenticated') setView({ kind: 'lost', why });
      return null;
    }
  }, [caseId]);

  const settle = useCallback(
    async (kept: AssignNotice, unread: AssignNotice = { kind: 'unconfirmed' }) => {
      const data = await reread();
      if (data === null) return setNotice(unread);
      setView({ kind: 'ready', data });
      setNotice(data.assignment ? { kind: 'confirmed' } : kept);
    },
    [reread],
  );

  /** "Check again": a read, never a write. */
  const checkAgain = async () => {
    if (writing.current) return;
    writing.current = true;
    setBusy(true);
    try {
      await settle({ kind: 'problem', message: NOT_CONFIRMED });
    } finally {
      writing.current = false;
      setBusy(false);
    }
  };

  const submit = async (data: AssignmentRead, input: AssignInput) => {
    if (writing.current) return;
    writing.current = true;
    setBusy(true);
    setNotice(null);
    setErrors({});
    const body: AssignBody = {
      intake: data.bid.intake_id,
      revision: data.bid.revision,
      candidate: input.candidate,
      role: input.role,
      reason: input.reason,
      ...('evidence' in input.proof ? { evidence: input.proof.evidence } : { upload_id: input.proof.uploadId, checked: true as const }),
    };
    try {
      try {
        await assignPm(caseId, body);
      } catch (thrown) {
        const error = thrown instanceof ApiError ? thrown : new ApiError(0, 'network', 'network_error', '');
        if (error.kind === 'unauthenticated') return setView({ kind: 'lost', why: 'unauthenticated' });
        if (error.kind === 'network' || error.kind === 'server' || error.kind === 'read_limited') return await settle({ kind: 'problem', message: NOT_CONFIRMED });
        switch (error.kind) {
          case 'csrf':
            await refreshSession().catch(() => undefined);
            return setNotice({ kind: 'problem', message: REFRESH });
          case 'forbidden':
            return setNotice({ kind: 'problem', message: FORBIDDEN });
          case 'not_found':
            return setNotice({ kind: 'problem', message: GONE });
          case 'stale':
            return await settle({ kind: 'stale' }, { kind: 'stale' });
          case 'too_large':
            return setNotice({ kind: 'problem', message: TOO_LARGE });
          case 'unsupported':
            return setNotice({ kind: 'problem', message: WRONG_TYPE });
          case 'rate_limited':
            return setNotice({ kind: 'problem', message: RATE_LIMITED });
          case 'invalid': {
            const mapped: Record<string, string> = {};
            const general: string[] = [];
            for (const problem of error.fields) {
              const control = CONTROL[problem.name];
              if (control) mapped[control] = mapped[control] ? `${mapped[control]} ${problem.message}` : problem.message;
              else general.push(problem.message);
            }
            if (error.fields.length === 0) general.push(error.message);
            setErrors(mapped);
            setAttempt((n) => n + 1);
            return setNotice({ kind: 'invalid', general });
          }
          default:
            return setNotice({ kind: 'problem', message: error.message });
        }
      }
      // 201: say "assigned" only after the assignment and the list are read again.
      const fresh = await reread();
      const listed = await reloadList();
      if (fresh?.assignment) setView({ kind: 'done', data: fresh, label: input.candidateLabel, listed });
      else if (fresh) {
        setView({ kind: 'ready', data: fresh });
        setNotice({ kind: 'problem', message: NOT_CONFIRMED });
      } else setNotice({ kind: 'unconfirmed' });
    } finally {
      writing.current = false;
      setBusy(false);
    }
  };

  return { view, notice, errors, attempt, busy, load, submit, checkAgain, setErrors, setAttempt };
}
