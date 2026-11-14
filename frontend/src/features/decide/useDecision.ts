'use client';

// SCR-03 flow: read the item, claim an actionable task once per task revision, decide one exact version.
// Nothing retries a decision: a 409 shows the stale view, a network or server error reloads the item so the
// person can see whether it was recorded (uncertain effect), and only a deliberate new tap sends again.
import { useCallback, useEffect, useRef, useState } from 'react';

import { api, call } from '@/api/client';
import { ApiError, networkError } from '@/api/errors';
import type { DecideBody, DecideResult, TaskDecision, WorkItem } from '@/api/types';

import { findDecisionTask, type Verdict } from './format';

export type DecideViewState =
  | { kind: 'loading' }
  | { kind: 'error'; error: ApiError }
  | { kind: 'item'; item: WorkItem }
  /** 403 on a write: read-only, keyed on the reloaded reason when there is one. */
  | { kind: 'forbidden'; item: WorkItem }
  | { kind: 'stale'; replaced: TaskDecision; item: WorkItem }
  | { kind: 'done'; result: DecideResult; label: string; item: WorkItem; reloaded: WorkItem | null; refreshFailed: boolean };

export type ClaimState =
  | { key: string; status: 'pending' }
  | { key: string; status: 'ready'; revision: number }
  | { key: string; status: 'invalid'; message: string }
  | { key: string; status: 'failed' };

export type SubmitState =
  | { status: 'idle' }
  | { status: 'busy'; verdict: Verdict }
  | { status: 'invalid'; message: string };

const asApiError = (error: unknown) => (error instanceof ApiError ? error : networkError());
const ACCESS_LOST = new Set<ApiError['kind']>(['unauthenticated', 'not_found']);

