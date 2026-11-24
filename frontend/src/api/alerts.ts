// The four alert operations of the live contract (API 1.24.0): the inbox, mark-read, and the person's alert preferences.
// Typed calls only; no business rules. Features call these and get data or an ApiError.
import type { AlertPrefs, PrefsBody, SavedPrefs } from '@/features/alerts/types';

import { call, csrfHeader, liveApi } from './client';

/** GET /notifications?page=<n>: 25 alerts to a page, the server's unread total and the in-app daily summary. */
export const readInbox = (page: number) => call(liveApi.GET('/api/v1/notifications', { params: { query: { page } } }));

/** The first page, as the bell reads it (the server's default page). */
export const readInboxFirstPage = () => call(liveApi.GET('/api/v1/notifications'));

/** POST /notifications/{id}/read with `{}`; the CSRF header is added by the client. */
export const markAlertRead = (id: string) => call(liveApi.POST('/api/v1/notifications/{notification_id}/read', { params: { ...csrfHeader, path: { notification_id: id } }, body: {} }));

/** GET the person's own alert preferences. */
export const readAlertPreferences = () => call(liveApi.GET('/api/v1/me/alert-preferences'));

/** POST the two switches with the revision of the last read. The 200 may omit the receipts. */
export const saveAlertPreferences = (body: PrefsBody): Promise<SavedPrefs & Partial<AlertPrefs>> =>
  call(liveApi.POST('/api/v1/me/alert-preferences', { params: csrfHeader, body }));
