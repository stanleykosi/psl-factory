// Project tabs (SCR-38 Milestones, SCR-11 Registers, SCR-29 Actions, and the Documents list that opens SCR-08): view state, the E-PROJECT-TAB query, response
// checks and the display text of each value. Pure functions only. Every value is shown as the response sends it:
// nothing is totalled, added, sorted or inferred from another fact (INV-UNKNOWN, INV-FACTS).
import type { operations } from '@/api/schema';
import { formatAmount, formatDayMonth, groupDigits, STATE_TAGS, UNKNOWN, type FactoryState } from '@/components';

import { textOf, type ProjectTab } from './model';

type TabOperation = operations['E-PROJECT-TAB'];
export type TabQuery = NonNullable<TabOperation['parameters']['query']>;
export type TabResponse = TabOperation['responses'][200]['content']['application/json'];
export type MilestoneRow = NonNullable<TabResponse['milestones']>[number];
export type RegisterRow = NonNullable<TabResponse['registers']>[number];
export type ActionRow = NonNullable<TabResponse['actions']>[number];
export type DocumentRow = NonNullable<TabResponse['documents']>[number];
export type TabSummary = NonNullable<TabResponse['summary']>;
export type Amount = MilestoneRow['contract_amount'];
export type Paid = NonNullable<MilestoneRow['paid']>;
export type Change = NonNullable<MilestoneRow['changes']>[number];
export type Register = NonNullable<TabQuery['register']>;
export type ListTab = 'milestones' | 'documents' | 'registers' | 'actions';
export type TabRows = { milestones: MilestoneRow[]; documents: DocumentRow[]; registers: RegisterRow[]; actions: ActionRow[] };

/** The tabs this model reads; Money keeps its own panel. */
export const hasTabContent = (tab: ProjectTab): tab is ListTab => tab === 'milestones' || tab === 'documents' || tab === 'registers' || tab === 'actions';

export type TabView = { register: Register; q?: string };

/** The request: limit always, register on Registers only (default Issues), q only when settled, cursor for "Show more". */
export function buildTabQuery(tab: ListTab, view: TabView, cursor?: string, limit: TabQuery['limit'] = 10): TabQuery {
  const query: TabQuery = { limit };
  if (tab === 'registers') query.register = view.register;
  if (view.q) query.q = view.q;
  if (cursor) query.cursor = cursor;
  return query;
}

const isObject = (value: unknown): value is Record<string, unknown> => typeof value === 'object' && value !== null && !Array.isArray(value);
const isText = (value: unknown) => typeof value === 'string' && value !== '';

const ROW_CHECKS: Record<ListTab, (row: Record<string, unknown>) => boolean> = {
  milestones: (row) => Number.isInteger(row.position) && isText(row.name) && isObject(row.contract_amount) && isObject(row.completion),
  documents: (row) => isText(row.document_id) && isText(row.title) && isText(row.version) && isText(row.status),
  registers: (row) => isText(row.reference) && isText(row.title),
  actions: (row) => isText(row.action_id) && isText(row.title) && isText(row.state),
};

/** A 200 body without the tab's typed array of well-formed rows (a misrouted response) is a load failure. */
export function isTabResponse(body: unknown, tab: ListTab): body is TabResponse {
  if (!isObject(body)) return false;
  const rows = body[tab];
  return Array.isArray(rows) && rows.every((row) => isObject(row) && ROW_CHECKS[tab](row));
}

export const rowsOf = <T extends ListTab>(data: TabResponse, tab: T): TabRows[T] => (data[tab] ?? []) as TabRows[T];

export const workHref = (workId: unknown) => (isText(workId) ? `/work/${encodeURIComponent(workId as string)}` : undefined);

/** A money value as text; undefined when it is unknown or has no readable amount (the caller draws Unknown, never 0). NGN
 *  is "₦4,250,000.00"; another currency is "<CODE> <grouped amount>", never converted. */
export function amountText(value: { amount?: string; currency?: string; unknown?: boolean } | undefined): string | undefined {
  if (!value || value.unknown === true || !isText(value.amount)) return undefined;
  const raw = (value.amount as string).replace(/,/g, '').trim();
  if (value.currency && value.currency !== 'NGN') return /^-?\d+(\.\d+)?$/.test(raw) ? `${value.currency} ${groupDigits(raw)}` : undefined;
  const text = formatAmount(raw);
  return text === UNKNOWN ? undefined : text;
}

/** "Done 27 Oct · proof", "Done 11 Nov · client UAT sign-off", "Not yet", then " · <amount_note>" when the row has one. */
export function completionText(row: Pick<MilestoneRow, 'completion' | 'amount_note'>): string {
  const { completion } = row;
  let text = 'Not yet';
  if (completion.status === 'done') {
    const day = completion.at ? formatDayMonth(completion.at) : UNKNOWN;
    text = day === UNKNOWN ? 'Done' : `Done ${day}`;
    const proof = textOf(completion.proof);
    if (proof) text += ` · ${proof}`;
    else if (textOf(completion.evidence_id)) text += ' · proof';
  }
  const note = textOf(row.amount_note);
  return note ? `${text} · ${note}` : text;
}

/** The invoice's state word from the shared tag words; undefined when the state is absent or not one of them. */
export const invoiceWord = (state: unknown): string | undefined => (typeof state === 'string' && Object.hasOwn(STATE_TAGS, state) ? STATE_TAGS[state as FactoryState].text : undefined);

export const PAID_WORDS: Record<Exclude<Paid['status'], 'unknown'>, string> = {
  paid: 'Paid',
  part_paid: 'Part paid',
  not_paid: 'Not paid',
  not_due: 'Not due',
  finance_tracks: 'Tracked by Finance',
};

/** The paid status as its own word; undefined when it is `unknown` or not a status the contract lists (drawn Unknown). */
export const paidWord = (paid: Paid): string | undefined => (Object.hasOwn(PAID_WORDS, paid.status) ? PAID_WORDS[paid.status as keyof typeof PAID_WORDS] : undefined);

/** Whether any returned milestone has a change; the CHANGES column then shows (it is not hidden otherwise). */
export const hasChanges = (rows: MilestoneRow[]) => rows.some((row) => (row.changes?.length ?? 0) > 0);
