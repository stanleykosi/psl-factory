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

/** Lines whose footer reads "Back" (to the chooser) on the board; every other line reads "Cancel" (closes). */
const BACK_LINES = new Set(['invoice']);

/** SCR-04-desktop draws the invoice drawer (and the chooser) 480px wide; the other line boards draw 500px. */
const NARROW_LINES = new Set(['invoice']);

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

export function narrowDrawer(lineKey: string): boolean {
  return NARROW_LINES.has(lineKey);
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
