'use client';

// SCR-16 RFP outcome (/work/[id]/outcome): read the item, upload the proof as it is chosen, then on one deliberate
// press record the outcome once. Nothing retries: a 409 keeps every entry and the proof and reloads the item (the
// next press carries the reloaded revision and case_revision); a 403 reloads and removes the form; a network or
// server error reloads once so the person can see whether it was recorded (uncertain effect), and when that reload
// fails too Record stays off and Try again only reads. E-RFP-OUTCOME has no idempotency key; a repeat after a
// success fails on expected_revision.
import { useCallback, useEffect, useRef, useState } from 'react';

import { ApiError, networkError } from '@/api/errors';
import { getWorkItem } from '@/features/response/api';
import type { ResponseWorkItem } from '@/features/response';
import { listWords, NOTE_MAX, watIso } from '@/features/response/labels';
import { useEvidenceUpload } from '@/features/response';

import { recordOutcome } from './api';
import type { OutcomeBody, OutcomeResult, RfpOutcome } from './contract';
import { amountValue } from './labels';

export type OutcomeEntries = {
  result: OutcomeResult | '';
  learned: string;
  recordAs: string;
  note: string;
  amount: string;
  amountUnknown: boolean;
  reason: string;
  lessons: string;
  expected: string;
  remind: string;
};

export type OutcomePage =
  | { kind: 'loading' }
  | { kind: 'error'; error: ApiError }
  | { kind: 'item'; item: ResponseWorkItem }
  /** A 403 on the write: the reloaded item, shown without the form, with the server's message. */
  | { kind: 'refused'; item: ResponseWorkItem; message: string }
  /** Recorded (200) but the reload failed: the returned result only, no invented rows. */
  | { kind: 'recorded'; before: ResponseWorkItem; result: OutcomeResult };

export type OutcomeNotice =
  | { kind: 'stale' }
  | { kind: 'uncertain' }
  | { kind: 'unconfirmed'; checking: boolean }
  | { kind: 'problem'; message: string };

const EMPTY: OutcomeEntries = { result: '', learned: '', recordAs: '', note: '', amount: '', amountUnknown: false, reason: '', lessons: '', expected: '', remind: '' };
const asApiError = (error: unknown) => (error instanceof ApiError ? error : networkError());
const ACCESS_LOST = new Set<ApiError['kind']>(['unauthenticated', 'not_found']);

/** The form is open only with a block that offers results and someone to record as. */
export const outcomeOpen = (outcome: RfpOutcome | undefined): outcome is RfpOutcome =>
  Boolean(outcome && outcome.results.length > 0 && outcome.record_as.length > 0);

/** Choices the block no longer offers are cleared; a single record_as option is chosen. A result never defaults. */
export function effectiveOutcome(e: OutcomeEntries, outcome: RfpOutcome): OutcomeEntries {
  const roles = outcome.record_as.map((r) => r.value);
  return {
    ...e,
    result: e.result && outcome.results.includes(e.result) ? e.result : '',
    recordAs: roles.includes(e.recordAs) ? e.recordAs : roles.length === 1 ? roles[0] : '',
    reason: (outcome.reasons ?? []).some((r) => r.value === e.reason) ? e.reason : '',
  };
}

/** The won amount's problem, when the typed text is not an amount. */
export function amountProblem(e: OutcomeEntries): string | null {
  if (e.result !== 'won' || e.amountUnknown || e.amount.trim() === '') return null;
  return amountValue(e.amount) ? null : 'Enter the amount in naira with at most two decimals, for example 40,951,000.';
}

/** The line beside a disabled Record, or null when nothing is missing. */
export function outcomeMissing(e: OutcomeEntries, proofCount: number): string | null {
  const parts: string[] = [];
  if (!e.result) parts.push('the result');
  if (!e.learned) parts.push(e.result === 'unknown' ? 'the last contact' : 'when you learned it');
  if (!e.recordAs) parts.push('who you are recording as');
  if (parts.length) return `Choose ${listWords(parts)}${proofCount === 0 ? ', and add the proof,' : ''} to record this.`;
  if (proofCount === 0) return 'Add the proof to record this.';
  return null;
}

/** The request for the chosen result: only that result's fields, so values typed under another result are not sent. */
export function outcomeBody(e: OutcomeEntries, item: ResponseWorkItem, outcome: RfpOutcome, evidenceId: string, caseRevision: number): OutcomeBody {
  const body: OutcomeBody = {
    expected_revision: item.revision,
    case_revision: caseRevision,
    submission_id: outcome.submission.id,
    result: e.result as OutcomeResult,
    learned_at: watIso(e.learned),
    record_as: e.recordAs,
    evidence_id: evidenceId,
  };
  const note = e.note.trim();
  if (note) body.note = note;
  if (e.result === 'won') {
    if (e.amountUnknown) body.awarded_amount = { currency: 'NGN', unknown: true };
    else if (e.amount.trim()) body.awarded_amount = { currency: 'NGN', amount: amountValue(e.amount)!, unknown: false };
  }
  if (e.result === 'lost') {
    if (e.reason) body.reason = e.reason;
    const lessons = e.lessons.trim();
    if (lessons) body.lessons = lessons;
  }
  if (e.result === 'pending' && e.expected) body.expected_decision_on = e.expected;
  if ((e.result === 'pending' || e.result === 'unknown') && e.remind) body.remind_at = watIso(e.remind);
  return body;
}

