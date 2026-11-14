// Display rules for Setup rows. A rule is Not set only when `set` is false; the value object is never read.
import type { RuleRow } from './contract-proposal';

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
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

/** "v2 · since 01 Oct" (year added outside the current Lagos year), "v2" without a date, null when not set. */
export function versionText(row: RuleRow, now = new Date()): string | null {
  if (!row.set) return null;
  if (!row.effective_from) return `v${row.revision}`;
  const from = lagosParts(new Date(row.effective_from));
  const year = from.year === lagosParts(now).year ? '' : ` ${from.year}`;
  return `v${row.revision} · since ${from.day} ${MONTHS[Number(from.month) - 1]}${year}`;
}

/** The value as text, or null for Not set. A set rule without display_value reads "Set". */
export function valueText(row: RuleRow): string | null {
  if (!row.set) return null;
  return row.display_value ?? 'Set';
}

const LINK_ROUTES: Record<string, string> = { 'costing-rule': '/setup/costing-rule' };
const AREA_ROUTES: Record<string, string> = { finance: '/setup/rules/finance', delivery: '/setup/rules/delivery' };

/** The screen a linked rule is edited on; an unknown slug has none. */
export const linkHref = (row: RuleRow) => (row.link && Object.hasOwn(LINK_ROUTES, row.link) ? LINK_ROUTES[row.link] : undefined);
export const areaHref = (row: RuleRow) => (row.area && Object.hasOwn(AREA_ROUTES, row.area) ? AREA_ROUTES[row.area] : undefined);

/** The backend's per-row right only: can_change, a role_set editor with options, and no other screen. */
export function isEditable(row: RuleRow): boolean {
  return row.can_change === true && row.editor?.kind === 'role_set' && (row.editor.options?.length ?? 0) > 0 && row.link === undefined;
}

/** "120 KB" below 1024 KB, else "1.5 MB". */
export function formatSize(bytes: number): string {
  if (bytes < 1024 * 1024) return `${Math.ceil(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
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