export function useDecision(id: string, taskId: string | undefined) {
  const [view, setView] = useState<DecideViewState>({ kind: 'loading' });
  const [claim, setClaim] = useState<ClaimState | null>(null);
  const [submit, setSubmit] = useState<SubmitState>({ status: 'idle' });
  const [uncertain, setUncertain] = useState(false);
  // "task id:revision" of the last claim sent, so StrictMode and re-renders never claim twice.
  const claimedKey = useRef<string | null>(null);
  // One write at a time, checked synchronously so a double click cannot send two decisions.
  const writing = useRef(false);

  const fetchItem = useCallback(() => call(api.GET('/api/v1/work/{work_id}', { params: { path: { work_id: id } } })), [id]);

  const load = useCallback(async () => {
    setView({ kind: 'loading' });
    try {
      setView({ kind: 'item', item: await fetchItem() });
    } catch (error) {
      setView({ kind: 'error', error: asApiError(error) });
    }
  }, [fetchItem]);

  useEffect(() => {
    // One read per opened decision; the effect only starts the request.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, [load]);

  /** Reload once after a write failed: the item, or the error (access loss replaces the page at once). */
  const reload = useCallback(async (): Promise<WorkItem | ApiError> => {
    try {
      return await fetchItem();
    } catch (error) {
      const apiError = asApiError(error);
      if (ACCESS_LOST.has(apiError.kind)) setView({ kind: 'error', error: apiError });
      return apiError;
    }
  }, [fetchItem]);

  const toStale = useCallback(
    async (replaced: TaskDecision) => {
      const item = await reload();
      if (item instanceof ApiError) {
        // Never leave the replaced version actionable: without the current one the page shows the load error.
        if (!ACCESS_LOST.has(item.kind)) setView({ kind: 'error', error: item });
        return;
      }
      const task = findDecisionTask(item, taskId);
      setView(task ? { kind: 'stale', replaced, item } : { kind: 'item', item });
    },
    [reload, taskId],
  );

  const toForbidden = useCallback(
    async (current: WorkItem) => {
      const item = await reload();
      if (item instanceof ApiError && ACCESS_LOST.has(item.kind)) return;
      setView({ kind: 'forbidden', item: item instanceof ApiError ? current : item });
    },
    [reload],
  );

  /** Shared handling for claim and decide errors other than 422 and network or server. */
  const handleWriteError = useCallback(
    async (error: ApiError, item: WorkItem, decision: TaskDecision): Promise<boolean> => {
      if (error.kind === 'unauthenticated' || error.kind === 'not_found') {
        setView({ kind: 'error', error });
        return true;
      }
      if (error.kind === 'forbidden') {
        await toForbidden(item);
        return true;
      }
      if (error.kind === 'stale') {
        await toStale(decision);
        return true;
      }
      return false;
    },
    [toForbidden, toStale],
  );

  const runClaim = useCallback(
    async (item: WorkItem, key: string) => {
      const task = findDecisionTask(item, taskId)!;
      try {
        const result = await call(
          api.POST('/api/v1/tasks/{task_id}/claim', { params: { path: { task_id: task.id } }, body: { expected_revision: task.revision } }),
        );
        setClaim({ key, status: 'ready', revision: result.revision });
      } catch (error) {
        const apiError = asApiError(error);
        if (await handleWriteError(apiError, item, task.decision)) return;
        setClaim(apiError.kind === 'invalid' ? { key, status: 'invalid', message: apiError.message } : { key, status: 'failed' });
      }
    },
    [handleWriteError, taskId],
  );

  // Claim once when an actionable task is on screen (E-TASK-CLAIM trigger "Open a decision you are eligible for").
  const actionable = view.kind === 'item' ? findDecisionTask(view.item, taskId) : undefined;
  const claimKey = actionable?.you_can_act ? `${actionable.id}:${actionable.revision}` : null;
  useEffect(() => {
    if (view.kind !== 'item' || !claimKey || claimedKey.current === claimKey) return;
    claimedKey.current = claimKey;
    void runClaim(view.item, claimKey);
  }, [view, claimKey, runClaim]);

  /** A claim records no decision, so the person may try it again. */
  const retryClaim = useCallback(() => {
    if (view.kind !== 'item' || !claimKey) return;
    setClaim({ key: claimKey, status: 'pending' });
    void runClaim(view.item, claimKey);
  }, [view, claimKey, runClaim]);

  const decide = useCallback(
    async (verdict: Verdict, note: string) => {
      if (writing.current || view.kind !== 'item' || claim?.key !== claimKey || claim?.status !== 'ready') return;
      const item = view.item;
      const task = findDecisionTask(item, taskId)!;
      writing.current = true;
      setSubmit({ status: 'busy', verdict });
      setUncertain(false);
      const body: DecideBody = { expected_revision: claim.revision, verdict };
      if (note.trim() !== '') body.note = note;
      try {
        const result = await call(api.POST('/api/v1/tasks/{task_id}/decision', { params: { path: { task_id: task.id } }, body }));
        setSubmit({ status: 'idle' });
        setView({ kind: 'done', result, label: task.decision.version.label, item, reloaded: null, refreshFailed: false });
        try {
          const reloaded = await fetchItem();
          setView((v) => (v.kind === 'done' ? { ...v, reloaded } : v));
        } catch {
          setView((v) => (v.kind === 'done' ? { ...v, refreshFailed: true } : v));
        }
      } catch (error) {
        // The buttons stay disabled until the follow-up view is on screen.
        const apiError = asApiError(error);
        if (await handleWriteError(apiError, item, task.decision)) {
          setSubmit({ status: 'idle' });
          return;
        }
        if (apiError.kind === 'invalid') {
          setSubmit({ status: 'invalid', message: apiError.message });
          return;
        }
        // Uncertain effect: reload once, never resend.
        setUncertain(true);
        const reloaded = await reload();
        setSubmit({ status: 'idle' });
        if (reloaded instanceof ApiError) return;
        const now = findDecisionTask(reloaded, taskId);
        if (now && now.you_can_act && now.revision !== task.revision) setView({ kind: 'stale', replaced: task.decision, item: reloaded });
        else setView({ kind: 'item', item: reloaded });
      } finally {
        writing.current = false;
      }
    },
    [view, claim, claimKey, taskId, handleWriteError, fetchItem, reload],
  );

  /** "Review version n": show the current version and claim it again, even at an unchanged revision. */
  const reviewCurrent = useCallback(() => {
    if (view.kind !== 'stale') return;
    claimedKey.current = null;
    setClaim(null);
    setSubmit({ status: 'idle' });
    setUncertain(false);
    setView({ kind: 'item', item: view.item });
  }, [view]);

  const claimNow: ClaimState | null = claimKey ? (claim?.key === claimKey ? claim : { key: claimKey, status: 'pending' }) : null;
  return { view, claim: claimNow, submit, uncertain, retry: load, retryClaim, decide, reviewCurrent };
}
