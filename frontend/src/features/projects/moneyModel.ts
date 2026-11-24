// SCR-12 Money tab: the live GET /projects/{case_id}/money body, its guard and the words shown. Pure functions only.
// Amounts are decimal strings formatted as text (formatAmount); nothing here adds, totals, rounds or converts an amount,
// and nothing is inferred: invoice status, paid and owed come from their own fields, a value the backend does not know
// is Unknown, never 0 (INV-UNKNOWN, INV-FACTS).
import type { operations } from '@/api/live-schema';
import { formatAmount, UNKNOWN } from '@/components';

export type Money = operations['workspaces_money']['responses'][200]['content']['application/json'];
export type MoneyItem = Money['items'][number];
export type MoneyInvoice = MoneyItem['invoices'][number];
export type MoneySource = MoneyItem['sources'][number];
export type MoneyChange = MoneyItem['changes'][number];

export const isObject = (value: unknown): value is Record<string, unknown> => typeof value === 'object' && value !== null && !Array.isArray(value);

const textOrNull = (value: unknown) => value === null || typeof value === 'string';

function isInvoice(value: unknown): boolean {
  return isObject(value) && Number.isInteger(value.id) && typeof value.currency === 'string' && typeof value.reference === 'string' && typeof value.status === 'string' && textOrNull(value.paid) && textOrNull(value.owed);
}

function isSource(value: unknown): boolean {
  return isObject(value) && typeof value.label === 'string' && textOrNull(value.kind) && textOrNull(value.reference) && textOrNull(value.at);
}

function isChange(value: unknown): boolean {
  return isObject(value) && Number.isInteger(value.link_id) && typeof value.reference === 'string' && typeof value.note === 'string' && value.additional_amount === null;
}

function isItem(value: unknown): value is MoneyItem {
  return (
    isObject(value) &&
    typeof value.key === 'string' &&
    typeof value.label === 'string' &&
    textOrNull(value.amount) &&
    typeof value.currency === 'string' &&
    textOrNull(value.due_date) &&
    textOrNull(value.completed_at) &&
    textOrNull(value.missing_reason) &&
    (value.milestone_id === null || Number.isInteger(value.milestone_id)) &&
    (value.stage_position === null || Number.isInteger(value.stage_position)) &&
    typeof value.contract_stage === 'boolean' &&
    Array.isArray(value.invoices) &&
    value.invoices.every(isInvoice) &&
    Array.isArray(value.sources) &&
    value.sources.every(isSource) &&
    Array.isArray(value.changes) &&
    value.changes.every(isChange)
  );
}

/** A body the tab can draw: every item has the shape it is drawn with; anything else is a bad body, not a crash. */
export function isMoney(body: unknown): body is Money {
  return isObject(body) && Array.isArray(body.items) && body.items.every(isItem) && typeof body.limited === 'boolean' && typeof body.as_of === 'string';
}

/** "NGN 4,250,000.00", "USD 1,000.00": the item's own currency code before the grouped amount, never converted. Undefined
 *  when the amount is null or not a decimal string; the caller shows Unknown. */
export function amountText(amount: string | null, currency: string): string | undefined {
  if (amount === null) return undefined;
  const digits = formatAmount(amount, { sign: false });
  return digits === UNKNOWN ? undefined : `${currency} ${digits}`;
}

/** The invoices of an item as sent, in order: reference and status text, paid and owed as text (undefined = Unknown). */
export function invoiceLines(item: MoneyItem) {
  return item.invoices.map((invoice) => ({
    id: invoice.id,
    reference: invoice.reference,
    status: invoice.status,
    paid: amountText(invoice.paid, invoice.currency),
    owed: amountText(invoice.owed, invoice.currency),
  }));
}

/** The number before a stage's label; nothing for a row with no stage position. */
export const stageLabel = (item: Pick<MoneyItem, 'label' | 'stage_position'>) => (item.stage_position === null ? item.label : `${item.stage_position} · ${item.label}`);
