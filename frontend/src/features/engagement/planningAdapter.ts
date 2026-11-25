// F-97: the planning panel (key 'planning-owner-requests', GET /work/{id}/planning-owner-requests) on the live work item, read only.
// The panel's own read is the department's request list; the packet and the source clarifications come from the project (ctx.caseId).
import { call, liveApi } from '@/api/client';
import { ApiError, networkError } from '@/api/errors';
import { readPanel, registerLineAdapter, type LineAdapter, type LineContext } from '@/features/workspace/adapter';

import { planningSections, type OwnerRequests, type PlanningReadback, type ReadFailed } from './planningModel';

/** A read that failed on its own keeps the rest of the page. */
async function alone<T>(read: Promise<T>): Promise<T | ReadFailed> {
  try {
    return await read;
  } catch (error) {
    return { error: error instanceof ApiError ? error : networkError() };
  }
}

async function read(ref: { key: string; url: string }, ctx?: LineContext): Promise<PlanningReadback> {
  if (!ctx) throw new Error('The planning panel needs its work item.');
  const path = { case_id: ctx.caseId };
  const [requests, planning, sources] = await Promise.all([
    readPanel<OwnerRequests>(ref),
    alone(call(liveApi.GET('/api/v1/projects/{case_id}/planning', { params: { path } }))),
    alone(call(liveApi.GET('/api/v1/projects/{case_id}/planning/source-clarifications', { params: { path } }))),
  ]);
  return { requests, planning, sources };
}

export const planningAdapter: LineAdapter<PlanningReadback> = {
  key: 'planning-owner-requests',
  read,
  sections: (readback) => planningSections(readback),
  commands: () => [],
};

registerLineAdapter(planningAdapter as LineAdapter);
