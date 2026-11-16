// SCR-12 Money tab: the E-PROJECT-TAB money rows and the E-REPORT figures, their guards and the words shown. Pure
// functions only. Amounts are decimal strings formatted as text (formatAmount); nothing here adds, totals, rounds or
// converts an amount, and nothing is inferred: invoice and paid come from their own fields (INV-FACTS), a value the
// backend does not know is Unknown, never 0 (INV-UNKNOWN).
import type { operations } from '@/api/schema';
import { formatAmount, UNKNOWN } from '@/components';

export type MoneyTabBody = operations['E-PROJECT-TAB']['responses'][200]['content']['application/json'];
export type MoneyRow = NonNullable<MoneyTabBody['money']>[number];
export type MoneyValue = MoneyRow['amount'];
export type Paid = NonNullable<MoneyRow['paid']>;
export type PaidStatus = Paid['status'];
export type Report = operations['E-REPORT']['responses'][200]['content']['application/json'];
export type Figure = Report['figures'][number];
export type SourceDetail = NonNullable<Figure['source_details']>[number];

/** What the tab draws: the rows in `position` order, the report to read for the drill-down, and the time. */
export type MoneyView = { rows: MoneyRow[]; reportId?: string; asOf?: string };

const isObject = (value: unknown): value is Record<string, unknown> => typeof value === 'object' && value !== null && !Array.isArray(value);

function isMoneyValue(value: unknown): value is MoneyValue {
  return isObject(value) && typeof value.currency === 'string' && typeof value.unknown === 'boolean';
}

function isMoneyRow(row: unknown): row is MoneyRow {
  return isObject(row) && Number.isInteger(row.position) && typeof row.stage === 'string' && isMoneyValue(row.amount);
}

/** The view, or null when `money` is missing or any row fails the guard: the tab then shows its error card and
 *  draws nothing partial. The untyped v5 `items` are never read. Rows keep the backend's order by `position`. */
export function moneyViewOf(body: unknown): MoneyView | null {
  if (!isObject(body) || !Array.isArray(body.money) || !body.money.every(isMoneyRow)) return null;
  const rows = [...(body.money as MoneyRow[])].sort((a, b) => a.position - b.position);
  const summary = isObject(body.summary) ? body.summary : {};
  const reportId = typeof summary.report_id === 'string' && summary.report_id !== '' ? summary.report_id : undefined;
  const asOf = typeof body.as_of === 'string' ? body.as_of : undefined;
  return { rows, reportId, asOf };
}

/** A report whose figures can be read (each an object with a label and a value); anything else is a report error. */
export function isReport(body: unknown): body is Report {
  return isObject(body) && Array.isArray(body.figures) && body.figures.every((f) => isObject(f) && typeof f.label === 'string' && isMoneyValue(f.value));
}

/** "₦4,250,000.00", or "1,200.00 USD" for another currency (formatAmount knows only ₦). Undefined when the value is
 *  not known: `unknown`, no amount, or an amount that is not a decimal string. The caller shows Unknown. */
export function amountText(value: MoneyValue): string | undefined {
  if (value.unknown || value.amount === undefined) return undefined;
  if (value.currency === 'NGN') {
    const text = formatAmount(value.amount);
    return text === UNKNOWN ? undefined : text;
  }
  const digits = formatAmount(value.amount, { sign: false });
  return digits === UNKNOWN ? undefined : `${digits} ${value.currency}`;
}

/** The words for each paid status, in one place (presentation only; the status is the backend's). `not_due` shows a
 *  dash with the hidden words "Not due"; `unknown` is drawn as the amber Unknown. */
export const PAID_WORDS: Record<PaidStatus, string> = {
  paid: 'Paid',
  part_paid: 'Part paid',
  not_paid: 'Not paid',
  not_due: '—',
  finance_tracks: 'Finance tracks',
  unknown: UNKNOWN,
};

/** The paid words for a status; a status outside the enum (only if the contract changes) shows its raw value. */
export function paidWords(status: string): string {
  return Object.hasOwn(PAID_WORDS, status) ? PAID_WORDS[status as PaidStatus] : status;
}

/** The invoice cell's text: the backend's composed status, else the reference; undefined when neither is sent. */
export function invoiceText(row: MoneyRow): string | undefined {
  return row.invoice_status ?? row.invoice?.reference;
}

/** The figure a row's amount explains, by id; undefined when the row names none or the report has no such figure. */
export function figureOf(report: Report | undefined, id: string | undefined): Figure | undefined {
  if (!report || id === undefined) return undefined;
  return report.figures.find((f) => f.id === id);
}

/** True when the two values differ in any field: unknown, currency or the amount text, compared as sent. */
export function valuesDiffer(a: MoneyValue, b: MoneyValue): boolean {
  return a.unknown !== b.unknown || a.currency !== b.currency || a.amount !== b.amount;
}

/** The drill-down title: "Where ₦4,250,000.00 comes from" from the figure's own value, never the row's. */
export function figureTitle(figure: Figure | undefined): string {
  const text = figure ? amountText(figure.value) : undefined;
  return text ? `Where ${text} comes from` : 'Where this figure comes from';
}
