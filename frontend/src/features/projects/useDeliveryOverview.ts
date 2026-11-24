'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

import { call, liveApi } from '@/api/client';
import { ApiError, networkError, UNEXPECTED_MESSAGE } from '@/api/errors';

import { holdReasons, isChecklist, isOverview, reasonsNeeded, type DeliveryOverview, type HoldReason } from './deliveryModel';

export type OverviewState = { status: 'loading' } | { status: 'error'; error: ApiError } | { status: 'ready'; overview: DeliveryOverview; reasons: HoldReason[] };

/**
 * One GET /projects/{case_id}/delivery-overview read per opened project, re-read only by "Try again". When closure has not started and the
 * release line has work, two more reads (release-register, then closure-checklist) give the closure reasons; a failure there is silent.
 * A late answer for an earlier project is ignored. No polling.
 */
export function useDeliveryOverview(caseId: string) {
  const [state, setState] = useState<OverviewState>({ status: 'loading' });
  const seq = useRef(0);

  const readReasons = useCallback(
    async (overview: DeliveryOverview, mine: number) => {
      const releaseWork = overview.lines.find((l) => l.key === 'delivery-release/v1')?.work_id;
      if (typeof releaseWork !== 'number') return;
      try {
        const register = await call(liveApi.GET('/api/v1/work/{work_id}/release-register', { params: { path: { work_id: releaseWork } } }));
        if (mine !== seq.current || typeof register?.dossier_id !== 'number') return;
        const checklist = await call(liveApi.GET('/api/v1/projects/{case_id}/delivery/{dossier_id}/closure-checklist', { params: { path: { case_id: caseId, dossier_id: register.dossier_id } } }));
        if (mine !== seq.current || !isChecklist(checklist)) return;
        const reasons = holdReasons(checklist);
        setState((prev) => (prev.status === 'ready' ? { ...prev, reasons } : prev));
      } catch {
        // the reason is secondary: the rows above stay true without it
      }
    },
    [caseId],
  );

  const load = useCallback(async () => {
    const mine = ++seq.current;
    setState({ status: 'loading' });
    try {
      const data = await call(liveApi.GET('/api/v1/projects/{case_id}/delivery-overview', { params: { path: { case_id: caseId } } }));
      if (mine !== seq.current) return;
      if (!isOverview(data)) throw new ApiError(200, 'server', 'unexpected_response', UNEXPECTED_MESSAGE);
      setState({ status: 'ready', overview: data, reasons: [] });
      if (reasonsNeeded(data)) void readReasons(data, mine);
    } catch (error) {
      if (mine !== seq.current) return;
      setState({ status: 'error', error: error instanceof ApiError ? error : networkError() });
    }
  }, [caseId, readReasons]);

  useEffect(() => {
    // The effect only starts the request.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, [load]);

  return { state, retry: load };
}
