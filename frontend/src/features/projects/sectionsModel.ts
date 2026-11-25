// Registers (SCR-11), Actions (SCR-29) and Documents on the live sectioned project tab (GET /projects/{case_id}/{tab}): which sections the
// pages draw, the view in the URL, the response check, the page merge and the display text of each value. Pure functions
// only. Every number comes from the server (`total`, `counts`); nothing is counted, sorted or inferred from loaded rows.
import type { operations } from '@/api/live-schema';
import { formatDayMonth, UNKNOWN, type TagTone } from '@/components';

import { settledQ } from './model';

type TabOperation = operations['workspaces_project_tab'];
export type TabBody = TabOperation['responses'][200]['content']['application/json'];
export type Section = TabBody['sections'][number];
export type SectionItem = Section['items'][number];
export type SectionsTab = 'registers' | 'actions' | 'documents';
export type RegisterId = 'issues' | 'changes' | 'emergencies' | 'rfps';

/** The registers the board draws, in its order. A section is drawn only when its `key` is here; `title` is never matched. */
export const REGISTER_SECTIONS: readonly { id: RegisterId; label: string; word: string; key: string; count: [one: string, many: string] }[] = [
  { id: 'issues', label: 'Issues', word: 'issues', key: 'issues', count: ['ISSUE', 'ISSUES'] },
  { id: 'changes', label: 'Changes', word: 'changes', key: 'changes', count: ['CHANGE', 'CHANGES'] },
  { id: 'emergencies', label: 'Emergencies', word: 'emergencies', key: 'emergencies', count: ['EMERGENCY', 'EMERGENCIES'] },
  { id: 'rfps', label: 'RFPs', word: 'RFPs', key: 'rfp', count: ['RFP', 'RFPS'] },
];
export const ACTIONS_SECTION_KEY = 'meetings';
export const DOCUMENTS_SECTION_KEY = 'documents';

export type RegisterEntry = (typeof REGISTER_SECTIONS)[number];

const isObject = (value: unknown): value is Record<string, unknown> => typeof value === 'object' && value !== null && !Array.isArray(value);
const isText = (value: unknown) => typeof value === 'string' && value !== '';
const isCount = (value: unknown) => Number.isInteger(value) && (value as number) >= 0;

const isCounts = (value: unknown) => value === null || (isObject(value) && isCount(value.overdue) && isCount(value.unassigned) && isCount(value.total));
const isItem = (item: unknown) =>
  isObject(item) && isText(item.title) && isText(item.state) && isText(item.state_code) && (item.age_days === null || item.age_days === undefined || isCount(item.age_days));
const isSection = (section: unknown) =>
  isObject(section) &&
  isText(section.key) &&
  isText(section.title) &&
  isCount(section.total) &&
  Number.isInteger(section.page) &&
  (section.page as number) >= 1 &&
  typeof section.has_more === 'boolean' &&
  isCounts(section.counts) &&
  Array.isArray(section.items) &&
  section.items.every(isItem);

/** A 200 body that is not the sections of the requested tab, or has a malformed section or row, is a load failure. */
export function isSectionsBody(body: unknown, tab: SectionsTab): body is TabBody {
  return isObject(body) && isText(body.case_id) && body.tab === tab && Array.isArray(body.sections) && body.sections.every(isSection);
}

/** The drawn registers whose section came back, in the table's order. */
export const availableRegisters = (sections: readonly { key: string }[]): RegisterEntry[] => REGISTER_SECTIONS.filter((r) => sections.some((s) => s.key === r.key));

export type SectionView = { register?: RegisterId; q?: string };

/** From the URL: `register` only on Registers and only a drawn register; `q` trimmed, cut at 120, empty is none. */
export function parseSectionView(params: URLSearchParams, tab: SectionsTab): SectionView {
  const register = tab === 'registers' ? REGISTER_SECTIONS.find((r) => r.id === params.get('register'))?.id : undefined;
  return { register, q: settledQ(params.get('q')) };
}

