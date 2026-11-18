// E-INVOICES body as the SCR-20 boards need it. The generated contract (src/api/schema.d.ts) carries the rows, `totals`,
// `filters`, `total` and `as_of`. The fields read here are a PROPOSAL (G-SCR20-1 to -6), served by the contract mock
// only; the backend developer may change or refuse any of them. Every reader treats an absent or malformed value as
// "not supplied", so the page works on the typed body alone. Nothing here adds, subtracts or compares an amount.
import type { operations } from '@/api/schema';

export type InvoiceList = operations['E-INVOICES']['responses'][200]['content']['application/json'];
export type InvoiceRow = InvoiceList['items'][number];
export type Amount = InvoiceRow['invoiced'];
export type InvoiceQuery = { q?: string; status?: string };

/** A strip figure as the backend composed it: the known part (if any) and whether part of it is not known. */
export type TotalDetail = { known?: { amount: string; currency: string }; hasUnknown: boolean };
export type TotalKey = 'owed' | 'overdue' | 'received_this_month';
export type Overdue = { days?: number; unknown: boolean };
export type AgentNote = { agent: 'chidi'; lines: string[]; workId?: string; strong: Set<number> };

const DECIMAL = /^-?\d+\.\d{2}$/;
const DAY = /^\d{4}-\d{2}-\d{2}$/;
const MONTH = /^\d{4}-(0[1-9]|1[0-2])$/;
export const RECORD_ID = /^[A-Za-z0-9][A-Za-z0-9._-]*$/;

const isObject = (value: unknown): value is Record<string, unknown> => typeof value === 'object' && value !== null && !Array.isArray(value);
const text = (value: unknown): value is string => typeof value === 'string' && value.trim() !== '';

/** G-SCR20-1, -2 `totals_detail.<key>`: {known?: {amount, currency}, has_unknown}. */
export function totalDetail(body: InvoiceList, key: TotalKey): TotalDetail | undefined {
  const detail = (body as { totals_detail?: unknown }).totals_detail;
  if (!isObject(detail) || !isObject(detail[key])) return undefined;
  const entry = detail[key] as { known?: unknown; has_unknown?: unknown };
  if (typeof entry.has_unknown !== 'boolean') return undefined;
  const known = entry.known;
  if (known === undefined) return { hasUnknown: entry.has_unknown };
  if (!isObject(known) || typeof known.amount !== 'string' || !DECIMAL.test(known.amount) || !text(known.currency)) return undefined;
  return { known: { amount: known.amount, currency: known.currency }, hasUnknown: entry.has_unknown };
}

/** G-SCR20-2 `period`: the month "received this month" covers ("2026-11"). */
export function period(body: InvoiceList): string | undefined {
  const value = (body as { period?: unknown }).period;
  return typeof value === 'string' && MONTH.test(value) ? value : undefined;
}

/** G-SCR20-3 `bank_data_as_of`: the last day bank data is imported for ("2026-11-10"). */
export function bankDataAsOf(body: InvoiceList): string | undefined {
  const value = (body as { bank_data_as_of?: unknown }).bank_data_as_of;
  return typeof value === 'string' && DAY.test(value) ? value : undefined;
}

/** G-SCR20-3 `coverage`: the sentence under the strip, word for word. */
export function coverage(body: InvoiceList): string | undefined {
  const value = (body as { coverage?: unknown }).coverage;
  return text(value) ? value : undefined;
}

/** G-SCR20-4 row `overdue`: {days?, unknown}. A bare due date is never turned into days here (D-94). */
export function rowOverdue(row: InvoiceRow): Overdue | undefined {
  const value = (row as { overdue?: unknown }).overdue;
  if (!isObject(value) || typeof value.unknown !== 'boolean') return undefined;
  const days = value.days;
  if (days === undefined) return { unknown: value.unknown };
  if (typeof days !== 'number' || !Number.isInteger(days) || days < 0) return undefined;
  return { days, unknown: value.unknown };
}

/** G-SCR20-5 row `milestone_label` ("M1", "final"). */
export function milestoneLabel(row: InvoiceRow): string | undefined {
  const value = (row as { milestone_label?: unknown }).milestone_label;
  return text(value) ? value : undefined;
}

/** G-SCR20-6 `agent_note`: {agent: "chidi", lines, work_id?, strong_lines?}. */
export function agentNote(body: InvoiceList): AgentNote | undefined {
  const note = (body as { agent_note?: unknown }).agent_note;
  if (!isObject(note) || note.agent !== 'chidi' || !Array.isArray(note.lines) || note.lines.length === 0 || !note.lines.every(text)) return undefined;
  const lines = note.lines as string[];
  const strong = new Set(Array.isArray(note.strong_lines) ? note.strong_lines.filter((n): n is number => Number.isInteger(n)) : []);
  const workId = text(note.work_id) && RECORD_ID.test(note.work_id) ? note.work_id : undefined;
  return { agent: 'chidi', lines, workId, strong };
}
