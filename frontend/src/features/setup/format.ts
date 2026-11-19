// Display rules for Setup rows. A rule is Not set only when `set` is false; the value object is never read.
import { formatClock, formatDayMonth } from '@/components';

import type { RuleRow } from './contract-proposal';

const LAGOS = new Intl.DateTimeFormat('en-GB', { timeZone: 'Africa/Lagos', year: 'numeric', month: '2-digit', day: '2-digit' });

function lagosParts(value: Date) {
  const parts = Object.fromEntries(LAGOS.formatToParts(value).map((p) => [p.type, p.value]));
  return { year: parts.year, month: parts.month, day: parts.day };
}

/** Today in Africa/Lagos as YYYY-MM-DD (the Starts default the board draws). */
export function lagosToday(now = new Date()): string {
  const { year, month, day } = lagosParts(now);
  return `${year}-${month}-${day}`;
}

/** The file's bytes as base64 (the E-TEMPLATE-VERSION and evidence bodies carry no other encoding). */
export async function fileToBase64(file: File): Promise<string> {
  const bytes = new Uint8Array(await file.arrayBuffer());
  let text = '';
  for (let i = 0; i < bytes.length; i += 0x8000) text += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  return btoa(text);
}

/** "12 Nov", "01 Oct" in Africa/Lagos, as the Setup boards write it, with the year added outside the current Lagos year. */
export function boardDay(value: string, now = new Date()): string {
  const year = lagosParts(new Date(value)).year;
  return year === lagosParts(now).year ? formatDayMonth(value) : `${formatDayMonth(value)} ${year}`;
}

/** "12 Nov, 10:40": the Templates board's as-of stamp. */
export function boardStamp(value: string, now = new Date()): string {
  return `${boardDay(value, now)}, ${formatClock(value)}`;
}

/** "v2 · since 01 Oct" (the year added outside the current Lagos year), "v2" without a date, null when not set. */
export function versionText(row: RuleRow, now = new Date()): string | null {
  if (!row.set) return null;
  if (!row.effective_from) return `v${row.revision}`;
  return `v${row.revision} · since ${boardDay(row.effective_from, now)}`;
}

/** The value as text, or null for Not set. A set rule without display_value reads "Set". */
export function valueText(row: RuleRow): string | null {
  if (!row.set) return null;
  return row.display_value ?? 'Set';
}

const LINK_ROUTES: Record<string, string> = { 'costing-rule': '/setup/costing-rule' };
export const AREA_ROUTES: Record<string, string> = { finance: '/setup/rules/finance', delivery: '/setup/rules/delivery' };

/** The screen a linked rule is edited on; an unknown slug has none. */
export const linkHref = (row: RuleRow) => (row.link && Object.hasOwn(LINK_ROUTES, row.link) ? LINK_ROUTES[row.link] : undefined);
export const areaHref = (row: RuleRow) => (row.area && Object.hasOwn(AREA_ROUTES, row.area) ? AREA_ROUTES[row.area] : undefined);

/** The backend's per-row right only: can_change, a role_set editor with options, and no other screen. */
export function isEditable(row: RuleRow): boolean {
  return row.can_change === true && row.editor?.kind === 'role_set' && (row.editor.options?.length ?? 0) > 0 && row.link === undefined;
}

export type RuleField = 'roles' | 'starts' | 'reason' | 'evidence_id';
const FIELD_NAMES: Record<string, RuleField> = { value: 'roles', 'value.roles': 'roles', roles: 'roles', starts: 'starts', reason: 'reason', evidence_id: 'evidence_id' };

/** The panel fields a 422 message names, matched as whole words ("Check these fields: reason, starts."). */
export function fieldsFromMessage(message: string): Set<RuleField> {
  const fields = new Set<RuleField>();
  for (const word of message.split(/[^\w.]+/)) {
    const name = word.replace(/\.+$/, '');
    if (Object.hasOwn(FIELD_NAMES, name)) fields.add(FIELD_NAMES[name]);
  }
  return fields;
}

/** "Set management accounts rules"; a first word in capitals stays ("Set BU totals rules"). */
export function groupButtonLabel(groupLabel: string): string {
  const [first, ...rest] = groupLabel.split(' ');
  const word = first === first.toUpperCase() && /[A-Z]/.test(first) ? first : first.toLowerCase();
  return `Set ${[word, ...rest].join(' ')} rules`;
}

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

/** A contract date (YYYY-MM-DD, a calendar day: no time zone applies) as its parts, or null when malformed. */
function dayParts(value: string): { day: string; month: string; year: string } | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  const month = match ? MONTHS[Number(match[2]) - 1] : undefined;
  return match && month ? { day: match[3], month, year: match[1] } : null;
}

/** "18 Nov 2026"; a malformed value is shown as sent. */
export function boardDate(value: string): string {
  const p = dayParts(value);
  return p ? `${p.day} ${p.month} ${p.year}` : value;
}

/** "18–25 Nov 2026", "28 Nov – 03 Dec 2026", "28 Dec 2026 – 03 Jan 2027", as the delegation boards write them. */
export function dateRange(starts: string, ends: string): string {
  const a = dayParts(starts);
  const b = dayParts(ends);
  if (!a || !b) return `${boardDate(starts)} – ${boardDate(ends)}`;
  if (a.year !== b.year) return `${a.day} ${a.month} ${a.year} – ${b.day} ${b.month} ${b.year}`;
  if (a.month !== b.month) return `${a.day} ${a.month} – ${b.day} ${b.month} ${b.year}`;
  return `${a.day}–${b.day} ${b.month} ${b.year}`;
}
