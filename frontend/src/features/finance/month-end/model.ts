// SCR-36 month-end values to the words on the boards. Presentation only: every count, label, state, link and amount
// comes from the response; nothing here counts tasks, buckets states, adds cash across projects, currencies or bases,
// or picks a month. Money is read from the decimal string (never a float) and unknown stays Unknown, never 0 (INV-UNKNOWN).
import { formatAmount, formatClock, groupDigits, STATE_TAGS, type TagTone } from '@/components';

import type { MonthEnd, MonthEndCash, MonthEndWork } from './types';

export const UNKNOWN = 'Unknown';
const PERIOD = /^[1-9][0-9]{3}-(0[1-9]|1[0-2])$/;
const DECIMAL = /^(-?)([0-9]+)\.[0-9]{2}$/;
const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];

/** The URL's `period` when it is exactly one YYYY-MM value naming a month; otherwise undefined (no request is sent). */
export function parsePeriod(value: string | string[] | undefined): string | undefined {
  return typeof value === 'string' && PERIOD.test(value) ? value : undefined;
}

/** "October 2026" and "Oct" for a returned period; undefined when it cannot be read as a month. */
export function periodNames(period: string): { long: string; short: string } | undefined {
  if (!PERIOD.test(period)) return undefined;
  const month = MONTHS[Number(period.slice(5)) - 1];
  return { long: `${month} ${period.slice(0, 4)}`, short: month.slice(0, 3) };
}

/** "UPDATED 10:42" (Africa/Lagos, as the SCR-36 board writes it); undefined when `as_of` cannot be read. */
export function asOfLine(asOf: string | undefined): string | undefined {
  const clock = asOf ? formatClock(asOf) : UNKNOWN;
  return clock === UNKNOWN ? undefined : `UPDATED ${clock}`;
}

const isCount = (value: unknown): value is number => typeof value === 'number' && Number.isInteger(value) && value >= 0;

/** A count as returned, or Unknown; never 0 for a missing value and never counted from the tasks. */
export function countText(value: number | undefined): string {
  return isCount(value) ? String(value) : UNKNOWN;
}

type Amount = { amount: string; currency: string };

/** A two-decimal amount as returned; anything else is not a known amount. */
const isKnown = (amount: unknown): amount is string => typeof amount === 'string' && DECIMAL.test(amount);

const UNITS: readonly [string, bigint][] = [
  ['B', 1_000_000_000n],
  ['M', 1_000_000n],
  ['K', 1_000n],
];

function roundTenths(whole: bigint, size: bigint): bigint {
  const scaled = whole * 10n;
  return (scaled % size) * 2n >= size ? scaled / size + 1n : scaled / size;
}

/** "₦4.7M", "-₦1.3K", "USD 1.2K": one decimal, half away from zero, from the integer digits; below 1,000 in full. */
export function compactAmount(amount: Amount): string {
  const [, sign, digits] = DECIMAL.exec(amount.amount)!;
  const whole = BigInt(digits);
  let index = UNITS.findIndex(([, size]) => whole >= size);
  if (index < 0) return amount.currency === 'NGN' ? formatAmount(amount.amount) : `${amount.currency} ${groupDigits(amount.amount)}`;
  let tenths = roundTenths(whole, UNITS[index][1]);
  // 999.95K rounds to 1000K: step up to the next unit (1M).
  if (tenths >= 10_000n && index > 0) tenths = roundTenths(whole, UNITS[--index][1]);
  const number = tenths % 10n === 0n ? `${tenths / 10n}` : `${tenths / 10n}.${tenths % 10n}`;
  const prefix = amount.currency === 'NGN' ? '₦' : `${amount.currency} `;
  return `${sign}${prefix}${number}${UNITS[index][0]}`;
}

export type CashLine = { key: string; workspace: string; text: string; unknown: boolean; basis?: string };
export type CashView = {
  /** The strip cell: the single amount, "By project", or Unknown. */
  cell: string;
  cellUnknown: boolean;
  /** One line per cash row; empty when the cell stands alone. */
  lines: CashLine[];
  more: boolean;
};

const NO_NAME = 'Project not named';

/**
 * The CASH RECEIVED cell and the lines under the strip. One amount stands alone only when it is the only row, no more
 * groups exist and no workspace says its cash cannot be read; otherwise "By project" and one line per row. A workspace
 * whose cash is unavailable reads Unknown whatever its row says. Nothing is added across rows, currencies or bases.
 */
export function cashView(body: Pick<MonthEnd, 'cash' | 'workspaces' | 'more_cash_groups'>): CashView {
  const unavailable = new Set(body.workspaces.filter((w) => w.cash_unavailable).map((w) => w.workspace.case_id));
  const anyUnavailable = unavailable.size > 0;
  const row = (item: MonthEndCash, i: number): CashLine => {
    const hidden = item.workspace_id !== null && unavailable.has(item.workspace_id);
    const known = !hidden && isKnown(item.amount);
    return {
      key: `${i}`,
      workspace: item.workspace ?? NO_NAME,
      text: known ? compactAmount({ amount: item.amount, currency: item.currency }) : UNKNOWN,
      unknown: !known,
      basis: known ? item.basis : undefined,
    };
  };
  const lines = body.cash.map(row);
  // a workspace with unavailable cash and no row of its own still reads Unknown
  const named = new Set(body.cash.map((c) => c.workspace_id));
  body.workspaces
    .filter((w) => w.cash_unavailable && !named.has(w.workspace.case_id))
    .forEach((w, i) => lines.push({ key: `u${i}`, workspace: w.workspace.title, text: UNKNOWN, unknown: true }));
  const single = body.cash.length === 1 && !body.more_cash_groups && !anyUnavailable;
  if (single) return { cell: lines[0].text, cellUnknown: lines[0].unknown, lines: [], more: false };
  if (lines.length === 0 && !body.more_cash_groups) return { cell: UNKNOWN, cellUnknown: true, lines: [], more: false };
  return { cell: 'By project', cellUnknown: false, lines, more: body.more_cash_groups };
}

/** The full amount for the single cash cell's description, e.g. "₦4,700,000.00 gross"; undefined when it is not one known amount. */
export function cashDescription(body: Pick<MonthEnd, 'cash' | 'workspaces' | 'more_cash_groups'>): string | undefined {
  const [only] = body.cash;
  if (body.cash.length !== 1 || body.more_cash_groups || body.workspaces.some((w) => w.cash_unavailable) || !isKnown(only.amount)) return undefined;
  return `${only.currency === 'NGN' ? formatAmount(only.amount) : `${only.currency} ${groupDigits(only.amount)}`} ${only.basis}`;
}

const STATE_TONE: Record<MonthEndWork['state'], { tone: TagTone }> = {
  done: STATE_TAGS.verified,
  waiting: STATE_TAGS.waiting,
  in_progress: STATE_TAGS.processing,
  // the boards' stopped tone (a person must act)
  stopped: STATE_TAGS.action_needed,
};

/** CMP-05 tag: the returned label, in the tone of the existing state tag for the returned state. */
export function taskTag(task: Pick<MonthEndWork, 'state' | 'label'>): { text: string; tone: TagTone } {
  return { text: task.label, tone: STATE_TONE[task.state]?.tone ?? 'neutral' };
}

/** The returned url when it is an app or Django path (starts with one "/"); otherwise the title is not a link. */
export const taskHref = (url: string): string | undefined => (/^\/(?![/\\])/.test(url) ? url : undefined);
