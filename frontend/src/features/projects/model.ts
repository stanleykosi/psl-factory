// Projects (SCR-22 list, SCR-07 journey): view state, the E-PROJECTS query and response checks. Pure functions only.
import type { operations } from '@/api/schema';
import { AGENT_NAMES, formatAmount } from '@/features/decide/format';

type ListOperation = operations['E-PROJECTS'];
export type ProjectsQuery = NonNullable<ListOperation['parameters']['query']>;
export type ProjectList = ListOperation['responses'][200]['content']['application/json'];
export type ProjectRow = ProjectList['items'][number];
export type Limit = NonNullable<ProjectsQuery['limit']>;
export type Journey = operations['E-PROJECT']['responses'][200]['content']['application/json'];
export type JourneyLine = Journey['lines'][number];

// PROPOSAL fields: the SCR-22 and SCR-07 boards draw values that E-PROJECTS and E-PROJECT (v6) do not carry. The
// shapes follow architecture v7 (D-PROJECTS-VIEW, proposed); the contract mock serves them. Every one is optional and
// read through the guards below, so a body without them, or with another shape, still renders ("—" or "Not known").
export type ListTab = 'active' | 'closed' | 'all';
export type MilestoneDue = { date?: string; unknown: boolean };
export type NextMilestone = { name: string; due?: MilestoneDue };
export type ProjectRowView = ProjectRow & { reference?: string; next_milestone?: NextMilestone; needs_person?: number; stopped?: number };
export type ProjectListView = ProjectList & { items: ProjectRowView[]; counts?: Partial<Record<ListTab, number>>; total?: number };
export type FactMoney = { amount?: string; currency: string; unknown: boolean };
export type JourneyFact = { label: string; value?: string; money?: FactMoney; unknown?: boolean };
export type LineTone = 'neutral' | 'person' | 'agent' | 'stopped' | 'uncertain' | 'verified' | 'restricted';
export type JourneyLineView = JourneyLine & {
  reference?: string;
  title?: string;
  detail?: string;
  station?: { index: number; count: number; name?: string };
  status_label?: string;
  tone?: LineTone;
};
export type JourneyView = Omit<Journey, 'lines'> & {
  lines: JourneyLineView[];
  revision?: number;
  tab_counts?: { milestones?: number; documents?: number; registers?: number; actions?: number };
  pm?: { name: string; role?: string; is_you?: boolean };
  route?: string;
  work_count?: number;
  line_count?: number;
  facts?: JourneyFact[];
  agent_summary?: { agent: 'tola' | 'chidi' | 'zainab'; text: string };
};

export type ProjectTab = 'journey' | 'milestones' | 'documents' | 'money' | 'registers' | 'actions';
type CountKey = keyof NonNullable<JourneyView['tab_counts']>;

// The project's tabs as drawn on SCR-07, each a link to its own address. Journey is built here; the other tabs'
// contents belong to FE-M3-PROJECT-TABS. Counts come from tab_counts (v6 proposal); Money has none on the board.
export const PROJECT_TABS: readonly { key: ProjectTab; label: string; path: string; count?: CountKey }[] = [
  { key: 'journey', label: 'Journey', path: '' },
  { key: 'milestones', label: 'Milestones', path: '/milestones', count: 'milestones' },
  { key: 'documents', label: 'Documents', path: '/documents', count: 'documents' },
  { key: 'money', label: 'Money', path: '/money' },
  { key: 'registers', label: 'Registers', path: '/registers', count: 'registers' },
  { key: 'actions', label: 'Actions', path: '/actions', count: 'actions' },
];

export const LIMITS: Limit[] = [10, 20, 50];
const DEFAULT_LIMIT: Limit = 20;
export const LIST_TABS: readonly { key: ListTab; label: string }[] = [
  { key: 'active', label: 'Active' },
  { key: 'closed', label: 'Closed' },
  { key: 'all', label: 'All I can see' },
];
const DEFAULT_TAB = 'active' satisfies ListTab;

export type ProjectsView = { q?: string; limit: Limit; tab: ListTab };

/** Reads the view from the URL; an empty q, an invalid limit or an unknown tab falls back to the default. */
export function parseProjectsView(params: URLSearchParams): ProjectsView {
  const q = params.get('q')?.trim() || undefined;
  const limit = LIMITS.find((n) => String(n) === params.get('limit')) ?? DEFAULT_LIMIT;
  const tab = LIST_TABS.find((t) => t.key === params.get('status'))?.key ?? DEFAULT_TAB;
  return { q, limit, tab };
}

/** The URL search for a view; q is left out when empty, limit when 20 and status when Active. Cursors are never written. */
export function projectsSearch(view: ProjectsView): string {
  const params = new URLSearchParams();
  if (view.tab !== DEFAULT_TAB) params.set('status', view.tab);
  if (view.q) params.set('q', view.q);
  if (view.limit !== DEFAULT_LIMIT) params.set('limit', String(view.limit));
  const search = params.toString();
  return search ? `?${search}` : '';
}

/** PROPOSAL (v7): `status` is not an E-PROJECTS parameter in v6. */
export type ProjectsRequest = ProjectsQuery & { status?: Exclude<ListTab, typeof DEFAULT_TAB> };

/**
 * limit is always sent; q only when it has text, so the request never carries an empty q. Active, the default tab,
 * sends no status (TECH-2-2): a backend without the parameter then answers as it always has.
 */
export function buildProjectsQuery(view: ProjectsView, cursor?: string): ProjectsRequest {
  const query: ProjectsRequest = { limit: view.limit };
  if (view.tab !== DEFAULT_TAB) query.status = view.tab;
  const q = view.q?.trim();
  if (q) query.q = q;
  if (cursor) query.cursor = cursor;
  return query;
}

