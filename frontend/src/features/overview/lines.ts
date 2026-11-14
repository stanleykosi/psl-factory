// How a line looks on the floor: the agent avatar and subtitle drawn on SCR-06, and the tag tone.
// Design copy keyed by the line name E-OVERVIEW returns; a line not listed here gets no avatar or subtitle.
import type { LineStatus, OverviewLine } from './types';

type Agent = 'tola' | 'chidi' | 'zainab';

/** Tola is the PMO agent, Chidi Finance and Zainab HR (design/system README § Mascots). */
export const AGENT_INITIAL: Record<Agent, string> = { tola: 'T', chidi: 'C', zainab: 'Z' };

export const LINE_IDENTITY: Record<string, { agent: Agent; subtitle: string }> = {
  'Pre-sale': { agent: 'tola', subtitle: 'RFP · commercial' },
  Planning: { agent: 'tola', subtitle: 'Engagement · plan' },
  Release: { agent: 'tola', subtitle: 'Gates · go-live' },
  Closing: { agent: 'tola', subtitle: 'Hypercare · handover · closure' },
  Invoices: { agent: 'chidi', subtitle: 'Milestone to verified' },
  'Month-end': { agent: 'chidi', subtitle: 'Accounts · schedules · PPE' },
  'Cash and BU': { agent: 'chidi', subtitle: 'Forecast · BU · ledger' },
  Payroll: { agent: 'zainab', subtitle: 'Restricted' },
};

const STATUS_TAG: Record<LineStatus, string> = {
  on_track: 'psl-tag--done',
  waiting: 'psl-tag--waiting',
  stopped: 'psl-tag--person',
  uncertain: 'psl-tag--person',
  problems: 'psl-tag--person',
};

/** Tag tone from the line's `status` when the response carries one; otherwise from needs_person. Never from `note`. */
export function tagTone(line: OverviewLine): string {
  if (line.status) return STATUS_TAG[line.status];
  return line.stations.some((s) => s.needs_person) ? 'psl-tag--person' : 'psl-tag--neutral';
}
