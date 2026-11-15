// E-EXCEPTIONS values to the words and tones of the state tags. Presentation only. The words come from the shared
// state list (STATE_TAGS); "Blocked" is not on that list, so it keeps its own words in the person tone.
import { formatClock, formatDate, formatDayMonth, STATE_TAGS, type TagTone } from '@/components';

import type { ExceptionKind, ExceptionsLimit } from './types';

/** Tag per `what` (and the Filter panel's words); a new contract value fails the typecheck here. */
export const KIND_TAGS: Record<ExceptionKind, { words: string; tone: TagTone }> = {
  effect_uncertain: { words: STATE_TAGS.effect_uncertain.text, tone: STATE_TAGS.effect_uncertain.tone },
  owner_needed: { words: STATE_TAGS.owner_needed.text, tone: STATE_TAGS.owner_needed.tone },
  setup_needed: { words: STATE_TAGS.setup_needed.text, tone: STATE_TAGS.setup_needed.tone },
  blocked: { words: 'Blocked', tone: 'person' },
  followup_needed: { words: STATE_TAGS.followup_needed.text, tone: STATE_TAGS.followup_needed.tone },
};

export const KINDS = Object.keys(KIND_TAGS) as ExceptionKind[];

export const EXCEPTIONS_LIMITS: readonly ExceptionsLimit[] = [10, 20, 50];

/** "since 11:02" on the same Lagos day as `asOf`, otherwise "since 10 Nov", as the SCR-10 boards write it. */
export function sinceText(since: string, asOf: string): string {
  return `since ${formatDate(since) === formatDate(asOf) ? formatClock(since) : formatDayMonth(since)}`;
}