/** "Lagoon Health · patient app" -> "Lagoon Health". */
export const clientOf = (journey: JourneyView) => journey.title.split(' · ')[0];

/** The journey's pieces of work and the lines they run on: work_count and line_count when sent, else from the lines. */
export function workCounts(journey: JourneyView) {
  return {
    pieces: countOf(journey.work_count) ?? journey.lines.length,
    lines: countOf(journey.line_count) ?? new Set(journey.lines.map((l) => l.line)).size,
  };
}

const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`;
export const piecesText = (n: number) => plural(n, 'piece of work', 'pieces of work');
export const linesText = (n: number) => plural(n, 'line', 'lines');

/** Footer text once the last page is loaded; there is no total, so only loaded rows are counted. */
export const allShowingText = (loaded: number) => `All ${loaded} showing`;
export const shownText = (loaded: number) => `${loaded} shown`;

const isText = (value: unknown) => typeof value === 'string' && value !== '';

// Guards for the PROPOSAL fields: each returns undefined unless the value has the drafted v7 shape (TECH-2-1).
type Loose = Record<string, unknown>;
const isObject = (value: unknown): value is Loose => typeof value === 'object' && value !== null && !Array.isArray(value);

export const textOf = (value: unknown) => (isText(value) ? (value as string) : undefined);
export const countOf = (value: unknown) => (Number.isInteger(value) && (value as number) >= 0 ? (value as number) : undefined);

const DAY_MONTH = new Intl.DateTimeFormat('en-GB', { day: '2-digit', month: 'short', timeZone: 'UTC' });

/** "UAT sign-off · due 14 Nov"; "· due not known" when the due date is unknown; undefined unless a name is sent. */
export function nextMilestoneText(value: unknown): string | undefined {
  if (!isObject(value) || !isText(value.name)) return undefined;
  const due = isObject(value.due) ? value.due : undefined;
  const date = due && !due.unknown && isText(due.date) ? new Date(`${due.date as string}T00:00:00Z`) : undefined;
  if (date && !Number.isNaN(date.getTime())) return `${value.name as string} · due ${DAY_MONTH.format(date)}`;
  if (due?.unknown === true) return `${value.name as string} · due not known`;
  return value.name as string;
}

export const pmNameOf = (value: unknown) => (isObject(value) ? textOf(value.name) : undefined);

/** The facts the response sends, in its order; undefined when it sends none or not as a list of labelled facts. */
export function factsOf(value: unknown): JourneyFact[] | undefined {
  if (!Array.isArray(value)) return undefined;
  const facts = value.filter((f): f is JourneyFact => isObject(f) && isText(f.label));
  return facts.length > 0 ? facts : undefined;
}

/** A fact's words; undefined (shown "Not known", never 0) when it is unknown or carries no readable value. */
export function factText(fact: JourneyFact | undefined): string | undefined {
  if (!fact || fact.unknown === true) return undefined;
  if (isObject(fact.money) && isText(fact.money.currency) && typeof fact.money.unknown === 'boolean') {
    return formatAmount(fact.money as FactMoney) ?? undefined;
  }
  return textOf(fact.value);
}

/** The fact with this label, matched without regard to case. */
export const findFact = (facts: JourneyFact[] | undefined, label: string) =>
  facts?.find((f) => f.label.toLowerCase() === label.toLowerCase());

/** "Station 4 of 7 · Finance review" from a line's station, when it sends no detail. */
export function lineDetail(line: JourneyLineView): string | undefined {
  const detail = textOf(line.detail);
  if (detail) return detail;
  const station: unknown = line.station;
  if (!isObject(station)) return undefined;
  const index = countOf(station.index);
  const count = countOf(station.count);
  if (!index || !count) return undefined;
  const name = textOf(station.name);
  return name ? `Station ${index} of ${count} · ${name}` : `Station ${index} of ${count}`;
}

const AGENT_ROLES: Record<string, string> = { tola: 'PMO agent', chidi: 'Finance agent' };

/** The agent summary as name, role and paragraphs (blank lines split the text); undefined unless agent and text are sent. */
export function agentSummaryOf(value: unknown) {
  if (!isObject(value) || !isText(value.agent) || !Object.hasOwn(AGENT_NAMES, value.agent as string) || !isText(value.text)) {
    return undefined;
  }
  const agent = value.agent as keyof typeof AGENT_NAMES;
  const paragraphs = (value.text as string).split(/\n\s*\n/).map((p) => p.trim()).filter(Boolean);
  return { name: AGENT_NAMES[agent], role: AGENT_ROLES[agent] as string | undefined, paragraphs };
}

/** A 200 body that is not a project list (for example a misrouted response) is treated as a load failure. */
export function isProjectList(body: unknown): body is ProjectListView {
  const items = (body as { items?: unknown } | null)?.items;
  return Array.isArray(items) && items.every((item) => isText(item?.case_id) && isText(item?.title));
}

export function isJourney(body: unknown): body is JourneyView {
  const value = body as Partial<Journey> | null;
  return (
    isText(value?.title) &&
    isText(value?.next) &&
    Array.isArray(value?.lines) &&
    value.lines.every((line) => isText(line?.line) && isText(line?.work_id))
  );
}

/** Next hands the route segment still percent-encoded; decode it once so the client encodes it only once (QA-1-1). */
export function routeCaseId(segment: string): string {
  try {
    return decodeURIComponent(segment);
  } catch {
    return segment;
  }
}
