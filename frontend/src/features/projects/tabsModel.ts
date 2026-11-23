// Project tabs (SCR-11 Registers, SCR-29 Actions, and the Documents list that opens SCR-08): view state, the E-PROJECT-TAB query, response
// checks and the display text of each value. Pure functions only. Every value is shown as the response sends it:
// nothing is totalled, added, sorted or inferred from another fact (INV-UNKNOWN, INV-FACTS).
import type { operations } from '@/api/schema';
import { formatDayMonth, UNKNOWN } from '@/components';

import { textOf, type ProjectTab } from './model';

type TabOperation = operations['E-PROJECT-TAB'];
export type TabQuery = NonNullable<TabOperation['parameters']['query']>;
export type TabResponse = TabOperation['responses'][200]['content']['application/json'];
export type RegisterRow = NonNullable<TabResponse['registers']>[number];
export type ActionRow = NonNullable<TabResponse['actions']>[number];
export type DocumentRow = NonNullable<TabResponse['documents']>[number];
export type TabSummary = NonNullable<TabResponse['summary']>;
export type Owner = NonNullable<ActionRow['owner']>;
export type Register = NonNullable<TabQuery['register']>;
export type ListTab = 'milestones' | 'documents' | 'registers' | 'actions';
/** The tabs read through E-PROJECT-TAB; Milestones and Money have their own live reads (milestonesModel, moneyModel). */
export type ReadTab = Exclude<ListTab, 'milestones'>;
export type TabRows = { documents: DocumentRow[]; registers: RegisterRow[]; actions: ActionRow[] };

/** The tabs this model reads; Money keeps its own panel. */
export const hasTabContent = (tab: ProjectTab): tab is ListTab => tab === 'milestones' || tab === 'documents' || tab === 'registers' || tab === 'actions';

export const REGISTERS: readonly { key: Register; label: string; word: string; count: [one: string, many: string] }[] = [
  { key: 'issues', label: 'Issues', word: 'issues', count: ['ISSUE', 'ISSUES'] },
  { key: 'changes', label: 'Changes', word: 'changes', count: ['CHANGE', 'CHANGES'] },
  { key: 'emergencies', label: 'Emergencies', word: 'emergencies', count: ['EMERGENCY', 'EMERGENCIES'] },
  { key: 'rfps', label: 'RFPs', word: 'RFPs', count: ['RFP', 'RFPS'] },
];
export const registerOf = (key: Register) => REGISTERS.find((r) => r.key === key) ?? REGISTERS[0];

export type TabView = { register: Register; q?: string };

/** From the URL: an unknown register reads as Issues, an empty q as none. Only Registers reads `register`. */
export function parseTabView(params: URLSearchParams, tab: ListTab): TabView {
  const register = tab === 'registers' ? (REGISTERS.find((r) => r.key === params.get('register'))?.key ?? 'issues') : 'issues';
  return { register, q: tab === 'milestones' ? undefined : params.get('q')?.trim() || undefined };
}

/** The URL search for a view: `register` is left out for Issues and `q` when empty. Cursors are never written. */
export function tabSearch(view: TabView): string {
  const params = new URLSearchParams();
  if (view.register !== 'issues') params.set('register', view.register);
  if (view.q) params.set('q', view.q);
  const text = params.toString();
  return text ? `?${text}` : '';
}

/** The request: limit always, register on Registers only (default Issues), q only when settled, cursor for "Show more". */
export function buildTabQuery(tab: ReadTab, view: TabView, cursor?: string, limit: TabQuery['limit'] = 10): TabQuery {
  const query: TabQuery = { limit };
  if (tab === 'registers') query.register = view.register;
  if (view.q) query.q = view.q;
  if (cursor) query.cursor = cursor;
  return query;
}

const isObject = (value: unknown): value is Record<string, unknown> => typeof value === 'object' && value !== null && !Array.isArray(value);
const isText = (value: unknown) => typeof value === 'string' && value !== '';

const ROW_CHECKS: Record<ReadTab, (row: Record<string, unknown>) => boolean> = {
  documents: (row) => isText(row.document_id) && isText(row.title) && isText(row.version) && isText(row.status),
  registers: (row) => isText(row.reference) && isText(row.title),
  actions: (row) => isText(row.action_id) && isText(row.title) && isText(row.state),
};

/** A 200 body without the tab's typed array of well-formed rows (a misrouted response) is a load failure. */
export function isTabResponse(body: unknown, tab: ReadTab): body is TabResponse {
  if (!isObject(body)) return false;
  const rows = body[tab];
  return Array.isArray(rows) && rows.every((row) => isObject(row) && ROW_CHECKS[tab](row));
}

export const rowsOf = <T extends ReadTab>(data: TabResponse, tab: T): TabRows[T] => (data[tab] ?? []) as TabRows[T];

export const workHref = (workId: unknown) => (isText(workId) ? `/work/${encodeURIComponent(workId as string)}` : undefined);

/** Owner text: "Client · Lagoon Health", "Engineering (recorded by PM)"; undefined when the row has no owner. */
export function ownerText(owner: Owner | undefined): string | undefined {
  const name = textOf(owner?.name);
  if (!owner || !name) return undefined;
  const text = [textOf(owner.role), name].filter(Boolean).join(' · ');
  return owner.recorded_by_pm ? `${text} (recorded by PM)` : text;
}

/** "2d" from one day, "4h" from one hour, "<1h" below; undefined (drawn Unknown) when the row carries no age. */
export function ageText(seconds: unknown): string | undefined {
  if (typeof seconds !== 'number' || !Number.isFinite(seconds) || seconds < 0) return undefined;
  if (seconds >= 86400) return `${Math.floor(seconds / 86400)}d`;
  if (seconds >= 3600) return `${Math.floor(seconds / 3600)}h`;
  return '<1h';
}

/** "13 Nov"; undefined (drawn Unknown) when the due date is unknown, absent or unreadable. */
export function dueText(due: ActionRow['due']): string | undefined {
  if (!due || due.unknown === true || !due.date) return undefined;
  const text = formatDayMonth(due.date);
  return text === UNKNOWN ? undefined : text;
}

/** "From Weekly sync · 10 Nov"; nothing without a `from`. */
export function fromText(from: ActionRow['from']): string | undefined {
  const meeting = textOf(from?.meeting);
  if (!meeting) return undefined;
  const day = from?.at ? formatDayMonth(from.at) : UNKNOWN;
  return day === UNKNOWN ? `From ${meeting}` : `From ${meeting} · ${day}`;
}

/** The ACTIONS header from `summary.actions`; each part only when its count is present. */
export function actionsSummaryText(summary: TabSummary | undefined): string {
  const counts = summary?.actions;
  const part = (n: unknown, words: string) => (Number.isInteger(n) && (n as number) >= 0 ? `${n} ${words}` : undefined);
  return [part(counts?.total, 'ACTIONS'), part(counts?.overdue, 'OVERDUE'), part(counts?.without_owner, 'WITHOUT OWNER')].filter(Boolean).join(' · ');
}

/** A register's count from `summary.registers`; undefined when absent (no badge, never 0 invented). */
export function registerCount(summary: TabSummary | undefined, key: Register): number | undefined {
  const n: unknown = summary?.registers?.[key];
  return Number.isInteger(n) && (n as number) >= 0 ? (n as number) : undefined;
}

/** "3 ISSUES", "1 RFP"; empty when the count is absent. */
export function registerCountText(summary: TabSummary | undefined, key: Register): string {
  const n = registerCount(summary, key);
  if (n === undefined) return '';
  const [one, many] = registerOf(key).count;
  return `${n} ${n === 1 ? one : many}`;
}
