'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

import { api, call } from '@/api/client';
import { ApiError, networkError, UNEXPECTED_MESSAGE } from '@/api/errors';

import { isReport, moneyViewOf, type MoneyView, type Report } from './moneyModel';

export type MoneyState = { status: 'loading' } | { status: 'error'; error: ApiError } | { status: 'ready'; view: MoneyView };
/** `none`: the money read named no report, so nothing is requested and no amount links anywhere. */
export type ReportState = { status: 'none' } | { status: 'loading' } | { status: 'error'; error: ApiError } | { status: 'ready'; report: Report };

const unexpected = () => new ApiError(200, 'server', 'unexpected_response', UNEXPECTED_MESSAGE);
const asApiError = (error: unknown) => (error instanceof ApiError ? error : networkError());

/** One E-PROJECT-TAB money read per opened tab, then one E-REPORT read when it names a report. Each has its own
 *  Try again; a late answer for an earlier case or an earlier try is ignored. No polling, no automatic retry. */
export function useMoney(caseId: string) {
  const [money, setMoney] = useState<MoneyState>({ status: 'loading' });
  const [report, setReport] = useState<ReportState>({ status: 'none' });
  const moneySeq = useRef(0);
  const reportSeq = useRef(0);

  const loadReport = useCallback(async (reportId: string) => {
    const mine = ++reportSeq.current;
    setReport({ status: 'loading' });
    try {
      const data = await call(api.GET('/api/v1/reports/{report_id}', { params: { path: { report_id: reportId } } }));
      if (mine !== reportSeq.current) return;
      if (!isReport(data)) throw unexpected();
      setReport({ status: 'ready', report: data });
    } catch (error) {
      if (mine !== reportSeq.current) return;
      setReport({ status: 'error', error: asApiError(error) });
    }
  }, []);

  const loadMoney = useCallback(async () => {
    const mine = ++moneySeq.current;
    // A report still on its way belongs to the earlier read.
    reportSeq.current++;
    setMoney({ status: 'loading' });
    setReport({ status: 'none' });
    try {
      const data = await call(api.GET('/api/v1/projects/{case_id}/{tab}', { params: { path: { case_id: caseId, tab: 'money' } } }));
      if (mine !== moneySeq.current) return;
      const view = moneyViewOf(data);
      if (!view) throw unexpected();
      setMoney({ status: 'ready', view });
      if (view.reportId) void loadReport(view.reportId);
    } catch (error) {
      if (mine !== moneySeq.current) return;
      setMoney({ status: 'error', error: asApiError(error) });
    }
  }, [caseId, loadReport]);

  useEffect(() => {
    // The effect only starts the request.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void loadMoney();
  }, [loadMoney]);

  const retryReport = useCallback(() => {
    if (money.status === 'ready' && money.view.reportId) void loadReport(money.view.reportId);
  }, [money, loadReport]);

  return { money, report, retryMoney: loadMoney, retryReport };
}
