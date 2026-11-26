// F-117: the handover line (delivery-handover/v1, SCR-48). The work read lists three panels (support-receipt, support-replies,
// support-publication); this adapter registers on support-replies and reads all three itself, so nothing draws twice and the other two
// keys (no adapter) are left out. A 403 or 404 on one read means the person has no view of that part (the PM is not a Support recipient);
// the others still draw. Writes are described in handoverModel.ts and drawn by HandoverActions.
import { call, liveApi } from '@/api/client';
import { ApiError, networkError } from '@/api/errors';
import { registerLineAdapter, type LineAdapter } from '@/features/workspace/adapter';

import { HandoverActions } from './HandoverActions';
import { handoverCommands, handoverSections, type Readback } from './handoverModel';

const settled = async <T,>(read: Promise<T>): Promise<{ value: T | null; error: ApiError | null }> => {
  try {
    return { value: await read, error: null };
  } catch (error) {
    return { value: null, error: error instanceof ApiError ? error : networkError() };
  }
};
const noView = (error: ApiError | null) => error !== null && (error.kind === 'forbidden' || error.kind === 'not_found');

async function read(_ref: { key: string; url: string }, ctx?: { workId: number }): Promise<Readback> {
  if (!ctx) throw new Error('The handover page needs its work item.');
  const path = { work_id: ctx.workId };
  const [publication, replies, receipt] = await Promise.all([
    settled(call(liveApi.GET('/api/v1/work/{work_id}/support-publication', { params: { path } }))),
    settled(call(liveApi.GET('/api/v1/work/{work_id}/support-replies', { params: { path } }))),
    settled(call(liveApi.GET('/api/v1/work/{work_id}/support-receipt', { params: { path } }))),
  ]);
  const parts = { publication, replies, receipt } as const;
  const failed = (Object.keys(parts) as (keyof typeof parts)[]).filter((k) => parts[k].error !== null && !noView(parts[k].error));
  // nothing could be read: the page shows its own "could not load" with Try again
  if (failed.length === 3) throw publication.error ?? networkError();
  return { publication: publication.value, replies: replies.value, receipt: receipt.value, failed };
}

export const handoverAdapter: LineAdapter<Readback> = {
  key: 'support-replies',
  read,
  sections: handoverSections,
  commands: handoverCommands,
  Actions: HandoverActions,
};

registerLineAdapter(handoverAdapter as LineAdapter);
