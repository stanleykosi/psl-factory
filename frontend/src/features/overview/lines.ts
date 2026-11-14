// How a line looks on the floor: the agent avatar and subtitle drawn on SCR-06, and the tag tone.
// Design copy keyed by the line name E-OVERVIEW returns; a line not listed here gets no avatar or subtitle.
import type { OverviewLine } from './types';

type Agent = 'tola' | 'chidi' | 'zainab';

/** The agent avatars (public/agents/, 192px from design/mascots/transparent/*-avatar.png), named as the README § Mascots asks. */
export const AGENT_AVATAR: Record<Agent, { src: string; alt: string }> = {
  tola: { src: '/agents/tola.png', alt: 'Tola · PMO agent' },
  chidi: { src: '/agents/chidi.png', alt: 'Chidi · Finance agent' },
  zainab: { src: '/agents/zainab.png', alt: 'Zainab · HR agent' },
};

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

type Tone = NonNullable<OverviewLine['status']>['tone'];
const TONE_TAG: Record<NonNullable<Tone>, string> = {
  verified: 'psl-tag--done',
  agent: 'psl-tag--agent',
  neutral: 'psl-tag--neutral',
  person: 'psl-tag--person',
  stopped: 'psl-tag--person',
  uncertain: 'psl-tag--person',
  restricted: 'psl-tag--person',
};

/** Tag tone from the line's backend-assigned `status.tone` when the response carries one; otherwise from needs_person. Never from `note`. */
export function tagTone(line: OverviewLine): string {
  if (line.status?.tone) return TONE_TAG[line.status.tone];
  return line.stations.some((s) => s.needs_person) ? 'psl-tag--person' : 'psl-tag--neutral';
}
