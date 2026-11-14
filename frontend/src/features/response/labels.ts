// Response and reconcile values to the words on the SCR-16 and SCR-02 boards. Presentation only: what may be
// recorded, by whom and with which options comes from the API; nothing here decides access.
import type { AgentKey, ReconcileOutcome, Reconcile, Responder, ResponseTask, ResponseVariant, TaskResponse } from './contract';

/** The variants this page records; the others (team input, go-live, handover) get the not-open state. */
export const RECORDABLE: ReadonlySet<ResponseVariant> = new Set(['client_response', 'sow_signature']);

export const RESPONSE_LABELS = {
  /** The SCR-02 waiting panel's link, in place of "Open the decision". */
  entry: { client_response: 'Record the client’s response', sow_signature: 'Record the client’s signature' } as Partial<Record<ResponseVariant, string>>,
  record: { client_response: 'Record response', sow_signature: 'Record signature' } as Partial<Record<ResponseVariant, string>>,
  busy: 'Recording…',
};

export const NOTE_MAX = 2000;

/** The response block of a task, when it has one. */
export function responseOf(task: ResponseTask): TaskResponse | undefined {
  return task.response;
}

export const AGENT_LABELS: Record<AgentKey, { name: string; role: string }> = {
  tola: { name: 'Tola', role: 'PMO agent' },
  chidi: { name: 'Chidi', role: 'Finance agent' },
  zainab: { name: 'Zainab', role: 'HR agent' },
};

/** "Client contact · Dr Amaka Obi, Lagoon Health" (client_response) or "Ngozi Bello · Head of …, Tamarind Loans". */
export function responderText(r: Responder, variant: ResponseVariant): string {
  if (variant === 'sow_signature') {
    const after = [r.role, r.organisation].filter(Boolean).join(', ');
    return after ? `${r.name} · ${after}` : r.name;
  }
  const named = r.organisation ? `${r.name}, ${r.organisation}` : r.name;
  return r.role ? `${r.role} · ${named}` : named;
}

/** "184 KB" or "1.1 MB". */
export function fileSize(bytes: number): string {
  if (bytes >= 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${Math.max(1, Math.round(bytes / 1024))} KB`;
}

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const WAT_DAY = new Intl.DateTimeFormat('en-GB', { timeZone: 'Africa/Lagos', day: 'numeric', month: 'numeric' });
const WAT_CLOCK = new Intl.DateTimeFormat('en-GB', { timeZone: 'Africa/Lagos', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' });

/** "11 Nov" in Africa/Lagos. */
export function formatDay(value: string): string {
  const parts = Object.fromEntries(WAT_DAY.formatToParts(new Date(value)).map((p) => [p.type, p.value]));
  return `${parts.day} ${MONTHS[Number(parts.month) - 1]}`;
}

/** "16:20" in Africa/Lagos. */
export function formatClock(value: string): string {
  return WAT_CLOCK.format(new Date(value));
}

/** A datetime-local value read as WAT (UTC+1 all year): "2026-11-11T16:20" → "2026-11-11T16:20:00+01:00". */
export function watIso(local: string): string {
  return `${local.length === 16 ? `${local}:00` : local.slice(0, 19)}+01:00`;
}

/** Adds a full stop unless the text already ends in closing punctuation. */
export function sentence(text: string): string {
  return /[.!?…]$/.test(text) ? text : `${text}.`;
}

/** "a", "a and b", "a, b and c". */
export function listWords(parts: string[]): string {
  return parts.length < 2 ? parts.join('') : `${parts.slice(0, -1).join(', ')} and ${parts[parts.length - 1]}`;
}

export const plural = (n: number, one: string) => `${n} ${one}${n === 1 ? '' : 's'}`;

/** "2 hours" or "45 minutes", rounded down; undefined without both times. */
export function checkDuration(checks: NonNullable<Reconcile['checks']>): string | undefined {
  if (!checks.first_at || !checks.last_at) return undefined;
  const minutes = Math.max(0, Math.floor((Date.parse(checks.last_at) - Date.parse(checks.first_at)) / 60000));
  return minutes < 60 ? plural(minutes, 'minute') : plural(Math.floor(minutes / 60), 'hour');
}

/** The desktop panel's first sentence, from reconcile.checks; undefined when there are no checks. */
export function checksSentence(checks: Reconcile['checks']): string | undefined {
  if (!checks) return undefined;
  const who = checks.agent ? AGENT_LABELS[checks.agent].name : 'The factory';
  const over = checkDuration(checks);
  return `${who} checked ${plural(checks.count, 'time')}${over ? ` over ${over}` : ''} and found no delivery receipt.`;
}

/** One reconcile option: the bold lead and the rest, from the API's notes. */
export function outcomeWords(outcome: ReconcileOutcome, reconcile: Reconcile): { lead: string; rest?: string } {
  if (outcome === 'delivered') return { lead: 'It arrived.', rest: 'I have proof the client received it (upload it next).' };
  if (outcome === 'not_delivered') return { lead: 'It didn’t arrive.', rest: reconcile.resend ? sentence(`Allow ${reconcile.resend}`) : undefined };
  return { lead: 'I can’t tell yet.', rest: reconcile.unknown_note ? sentence(reconcile.unknown_note) : undefined };
}

