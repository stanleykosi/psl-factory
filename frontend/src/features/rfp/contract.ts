// The v7 shapes this feature reads and writes, taken from the generated client (src/api/schema.d.ts): rfp and
// rfp_outcome on E-WORK-ITEM, E-RFP-OUTCOME and E-RFP-FOLLOWUP. No field is added here.
import type { paths } from '@/api/schema';
import type { WorkItem } from '@/api/types';

export type Rfp = NonNullable<WorkItem['rfp']>;
export type RfpTab = NonNullable<Rfp['tabs']>[number];
export type RfpOutcome = NonNullable<WorkItem['rfp_outcome']>;
export type OutcomeResult = RfpOutcome['results'][number];
export type RecordedOutcome = NonNullable<RfpOutcome['recorded']>;
export type Followup = NonNullable<RfpOutcome['followup']>;

type Post<P extends keyof paths> = paths[P] extends { post: { requestBody?: { content: { 'application/json': infer B } } } } ? B : never;
type Reply<P extends keyof paths> = paths[P] extends { post: { responses: { 200: { content: { 'application/json': infer R } } } } } ? R : never;

export type OutcomeBody = Post<'/api/v1/work/{work_id}/rfp-outcome'>;
export type OutcomeReply = Reply<'/api/v1/work/{work_id}/rfp-outcome'>;
export type FollowupBody = Post<'/api/v1/work/{work_id}/rfp-outcome/followup'>;
export type FollowupReply = Reply<'/api/v1/work/{work_id}/rfp-outcome/followup'>;
