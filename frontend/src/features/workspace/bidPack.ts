// F-98: the bid pack, read once for the RFP lines that need it (the submission panel and F-96's Send for review). The pack read
// carries no revision tokens and no can_* flags: the pack and its exact document version come from GET /work/{id}/bid-pack, and the
// open review (who may decide it) from the work item's own tasks. The PM's send and the reviewer's verdict are described here so
// both panels send the same bodies.
import { call, liveApi } from '@/api/client';
import { ApiError } from '@/api/errors';
import type { LiveBidPack, LiveWorkItem } from '@/api/types';

import { makeCommand, type CommandDescriptor, type CommandTokens } from './adapter';

/** What was read: the pack (null when there is none to see), and whether the read worked at all. */
export type PackContext = {
  /** `none`: the server has no pack for this item, or not one this person may read (404, 403). `failed`: the read itself failed. */
  read: 'ok' | 'none' | 'failed';
  pack: LiveBidPack | null;
  tasks: LiveWorkItem['tasks'];
};

export const DOCUMENT_REVIEW = 'document_review';
export const NO_PACK = 'No bid pack has been prepared yet.';
export const PACK_UNREAD = 'We couldn’t read the bid pack. Reload to try again.';

/** The review tasks on this item that are open. */
export const openReviews = (tasks: LiveWorkItem['tasks']) => tasks.filter((t) => t.kind === DOCUMENT_REVIEW && t.status === 'open');

/** The review this person may decide (the server's `can_decide`), if any. */
export const myReview = (tasks: LiveWorkItem['tasks']) => openReviews(tasks).find((t) => t.can_decide) ?? null;

export async function readPackContext(workId: number): Promise<PackContext> {
  let tasks: LiveWorkItem['tasks'];
  try {
    tasks = (await call(liveApi.GET('/api/v1/work/{work_id}', { params: { path: { work_id: workId } } }))).tasks;
  } catch {
    return { read: 'failed', pack: null, tasks: [] };
  }
  try {
    return { read: 'ok', pack: await call(liveApi.GET('/api/v1/work/{work_id}/bid-pack', { params: { path: { work_id: workId } } })), tasks };
  } catch (error) {
    return { read: error instanceof ApiError && (error.kind === 'not_found' || error.kind === 'forbidden') ? 'none' : 'failed', pack: null, tasks };
  }
}

/** Why the PM's send can't be pressed now, or null when it can. The server still decides who may send. */
export function sendHeldReason(context: PackContext | null | undefined): string | null {
  if (!context || context.read === 'failed') return PACK_UNREAD;
  const { pack } = context;
  if (!pack) return NO_PACK;
  if (pack.decision) return 'This pack has already been decided.';
  if (pack.document_version_id === null) return 'The bid pack isn’t prepared for review yet.';
  if (openReviews(context.tasks).length > 0) return 'This pack is already with the reviewer.';
  return null;
}

/** POST /work/{id}/bid-pack/review-request: the exact pack and the exact document version. */
export function sendForReviewCommand(id: string, workId: number, context: PackContext | null | undefined, tokens: CommandTokens, held: string | null): CommandDescriptor {
  const reason = held ?? sendHeldReason(context) ?? (tokens.expected_revision == null || tokens.case_revision == null ? 'We don’t have this item’s current version yet. Reload and try again.' : undefined);
  const pack = context?.pack;
  return makeCommand({
    id,
    label: 'Send for review',
    url: `/api/v1/work/${workId}/bid-pack/review-request`,
    tokens,
    action: null,
    fixed: { pack_id: pack?.pack_id ?? null, version_id: pack?.document_version_id ?? null },
    ...(reason ? { disabledReason: reason } : {}),
    successStatuses: [200],
  });
}
