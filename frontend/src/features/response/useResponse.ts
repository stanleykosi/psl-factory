'use client';

// SCR-16 flow: read the item, upload proof as it is chosen, then on one deliberate press claim (only when the
// API asks for it) and record the response once. Nothing retries a record: a 409 keeps every entry and reloads
// the item, and a network or server error reloads the item so the person can see whether it was recorded
// (uncertain effect); only a new press sends again. When that reload fails too, Record stays off and Try again
// only reads the item. E-RESPONSE has no idempotency key, so these guards are the only protection.
import { useCallback, useEffect, useRef, useState } from 'react';

import { ApiError, networkError } from '@/api/errors';

import { claimTask, getWorkItem, recordResponse } from './api';
import type { Recorded, ResponseBody, ResponseTask, ResponseWorkItem, TaskResponse } from './contract';
import { listWords, NOTE_MAX, watIso } from './labels';
import { useEvidenceUpload } from './useEvidenceUpload';

export type Entries = { who: string; when: string; action: string; version: string; channel: string; note: string; attested: boolean };

export type ResponseView =
  | { kind: 'loading' }
  | { kind: 'error'; error: ApiError }
  | { kind: 'form'; item: ResponseWorkItem }
  /** before: the item as it was when Record was pressed (its current station names the success heading). */
  | { kind: 'done'; before: ResponseWorkItem; recorded?: Recorded; next?: string[]; responderId?: string };

export type Notice =
  | { kind: 'stale' }
  | { kind: 'uncertain' }
  /** Uncertain effect and the reload failed: nothing is known, so Record stays off. */
  | { kind: 'unconfirmed'; checking: boolean }
  | { kind: 'problem'; message: string }
  | { kind: 'claim_failed' };

const EMPTY: Entries = { who: '', when: '', action: '', version: '', channel: '', note: '', attested: false };
const asApiError = (error: unknown) => (error instanceof ApiError ? error : networkError());
const ACCESS_LOST = new Set<ApiError['kind']>(['unauthenticated', 'not_found']);

export function findTask(item: ResponseWorkItem, taskId: string | undefined): ResponseTask | undefined {
  return taskId ? item.tasks.find((t) => t.id === taskId) : undefined;
}

/** Actions the page offers: the API's, in order, and only those with a label to show. */
export const offeredActions = (response: TaskResponse) => response.actions.filter((a) => a.label);

/**
 * The entries as they apply to this response: a choice the task no longer offers is cleared, and a list with
 * exactly one responder, version or channel has it chosen (the API offers no alternative). Actions never default.
 */
export function effectiveEntries(entries: Entries, response: TaskResponse): Entries {
  const pick = (value: string, ids: string[]) => (ids.includes(value) ? value : ids.length === 1 ? ids[0] : '');
  return {
    ...entries,
    who: pick(entries.who, response.responders.map((r) => r.id)),
    version: pick(entries.version, (response.versions ?? []).map((v) => v.id)),
    channel: pick(entries.channel, (response.channels ?? []).map((c) => c.value)),
    action: offeredActions(response).some((a) => a.value === entries.action) ? entries.action : '',
  };
}

/** The alert beside a disabled Record, or null when nothing is missing. */
export function missingLine(e: Entries, response: TaskResponse, proofCount: number): string | null {
  const parts: string[] = [];
  if (!e.who) parts.push('who responded');
  if (!e.when) parts.push('when');
  if (!e.action) parts.push('what they did');
  if ((response.versions?.length ?? 0) > 0 && !e.version) parts.push('which version');
  if ((response.channels?.length ?? 0) > 1 && !e.channel) parts.push('how they responded');
  if (parts.length) return `Choose ${listWords(parts)} to record this.`;
  if (proofCount === 0 || !e.attested) return 'Add the proof and confirm it’s genuine to record this.';
  return null;
}

