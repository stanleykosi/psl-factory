// F-97: the engagement panel (key 'engagement', GET /work/{id}/engagement) on the live work item. Writes are described in model.ts
// and drawn by EngagementActions; sent by useWorkCommand.
import { call, liveApi } from '@/api/client';
import { readPanel, registerLineAdapter, type LineAdapter } from '@/features/workspace/adapter';

import { EngagementActions } from './EngagementActions';
import { engagementCommands, engagementSections, type Engagement, type EngagementIntake, type Readback } from './model';

async function read(ref: { key: string; url: string }, ctx?: { caseId: string }): Promise<Readback> {
  const engagement = await readPanel<Engagement>(ref);
  // the intake read is extra: when it fails the rest of the panel still draws
  const intake: EngagementIntake | null = ctx
    ? await call(liveApi.GET('/api/v1/projects/{case_id}/engagement-intake', { params: { path: { case_id: ctx.caseId } } })).catch(() => null)
    : null;
  return { engagement, intake };
}

export const engagementAdapter: LineAdapter<Readback> = {
  key: 'engagement',
  read,
  sections: (readback) => engagementSections(readback),
  commands: (readback, ctx) => engagementCommands(readback.engagement, ctx),
  Actions: EngagementActions,
};

registerLineAdapter(engagementAdapter as LineAdapter);
