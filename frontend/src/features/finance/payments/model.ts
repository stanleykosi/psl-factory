// SCR-20 values to the words on the boards. Presentation only: every amount, total, status, age and count comes from the
// response as a decimal string or a returned number. Nothing here adds, subtracts or compares money, counts rows, works
// out days from a due date or infers a status from amounts (INV-UNKNOWN, D-94). Unknown is never 0 and a figure is never
// merged across currencies or bases.
import { formatAmount, formatDayMonth, groupDigits, UNKNOWN } from '@/components';
import { plural } from '@/features/response/labels';

import type { InvoiceList, InvoiceQuery, InvoiceRow, InvoiceTotal } from './types';

export { UNKNOWN };
export const PAYMENTS_PATH = '/finance/payments';
const DECIMAL = /^-?\d+\.\d{2}$/;
const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];

/** The five states the list can be narrowed to, in the order the filter shows them (the contract's `state` values). */
export const STATES = [
  { value: 'issued', label: 'Issued' },
  { value: 'part-paid', label: 'Part-paid' },
  { value: 'overdue', label: 'Overdue' },
  { value: 'paid', label: 'Paid' },
  { value: 'unknown', label: 'Unknown' },
] as const;

/** A known amount in full (two decimals, never rounded; another currency with its code), or undefined when it is not known. */
export function knownAmountText(amount: string | null | undefined, currency: string): string | undefined {
  if (typeof amount !== 'string' || !DECIMAL.test(amount)) return undefined;
  return currency === 'NGN' ? formatAmount(amount) : `${currency} ${groupDigits(amount)}`;
}

/** "₦4,700,000.00 gross" for a strip figure; undefined when the amount is not known. */
export function figureText(amount: string | null | undefined, currency: string, basis: string): string | undefined {
  const text = knownAmountText(amount, currency);
  return text === undefined ? undefined : `${text} ${basis}`;
}

export type StripValue = { key: string; text: string; unknown: boolean; note?: string };

const unknownValue = (key: string): StripValue => ({ key, text: UNKNOWN, unknown: true });

/** OWED TO PSL, one value per returned total: `owed`; when it is null "<known part> + Unknown" with the count of invoices
 *  that have no known balance; when that is null too, Unknown. No totals at all reads Unknown. */
export function owedValues(totals: InvoiceTotal[]): StripValue[] {
  if (totals.length === 0) return [unknownValue('none')];
  return totals.map((total, i) => {
    const key = `${i}`;
    const owed = figureText(total.owed, total.currency, total.basis);
    if (owed !== undefined) return { key, text: owed, unknown: false };
    const known = figureText(total.known_owed, total.currency, total.basis);
    if (known === undefined) return unknownValue(key);
    const count = total.unknown_owed_count;
    return { key, text: `${known} + ${UNKNOWN}`, unknown: true, note: count > 0 ? `${count} ${count === 1 ? 'invoice has' : 'invoices have'} no known balance` : undefined };
  });
}

/** OVERDUE, one value per returned total; null reads Unknown. */
export function overdueValues(totals: InvoiceTotal[]): StripValue[] {
  if (totals.length === 0) return [unknownValue('none')];
  return totals.map((total, i) => {
    const text = figureText(total.overdue, total.currency, total.basis);
    return text === undefined ? unknownValue(`${i}`) : { key: `${i}`, text, unknown: false };
  });
}

/** RECEIVED THIS MONTH, one value per returned total. No totals reads Unknown, never 0 (the API gives no confirmed zero). */
export function receivedValues(received: InvoiceList['received_this_month']): StripValue[] {
  if (received.totals.length === 0) return [unknownValue('none')];
  return received.totals.map((total, i) => {
    const text = figureText(total.amount, total.currency, total.basis);
    return text === undefined ? unknownValue(`${i}`) : { key: `${i}`, text, unknown: false };
  });
}

/** "Received this month covers 2 of 3 projects; 1 could not be read." Only when some could not be read. */
export function coverageText(received: InvoiceList['received_this_month']): string | undefined {
  const unread = received.workspaces_unknown;
  if (!(unread > 0)) return undefined;
  const read = received.workspaces_read;
  return `Received this month covers ${read} of ${read + unread} projects; ${unread} could not be read.`;
}

/** DATA DATE: "12 Nov" from the list's `as_of` day. */
export const dataDate = (asOf: string) => formatDayMonth(asOf);

/** "November 2026" for the spoken name of RECEIVED THIS MONTH. */
export function monthName(value: string): string | undefined {
  const month = MONTHS[Number(value.slice(5, 7)) - 1];
  return month ? `${month} ${value.slice(0, 4)}` : undefined;
}

/** WORK: "<customer> · <contract>"; a blank part is left out and both blank reads Unknown. */
export function workText(row: InvoiceRow): string {
  const parts = [row.customer, row.contract].filter((part) => part.trim() !== '');
  return parts.length > 0 ? parts.join(' · ') : UNKNOWN;
}

/** OVERDUE BY: "9 days overdue" / "1 day overdue" from the returned days past due; "—" for 0 (not past due); null is Unknown. */
export function overdueText(row: Pick<InvoiceRow, 'age_days'>): string {
  const days = row.age_days;
  if (days === null || !Number.isInteger(days) || days < 0) return UNKNOWN;
  return days === 0 ? '—' : `${plural(days, 'day')} overdue`;
}

/** The chip's tone name for a returned status; voided and unknown are neutral. */
export const STATUS_TONE: Record<InvoiceRow['status'], string> = {
  issued: 'neutral',
  'part-paid': 'uncertain',
  overdue: 'stopped',
  paid: 'verified',
  voided: 'neutral',
  unknown: 'neutral',
};

/** A returned link when it is a path on this site; otherwise the action is not offered. */
export const linkOf = (url: string | null | undefined): string | undefined => (typeof url === 'string' && /^\/(?![/\\])/.test(url) ? url : undefined);

export const NOT_AVAILABLE = 'Not available to you for this invoice';

/** q and status from the address; a blank or repeated value is not a filter, and a status outside the five is dropped. */
export function parseQuery(params: URLSearchParams): InvoiceQuery {
  const one = (name: string) => {
    const all = params.getAll(name);
    return all.length === 1 && all[0].trim() !== '' ? all[0].trim() : undefined;
  };
  const status = one('status');
  return { q: one('q')?.slice(0, 100), status: STATES.some((s) => s.value === status) ? status : undefined };
}

export function querySearch(query: InvoiceQuery): string {
  const params = new URLSearchParams();
  if (query.q) params.set('q', query.q);
  if (query.status) params.set('status', query.status);
  const text = params.toString();
  return text ? `?${text}` : '';
}

/** The State filter's label for a value. */
export const filterLabel = (value: string) => STATES.find((s) => s.value === value)?.label ?? value;
