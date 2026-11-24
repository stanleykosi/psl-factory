// SCR-15 alerts: contract values to the words on the boards, the typed link of an alert, and the settings body.
// Presentation only: a field the API returns as null is never defaulted, and nothing here decides access.
import { AGENTS as AGENT_INFO, agentKey, formatClock, formatDayMonth } from '@/components';

import type { Alert, AlertPrefs, DailySummary, Delivery, PrefsBody } from './types';

/** The agent's display name; a persona key we do not know is shown as it came. */
export function agentName(agent: string): string {
  const key = agentKey(agent);
  return key ? AGENT_INFO[key].name : agent;
}

const WAT_DAY = new Intl.DateTimeFormat('en-CA', { timeZone: 'Africa/Lagos', year: 'numeric', month: '2-digit', day: '2-digit' });
const DAY_MS = 86_400_000;

/** "10:42 WAT" on the same WAT day as now, "yesterday" on the day before, else "12 Nov 2026". */
export function dayWords(value: string, now: number): string {
  const day = WAT_DAY.format(new Date(value));
  if (day === WAT_DAY.format(new Date(now))) return formatClock(value);
  if (day === WAT_DAY.format(new Date(now - DAY_MS))) return 'yesterday';
  return formatDayMonth(value);
}

/** The secondary line: subject and detail as returned, "Ojo Foods · INV-0398"; nothing when both are empty. */
export const subjectLine = (alert: Alert) => [alert.subject, alert.detail].filter((part) => part.trim()).join(' · ');

/** "<Agent> · <time>": each part only when the alert has it (older alerts have neither). */
export function metaLine(alert: Alert, now: number): string {
  return [alert.agent && agentName(alert.agent), alert.at && dayWords(alert.at, now)].filter(Boolean).join(' · ');
}

const SEGMENT = /^[^/.?#\s\\]+$/;
const LINKS: readonly (readonly [RegExp, string])[] = [
  [/^\/api\/v1\/work\/([^/]*)$/, '/work/'],
  [/^\/api\/v1\/projects\/([^/]*)$/, '/projects/'],
  [/^\/api\/v1\/assistant\/conversations\/([^/]*)$/, '/assistant/'],
];

function decoded(segment: string): string | undefined {
  try {
    const value = decodeURIComponent(segment);
    return SEGMENT.test(value) ? value : undefined;
  } catch {
    return undefined;
  }
}

/**
 * The page an alert opens: a same-origin path from its typed `api_url` (work, project, assistant conversation), else
 * from a `django_url` of the form /work/<id>/. Anything else (null, absolute, protocol-relative, javascript:, several
 * segments, dots) gives no link; the retired Django page is never linked.
 */
export function alertHref(alert: Pick<Alert, 'api_url' | 'django_url'>): string | undefined {
  for (const [pattern, base] of LINKS) {
    const id = alert.api_url ? pattern.exec(alert.api_url)?.[1] : undefined;
    const value = id === undefined ? undefined : decoded(id);
    if (value) return `${base}${encodeURIComponent(value)}`;
  }
  const id = /^\/work\/([^/]*)\/$/.exec(alert.django_url ?? '')?.[1];
  const value = id === undefined ? undefined : decoded(id);
  return value ? `/work/${encodeURIComponent(value)}` : undefined;
}

/** Only `group: "action"` waits on the person; "update" is for information. */
export const needsYou = (alert: Pick<Alert, 'group'>) => alert.group === 'action';

/** The bell badge: the unread count when it is a number above zero, "99+" above 99; otherwise none (unknown is not zero). */
export function badgeText(unread: number | undefined): string | undefined {
  if (typeof unread !== 'number' || unread <= 0) return undefined;
  return unread > 99 ? '99+' : String(unread);
}

/** The bell's accessible name: "Alerts", "Alerts, 3 unread", "Alerts, 3 unread, 2 need you". */
export function bellName(unread: number | undefined, need: number): string {
  const parts = ['Alerts'];
  if (typeof unread === 'number' && unread > 0) parts.push(`${unread} unread`);
  if (need > 0) parts.push(`${need} need you`);
  return parts.join(', ');
}

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

/** "Today, 23 Nov: 3 need you, 2 new updates, 1 older unread." Each part is left out only when its field is missing. */
export function summaryLine(summary: Partial<DailySummary> | undefined): string | undefined {
  if (!summary) return undefined;
  const date = /^\d{4}-(\d{2})-(\d{2})$/.exec(summary.date ?? '');
  const month = date ? MONTHS[parseInt(date[1], 10) - 1] : undefined;
  const counts = [
    typeof summary.actions_open === 'number' && `${summary.actions_open} need you`,
    typeof summary.unread_updates_today === 'number' && `${summary.unread_updates_today} new ${summary.unread_updates_today === 1 ? 'update' : 'updates'}`,
    typeof summary.unread_without_timestamp === 'number' && `${summary.unread_without_timestamp} older unread`,
  ].filter(Boolean);
  if (counts.length === 0) return undefined;
  return `Today${date && month ? `, ${parseInt(date[2], 10)} ${month}` : ''}: ${counts.join(', ')}.`;
}

/** The loaded-alerts line: "12 loaded, 7 unread". The API gives no total of alerts, so none is claimed. */
export const loadedLine = (loaded: number, unread: number | undefined) =>
  typeof unread === 'number' ? `${loaded} loaded, ${unread} unread` : `${loaded} loaded`;

// The receipt's state in plain words (D-182, F-61 Q6). "Delivered" is shown only for the server's receipt state `delivered`;
// `uncertain` is "Not confirmed" and never worded as delivered.
export const DELIVERY_STATE_WORDS: Record<Delivery['state'], string> = { queued: 'Queued', uncertain: 'Not confirmed', delivered: 'Delivered', held: 'Held' };
export const deliveryWord = (state: Delivery['state']) => DELIVERY_STATE_WORDS[state];

export const CHANNEL_WORDS: Record<Delivery['channel'], string> = { email: 'Email', whatsapp: 'WhatsApp' };

/** The receipt's time: when it was delivered, else when it was queued. */
export const deliveryTime = (delivery: Delivery) => delivery.delivered_at ?? delivery.created_at;

/** The two switches the person edits; the rest of the read is held beside them. */
export type Draft = { email: boolean; whatsapp: boolean };

export const draftFrom = (prefs: AlertPrefs): Draft => ({ email: prefs.email_requested, whatsapp: prefs.whatsapp_requested });

/** Whether the draft differs from what was read: Save stays off until it does. */
export const prefsChanged = (prefs: AlertPrefs, draft: Draft) => draft.email !== prefs.email_requested || draft.whatsapp !== prefs.whatsapp_requested;

/** The save body: the revision of the last read and both switches, nothing else. */
export const buildPrefsBody = (prefs: AlertPrefs, draft: Draft): PrefsBody => ({
  revision: prefs.revision,
  email_requested: draft.email,
  whatsapp_requested: draft.whatsapp,
});
