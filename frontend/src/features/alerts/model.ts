// SCR-15 alerts: contract values to the words on the boards, the list view in the URL, and the settings PUT body.
// Presentation only: a proposal field the API does not return is never defaulted, and nothing here decides access.
import { AGENT_NAMES, formatClock } from '@/features/decide/format';

import type { Alert, AlertAgent, AlertPrefs, AlertQuery, PrefsBody } from './types';

export const AGENTS: readonly AlertAgent[] = ['tola', 'chidi', 'zainab'];

const isAgent = (value: string | null | undefined): value is AlertAgent => AGENTS.includes(value as AlertAgent);

export function agentName(agent: string): string {
  return isAgent(agent) ? AGENT_NAMES[agent] : agent;
}

/** The mascot image for a known agent; none for any other key (the avatar is then a neutral circle). */
export function agentImage(agent: string): string | undefined {
  return isAgent(agent) ? `/agents/${agent}.png` : undefined;
}

const CHANNEL_ORDER = ['whatsapp', 'email', 'in_app'] as const;
const CHANNEL_WORDS: Record<(typeof CHANNEL_ORDER)[number], string> = { whatsapp: 'WhatsApp', email: 'email', in_app: 'in app' };

/** ["whatsapp","email"] → "WhatsApp and email", ["in_app","email"] → "Email and in app". */
export function deliveryWords(via: readonly string[]): string {
  const words = CHANNEL_ORDER.filter((c) => via.includes(c)).map((c) => CHANNEL_WORDS[c]).join(' and ');
  return words.charAt(0).toUpperCase() + words.slice(1);
}

const WAT_DAY = new Intl.DateTimeFormat('en-CA', { timeZone: 'Africa/Lagos', year: 'numeric', month: '2-digit', day: '2-digit' });
const DAY_MONTH = new Intl.DateTimeFormat('en-GB', { timeZone: 'Africa/Lagos', day: 'numeric', month: 'short' });
const DAY_MS = 86_400_000;

/** "10:42" on the same WAT day as now, "yesterday" on the day before, else "12 Nov". */
export function dayWords(value: string, now: number): string {
  const day = WAT_DAY.format(new Date(value));
  if (day === WAT_DAY.format(new Date(now))) return formatClock(value);
  if (day === WAT_DAY.format(new Date(now - DAY_MS))) return 'yesterday';
  return DAY_MONTH.format(new Date(value));
}

/** "<Agent> · <how> · <when>", or "<Agent> · In app only (<reason>)". */
export function metaLine(alert: Alert, now: number): string {
  const name = agentName(alert.agent);
  if (alert.in_app_reason) return `${name} · In app only (${alert.in_app_reason})`;
  const when = alert.digest_at ? `${formatClock(alert.digest_at)} daily digest` : dayWords(alert.delivered_at ?? alert.at, now);
  return [name, alert.delivered_via && deliveryWords(alert.delivered_via), when].filter(Boolean).join(' · ');
}

/** "4 ALERTS" / "1 ALERT" from the returned total; undefined when the API returns none. */
export function countLine(total: number | undefined): string | undefined {
  if (typeof total !== 'number') return undefined;
  return `${total} ${total === 1 ? 'ALERT' : 'ALERTS'}`;
}

/** The list view held in the URL: /notifications?q=<text>&agent=<key>&unread=1. */
export type View = { q?: string; agent?: AlertAgent; unread?: true };

export function parseView(params: URLSearchParams): View {
  const view: View = {};
  const q = params.get('q')?.trim();
  if (q) view.q = q;
  const agent = params.get('agent');
  if (isAgent(agent)) view.agent = agent;
  if (params.get('unread') === '1') view.unread = true;
  return view;
}

export function viewSearch(view: View): string {
  const params = new URLSearchParams();
  if (view.q) params.set('q', view.q);
  if (view.agent) params.set('agent', view.agent);
  if (view.unread) params.set('unread', '1');
  const text = params.toString();
  return text ? `?${text}` : '';
}

export const isNarrowed = (view: View) => Boolean(view.q || view.agent || view.unread);

/** Facets set in the Filter panel (agent, unread); search is not counted. */
export const filterCount = (view: View) => (view.agent ? 1 : 0) + (view.unread ? 1 : 0);

/** Only the v7 parameters; limit is never sent, so the server default applies. */
export function buildAlertQuery(view: View, cursor?: string): AlertQuery {
  const query: AlertQuery = {};
  if (view.q) query.q = view.q;
  if (view.agent) query.agent = view.agent;
  if (view.unread) query.unread = true;
  if (cursor) query.cursor = cursor;
  return query;
}

export type Switches = { key: string; whatsapp: boolean; email: boolean };
/** The person's edits: switches per event, and the chosen digest time and quiet hours ('' = not set). */
export type Draft = { events: Switches[]; digest: string; quiet: string };

export function draftFrom(prefs: AlertPrefs): Draft {
  return {
    events: prefs.events.map(({ key, whatsapp, email }) => ({ key, whatsapp, email })),
    digest: prefs.digest_at?.value ?? '',
    quiet: prefs.quiet_hours?.value ?? '',
  };
}

const hasOptions = (field: { options: unknown[] } | undefined) => Boolean(field && field.options.length > 0);

/** Whether the desktop card shows the digest select and the quiet-hours select. */
export function selectsShown(prefs: AlertPrefs): { digest: boolean; quiet: boolean } {
  return { digest: hasOptions(prefs.digest_at), quiet: hasOptions(prefs.quiet_hours) };
}

/**
 * E-ALERT-PREFS body: channel and frequency exactly as read, the read revision, every event's switches in
 * returned order, and the digest and quiet hours only where the select is shown and set (never on the phone).
 */
export function buildPrefsBody(prefs: AlertPrefs, draft: Draft, phone: boolean): PrefsBody {
  const body = { channel: prefs.channel, frequency: prefs.frequency } as PrefsBody;
  if (prefs.revision !== undefined) body.expected_revision = prefs.revision;
  body.events = draft.events.map(({ key, whatsapp, email }) => ({ key, whatsapp, email }));
  const shown = selectsShown(prefs);
  if (!phone && shown.digest && draft.digest) body.digest_at = draft.digest;
  if (!phone && shown.quiet && draft.quiet) body.quiet_hours = draft.quiet;
  return body;
}

/** "20:00 to 07:00, and weekends": the label of the option whose value is the current one. */
export function quietLabel(prefs: AlertPrefs): string | undefined {
  const value = prefs.quiet_hours?.value;
  return value === undefined ? undefined : prefs.quiet_hours?.options.find((o) => o.value === value)?.label;
}
