// How a line looks on the floor: the agent avatar and subtitle drawn on SCR-06, and the tag tone.
// Design copy keyed by the line name E-OVERVIEW returns; a line not listed here gets no avatar or subtitle.
import type { TagTone } from '@/components';

import type { OverviewLine } from './types';

type Agent = 'tola' | 'chidi' | 'zainab';

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

type Tone = NonNullable<NonNullable<OverviewLine['status']>['tone']>;
const TONE_TAG: Record<Tone, TagTone> = {
  verified: 'done',
  agent: 'agent',
  neutral: 'neutral',
  person: 'person',
  stopped: 'person',
  uncertain: 'waiting',
  restricted: 'neutral',
};

/** Tag tone from the line's backend-assigned `status.tone` when the response carries one; otherwise from needs_person. Never from `note`. */
export function tagTone(line: OverviewLine): TagTone {
  if (line.status?.tone) return TONE_TAG[line.status.tone];
  return line.stations.some((s) => s.needs_person) ? 'person' : 'neutral';
}