export function useResponse(id: string, taskId: string | undefined) {
  const [view, setView] = useState<ResponseView>({ kind: 'loading' });
  const [entries, setEntries] = useState<Entries>(EMPTY);
  const [notice, setNotice] = useState<Notice | null>(null);
  const [busy, setBusy] = useState(false);
  // One write at a time, checked synchronously so a double press cannot record twice.
  const writing = useRef(false);

  const load = useCallback(async () => {
    setView({ kind: 'loading' });
    try {
      const item = await getWorkItem(id);
      const recorded = findTask(item, taskId)?.response?.recorded;
      setView(recorded ? { kind: 'done', before: item, recorded, next: findTask(item, taskId)?.response?.next } : { kind: 'form', item });
    } catch (error) {
      setView({ kind: 'error', error: asApiError(error) });
    }
  }, [id, taskId]);

  useEffect(() => {
    // One read per opened form; the effect only starts the request.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, [load]);

  const formItem = view.kind === 'form' ? view.item : undefined;
  const task = formItem ? findTask(formItem, taskId) : undefined;
  const response = task?.response;

  const reloadCaseRevision = useCallback(async () => {
    const item = await getWorkItem(id);
    setView((v) => (v.kind === 'form' ? { kind: 'form', item } : v));
    return item.case_revision;
  }, [id]);
  const onAccessError = useCallback((error: ApiError) => setView({ kind: 'error', error }), []);
  const proof = useEvidenceUpload({
    caseId: formItem?.case_id,
    caseRevision: formItem?.case_revision,
    kind: response?.evidence_kind,
    reloadCaseRevision,
    onAccessError,
  });

  /** After a reload: a recorded task (or one gone from the item) is done; otherwise the form shows the new item. */
  const settle = useCallback(
    (before: ResponseWorkItem, item: ResponseWorkItem, responderId: string, keepForm: Notice | null) => {
      const now = findTask(item, taskId);
      if (now?.response?.recorded) {
        setView({ kind: 'done', before, recorded: now.response.recorded, next: now.response.next, responderId });
        return;
      }
      setView({ kind: 'form', item });
      setNotice(keepForm);
    },
    [taskId],
  );

  /** Re-read the item after a failed write; the error when the read failed (access loss replaces the page). */
  const reread = useCallback(async (): Promise<ResponseWorkItem | ApiError> => {
    try {
      return await getWorkItem(id);
    } catch (error) {
      const apiError = asApiError(error);
      if (ACCESS_LOST.has(apiError.kind) || apiError.kind === 'forbidden') setView({ kind: 'error', error: apiError });
      return apiError;
    }
  }, [id]);

  /** 403 or 409 on claim or record: reload, keep every entry, never resend. */
  const afterRefusal = useCallback(
    async (error: ApiError, before: ResponseWorkItem, responderId: string) => {
      const item = await reread();
      if (item instanceof ApiError) {
        if (!ACCESS_LOST.has(item.kind) && item.kind !== 'forbidden') setView({ kind: 'error', error: item });
        return;
      }
      if (error.kind === 'stale') return settle(before, item, responderId, { kind: 'stale' });
      // 403: a task that is no longer actionable shows the not-open state (the form view decides that from the
      // reloaded task); otherwise the server's message shows and the controls stay.
      settle(before, item, responderId, { kind: 'problem', message: error.message });
    },
    [reread, settle],
  );

  /** Uncertain effect: one read, never a resend. */
  const confirm = useCallback(
    async (before: ResponseWorkItem, responderId: string) => {
      const item = await reread();
      if (item instanceof ApiError) {
        if (!ACCESS_LOST.has(item.kind) && item.kind !== 'forbidden') setNotice({ kind: 'unconfirmed', checking: false });
        return;
      }
      settle(before, item, responderId, { kind: 'uncertain' });
    },
    [reread, settle],
  );

  const record = useCallback(async () => {
    if (writing.current || !formItem || !task || !response || notice?.kind === 'unconfirmed') return;
    const e = effectiveEntries(entries, response);
    const ids = proof.evidenceIds;
    if (missingLine(e, response, ids.length) || proof.uploading || e.note.length > NOTE_MAX) return;
    writing.current = true;
    setBusy(true);
    setNotice(null);
    const before = formItem;
    try {
      let expected = task.revision;
      if (response.claim_required) {
        try {
          expected = (await claimTask(task.id, task.revision)).revision;
        } catch (error) {
          const apiError = asApiError(error);
          if (ACCESS_LOST.has(apiError.kind)) setView({ kind: 'error', error: apiError });
          else if (apiError.kind === 'stale' || apiError.kind === 'forbidden') await afterRefusal(apiError, before, e.who);
          else if (apiError.kind === 'invalid') setNotice({ kind: 'problem', message: apiError.message });
          // A claim records nothing, so the next press may claim again.
          else setNotice({ kind: 'claim_failed' });
          return;
        }
      }
      const body: ResponseBody = {
        expected_revision: expected,
        who: e.who,
        action: offeredActions(response).find((a) => a.value === e.action)!.value,
        responded_at: watIso(e.when),
        evidence_id: ids[0],
        attested: true,
      };
      if (ids.length > 1) body.evidence_ids = ids.slice(1);
      const caseRevision = proof.caseRevision();
      if (caseRevision !== undefined) body.case_revision = caseRevision;
      if ((response.versions?.length ?? 0) > 0) body.version_id = e.version;
      if ((response.channels?.length ?? 0) > 0) body.received_via = e.channel;
      const note = e.note.trim();
      if (note) body.note = note;

      let result;
      try {
        result = await recordResponse(task.id, body);
      } catch (error) {
        const apiError = asApiError(error);
        if (ACCESS_LOST.has(apiError.kind)) setView({ kind: 'error', error: apiError });
        else if (apiError.kind === 'stale' || apiError.kind === 'forbidden') await afterRefusal(apiError, before, e.who);
        else if (apiError.kind === 'invalid') setNotice({ kind: 'problem', message: apiError.message });
        else {
          setNotice({ kind: 'uncertain' });
          await confirm(before, e.who);
        }
        return;
      }
      setView({ kind: 'done', before, recorded: result.recorded, next: result.next, responderId: e.who });
      // One reload so the rest of the app sees the new state; it fills what the 200 left out.
      try {
        const item = await getWorkItem(id);
        const now = findTask(item, taskId)?.response;
        setView((v) => (v.kind === 'done' ? { ...v, recorded: v.recorded ?? now?.recorded, next: v.next ?? now?.next } : v));
      } catch {
        // The success view stands on the 200 alone.
      }
    } finally {
      writing.current = false;
      setBusy(false);
    }
  }, [formItem, task, response, entries, proof, notice, afterRefusal, confirm, id, taskId]);

  /** Try again on the unconfirmed notice: one GET, never the response. */
  const recheck = useCallback(async () => {
    if (notice?.kind !== 'unconfirmed' || notice.checking || !formItem) return;
    setNotice({ kind: 'unconfirmed', checking: true });
    await confirm(formItem, response ? effectiveEntries(entries, response).who : '');
  }, [notice, formItem, confirm, entries, response]);

  const setEntry = useCallback(<K extends keyof Entries>(key: K, value: Entries[K]) => setEntries((e) => ({ ...e, [key]: value })), []);

  return { view, task, response, entries: response ? effectiveEntries(entries, response) : entries, setEntry, proof, notice, busy, record, recheck, retry: load };
}
