// Alert types read from the generated v7 contract (src/api/schema.d.ts).
import type { operations } from '@/api/schema';

type Json<T> = T extends { content: { 'application/json': infer B } } ? B : never;
export type AlertList = Json<operations['E-NOTIFICATIONS']['responses'][200]>;
export type Alert = AlertList['items'][number];
export type AlertQuery = NonNullable<operations['E-NOTIFICATIONS']['parameters']['query']>;
export type AlertAgent = NonNullable<AlertQuery['agent']>;
export type MarkReadResult = Json<operations['E-NOTIFICATION-READ']['responses'][200]>;
export type AlertPrefs = Json<operations['E-ALERT-PREFS-READ']['responses'][200]>;
export type AlertEvent = AlertPrefs['events'][number];
export type AlertOption = NonNullable<AlertPrefs['digest_at']>['options'][number];
export type SavedPrefs = Json<operations['E-ALERT-PREFS']['responses'][200]>;
export type PrefsBody = NonNullable<operations['E-ALERT-PREFS']['requestBody']>['content']['application/json'];

/**
 * PROPOSAL: not in v7. An E-NOTIFICATIONS item that may carry `needs_you`: true when the alert waits on this person
 * (a decision or an exception). It may also carry `case_id` (D-164): an alert about a project (a won RFP made it) then opens
 * that project instead of its work item. The backend adds both through the contract-change route; until then they are absent.
 */
export type AlertWithNeed = Alert & { needs_you?: boolean; case_id?: string };

