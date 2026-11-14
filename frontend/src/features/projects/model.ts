// Projects (SCR-22 list, SCR-07 journey): view state, the E-PROJECTS query and response checks. Pure functions only.
import type { operations } from '@/api/schema';

type ListOperation = operations['E-PROJECTS'];
export type ProjectsQuery = NonNullable<ListOperation['parameters']['query']>;
export type ProjectList = ListOperation['responses'][200]['content']['application/json'];
export type ProjectRow = ProjectList['items'][number];
export type Limit = NonNullable<ProjectsQuery['limit']>;
export type Journey = operations['E-PROJECT']['responses'][200]['content']['application/json'];
export type JourneyLine = Journey['lines'][number];

// PROPOSAL fields: the SCR-22 and SCR-07 boards draw values that E-PROJECTS and E-PROJECT (v4/v5) do not carry.
// The contract mock serves them (mock/projects.mjs PROPOSED_FIELDS); every one is optional, so a body without them
// still renders. revision and tab_counts are in the v6 proposal; the rest are listed for the architecture.
export type ListTab = 'active' | 'closed' | 'all';
export type ProjectRowView = ProjectRow & { next_milestone?: string; needs_person?: number; stopped?: number };
export type ProjectListView = ProjectList & { items: ProjectRowView[]; counts?: Partial<Record<ListTab, number>> };
export type JourneyFacts = {
  contract_stages?: number;
  invoices_verified?: number;
  waiting_on_people?: number;
  stopped?: number;
  next_milestone?: string;
  paid?: string;
};
export type JourneyLineView = JourneyLine & { title?: string; reference?: string; detail?: string };
export type JourneyView = Omit<Journey, 'lines'> & {
  lines: JourneyLineView[];
  revision?: number;
  tab_counts?: { milestones?: number; documents?: number; registers?: number; actions?: number };
  client?: string;
  pm?: string;
  route?: string;
  facts?: JourneyFacts;
  summary?: { agent?: string; role?: string; paragraphs: string[] };
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
const DEFAULT_TAB: ListTab = 'active';

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

/** PROPOSAL: `status` (active | closed) is not an E-PROJECTS parameter yet; All I can see sends none. */
export type ProjectsRequest = ProjectsQuery & { status?: Exclude<ListTab, 'all'> };

/** limit is always sent; q only when it has text, so the request never carries an empty q. */
export function buildProjectsQuery(view: ProjectsView, cursor?: string): ProjectsRequest {
  const query: ProjectsRequest = { limit: view.limit };
  if (view.tab !== 'all') query.status = view.tab;
  const q = view.q?.trim();
  if (q) query.q = q;
  if (cursor) query.cursor = cursor;
  return query;
}

/** "Lagoon Health · patient app" -> "Lagoon Health" when the body has no client. */
export const clientOf = (journey: JourneyView) => journey.client ?? journey.title.split(' · ')[0];

/** Counts the journey's pieces of work and the distinct lines they run on. */
export function workCounts(lines: readonly JourneyLine[]) {
  return { pieces: lines.length, lines: new Set(lines.map((l) => l.line)).size };
}

const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`;
export const piecesText = (n: number) => plural(n, 'piece of work', 'pieces of work');
export const linesText = (n: number) => plural(n, 'line', 'lines');

/** Footer text once the last page is loaded; there is no total, so only loaded rows are counted. */
export const allShowingText = (loaded: number) => `All ${loaded} showing`;
export const shownText = (loaded: number) => `${loaded} shown`;

const isText = (value: unknown) => typeof value === 'string' && value !== '';

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
