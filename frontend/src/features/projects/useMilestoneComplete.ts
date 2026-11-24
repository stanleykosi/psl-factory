'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

import { call, csrfHeader, liveApi } from '@/api/client';
import { ApiError, networkError } from '@/api/errors';
import type { UploadedFile } from '@/features/workspace/evidence';

import { isRecordedCompletion, type Completion, type CompletionOptions } from './milestonesModel';
import { readCompletion, readOptions } from './useMilestones';

export type OptionsRead = { status: 'loading' } | { status: 'error'; error: ApiError } | { status: 'ready'; options: CompletionOptions; moreFailed: boolean; loadingMore: boolean };
/** One entry's write, from the person's press to what the re-read says. Nothing here is sent twice. */
export type Submit =
  | { status: 'idle' }
  | { status: 'busy' }
  /** Recorded (201); the re-read has not answered yet. */
  | { status: 'confirming' }
  /** The re-read confirmed it: shown from the re-read body, never from the 201. */
  | { status: 'recorded'; completion: Completion }
  /** The 201 came, but the re-read failed. Check again only re-reads. */
  | { status: 'unconfirmed'; id: number; checking: boolean }
  /** Network failure or 5xx: the server may have recorded it. Check again only reads the options. */
  | { status: 'uncertain'; checking: boolean }
  /** The check found a completion with this name; no id is known, so it is not claimed to be this press. */
  | { status: 'now_recorded' }
  | { status: 'refused'; message: string }
  | { status: 'no_access' }
  | { status: 'signed_out' };
export type Chosen = { kind: 'proof'; id: number } | { kind: 'pdf' } | null;

const asApiError = (error: unknown) => (error instanceof ApiError ? error : networkError());

const FALLBACK = 'We couldn’t record this. Check the proof and try again.';

/** The refusal in words for a status where nothing was recorded; null when the result is uncertain. */
function refusal(e: ApiError): string | null {
  switch (e.kind) {
    case 'forbidden':
      return 'You can’t mark this milestone complete.';
    case 'invalid':
    case 'bad_request':
      return e.fields[0]?.message ?? (e.kind === 'invalid' && e.message ? e.message : FALLBACK);
    case 'too_large':
      return 'That file is too large to upload.';
    case 'unsupported':
      return 'Only a PDF can be attached as proof.';
    case 'csrf':
    case 'rate_limited':
      return e.message;
    default:
      return null;
  }
}

/**
 * SCR-19: the options read for one milestone name, the form's choices, and the one write
 * POST /projects/{case_id}/milestones/completions. "Recorded" comes only from the re-read of the new completion. A 409
 * reloads the options and keeps what the person entered. An uncertain result is never resent: "Check again" re-reads the
 * options only. One press is one POST; there is no timer, retry or idempotency key. Authority is the server's `can_complete`.
 */
