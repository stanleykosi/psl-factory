// SCR-20 values to the words on the boards. Presentation only: every amount, total, state, overdue figure and count
// comes from the response as a decimal string or a returned number. Nothing here adds, subtracts or compares money,
// counts rows, works out days from a due date or infers a state from amounts (INV-UNKNOWN, D-94). Unknown is never 0.
import { formatAmount, formatDayMonth, formatDayTime, groupDigits, UNKNOWN } from '@/components';
import { plural } from '@/features/response/labels';

import { bankDataAsOf, milestoneLabel, rowOverdue, totalDetail, type Amount, type InvoiceList, type InvoiceQuery, type InvoiceRow, type TotalKey } from './proposal';

export { UNKNOWN };
export const PAYMENTS_PATH = '/finance/payments';
const DECIMAL = /^-?\d+\.\d{2}$/;

/** A known amount in full (two decimals, never rounded; another currency with its code), or undefined when it is not known. */
export function knownAmountText(amount: { amount?: string; currency: string; unknown?: boolean } | undefined): string | undefined {
  if (!amount || amount.unknown === true || typeof amount.amount !== 'string' || !DECIMAL.test(amount.amount)) return undefined;
  return amount.currency === 'NGN' ? formatAmount(amount.amount) : `${amount.currency} ${groupDigits(amount.amount)}`;
}

/** A row amount: its text, or undefined for Unknown. */
export const amountText = (amount: Amount | undefined) => knownAmountText(amount);

export type StripValue = { known?: string; hasUnknown: boolean };

/** OWED, OVERDUE and RECEIVED THIS MONTH as the backend composed them. Without `totals_detail`, OWED falls back to the
 *  typed `totals.owed`; the other two read Unknown. The page never adds up rows. */
export function stripValue(body: InvoiceList, key: TotalKey): StripValue {
  const detail = totalDetail(body, key);
  if (detail) {
    const known = detail.known ? knownAmountText({ ...detail.known, unknown: false }) : undefined;
    return known ? { known, hasUnknown: detail.hasUnknown } : { hasUnknown: true };
  }
  if (key === 'owed') {
    const known = knownAmountText(body.totals?.owed);
    return known ? { known, hasUnknown: false } : { hasUnknown: true };
  }
  return { hasUnknown: true };
}

/** "<known amount> + Unknown", "<known amount>" or "Unknown". */
export const stripText = (value: StripValue) => (value.known ? (value.hasUnknown ? `${value.known} + ${UNKNOWN}` : value.known) : UNKNOWN);

/** BANK DATA TO: "10 Nov", or Unknown. */
export function bankDataText(body: InvoiceList): string {
  const day = bankDataAsOf(body);
  return day ? formatDayMonth(day) : UNKNOWN;
}

/** WORK: "<client> · <milestone>" when the backend names the milestone, else "<client> · <project title>" as sent. */
export function workText(row: InvoiceRow): string {
  const second = milestoneLabel(row) ?? row.project?.title;
  const parts = [row.client, second].filter((part): part is string => typeof part === 'string' && part !== '');
  return parts.length > 0 ? parts.join(' · ') : UNKNOWN;
}

/** OVERDUE BY: "9 days" from the backend's days; "—" only when the backend says it is not overdue; else Unknown. */
export function overdueText(row: InvoiceRow): string {
  const overdue = rowOverdue(row);
  if (!overdue || overdue.unknown) return UNKNOWN;
  if (overdue.days !== undefined) return plural(overdue.days, 'day');
  return '—';
}

/** The phone card's line under the amount: "INV-0398 · overdue 9 days"; the reference alone when the backend says it is not overdue. */
export function cardOverdue(row: InvoiceRow): 'none' | 'unknown' | string {
  const text = overdueText(row);
  if (text === '—') return 'none';
  if (text === UNKNOWN) return 'unknown';
  return text;
}

/** "4 INVOICES": the count only when the backend returns `total` (rows are never counted). */
export function countText(total: number | undefined): string {
  return typeof total === 'number' && Number.isInteger(total) && total >= 0 ? `${total} ${total === 1 ? 'INVOICE' : 'INVOICES'}` : '';
}

/** "Updated 12 Nov 10:00" (WAT) from the list's `as_of`. */
export function updatedText(asOf: string): string | undefined {
  const at = formatDayTime(asOf);
  return at === UNKNOWN ? undefined : `Updated ${at}`;
}

/** The State filter's label for a value: the backend's `filters[]` label, else the value as given. */
export function filterLabel(filters: InvoiceList['filters'], value: string): string {
  return filters?.find((f) => f.value === value)?.label ?? value;
}

/** q and status from the address; a blank or repeated value is not a filter. */
export function parseQuery(params: URLSearchParams): InvoiceQuery {
  const one = (name: string) => {
    const all = params.getAll(name);
    return all.length === 1 && all[0].trim() !== '' ? all[0].trim() : undefined;
  };
  return { q: one('q'), status: one('status') };
}

export function querySearch(query: InvoiceQuery): string {
  const params = new URLSearchParams();
  if (query.q) params.set('q', query.q);
  if (query.status) params.set('status', query.status);
  const text = params.toString();
  return text ? `?${text}` : '';
}

/** "November 2026" for the spoken name of RECEIVED THIS MONTH. */
const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
export function monthName(value: string | undefined): string | undefined {
  if (!value) return undefined;
  return `${MONTHS[Number(value.slice(5, 7)) - 1]} ${value.slice(0, 4)}`;
}

export const workHref = (workId: string) => `/work/${encodeURIComponent(workId)}`;
