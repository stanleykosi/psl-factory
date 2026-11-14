// SCR-36 month-end values to the words on the boards. Presentation only: every count, label, tone, restriction and
// link comes from the response; nothing here counts tasks, buckets states, totals cash or picks a month.
// Money is read from the decimal string (never a float) and unknown stays Unknown, never 0 (INV-UNKNOWN).
import { formatAmount, formatClock } from '@/features/decide/format';
import { STATE_TAGS } from '@/features/work-item/labels';

import type { AgentKey, MonthEnd, MonthEndTask, MonthEndTone } from './proposal';

export const UNKNOWN = 'Unknown';
const PERIOD = /^[0-9]{4}-(0[1-9]|1[0-2])$/;
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

/** "FROM RECORDS YOU CAN SEE · UPDATED 10:42" (Africa/Lagos); either part alone when the other is missing. */
export function asOfLine(body: Pick<MonthEnd, 'as_of' | 'coverage'>): string | undefined {
  const parts = [body.coverage, body.as_of ? `UPDATED ${formatClock(body.as_of)}` : undefined].filter(Boolean);
  return parts.length ? parts.join(' · ') : undefined;
}

const isCount = (value: unknown): value is number => typeof value === 'number' && Number.isInteger(value) && value >= 0;

/** A count as returned, or Unknown; never 0 for a missing value and never counted from the tasks. */
export function countText(value: number | undefined): string {
  return isCount(value) ? String(value) : UNKNOWN;
}

/** "2 of 7" from the returned summary; Unknown when either number is missing. */
export function doneText(summary: MonthEnd['summary']): string {
  return isCount(summary?.done) && isCount(summary?.total) ? `${summary.done} of ${summary.total}` : UNKNOWN;
}

type Amount = { amount?: string; currency: string; unknown: boolean };

function knownAmount(amount: Amount | undefined): (Amount & { amount: string }) | undefined {
  return amount && amount.unknown === false && typeof amount.amount === 'string' && DECIMAL.test(amount.amount)
    ? (amount as Amount & { amount: string })
    : undefined;
}

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
export function compactAmount(amount: Amount & { amount: string }): string {
  const [, sign, digits] = DECIMAL.exec(amount.amount)!;
  const whole = BigInt(digits);
  let index = UNITS.findIndex(([, size]) => whole >= size);
  if (index < 0) return formatAmount(amount)!;
  let tenths = roundTenths(whole, UNITS[index][1]);
  // 999.95K rounds to 1000K: step up to the next unit (1M).
  if (tenths >= 10_000n && index > 0) tenths = roundTenths(whole, UNITS[--index][1]);
  const number = tenths % 10n === 0n ? `${tenths / 10n}` : `${tenths / 10n}.${tenths % 10n}`;
  const prefix = amount.currency === 'NGN' ? '₦' : `${amount.currency} `;
  return `${sign}${prefix}${number}${UNITS[index][0]}`;
}

export type CashView = { text: string; description: string; unknown: boolean };

const NOT_KNOWN: CashView = { text: UNKNOWN, description: 'Not known yet.', unknown: true };

/** The CASH RECEIVED cell: the known part plus Unknown, the known amount, or Unknown; never 0 and never blank. */
export function cashView(body: Pick<MonthEnd, 'cash_received' | 'cash_received_detail'>): CashView {
  const detail = body.cash_received_detail;
  const known = knownAmount(detail ? detail.known : body.cash_received);
  if (!known) return NOT_KNOWN;
  if (detail?.has_unknown) {
    return {
      text: `${compactAmount(known)} + ${UNKNOWN}`,
      description: `Known so far ${formatAmount(known)}; the rest is not known yet.`,
      unknown: true,
    };
  }
  return { text: compactAmount(known), description: formatAmount(known)!, unknown: false };
}

const TONE_CLASS: Record<MonthEndTone, string> = {
  neutral: 'neutral',
  person: 'person',
  stopped: 'person',
  agent: 'agent',
  uncertain: 'waiting',
  restricted: 'waiting',
  verified: 'done',
};

/** CMP-05 tag: the backend's label and tone, else the STATE_TAGS words (upper case) and colour for the state. */
export function taskTag(task: MonthEndTask): { text: string; className: string } {
  const tag = STATE_TAGS[task.state];
  const tone = task.tone ? TONE_CLASS[task.tone] : tag.tone;
  return { text: task.status_label ?? tag.text.toUpperCase(), className: `psl-tag psl-tag--${tone}` };
}

export const workHref = (workId: string) => `/work/${encodeURIComponent(workId)}`;

/** The last desktop cell: a restricted row never links, whatever work_id says (INV-RESTRICTED). */
export function taskEnd(task: MonthEndTask): { kind: 'restricted'; text: string } | { kind: 'link'; href: string } | { kind: 'none' } {
  if (task.restricted === true) return { kind: 'restricted', text: task.restricted_label ?? 'Restricted' };
  if (task.work_id) return { kind: 'link', href: workHref(task.work_id) };
  return { kind: 'none' };
}

/** The primary action, only when the backend names the work item it opens (D-07). */
export function nextAction(body: Pick<MonthEnd, 'next_action'>): { label: string; href: string } | undefined {
  const action = body.next_action;
  return action?.work_id ? { label: action.label, href: workHref(action.work_id) } : undefined;
}

export const AGENT_NAMES: Record<AgentKey, { name: string; role: string }> = {
  tola: { name: 'Tola', role: 'PMO agent' },
  chidi: { name: 'Chidi', role: 'Finance agent' },
  zainab: { name: 'Zainab', role: 'HR agent' },
};
