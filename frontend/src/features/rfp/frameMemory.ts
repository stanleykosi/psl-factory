// A small memory of the last RFP frame drawn, so the next item of the same RFP (each tab is its own work item) keeps
// the frame on screen while it loads. It is only used for an id the remembered RFP lists in its own tabs; the item's
// own read then replaces it, and a failed or no-access read draws the normal failure state instead (INV-ACCESS).
import type { WorkItem } from '@/api/types';

import type { Rfp, RfpTab } from './contract';

type Kept = { rfp: Rfp; item: Pick<WorkItem, 'line' | 'rfp_outcome'>; fallback: string };
let last: Kept | undefined;

export function rememberRfpFrame(kept: Kept) {
  last = kept;
}

/** The remembered frame for work item `id` when it is one of that RFP's Requirements or Submission tabs. */
export function rememberedRfpFrame(id: string): (Kept & { current: RfpTab['key'] }) | undefined {
  const tab = last?.rfp.tabs?.find((t) => t.work_id === id && (t.key === 'requirements' || t.key === 'submission'));
  return last && tab ? { ...last, current: tab.key } : undefined;
}
