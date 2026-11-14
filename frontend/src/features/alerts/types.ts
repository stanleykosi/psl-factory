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
