// PROPOSAL (D-LINE-WORKSPACE, contract mock only): the `workspace` block's enum values to the words and classes
// the frame draws. Presentation only: which sections and steps exist, their values and who may act are the
// backend's. A value outside these lists is shown as it came, never hidden.
import { formatAmount } from '@/features/decide/format';
import { formatWat, type WorkItem } from '@/features/work-item/labels';

export type Workspace = NonNullable<WorkItem['workspace']>;
export type Section = Workspace['sections'][number];
export type SectionKind = Section['kind'];
export type Item = Section['items'][number];
export type Cell = NonNullable<Item['cells']>[number];
export type Column = NonNullable<Section['columns']>[number];
export type Step = NonNullable<Workspace['steps']>[number];
export type Tone = NonNullable<NonNullable<Workspace['status']>['tone']>;
export type Ref = NonNullable<Cell['link']>;
export type Money = NonNullable<Item['money']>;
export type DateValue = NonNullable<Item['due']>;

/** Tone to the design system's existing tag colours (tokens only); an unlisted tone draws the neutral tag. */
const TONE_CLASS: Record<Tone, string> = {
  neutral: 'psl-tag--neutral',
  person: 'psl-tag--person',
  agent: 'psl-tag--agent',
  stopped: 'psl-tag--person',
  uncertain: 'psl-tag--waiting',
  verified: 'psl-tag--done',
  restricted: 'psl-tag--neutral',
};

export function tagClass(tone: string | undefined): string {
  return `psl-tag ${TONE_CLASS[tone as Tone] ?? 'psl-tag--neutral'}`;
}

export const STATUS_WORDS: Record<NonNullable<Item['status']>, string> = {
  done: 'Done',
  now: 'In progress',
  next: 'Next',
  not_yet: 'Not yet',
  held: 'Held',
  blocked: 'Blocked',
  unknown: 'Unknown',
  not_applicable: 'Not applicable',
};

/** `uncertain` is never read as received; `unknown` reads Unknown (INV-UNKNOWN). */
export const RECEIPT_WORDS: Record<NonNullable<Item['receipt']>, string> = {
  received: 'Received',
  not_yet: 'Not yet',
  uncertain: 'Uncertain',
  failed: 'Failed',
  unknown: 'Unknown',
};

export const SEVERITY_WORDS: Record<NonNullable<Item['severity']>, string> = {
  high: 'High',
  medium: 'Medium',
  low: 'Low',
  info: 'Info',
};

export const AGENT_NAMES: Record<NonNullable<Section['agent']>, string> = { tola: 'Tola', chidi: 'Chidi', zainab: 'Zainab' };

/** The word for an enum value; a value the frame does not know is shown raw. */
export function word<K extends string>(words: Record<K, string>, value: string): string {
  return Object.hasOwn(words, value) ? words[value as K] : value;
}

export const agentName = (agent: string) => word(AGENT_NAMES, agent);

// Frontend-owned neutral sentences (spec Assumptions); none of them is a business rule.
export const WS_TEXT = {
  empty: 'Nothing here yet.',
  restricted: 'Restricted',
  unknown: 'Unknown',
  noMore: 'More rows aren’t available yet.',
  showMore: 'Show more',
  filter: 'Filter',
  you: 'You',
} as const;

/** "As of 14 Nov 10:40 WAT". */
export const asOfLine = (value: string) => `As of ${formatWat(value)} WAT`;

/** Money in the decide page's format; null when unknown or absent, so the caller draws Unknown (never 0). */
export const moneyText = (money: Money) => formatAmount(money);

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

/** A calendar date ("2026-11-28") as "28 Nov 2026"; null when unknown or missing (INV-UNKNOWN). */
export function dateText(value: DateValue): string | null {
  if (value.unknown || !value.date) return null;
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value.date);
  if (!match) return null;
  return `${Number(match[3])} ${MONTHS[Number(match[2]) - 1]} ${match[1]}`;
}

const RECORD_ID = /^[A-Za-z0-9][A-Za-z0-9._-]*$/;

/** The app path for a cited record: only work items and projects have pages, and only a plain record id
 *  ("W-1004") becomes one; a URL or anything else in an id stays plain text. */
export function refPath(ref: Ref): string | undefined {
  if (ref.work_id) return RECORD_ID.test(ref.work_id) ? `/work/${ref.work_id}` : undefined;
  if (ref.case_id) return RECORD_ID.test(ref.case_id) ? `/projects/${ref.case_id}` : undefined;
  return undefined;
}

export const refText = (ref: Ref) => ref.label ?? ref.reference ?? '';
