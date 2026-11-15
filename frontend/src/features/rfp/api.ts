// The only module that calls the RFP outcome endpoints (D-RFP-OUTCOME r2, proposed; contract mock only). Both go
// through the shared client (`api`, `call`), so CSRF on writes and ApiError come from there. Nothing here retries.
import { api, call } from '@/api/client';

import type { FollowupBody, OutcomeBody } from './contract';

export function recordOutcome(workId: string, body: OutcomeBody) {
  return call(api.POST('/api/v1/work/{work_id}/rfp-outcome', { params: { path: { work_id: workId } }, body }));
}

/** E-RFP-FOLLOWUP: called only from a person's press on Send (INV-AGENT). */
export function sendFollowup(workId: string, body: FollowupBody) {
  return call(api.POST('/api/v1/work/{work_id}/rfp-outcome/followup', { params: { path: { work_id: workId } }, body }));
}
