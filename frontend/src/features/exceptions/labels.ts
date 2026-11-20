// E-EXCEPTIONS values to the words and tones of the state tags. Presentation only. The words come from the shared
// state list (STATE_TAGS); `blocked` has no word of its own there and no board draws "Blocked", so it reads as
// the README's "Action needed" (a person must act).
import { formatClock, formatDate, formatDayMonth, STATE_TAGS, type TagTone } from '@/components';

import type { ExceptionKind } from './types';

/** Tag per `what` (and the Filter panel's words); a new contract value fails the typecheck here. */
export const KIND_TAGS: Record<ExceptionKind, { words: string; tone: TagTone }> = {
  effect_uncertain: { words: STATE_TAGS.effect_uncertain.text, tone: STATE_TAGS.effect_uncertain.tone },
  owner_needed: { words: STATE_TAGS.owner_needed.text, tone: STATE_TAGS.owner_needed.tone },
  setup_needed: { words: STATE_TAGS.setup_needed.text, tone: STATE_TAGS.setup_needed.tone },
  blocked: { words: STATE_TAGS.action_needed.text, tone: STATE_TAGS.action_needed.tone },
  followup_needed: { words: STATE_TAGS.followup_needed.text, tone: STATE_TAGS.followup_needed.tone },
};

export const KINDS = Object.keys(KIND_TAGS) as ExceptionKind[];


/** "since 11:02" on the same Lagos day as `asOf`, otherwise "since 10 Nov", as the SCR-10 boards write it. */
export function sinceText(since: string, asOf: string): string {
  return `since ${formatDate(since) === formatDate(asOf) ? formatClock(since) : formatDayMonth(since)}`;
}
