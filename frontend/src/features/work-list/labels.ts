// Words for the rows of the live work list. Presentation only.
import { STATE_TAGS, type FactoryState } from '@/components';

import type { LineKey, WorkLine, WorkState } from './types';

/** The state tag per live state; a state added to the contract fails the typecheck here. */
export const ROW_TAGS: Record<WorkState, FactoryState> = {
  ready: 'ready',
  waiting: 'waiting',
  action_needed: 'action_needed',
  owner_needed: 'owner_needed',
  setup_needed: 'setup_needed',
  verified: 'verified',
  cancelled: 'cancelled',
  awaiting_reconciliation: 'awaiting_reconciliation',
  followup_needed: 'followup_needed',
  processing: 'processing',
  effect_uncertain: 'effect_uncertain',
};

export const stateTag = (state: WorkState) => STATE_TAGS[ROW_TAGS[state]];

/** The line's title from the latest response's `lines[]`; a key the response does not list shows as received. */
export function lineTitle(lines: WorkLine[], key: string): string {
  return lines.find((line) => line.key === key)?.title ?? key;
}

export const asLineKey = (key: string) => key as LineKey;

export const ownerText = (owner: string | null) => owner ?? 'Unassigned';

/** The one place a person opens a work item from a list: the integer id, never the server's own urls. */
export const workHref = (id: number) => `/work/${id}`;
