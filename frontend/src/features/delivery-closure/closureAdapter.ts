// F-118: the closure line (delivery-closure/v1, SCR-49). The work read lists one panel, `closure-checklist`, whose url carries the
// project and the dossier; this adapter reads the checklist, the work item (who may decide), the decision history (a returned
// closure) and, while Finance has not confirmed, the Finance confirmation read. A 403 or 404 on the Finance read means the person
// cannot confirm: that block is simply absent, with no message. Writes are described in closureModel.ts and drawn by ClosureActions.
import { call, liveApi } from '@/api/client';
import { ApiError, networkError } from '@/api/errors';
import { registerLineAdapter, type LineAdapter } from '@/features/workspace/adapter';

import { ClosureActions } from './ClosureActions';
import { closureCommands, closureSections, type Readback } from './closureModel';

const settled = async <T,>(read: Promise<T>): Promise<{ value: T | null; error: ApiError | null }> => {
  try {
    return { value: await read, error: null };
  } catch (error) {
    return { value: null, error: error instanceof ApiError ? error : networkError() };
  }
};
const noView = (error: ApiError | null) => error !== null && (error.kind === 'forbidden' || error.kind === 'not_found');

const PANEL = /^\/api\/v1\/projects\/([0-9a-fA-F-]{36})\/delivery\/(\d+)\/closure-checklist$/;

async function read(ref: { key: string; url: string }, ctx?: { workId: number }): Promise<Readback> {
  const found = PANEL.exec(ref.url);
  if (!ctx || !found) throw new Error('The closure page needs its work item and dossier.');
  const caseId = found[1];
  const dossierId = Number(found[2]);
  const [checklist, work] = await Promise.all([
    call(liveApi.GET('/api/v1/projects/{case_id}/delivery/{dossier_id}/closure-checklist', { params: { path: { case_id: caseId, dossier_id: dossierId } } })),
    settled(call(liveApi.GET('/api/v1/work/{work_id}', { params: { path: { work_id: ctx.workId } } }))),
  ]);
  const confirmed = checklist.checks.find((c) => c.key === 'finance')?.status;
  const closed = checklist.recorded_closure_id !== null;
  const [history, finance] = await Promise.all([
    settled(call(liveApi.GET('/api/v1/work/{work_id}/history', { params: { path: { work_id: ctx.workId }, query: { kind: 'decision' } } }))),
    // asked only while Finance has not confirmed; a person with no Finance authority gets a 403 or 404 and sees nothing of it
    closed || confirmed === 'current' || confirmed === 'recorded' ? Promise.resolve({ value: null, error: null }) : settled(call(liveApi.GET('/api/v1/projects/{case_id}/delivery/{dossier_id}/finance-confirmation', { params: { path: { case_id: caseId, dossier_id: dossierId } } }))),
  ]);
  const failed: Readback['failed'] = [];
  if (work.error) failed.push('work');
  if (history.error) failed.push('history');
  if (finance.error && !noView(finance.error)) failed.push('finance');
  return {
    caseId,
    dossierId,
    checklist,
    work: work.value ? { revision: work.value.revision, case_revision: work.value.case_revision, state: work.value.state, tasks: work.value.tasks } : null,
    history: history.value?.items ?? [],
    finance: finance.value,
    // no read lists the Finance proofs, and none serves the closure document version or decision proof (D-26, LD-2): held until one does
    financeEvidence: [],
    decision: null,
    failed,
  };
}

export const closureAdapter: LineAdapter<Readback> = {
  key: 'closure-checklist',
  read,
  sections: closureSections,
  commands: closureCommands,
  Actions: ClosureActions,
};

registerLineAdapter(closureAdapter as LineAdapter);