export function useMilestoneComplete(caseId: string, name: string) {
  const [read, setRead] = useState<OptionsRead>({ status: 'loading' });
  const [chosen, setChosen] = useState<Chosen>(null);
  const [upload, setUpload] = useState<UploadedFile | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const [fileChecked, setFileChecked] = useState(false);
  const [submit, setSubmit] = useState<Submit>({ status: 'idle' });
  const [notes, setNotes] = useState<{ conflict: boolean; proofGone: boolean; notRecorded: boolean }>({ conflict: false, proofGone: false, notRecorded: false });
  const seq = useRef(0);
  const inFlight = useRef(false);
  const written = useRef<{ id: number | null }>({ id: null });
  const optionsRef = useRef<CompletionOptions | null>(null);

  const load = useCallback(async () => {
    const mine = ++seq.current;
    setRead({ status: 'loading' });
    try {
      const options = await readOptions(caseId, { name });
      if (mine !== seq.current) return;
      optionsRef.current = options;
      setRead({ status: 'ready', options, moreFailed: false, loadingMore: false });
    } catch (error) {
      if (mine !== seq.current) return;
      setRead({ status: 'error', error: asApiError(error) });
    }
  }, [caseId, name]);

  useEffect(() => {
    // The effect only starts the read; another case or name starts clean.
    inFlight.current = false;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setSubmit({ status: 'idle' });
    setChosen(null);
    setUpload(null);
    setConfirmed(false);
    setFileChecked(false);
    setNotes({ conflict: false, proofGone: false, notRecorded: false });
    void load();
  }, [load]);

  /** Re-read the options in place after a 409 or a refusal: the form stays, the revision and proofs are the new ones. */
  const reload = useCallback(
    async (afterConflict: boolean) => {
      const mine = ++seq.current;
      try {
        const options = await readOptions(caseId, { name });
        if (mine !== seq.current) return null;
        optionsRef.current = options;
        setRead({ status: 'ready', options, moreFailed: false, loadingMore: false });
        if (afterConflict) {
          setChosen((prev) => {
            if (prev?.kind === 'proof' && !options.proofs.some((p) => p.id === prev.id)) {
              setNotes((n) => ({ ...n, proofGone: true }));
              return null;
            }
            return prev;
          });
        }
        return options;
      } catch {
        return null;
      }
    },
    [caseId, name],
  );

  const showMore = useCallback(async () => {
    if (read.status !== 'ready' || read.options.next_page === null || read.loadingMore) return;
    const page = read.options.next_page;
    const mine = seq.current;
    setRead({ ...read, loadingMore: true, moreFailed: false });
    try {
      const next = await readOptions(caseId, { name, page });
      if (mine !== seq.current) return;
      const base = optionsRef.current ?? read.options;
      const seen = new Set(base.proofs.map((p) => p.id));
      const merged = { ...base, next_page: next.next_page, proofs: [...base.proofs, ...next.proofs.filter((p) => !seen.has(p.id))] };
      optionsRef.current = merged;
      setRead({ status: 'ready', options: merged, moreFailed: false, loadingMore: false });
    } catch {
      if (mine !== seq.current) return;
      setRead((prev) => (prev.status === 'ready' ? { ...prev, loadingMore: false, moreFailed: true } : prev));
    }
  }, [caseId, name, read]);

  /** The re-read of the new completion; "recorded" only when it answers and names what was written. */
  const confirm = useCallback(
    async (id: number) => {
      try {
        const completion = await readCompletion(caseId, id);
        if (completion.name !== name) throw new ApiError(200, 'server', 'unexpected_response', 'The completion does not match.');
        setSubmit({ status: 'recorded', completion });
      } catch (error) {
        const e = asApiError(error);
        if (e.kind === 'unauthenticated') setSubmit({ status: 'signed_out' });
        else setSubmit({ status: 'unconfirmed', id, checking: false });
      }
    },
    [caseId, name],
  );

  const complete = useCallback(async () => {
    const options = optionsRef.current;
    if (inFlight.current || !options || !options.can_complete || chosen === null) return;
    if (chosen.kind === 'pdf' && !(upload && fileChecked)) return;
    if (!confirmed) return;
    inFlight.current = true;
    setNotes({ conflict: false, proofGone: false, notRecorded: false });
    setSubmit({ status: 'busy' });
    const body = chosen.kind === 'proof' ? { revision: options.revision, name, evidence_id: chosen.id } : { revision: options.revision, name, upload_id: upload!.upload_id as number, checked: true as const };
    let recorded;
    try {
      recorded = await call(liveApi.POST('/api/v1/projects/{case_id}/milestones/completions', { params: { path: { case_id: caseId }, ...csrfHeader }, body }));
      if (!isRecordedCompletion(recorded)) throw new ApiError(201, 'server', 'unexpected_response', 'unexpected');
    } catch (error) {
      const e = asApiError(error);
      if (e.kind === 'unauthenticated') {
        setSubmit({ status: 'signed_out' });
        return;
      }
      if (e.kind === 'stale') {
        setSubmit({ status: 'idle' });
        setNotes((n) => ({ ...n, conflict: true }));
        inFlight.current = false;
        await reload(true);
        return;
      }
      if (e.kind === 'not_found') {
        setSubmit({ status: 'no_access' });
        inFlight.current = false;
        return;
      }
      const message = refusal(e);
      if (message === null) {
        // network, timeout, 5xx or an unreadable 201: the server may have recorded it, so nothing is sent again
        setSubmit({ status: 'uncertain', checking: false });
        return;
      }
      setSubmit({ status: 'refused', message });
      inFlight.current = false;
      if (e.kind === 'forbidden') void reload(false);
      return;
    }
    written.current = { id: recorded.id };
    setSubmit({ status: 'confirming' });
    await confirm(recorded.id);
  }, [caseId, name, chosen, upload, fileChecked, confirmed, reload, confirm]);

  /** After an unconfirmed or uncertain result: reads only, never a second write. */
  const check = useCallback(async () => {
    if (submit.status === 'unconfirmed') {
      setSubmit({ ...submit, checking: true });
      await confirm(submit.id);
      return;
    }
    if (submit.status !== 'uncertain') return;
    setSubmit({ status: 'uncertain', checking: true });
    const options = await reload(false);
    if (options?.hold === 'name_in_use') setSubmit({ status: 'now_recorded' });
    else if (options && options.hold === null && options.can_complete) {
      setNotes((n) => ({ ...n, notRecorded: true }));
      setSubmit({ status: 'idle' });
      inFlight.current = false;
    } else setSubmit({ status: 'uncertain', checking: false });
  }, [submit, confirm, reload]);

  return { read, retry: load, showMore, chosen, setChosen, upload, setUpload, confirmed, setConfirmed, fileChecked, setFileChecked, submit, notes, complete, check };
}
