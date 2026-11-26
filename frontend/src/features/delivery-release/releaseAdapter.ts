// F-113B: the release line's work item (SCR-44). Registered on the release-register panel: its read fetches the planning exit itself
// (the work read lists it as a panel with no adapter, so it draws nothing twice), then the client testing and, only for an item that
// needs an owner, the decision appointments. Writes are described in releaseModel.ts and drawn by ReleaseActions.
import { call, liveApi } from '@/api/client';
import { registerLineAdapter, type LineAdapter } from '@/features/workspace/adapter';

import { ReleaseActions } from './ReleaseActions';
import { releaseCommands, releaseSections, type Readback } from './releaseModel';

async function read(_ref: { key: string; url: string }, ctx?: { workId: number; caseId: string; state?: string }): Promise<Readback> {
  if (!ctx) throw new Error('The release page needs its work item.');
  const path = { work_id: ctx.workId };
  const [register, exit] = await Promise.all([
    call(liveApi.GET('/api/v1/work/{work_id}/release-register', { params: { path } })),
    call(liveApi.GET('/api/v1/work/{work_id}/planning-exit', { params: { path } })),
  ]);
  // these two are extra: when one fails the rest of the page still draws
  const [uat, appointments] = await Promise.all([
    call(liveApi.GET('/api/v1/projects/{case_id}/delivery/{dossier_id}/client-testing', { params: { path: { case_id: ctx.caseId, dossier_id: register.dossier_id } } })).catch(() => null),
    ctx.state === 'owner_needed' ? call(liveApi.GET('/api/v1/setup/{case_id}/decision-appointments', { params: { path: { case_id: ctx.caseId } } })).catch(() => null) : Promise.resolve(null),
  ]);
  return { register, exit, uat, appointments };
}

export const releaseAdapter: LineAdapter<Readback> = {
  key: 'release-register',
  read,
  sections: releaseSections,
  commands: releaseCommands,
  Actions: ReleaseActions,
};

registerLineAdapter(releaseAdapter as LineAdapter);
