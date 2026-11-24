'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

import { call, liveApi } from '@/api/client';
import { ApiError, UNEXPECTED_MESSAGE } from '@/api/errors';

import { isCompletion, isCompletionOptions, isCompletions, type Completion, type CompletionOptions, type CompletionRow } from './milestonesModel';
import type { Money } from './moneyModel';
import { asApiError, readMoney } from './useMoney';

export type MoneyRead = { status: 'loading' } | { status: 'error'; error: ApiError } | { status: 'ready'; money: Money };
export type CompletionsRead =
  | { status: 'loading' }
  | { status: 'error'; error: ApiError }
  | { status: 'ready'; rows: CompletionRow[]; page: number; hasMore: boolean; asOf: string };
/** One proof press: the recorded completion, or why it is not shown (`refused` is 403 or 404). */
export type ProofState = { status: 'loading' } | { status: 'refused' } | { status: 'error' } | { status: 'ready'; completion: Completion };
export type MoreState = 'idle' | 'loading' | 'error';

const unexpected = () => new ApiError(200, 'server', 'unexpected_response', UNEXPECTED_MESSAGE);

async function readCompletions(caseId: string, page: number) {
  const data = await call(liveApi.GET('/api/v1/projects/{case_id}/{tab}', { params: { path: { case_id: caseId, tab: 'milestones' }, query: page > 1 ? { page } : {} } }));
  if (!isCompletions(data)) throw unexpected();
  return data;
}

/** GET .../milestones/{id}: the recorded completion, or an ApiError. A body that fails the guard is not shown. */
export async function readCompletion(caseId: string, milestoneId: number): Promise<Completion> {
  const data = await call(liveApi.GET('/api/v1/projects/{case_id}/milestones/{milestone_id}', { params: { path: { case_id: caseId, milestone_id: milestoneId } } }));
  if (!isCompletion(data)) throw unexpected();
  return data;
}

/** GET .../milestones/completions: what may be done and the proofs on record; `name` asks about one milestone. */
export async function readOptions(caseId: string, query: { name?: string; page?: number } = {}): Promise<CompletionOptions> {
  const data = await call(liveApi.GET('/api/v1/projects/{case_id}/milestones/completions', { params: { path: { case_id: caseId }, query } }));
  if (!isCompletionOptions(data)) throw unexpected();
  return data;
}

/**
 * Two independent reads when the tab opens (the money body for the stage rows, the recorded completions) and, on a press,
 * one read of a completion. "Show more" asks for the next page of completions. A late answer for an earlier case or an
 * earlier try is ignored. No polling, no automatic retry.
 */
export function useMilestones(caseId: string) {
  const [money, setMoney] = useState<MoneyRead>({ status: 'loading' });
  const [completions, setCompletions] = useState<CompletionsRead>({ status: 'loading' });
  const [more, setMore] = useState<MoreState>('idle');
  const [proofs, setProofs] = useState<Record<string, ProofState>>({});
  // SCR-19 entry: the server's own answer on whether a completion may be recorded. A failed read leaves the tab as it was.
  const [entry, setEntry] = useState<Pick<CompletionOptions, 'can_complete' | 'hold'> | null>(null);
  const entrySeq = useRef(0);
  const moneySeq = useRef(0);
  const completionsSeq = useRef(0);
  const caseRef = useRef(caseId);

  const loadMoney = useCallback(async () => {
    const mine = ++moneySeq.current;
    setMoney({ status: 'loading' });
    try {
      const data = await readMoney(caseId);
      if (mine !== moneySeq.current) return;
      setMoney({ status: 'ready', money: data });
    } catch (error) {
      if (mine !== moneySeq.current) return;
      setMoney({ status: 'error', error: asApiError(error) });
    }
  }, [caseId]);

  const loadCompletions = useCallback(async () => {
    const mine = ++completionsSeq.current;
    setCompletions({ status: 'loading' });
    setMore('idle');
    try {
      const data = await readCompletions(caseId, 1);
      if (mine !== completionsSeq.current) return;
      const section = data.sections[0];
      setCompletions({ status: 'ready', rows: section.items, page: section.page, hasMore: section.has_more, asOf: data.as_of });
    } catch (error) {
      if (mine !== completionsSeq.current) return;
      setCompletions({ status: 'error', error: asApiError(error) });
    }
  }, [caseId]);

  const showMore = useCallback(async () => {
    if (completions.status !== 'ready' || !completions.hasMore) return;
    const mine = completionsSeq.current;
    setMore('loading');
    try {
      const data = await readCompletions(caseId, completions.page + 1);
      if (mine !== completionsSeq.current) return;
      const section = data.sections[0];
      setCompletions((prev) => (prev.status !== 'ready' ? prev : { ...prev, rows: [...prev.rows, ...section.items], page: section.page, hasMore: section.has_more }));
      setMore('idle');
    } catch (error) {
      if (mine !== completionsSeq.current) return;
      const e = asApiError(error);
      if (e.kind === 'unauthenticated' || e.kind === 'forbidden' || e.kind === 'not_found') setCompletions({ status: 'error', error: e });
      else setMore('error');
    }
  }, [caseId, completions]);

  /** One GET of the completion per press; `slot` names where the answer is drawn. */
  const readProof = useCallback(
    async (slot: string, milestoneId: number) => {
      setProofs((prev) => ({ ...prev, [slot]: { status: 'loading' } }));
      let next: ProofState;
      try {
        next = { status: 'ready', completion: await readCompletion(caseId, milestoneId) };
      } catch (error) {
        const kind = asApiError(error).kind;
        next = kind === 'forbidden' || kind === 'not_found' ? { status: 'refused' } : { status: 'error' };
      }
      if (caseRef.current !== caseId) return;
      setProofs((prev) => ({ ...prev, [slot]: next }));
    },
    [caseId],
  );

  const loadEntry = useCallback(async () => {
    const mine = ++entrySeq.current;
    setEntry(null);
    try {
      const data = await readOptions(caseId);
      if (mine === entrySeq.current) setEntry({ can_complete: data.can_complete, hold: data.hold });
    } catch {
      // no link and no message: the tab's own reads are unaffected
    }
  }, [caseId]);

  useEffect(() => {
    // The effect only starts the requests; a new case drops the proofs of the old one.
    caseRef.current = caseId;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setProofs({});
    void loadMoney();
    void loadCompletions();
    void loadEntry();
  }, [caseId, loadMoney, loadCompletions, loadEntry]);

  return { money, completions, more, proofs, entry, retryMoney: loadMoney, retryCompletions: loadCompletions, showMore, readProof };
}
