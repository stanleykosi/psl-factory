// Alert types read from the generated live contract (src/api/live-schema.d.ts, API 1.24.0).
import type { operations } from '@/api/live-schema';

type Json<T> = T extends { content: { 'application/json': infer B } } ? B : never;
export type AlertList = Json<operations['notifications_inbox']['responses'][200]>;
export type Alert = AlertList['items'][number];
export type DailySummary = AlertList['daily_summary'];
export type MarkReadResult = Json<operations['notifications_mark_read']['responses'][200]>;
export type AlertPrefs = Json<operations['notifications_preferences']['responses'][200]>;
export type Delivery = AlertPrefs['recent_deliveries'][number];
export type SavedPrefs = Json<operations['notifications_save_preferences']['responses'][200]>;
export type PrefsBody = NonNullable<operations['notifications_save_preferences']['requestBody']>['content']['application/json'];
