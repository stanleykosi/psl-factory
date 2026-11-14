// E-EXCEPTIONS values to the words and classes on the SCR-10 boards. Presentation only.
import type { ExceptionKind, ExceptionsLimit } from './types';

/** Kind tag per `what`; a new contract value fails the typecheck here. */
export const KIND_TAGS: Record<ExceptionKind, { text: string; className: string }> = {
  effect_uncertain: { text: 'SEND UNCERTAIN', className: 'psl-tag psl-tag--waiting' },
  owner_needed: { text: 'OWNER NEEDED', className: 'psl-tag psl-tag--person' },
  setup_needed: { text: 'SETUP NEEDED', className: 'psl-tag psl-tag--person' },
  blocked: { text: 'BLOCKED', className: 'psl-tag psl-tag--person' },
  followup_needed: { text: 'FOLLOW-UP NEEDED', className: 'psl-tag psl-tag--person' },
};

export const EXCEPTIONS_LIMITS: readonly ExceptionsLimit[] = [10, 20, 50];

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const WAT = new Intl.DateTimeFormat('en-GB', {
  timeZone: 'Africa/Lagos',
  year: 'numeric',
  month: 'numeric',
  day: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
  hourCycle: 'h23',
});

function watParts(value: string): Record<string, string> {
  return Object.fromEntries(WAT.formatToParts(new Date(value)).map((p) => [p.type, p.value]));
}

/** "since 11:02" on the same Lagos day as `asOf`, otherwise "since 10 Nov". */
export function sinceText(since: string, asOf: string): string {
  const s = watParts(since);
  const a = watParts(asOf);
  if (s.year === a.year && s.month === a.month && s.day === a.day) return `since ${s.hour}:${s.minute}`;
  return `since ${Number(s.day)} ${MONTHS[Number(s.month) - 1]}`;
}
