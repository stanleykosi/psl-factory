'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

import { call, liveApi } from '@/api/client';
import { ApiError, UNEXPECTED_MESSAGE } from '@/api/errors';

import { isCompletion, isCompletions, type Completion, type CompletionRow } from './milestonesModel';
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
        const data = await call(liveApi.GET('/api/v1/projects/{case_id}/milestones/{milestone_id}', { params: { path: { case_id: caseId, milestone_id: milestoneId } } }));
        next = isCompletion(data) ? { status: 'ready', completion: data } : { status: 'error' };
      } catch (error) {
        const kind = asApiError(error).kind;
        next = kind === 'forbidden' || kind === 'not_found' ? { status: 'refused' } : { status: 'error' };
      }
      if (caseRef.current !== caseId) return;
      setProofs((prev) => ({ ...prev, [slot]: next }));
    },
    [caseId],
  );

  useEffect(() => {
    // The effect only starts the requests; a new case drops the proofs of the old one.
    caseRef.current = caseId;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setProofs({});
    void loadMoney();
    void loadCompletions();
  }, [caseId, loadMoney, loadCompletions]);

  return { money, completions, more, proofs, retryMoney: loadMoney, retryCompletions: loadCompletions, showMore, readProof };
}
