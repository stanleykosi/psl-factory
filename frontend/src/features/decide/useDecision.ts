'use client';

// SCR-03 flow on the live task API: read the work and the task, claim an open task once per task revision, decide
// one exact revision on one piece of evidence the person chose. Who may act comes only from the task read
// (can_decide, can_claim, claimed_by_you). Nothing retries a decision: a 409 shows the stale view, a network or
// server error reloads so the person can see whether it was recorded (uncertain effect), and only a deliberate new
// tap sends again. When that reload fails too, the controls stay off and Try again only reads.
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { call, csrfHeader, liveApi } from '@/api/client';
import { ApiError, networkError, type FieldError } from '@/api/errors';
import type { LiveDecisionBody, LiveDecisionResult, LiveHistoryItem, LiveTaskRead, LiveWork } from '@/api/types';

import { liveId, type Verdict } from './format';

/** The version, amount and recipient of a task read: what the stale board compares. */
export type Snapshot = { version: number | null; amount: string | null; currency: string | null; recipient: string | null };

export function snapshotOf(read: LiveTaskRead): Snapshot {
  const packet = read.invoice_packet;
  return {
    version: packet?.version ?? null,
    amount: packet?.amount || null,
    currency: packet?.currency ?? null,
    recipient: read.recipient_change?.current ?? packet?.recipient ?? null,
  };
}

export type Loaded = { work: LiveWork; read: LiveTaskRead };
export type QueueEntry = { id: number; title: string };

export type DecideViewState =
  | { kind: 'loading' }
  | { kind: 'error'; error: ApiError }
  /** The task is not on this work (or the route ids are not integers): nothing to decide here. */
  | { kind: 'notopen'; work: LiveWork | null }
  | ({ kind: 'item' } & Loaded)
  /** 403 on a write: read-only. */
  | ({ kind: 'forbidden' } & Loaded)
  | ({ kind: 'stale'; replaced: Snapshot; note: string } & Loaded)
  /** Decide had an uncertain effect and the reload failed: nothing is known, so nothing can be decided. */
  | ({ kind: 'unconfirmed'; replaced: Snapshot; revision: number; checking: boolean } & Loaded)
  | {
      kind: 'done';
      result: LiveDecisionResult;
      label: string;
      note: string;
      work: LiveWork;
      reloaded: LiveWork | null;
      /** The decision history item for this task; null when the read has none (then "decided by" is not drawn). */
      history: LiveHistoryItem | null;
      refreshFailed: boolean;
    };

export type ClaimState =
  | { key: string; status: 'pending' }
  | { key: string; status: 'ready'; revision: number }
  | { key: string; status: 'invalid'; message: string }
  | { key: string; status: 'failed' };

export type CommentState =
  | { status: 'idle' }
  | { status: 'busy' }
  | { status: 'sent' }
  | { status: 'error'; message: string }
  /** 403: the server does not let this person comment, so the box goes away. */
  | { status: 'closed'; message: string }
  | { status: 'uncertain' };

export type SubmitState =
  | { status: 'idle' }
  | { status: 'busy'; verdict: Verdict }
  | { status: 'invalid'; message: string; fields: FieldError[] };

const asApiError = (error: unknown) => (error instanceof ApiError ? error : networkError());
const ACCESS_LOST = new Set<ApiError['kind']>(['unauthenticated', 'not_found']);
const NO_ACCESS = new Set<ApiError['kind']>(['unauthenticated', 'forbidden', 'not_found']);

/** The history item of the decision on this task: the latest one when there are several. */
function decisionOf(items: LiveHistoryItem[], taskId: number): LiveHistoryItem | null {
  const own = items.filter((item) => item.task_id === taskId);
  return own.reduce<LiveHistoryItem | null>((latest, item) => (latest === null || item.at > latest.at ? item : latest), null);
}

