'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

import { call, liveApi } from '@/api/client';
import { ApiError, networkError, UNEXPECTED_MESSAGE } from '@/api/errors';

import { isMoney, type Money, type MoneyItem } from './moneyModel';

export type MoneyState = { status: 'loading' } | { status: 'error'; error: ApiError } | { status: 'ready'; money: Money };
/** `idle`: no figure chosen. `missing`: the backend has no such figure (404), which is not an error. */
export type FigureState =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'missing' }
  | { status: 'error'; error: ApiError }
  | { status: 'ready'; item: MoneyItem };

const unexpected = () => new ApiError(200, 'server', 'unexpected_response', UNEXPECTED_MESSAGE);
export const asApiError = (error: unknown) => (error instanceof ApiError ? error : networkError());

/** One GET /projects/{case_id}/money read; a body that fails the guard is an unexpected response. */
export async function readMoney(caseId: string, figure?: string): Promise<Money> {
  const data = await call(liveApi.GET('/api/v1/projects/{case_id}/money', { params: { path: { case_id: caseId }, query: figure === undefined ? {} : { figure } } }));
  if (!isMoney(data)) throw unexpected();
  return data;
}

/**
 * One money read per opened tab, and one `?figure=<key>` read per chosen figure. Each has its own Try again; a late answer
 * for an earlier case or an earlier try is ignored. No polling, no automatic retry.
 */
export function useMoney(caseId: string, figureKey?: string) {
  const [money, setMoney] = useState<MoneyState>({ status: 'loading' });
  const [figure, setFigure] = useState<FigureState>({ status: 'idle' });
  const moneySeq = useRef(0);
  const figureSeq = useRef(0);

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

  const loadFigure = useCallback(async () => {
    const mine = ++figureSeq.current;
    if (figureKey === undefined) {
      setFigure({ status: 'idle' });
      return;
    }
    setFigure({ status: 'loading' });
    try {
      const data = await readMoney(caseId, figureKey);
      if (mine !== figureSeq.current) return;
      const item = data.items.find((i) => i.key === figureKey);
      setFigure(item ? { status: 'ready', item } : { status: 'missing' });
    } catch (error) {
      if (mine !== figureSeq.current) return;
      const e = asApiError(error);
      setFigure(e.kind === 'not_found' ? { status: 'missing' } : { status: 'error', error: e });
    }
  }, [caseId, figureKey]);

  useEffect(() => {
    // The effect only starts the request.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void loadMoney();
  }, [loadMoney]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void loadFigure();
  }, [loadFigure]);

  return { money, figure, retryMoney: loadMoney, retryFigure: loadFigure };
}
