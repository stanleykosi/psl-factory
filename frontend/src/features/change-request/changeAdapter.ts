// F-112: the change request on the live work item (SCR-31, part 1). Registered on the `change` panel: its read fetches the change itself
// and, as an extra, the project's ordinary-changes list for the reference and module (a failure of that read leaves them out; nothing is
// guessed). Writes are described in changeModel.ts and drawn by ChangeActions.
import { call, liveApi } from '@/api/client';
import { registerLineAdapter, type LineAdapter } from '@/features/workspace/adapter';

import { ChangeActions } from './ChangeActions';
import { changeCommands, changeSections, type Readback } from './changeModel';

async function read(_ref: { key: string; url: string }, ctx?: { workId: number; caseId: string }): Promise<Readback> {
  if (!ctx) throw new Error('The change page needs its work item.');
  const [change, register] = await Promise.all([
    call(liveApi.GET('/api/v1/work/{work_id}/change', { params: { path: { work_id: ctx.workId } } })),
    call(liveApi.GET('/api/v1/projects/{case_id}/ordinary-changes', { params: { path: { case_id: ctx.caseId } } })).catch(() => null),
  ]);
  return { change, register };
}

export const changeAdapter: LineAdapter<Readback> = {
  key: 'change',
  read,
  sections: changeSections,
  commands: changeCommands,
  Actions: ChangeActions,
};

registerLineAdapter(changeAdapter as LineAdapter);