/** The URL search for a view: `register` for any register but Issues, `q` when set. `page` never goes in the URL. */
export function sectionSearch(view: SectionView): string {
  const params = new URLSearchParams();
  if (view.register && view.register !== 'issues') params.set('register', view.register);
  if (view.q) params.set('q', view.q);
  const text = params.toString();
  return text ? `?${text}` : '';
}

/** The request: `q` only when set, `page` only on "Show more". Never limit, state, owner or severity. */
export function buildSectionQuery(q?: string, page?: number): { q?: string; page?: number } {
  const query: { q?: string; page?: number } = {};
  if (q) query.q = q;
  if (page) query.page = page;
  return query;
}

/** The register on show: the one the URL names when it came back, else the first that came back. */
export const selectedRegister = (available: readonly RegisterEntry[], wanted?: RegisterId): RegisterEntry | undefined => available.find((r) => r.id === wanted) ?? available[0];

const itemKey = (item: SectionItem) => `${item.api_url ?? ''}|${item.record_id}`;

/**
 * Adds a "Show more" answer to the rows held. Every section carries its own page: only one whose `page` is the page
 * asked for is new data (the others answered their last page again), so its rows are appended without any row already
 * held and it takes that answer's page, has_more, total and counts. A section that answered an earlier page keeps its
 * rows and is done (has_more false). A section the answer adds is taken whole; one it leaves out stays as held.
 */
export function mergePage(prev: readonly Section[], next: readonly Section[], requestedPage: number): Section[] {
  const merged = prev.map((held) => {
    const answer = next.find((s) => s.key === held.key);
    if (!answer) return held;
    if (answer.page !== requestedPage) return { ...held, has_more: false };
    const seen = new Set(held.items.map(itemKey));
    return { ...held, items: [...held.items, ...answer.items.filter((item) => !seen.has(itemKey(item)))], page: answer.page, has_more: answer.has_more, total: answer.total, counts: answer.counts };
  });
  return [...merged, ...next.filter((s) => !prev.some((held) => held.key === s.key))];
}

/** Actions state tag tone, from `state_code`: a display choice, not a status model. Any other code is neutral. */
export function stateTone(code: string): TagTone {
  if (code === 'open' || code === 'in_progress' || code === 'paused') return 'waiting';
  if (code === 'completed') return 'done';
  return 'neutral';
}

/** The three words the shared PriorityTag draws; any other severity ("Critical") is drawn as the word the server sent. */
export function knownPriority(text: string | null | undefined): 'high' | 'medium' | 'low' | undefined {
  const word = text?.toLowerCase();
  return word === 'high' || word === 'medium' || word === 'low' ? word : undefined;
}

/** "3d" for a known number of days (0 reads "0d"); "—" when the server sent none (an unknown age is never 0). */
export const ageText = (days: number | null | undefined): string => (Number.isInteger(days) && (days as number) >= 0 ? `${days}d` : '—');

/** "13 Nov"; undefined (the caller draws Unknown) when the due date is absent or unreadable. */
export function dueText(due: string | null | undefined): string | undefined {
  if (!due) return undefined;
  const text = formatDayMonth(due);
  return text === UNKNOWN ? undefined : text;
}

/** "From Weekly sync · 10 Nov"; nothing without a meeting the person can see. */
export function fromText(origin: SectionItem['origin_meeting'] | undefined): string | undefined {
  if (!origin || !isText(origin.reference)) return undefined;
  const day = formatDayMonth(origin.at);
  return day === UNKNOWN ? `From ${origin.reference}` : `From ${origin.reference} · ${day}`;
}

/** "3 ISSUES", "1 RFP", from the server's `total`. */
export function registerCountText(entry: RegisterEntry, total: number): string {
  return `${total} ${entry.count[total === 1 ? 0 : 1]}`;
}

/** The Actions header from the server's `counts`: "9 ACTIONS · 2 OVERDUE · 1 WITHOUT OWNER". Empty when `counts` is null. */
export function actionsHeaderText(counts: Section['counts'] | undefined): string {
  return counts ? `${counts.total} ACTIONS · ${counts.overdue} OVERDUE · ${counts.unassigned} WITHOUT OWNER` : '';
}

export const NO_OWNER = 'Owner needed';
