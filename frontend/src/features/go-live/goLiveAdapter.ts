// F-114: go-live acceptance (SCR-45) on the live work item. Registered on the go-live-signoff panel: its read fetches the sign-off, the
// client's replies and, only when a reply was declined, the decline options itself (the work read also lists the replies and milestone
// panels, which have no adapter, so nothing draws twice). A 403 or 404 on the sign-off read means the person is not the appointed PM:
// the replies still draw. Writes are described in goLiveModel.ts and drawn by GoLiveActions.
import { call, liveApi } from '@/api/client';
import { ApiError, networkError } from '@/api/errors';
import { registerLineAdapter, type LineAdapter } from '@/features/workspace/adapter';

import { GoLiveActions } from './GoLiveActions';
import { goLiveCommands, goLiveSections, type Access, type Readback } from './goLiveModel';

const settled = async <T,>(read: Promise<T>): Promise<{ value: T | null; error: ApiError | null }> => {
  try {
    return { value: await read, error: null };
  } catch (error) {
    return { value: null, error: error instanceof ApiError ? error : networkError() };
  }
};

async function read(_ref: { key: string; url: string }, ctx?: { workId: number }): Promise<Readback> {
  if (!ctx) throw new Error('The go-live page needs its work item.');
  const path = { work_id: ctx.workId };
  const [signoff, replies] = await Promise.all([
    settled(call(liveApi.GET('/api/v1/work/{work_id}/go-live-signoff', { params: { path } }))),
    settled(call(liveApi.GET('/api/v1/work/{work_id}/go-live-replies', { params: { path } }))),
  ]);
  // both failed: the page shows its own "could not load" with Try again
  if (signoff.error && replies.error) throw replies.error;
  const access: Access = signoff.error === null ? 'ok' : signoff.error.kind === 'forbidden' || signoff.error.kind === 'not_found' ? 'not_pm' : 'failed';
  const declined = replies.value?.replies.some((x) => x.outcome === 'declined') ?? false;
  const decline = declined ? (await settled(call(liveApi.GET('/api/v1/work/{work_id}/go-live-replies/decline', { params: { path } })))).value : null;
  return { signoff: signoff.value, access, replies: replies.value, decline };
}

export const goLiveAdapter: LineAdapter<Readback> = {
  key: 'go-live-signoff',
  read,
  sections: goLiveSections,
  commands: goLiveCommands,
  Actions: GoLiveActions,
};

registerLineAdapter(goLiveAdapter as LineAdapter);