export function useDecision(id: string, taskId: string | undefined) {
  const workId = liveId(id);
  const taskNumber = taskId === undefined ? undefined : liveId(taskId);
  // A route id that is not an integer is never sent to the API.
  const unreadable = workId === null || (taskId !== undefined && taskNumber === null);
  const [view, setView] = useState<DecideViewState>(unreadable ? { kind: 'notopen', work: null } : { kind: 'loading' });
  const [claimState, setClaimState] = useState<ClaimState | null>(null);
  const [submit, setSubmit] = useState<SubmitState>({ status: 'idle' });
  const [uncertain, setUncertain] = useState(false);
  const [queue, setQueue] = useState<QueueEntry[] | null>(null);
  // "task id:revision" of the last claim sent, so StrictMode and re-renders never claim twice.
  const claimedKey = useRef<string | null>(null);
  // One write at a time, checked synchronously so a double click cannot send two decisions.
  const writing = useRef(false);
  const commenting = useRef(false);
  const [commentState, setCommentState] = useState<CommentState>({ status: 'idle' });

  const fetchWork = useCallback(() => call(liveApi.GET('/api/v1/work/{work_id}', { params: { path: { work_id: workId! } } })), [workId]);

  /** The work, and the task read when the work lists the task. */
  const fetchLoaded = useCallback(async (): Promise<{ work: LiveWork; read: LiveTaskRead | null }> => {
    const work = await fetchWork();
    if (typeof taskNumber !== 'number' || !work.tasks.some((t) => t.id === taskNumber)) return { work, read: null };
    return { work, read: await call(liveApi.GET('/api/v1/tasks/{task_id}', { params: { path: { task_id: taskNumber } } })) };
  }, [fetchWork, taskNumber]);

  /** The person's decision list: for the pager and "next decision" only. A failed read leaves them out. */
  const loadQueue = useCallback(async () => {
    try {
      const data = await call(liveApi.GET('/api/v1/work', { params: { query: { queue: 'decisions' } } }));
      setQueue(data.items.map(({ id: itemId, title }) => ({ id: itemId, title })));
    } catch {
      setQueue(null);
    }
  }, []);

  const show = (found: { work: LiveWork; read: LiveTaskRead | null }): DecideViewState =>
    found.read ? { kind: 'item', work: found.work, read: found.read } : { kind: 'notopen', work: found.work };

  const load = useCallback(async () => {
    if (unreadable) return;
    setView({ kind: 'loading' });
    try {
      setView(show(await fetchLoaded()));
    } catch (error) {
      setView({ kind: 'error', error: asApiError(error) });
    }
  }, [fetchLoaded, unreadable]);

  useEffect(() => {
    // One read per opened decision; the effects only start the requests.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
    if (!unreadable) void loadQueue();
  }, [load, loadQueue, unreadable]);

  /** Reload once after a write failed: the work and task, or the error (access loss replaces the page at once). */
  const reload = useCallback(async () => {
    try {
      return await fetchLoaded();
    } catch (error) {
      const apiError = asApiError(error);
      if (ACCESS_LOST.has(apiError.kind)) setView({ kind: 'error', error: apiError });
      return apiError;
    }
  }, [fetchLoaded]);

  const toStale = useCallback(
    async (replaced: Snapshot, note: string) => {
      const found = await reload();
      if (found instanceof ApiError) {
        // Never leave the replaced version actionable: without the current one the page shows the load error.
        if (!ACCESS_LOST.has(found.kind)) setView({ kind: 'error', error: found });
        return;
      }
      setView(found.read ? { kind: 'stale', work: found.work, read: found.read, replaced, note } : show(found));
    },
    [reload],
  );

  const toForbidden = useCallback(
    async (current: Loaded) => {
      const found = await reload();
      if (found instanceof ApiError && ACCESS_LOST.has(found.kind)) return;
      const next = found instanceof ApiError ? current : found.read ? { work: found.work, read: found.read } : current;
      setView({ kind: 'forbidden', ...next });
    },
    [reload],
  );

  /** Shared handling for claim and decide errors other than 422 and network or server. */
  const handleWriteError = useCallback(
    async (error: ApiError, loaded: Loaded, note: string): Promise<boolean> => {
      if (error.kind === 'unauthenticated' || error.kind === 'not_found') {
        setView({ kind: 'error', error });
        return true;
      }
      if (error.kind === 'forbidden') {
        await toForbidden(loaded);
        return true;
      }
      if (error.kind === 'stale') {
        await toStale(snapshotOf(loaded.read), note);
        return true;
      }
      return false;
    },
    [toForbidden, toStale],
  );

  /**
   * After an uncertain decide: read again (never resend). The controls come back only when the task is still
   * actionable at the claimed revision; a newer actionable revision is stale; a failed read leaves the controls off.
   */
  const reconcile = useCallback(
    async (loaded: Loaded, revision: number, note: string) => {
      const replaced = snapshotOf(loaded.read);
      let found: { work: LiveWork; read: LiveTaskRead | null };
      try {
        found = await fetchLoaded();
      } catch (error) {
        const apiError = asApiError(error);
        setView(NO_ACCESS.has(apiError.kind) ? { kind: 'error', error: apiError } : { kind: 'unconfirmed', ...loaded, replaced, revision, checking: false });
        return;
      }
      const now = found.read?.task;
      if (found.read && now && (now.can_decide || now.can_claim) && now.revision !== revision) {
        setView({ kind: 'stale', work: found.work, read: found.read, replaced, note });
      } else setView(show(found));
    },
    [fetchLoaded],
  );

  /** "Try again" on the unconfirmed view: one GET, never the decision. */
  const recheck = useCallback(() => {
    if (view.kind !== 'unconfirmed' || view.checking) return;
    setView({ ...view, checking: true });
    void reconcile(view, view.revision, '');
  }, [view, reconcile]);

  const runClaim = useCallback(
    async (loaded: Loaded, key: string) => {
      const { task } = loaded.read;
      try {
        const result = await call(
          liveApi.POST('/api/v1/tasks/{task_id}/claim', { params: { path: { task_id: task.id }, ...csrfHeader }, body: { expected_revision: task.revision } }),
        );
        setClaimState({ key, status: 'ready', revision: result.revision });
      } catch (error) {
        const apiError = asApiError(error);
        if (await handleWriteError(apiError, loaded, '')) return;
        setClaimState(apiError.kind === 'invalid' || apiError.kind === 'bad_request' ? { key, status: 'invalid', message: apiError.message } : { key, status: 'failed' });
      }
    },
    [handleWriteError],
  );

  // The task read says who may act: can_decide with the claim held opens the deciding board; an open task the
  // person can claim is claimed once (per task revision), then the same board. Anything else is read-only.
  const open = view.kind === 'item' || view.kind === 'unconfirmed' ? view : null;
  const task = open?.read.task;
  const held = Boolean(task?.can_decide && task.claimed_by_you);
  const claimKey = task && !held && task.can_claim ? `${task.id}:${task.revision}` : null;
  useEffect(() => {
    if (view.kind !== 'item' || !claimKey || claimedKey.current === claimKey) return;
    claimedKey.current = claimKey;
    void runClaim(view, claimKey);
  }, [view, claimKey, runClaim]);

  /** A claim records no decision, so the person may try it again. */
  const retryClaim = useCallback(() => {
    if (view.kind !== 'item' || !claimKey) return;
    setClaimState({ key: claimKey, status: 'pending' });
    void runClaim(view, claimKey);
  }, [view, claimKey, runClaim]);

  const claim = useMemo<ClaimState | null>(
    () =>
      task && held
        ? { key: `${task.id}:${task.revision}`, status: 'ready', revision: task.revision }
        : claimKey
          ? claimState?.key === claimKey
            ? claimState
            : { key: claimKey, status: 'pending' }
          : null,
    [task, held, claimKey, claimState],
  );

  const decide = useCallback(
    async (verdict: Verdict, evidenceId: number, note: string) => {
      if (writing.current || view.kind !== 'item' || claim?.status !== 'ready') return;
      const loaded: Loaded = { work: view.work, read: view.read };
      const revision = claim.revision;
      const sent = note.trim() === '' ? '' : note;
      writing.current = true;
      setSubmit({ status: 'busy', verdict });
      setUncertain(false);
      const body: LiveDecisionBody = { expected_revision: revision, verdict, evidence_id: evidenceId, note: sent };
      try {
        const result = await call(liveApi.POST('/api/v1/tasks/{task_id}/decision', { params: { path: { task_id: loaded.read.task.id }, ...csrfHeader }, body }));
        setSubmit({ status: 'idle' });
        setView({ kind: 'done', result, label: loaded.read.label, note: sent, work: loaded.work, reloaded: null, history: null, refreshFailed: false });
        void loadQueue();
        const [work, history] = await Promise.allSettled([
          fetchWork(),
          call(liveApi.GET('/api/v1/work/{work_id}/history', { params: { path: { work_id: workId! }, query: { kind: 'decision' } } })),
        ]);
        setView((v) =>
          v.kind === 'done'
            ? {
                ...v,
                reloaded: work.status === 'fulfilled' ? work.value : null,
                history: history.status === 'fulfilled' ? decisionOf(history.value.items, loaded.read.task.id) : null,
                refreshFailed: work.status === 'rejected' || history.status === 'rejected',
              }
            : v,
        );
      } catch (error) {
        // The buttons stay disabled until the follow-up view is on screen.
        const apiError = asApiError(error);
        if (await handleWriteError(apiError, loaded, sent)) {
          setSubmit({ status: 'idle' });
          return;
        }
        if (apiError.kind === 'invalid' || apiError.kind === 'bad_request') {
          setSubmit({ status: 'invalid', message: apiError.message, fields: apiError.fields });
          return;
        }
        // Uncertain effect: reload once, never resend.
        setUncertain(true);
        await reconcile(loaded, revision, sent);
        setSubmit({ status: 'idle' });
      } finally {
        writing.current = false;
      }
    },
    [view, claim, workId, handleWriteError, fetchWork, loadQueue, reconcile],
  );

  /** "Review version n": show the current version and claim it again, even at an unchanged revision. */
  const reviewCurrent = useCallback(() => {
    if (view.kind !== 'stale') return;
    claimedKey.current = null;
    setClaimState(null);
    setSubmit({ status: 'idle' });
    setUncertain(false);
    setView({ kind: 'item', work: view.work, read: view.read });
  }, [view]);

  /** Read the work and task again without the loading view (after a comment that moved or could not be confirmed). */
  const refresh = useCallback(async () => {
    const found = await reload();
    if (found instanceof ApiError || !found.read) return;
    const next = { work: found.work, read: found.read };
    setView((v) => (v.kind === 'forbidden' ? { kind: 'forbidden', ...next } : v.kind === 'item' ? { kind: 'item', ...next } : v));
  }, [reload]);

  /** A comment on a task the person cannot decide. True once sent. One at a time; never resent on an uncertain failure. */
  const comment = useCallback(
    async (body: string): Promise<boolean> => {
      if (commenting.current || (view.kind !== 'item' && view.kind !== 'forbidden')) return false;
      commenting.current = true;
      setCommentState({ status: 'busy' });
      try {
        await call(
          liveApi.POST('/api/v1/tasks/{task_id}/comments', { params: { path: { task_id: view.read.task.id }, ...csrfHeader }, body: { revision: view.read.task.revision, body } }),
        );
        setCommentState({ status: 'sent' });
        return true;
      } catch (error) {
        const apiError = asApiError(error);
        if (apiError.kind === 'unauthenticated' || apiError.kind === 'not_found') setView({ kind: 'error', error: apiError });
        else if (apiError.kind === 'forbidden') setCommentState({ status: 'closed', message: apiError.message });
        else if (apiError.kind === 'invalid' || apiError.kind === 'bad_request') {
          setCommentState({ status: 'error', message: [apiError.message, ...apiError.fields.map((f) => f.message)].join(' ') });
        } else if (apiError.kind === 'stale') {
          setCommentState({ status: 'error', message: apiError.message });
          await refresh();
        } else {
          setCommentState({ status: 'uncertain' });
          await refresh();
        }
        return false;
      } finally {
        commenting.current = false;
      }
    },
    [view, refresh],
  );

  return { view, claim, submit, uncertain, queue, commentState, comment, retry: load, retryClaim, decide, recheck, reviewCurrent };
}
