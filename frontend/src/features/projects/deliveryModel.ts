// SCR-43 Delivery overview: the six lines in their fixed order, the state words and the closure hold reasons. Pure functions only.
// Nothing is counted or derived; an absent value stays empty, never 0.
import type { operations } from '@/api/live-schema';
import type { TagTone } from '@/components';

export type DeliveryOverview = operations['delivery_overview']['responses'][200]['content']['application/json'];
export type DeliveryLine = DeliveryOverview['lines'][number];
export type ClosureChecklist = operations['closure_checklist']['responses'][200]['content']['application/json'];

export const LINE_KEYS = ['delivery-release/v1', 'delivery-go-live/v1', 'delivery-hypercare/v1', 'delivery-handover/v1', 'delivery-archive/v1', 'delivery-closure/v1'] as const;
export type LineKey = (typeof LINE_KEYS)[number];

// The tone names are the spec's; caution is the "a person must act" tag, stopped the amber waiting tag (as the state tags use for an uncertain effect).
const STATE_WORDS: Record<string, { text: string; tone: TagTone }> = {
  not_started: { text: 'NOT STARTED', tone: 'neutral' },
  ready: { text: 'READY', tone: 'neutral' },
  processing: { text: 'IN PROGRESS', tone: 'neutral' },
  waiting: { text: 'WAITING', tone: 'neutral' },
  action_needed: { text: 'ACTION NEEDED', tone: 'person' },
  owner_needed: { text: 'NEEDS AN OWNER', tone: 'person' },
  setup_needed: { text: 'SET-UP NEEDED', tone: 'person' },
  followup_needed: { text: 'FOLLOW-UP NEEDED', tone: 'person' },
  awaiting_reconciliation: { text: 'CHECKING WHAT HAPPENED', tone: 'person' },
  effect_uncertain: { text: 'RESULT UNCERTAIN', tone: 'waiting' },
  verified: { text: 'VERIFIED', tone: 'done' },
  cancelled: { text: 'CANCELLED', tone: 'neutral' },
};
const UNKNOWN_WORDS = { text: 'UNKNOWN', tone: 'neutral' as TagTone };

/** The tag for a line: `state`, or `gate_state` only when `state` is null and the gate has started; null state with no start is NOT STARTED. */
export function stateWords(line: Pick<DeliveryLine, 'state' | 'gate_state'>): { text: string; tone: TagTone } {
  const value = line.state ?? (line.gate_state === 'not_started' ? 'not_started' : line.gate_state);
  return Object.hasOwn(STATE_WORDS, value) ? STATE_WORDS[value] : UNKNOWN_WORDS;
}

const isObject = (v: unknown): v is Record<string, unknown> => typeof v === 'object' && v !== null && !Array.isArray(v);
const isText = (v: unknown) => typeof v === 'string';

/** Exactly six lines, each key once, every field present. Anything else is an invalid response, not a partial list. */
export function isOverview(data: unknown): data is DeliveryOverview {
  if (!isObject(data) || !isText(data.as_of) || !Array.isArray(data.lines) || data.lines.length !== LINE_KEYS.length) return false;
  const seen = new Set<string>();
  for (const line of data.lines) {
    if (!isObject(line) || !isText(line.key) || !(LINE_KEYS as readonly string[]).includes(line.key) || seen.has(line.key)) return false;
    seen.add(line.key);
    if (!isText(line.title)) return false;
    if (!(line.work_id === null || typeof line.work_id === 'number')) return false;
    for (const field of ['state', 'reference', 'updated_at', 'work_url', 'gate_url']) if (!(line[field] === null || isText(line[field]))) return false;
    if (!isText(line.gate_state)) return false;
  }
  return true;
}

export type DeliveryRow = { number: string; line: DeliveryLine; reference: string | null; updatedAt: string | null; href: string | null };

/** The six rows in the fixed order, numbered 01 to 06, whatever order the API returned. */
export function deliveryRows(overview: DeliveryOverview): DeliveryRow[] {
  return LINE_KEYS.map((key, i) => {
    const line = overview.lines.find((l) => l.key === key)!;
    return {
      number: String(i + 1).padStart(2, '0'),
      line,
      reference: line.reference,
      updatedAt: line.updated_at,
      href: line.work_id !== null && line.work_url ? `/work/${encodeURIComponent(String(line.work_id))}` : null,
    };
  });
}

export const lineOf = (overview: DeliveryOverview, key: LineKey) => overview.lines.find((l) => l.key === key);

/** Whether the closure hold reasons are read at all: closure not started and the release line has work. */
export function reasonsNeeded(overview: DeliveryOverview): boolean {
  return lineOf(overview, 'delivery-closure/v1')?.work_id === null && typeof lineOf(overview, 'delivery-release/v1')?.work_id === 'number';
}

export type HoldReason = { title: string; finding: string | null };

export function isChecklist(data: unknown): data is ClosureChecklist {
  return isObject(data) && typeof data.ready_to_prepare === 'boolean' && Array.isArray(data.checks) && data.checks.every((c) => isObject(c) && isText(c.title) && isText(c.status) && (c.finding === null || c.finding === undefined || isText(c.finding)));
}

/** The checks that hold closure back, in the order the API sent them; none when it is ready to prepare. */
export function holdReasons(checklist: ClosureChecklist): HoldReason[] {
  if (checklist.ready_to_prepare) return [];
  return checklist.checks.filter((c) => ['held', 'unknown', 'unavailable'].includes(c.status)).map((c) => ({ title: c.title, finding: c.finding ?? null }));
}