export function useOutcome(id: string) {
  const [page, setPage] = useState<OutcomePage>({ kind: 'loading' });
  const [entries, setEntries] = useState<OutcomeEntries>(EMPTY);
  const [notice, setNotice] = useState<OutcomeNotice | null>(null);
  const [busy, setBusy] = useState(false);
  // "Record the outcome" on a pending or unknown recorded view shows the form again.
  const [reopened, setReopened] = useState(false);
  // One write at a time, checked synchronously so a double press cannot record twice.
  const writing = useRef(false);

  const load = useCallback(async () => {
    setPage({ kind: 'loading' });
    try {
      setPage({ kind: 'item', item: await getWorkItem(id) });
    } catch (error) {
      setPage({ kind: 'error', error: asApiError(error) });
    }
  }, [id]);

  useEffect(() => {
    // One read per opened page; the effect only starts the request.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, [load]);

  const item = page.kind === 'item' ? page.item : undefined;
  const outcome = item?.rfp_outcome;

  const reloadCaseRevision = useCallback(async () => {
    const next = await getWorkItem(id);
    setPage((p) => (p.kind === 'item' ? { kind: 'item', item: next } : p));
    return next.case_revision;
  }, [id]);
  const onAccessError = useCallback((error: ApiError) => setPage({ kind: 'error', error }), []);
  const proof = useEvidenceUpload({
    caseId: item?.case_id,
    caseRevision: item?.case_revision,
    kind: outcome?.evidence_kind,
    reloadCaseRevision,
    onAccessError,
  });
  const { sync } = proof;

  /** Re-read after a failed write; the error when that read failed (access loss replaces the page). */
  const reread = useCallback(async (): Promise<ResponseWorkItem | ApiError> => {
    try {
      const next = await getWorkItem(id);
      sync(next.case_revision);
      return next;
    } catch (error) {
      const apiError = asApiError(error);
      if (ACCESS_LOST.has(apiError.kind) || apiError.kind === 'forbidden') setPage({ kind: 'error', error: apiError });
      return apiError;
    }
  }, [id, sync]);

  /** Re-read for the follow-up card: the page shows the new item, or the read's error (access loss replaces the page). */
  const refresh = useCallback(async () => {
    const next = await reread();
    if (!(next instanceof ApiError)) setPage((p) => (p.kind === 'item' ? { kind: 'item', item: next } : p));
    return next;
  }, [reread]);

  const record = useCallback(async () => {
    if (writing.current || !item || !outcomeOpen(outcome) || notice?.kind === 'unconfirmed') return;
    const e = effectiveOutcome(entries, outcome);
    const ids = proof.evidenceIds;
    const caseRevision = proof.caseRevision();
    if (outcomeMissing(e, ids.length) || amountProblem(e) || proof.uploading || e.note.length > NOTE_MAX || caseRevision === undefined) return;
    writing.current = true;
    setBusy(true);
    setNotice(null);
    try {
      let reply;
      try {
        reply = await recordOutcome(id, outcomeBody(e, item, outcome, ids[0], caseRevision));
      } catch (error) {
        const apiError = asApiError(error);
        if (ACCESS_LOST.has(apiError.kind)) return setPage({ kind: 'error', error: apiError });
        if (apiError.kind === 'invalid') return setNotice({ kind: 'problem', message: apiError.message });
        const refusal = apiError.kind === 'stale' || apiError.kind === 'forbidden';
        if (!refusal) setNotice({ kind: 'uncertain' });
        const next = await reread();
        if (next instanceof ApiError) {
          if (ACCESS_LOST.has(next.kind) || next.kind === 'forbidden') return;
          if (refusal) return setPage({ kind: 'error', error: next });
          return setNotice({ kind: 'unconfirmed', checking: false });
        }
        if (apiError.kind === 'forbidden') return setPage({ kind: 'refused', item: next, message: apiError.message });
        setReopened(false);
        setPage({ kind: 'item', item: next });
        if (apiError.kind === 'stale') setNotice({ kind: 'stale' });
        return;
      }
      // One reload so the page shows what the backend recorded; without it, the returned result only.
      try {
        const next = await getWorkItem(id);
        setReopened(false);
        setPage({ kind: 'item', item: next });
        if (!next.rfp_outcome?.recorded) setPage({ kind: 'recorded', before: item, result: reply.result });
      } catch {
        setPage({ kind: 'recorded', before: item, result: reply.result });
      }
    } finally {
      writing.current = false;
      setBusy(false);
    }
  }, [item, outcome, entries, proof, notice, id, reread]);

  /** Try again on the unconfirmed notice: one GET, never the outcome. */
  const recheck = useCallback(async () => {
    if (notice?.kind !== 'unconfirmed' || notice.checking) return;
    setNotice({ kind: 'unconfirmed', checking: true });
    const next = await reread();
    if (next instanceof ApiError) {
      if (!ACCESS_LOST.has(next.kind) && next.kind !== 'forbidden') setNotice({ kind: 'unconfirmed', checking: false });
      return;
    }
    setPage({ kind: 'item', item: next });
    setNotice({ kind: 'uncertain' });
  }, [notice, reread]);

  // Until the person changes something, what is missing is a hint, not an error.
  const [changed, setChanged] = useState(false);
  const setEntry = useCallback(<K extends keyof OutcomeEntries>(key: K, value: OutcomeEntries[K]) => {
    setChanged(true);
    setEntries((e) => ({ ...e, [key]: value }));
  }, []);
  const touched = changed || proof.files.length > 0;

  return {
    page,
    outcome,
    entries: outcomeOpen(outcome) ? effectiveOutcome(entries, outcome) : entries,
    setEntry,
    touched,
    proof,
    notice,
    busy,
    reopened,
    reopen: () => setReopened(true),
    record,
    recheck,
    refresh,
    retry: load,
  };
}
