// Start work copy. Presentation only, per line key, matching the SCR-04 boards: the primary button's words, the
// drawer title where the board draws a shorter one than the line `title`, the footer's other button, and the
// journey link. No contract field carries these yet; any other line reads "Start work" under its own title.
import type { Line } from './types';

const START_LABELS: Record<string, string> = {
  invoice: 'Start the invoice',
  weekly_report: 'Start report',
  leadership_report: 'Start report',
  minutes: 'Start minutes',
  issue_followup: 'Start follow-up',
  change_request: 'Log change',
  emergency_change: 'Ask for preauthorisation',
  escalation: 'Raise escalation',
  income_schedules: 'Start schedule',
  ledger_sources: 'Record source',
  rfp_intake: 'Log RFP',
};

const DRAWER_TITLES: Record<string, string> = {
  weekly_report: 'Weekly client report',
  minutes: 'Minutes after a meeting',
  issue_followup: 'Chase an open issue',
  change_request: 'Scope or timeline change',
};

/** SCR-04-mobile names the invoice sheet more briefly than the desktop drawer. */
const PHONE_TITLES: Record<string, string> = {
  invoice: 'Invoice preparation',
};

/** Lines whose board draws the line's group after "START WORK" ("START WORK · PRE-SALE", SCR-23); the group is data. */
const EYEBROW_GROUP = new Set(['rfp_intake']);

/** Lines whose board draws a four-way choice as joined segments instead of a select (SCR-23's submission method). */
const FOUR_SEGMENTS = new Set(['rfp_intake']);

/** Lines whose help stays under its own field; elsewhere a field's help moves under the Proof box that follows it (SCR-04-*-change). */
const HELP_STAYS = new Set(['rfp_intake']);

/** Lines whose footer reads "Back" (to the chooser) on the board; every other line reads "Cancel" (closes). */
const BACK_LINES = new Set(['invoice']);

/** "See the full <noun> journey"; a line not listed reads "See the full journey". */
const JOURNEY_NOUNS: Record<string, string> = {
  invoice: 'invoice',
};

export function startLabel(lineKey: string): string {
  return START_LABELS[lineKey] ?? 'Start work';
}

export function drawerTitle(line: Pick<Line, 'key' | 'title'>, phone: boolean): string {
  return (phone && PHONE_TITLES[line.key]) || DRAWER_TITLES[line.key] || line.title;
}

export function footerGoesBack(lineKey: string): boolean {
  return BACK_LINES.has(lineKey);
}

export function journeyLabel(lineKey: string): string {
  const noun = JOURNEY_NOUNS[lineKey];
  return noun ? `See the full ${noun} journey` : 'See the full journey';
}

export const AGENT_NAMES: Record<NonNullable<NonNullable<Line['next']>['agent']>, string> = {
  tola: 'Tola',
  chidi: 'Chidi',
  zainab: 'Zainab',
};

/** Under the Proof box after the project changed: the file was uploaded to the other project's case (Conflicts 4). */
export const PROOF_MOVED = 'Proof removed: it was added to the other project. Add it again.';
/** F-09's 403 sentence (useEvidenceUpload), also shown for a 404 so the two can't be told apart. */
export const CANT_ADD = 'You can’t add proof to this item.';

export function drawerEyebrow(line: Pick<Line, 'key' | 'group'>): string {
  return EYEBROW_GROUP.has(line.key) && line.group ? `START WORK · ${line.group.toUpperCase()}` : 'START WORK';
}

export function helpMovesBelowProof(lineKey: string): boolean {
  return !HELP_STAYS.has(lineKey);
}

export function fourSegments(lineKey: string): boolean {
  return FOUR_SEGMENTS.has(lineKey);
}
