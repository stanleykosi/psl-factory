// Start work copy. Presentation only: the primary button's words per line key, matching the SCR-04 boards.
// No contract field carries a button label yet; any other line reads "Start work".
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

export function startLabel(lineKey: string): string {
  return START_LABELS[lineKey] ?? 'Start work';
}

export const AGENT_NAMES: Record<NonNullable<NonNullable<Line['next']>['agent']>, string> = {
  tola: 'Tola',
  chidi: 'Chidi',
  zainab: 'Zainab',
};
