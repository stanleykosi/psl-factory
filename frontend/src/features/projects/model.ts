// Projects (SCR-22 list, SCR-07 journey): view state, the live GET /projects query and response checks. Pure functions only.
// Every value is shown as the live API sends it; an absent one reads "Not available" or "Unknown", never 0.
import type { operations } from '@/api/live-schema';

type ListOperation = operations['workspaces_projects'];
export type ProjectsQuery = NonNullable<ListOperation['parameters']['query']>;
export type ProjectList = ListOperation['responses'][200]['content']['application/json'];
export type ProjectRow = ProjectList['items'][number];
export type Journey = operations['workspaces_project']['responses'][200]['content']['application/json'];
export type JourneyItem = Journey['items'][number];
export type JourneyTabInfo = Journey['tabs'][number];
export type ListTab = NonNullable<ProjectsQuery['status']>;

export type ProjectTab = 'journey' | 'delivery' | 'milestones' | 'documents' | 'money' | 'registers' | 'actions';

// The project's tabs as drawn on SCR-07, each a link to its own address. Journey is built here; the other tabs' contents
// belong to their own features. Delivery has no live tab; visibleTabs adds it after Journey for every project.
export const PROJECT_TABS: readonly { key: ProjectTab; label: string; path: string }[] = [
  { key: 'journey', label: 'Journey', path: '' },
  { key: 'delivery', label: 'Delivery', path: '/delivery' },
  { key: 'milestones', label: 'Milestones', path: '/milestones' },
  { key: 'documents', label: 'Documents', path: '/documents' },
  { key: 'money', label: 'Money', path: '/money' },
  { key: 'registers', label: 'Registers', path: '/registers' },
  { key: 'actions', label: 'Actions', path: '/actions' },
];

/** The live `tabs[]` keys the frontend routes; Templates, Month-end and HR are not in the bar, and Delivery is added by visibleTabs. */
const BAR_TABS = PROJECT_TABS.filter((t) => t.key !== 'delivery');

/** The bar's tabs: the keys live returned that the frontend routes, in the order returned, with Delivery after Journey. */
export function visibleTabs(tabs: readonly { key: string }[]) {
  const live = tabs.flatMap(({ key }) => BAR_TABS.filter((t) => t.key === key));
  const at = live.findIndex((t) => t.key === 'journey');
  return at < 0 ? live : [...live.slice(0, at + 1), PROJECT_TABS[1], ...live.slice(at + 1)];
}

export const LIST_TABS: readonly { key: ListTab; label: string }[] = [
  { key: 'active', label: 'Active' },
  { key: 'closed', label: 'Closed' },
  { key: 'all', label: 'All I can see' },
];
const DEFAULT_TAB = 'active' satisfies ListTab;
export const MAX_Q = 120;

export type ProjectsView = { q?: string; tab: ListTab };

/** A search the person typed or pasted, trimmed and cut at 120 characters; undefined when empty. */
export const settledQ = (value: string | null | undefined) => value?.trim().slice(0, MAX_Q).trim() || undefined;

/** Reads the view from the URL; an empty q or an unknown tab falls back to the default. An old `limit` is ignored. */
export function parseProjectsView(params: URLSearchParams): ProjectsView {
  const tab = LIST_TABS.find((t) => t.key === params.get('status'))?.key ?? DEFAULT_TAB;
  return { q: settledQ(params.get('q')), tab };
}

/** The URL search for a view; q is left out when empty and status when Active. Cursors are never written. */
export function projectsSearch(view: ProjectsView): string {
  const params = new URLSearchParams();
  if (view.tab !== DEFAULT_TAB) params.set('status', view.tab);
  if (view.q) params.set('q', view.q);
  const search = params.toString();
  return search ? `?${search}` : '';
}

/** status is always sent (the live default is All, the page's is Active); q only when it has text; no limit. */
export function buildProjectsQuery(view: ProjectsView, cursor?: string): ProjectsQuery {
  const query: ProjectsQuery = { status: view.tab };
  const q = settledQ(view.q);
  if (q) query.q = q;
  if (cursor) query.cursor = cursor;
  return query;
}

/** "Lagoon Health · patient app" -> "Lagoon Health"; undefined when the title has no " · ". */
export function clientOf(title: string): string | undefined {
  const at = title.indexOf(' · ');
  return at > 0 ? title.slice(0, at) : undefined;
}

const isText = (value: unknown) => typeof value === 'string' && value !== '';
export const textOf = (value: unknown) => (isText(value) ? (value as string) : undefined);
export const countOf = (value: unknown) => (Number.isInteger(value) && (value as number) >= 0 ? (value as number) : undefined);

/** A figure the project read may not carry (finance not readable by this person, or not given): "Not available", never 0. */
export function factText(value: number | string | null | undefined): string {
  if (typeof value === 'number') return Number.isFinite(value) ? String(value) : 'Not available';
  return textOf(value) ?? 'Not available';
}

/** WHERE IT IS: the phase, else the lifecycle, else Unknown. */
export const whereText = (row: Pick<ProjectRow, 'phase' | 'lifecycle'>) => textOf(row.phase) ?? textOf(row.lifecycle) ?? 'Unknown';

export const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`;
export const piecesText = (n: number) => plural(n, 'piece of work', 'pieces of work');

/** The whole project's counts from facts (not a page's). */
export function projectCounts(journey: Journey) {
  const { total, waiting, stopped } = journey.facts;
  return { pieces: total, waiting, stopped };
}

/** Beside the search: only the loaded rows are counted; a total from one page is not a total. */
export const shownText = (loaded: number, more: boolean) => (more ? `${loaded} shown, more available` : `${loaded} shown`);

/** A 200 body that is not a project list (for example a misrouted response) is treated as a load failure. */
export function isProjectList(body: unknown): body is ProjectList {
  const items = (body as { items?: unknown } | null)?.items;
  return Array.isArray(items) && items.every((item) => isText(item?.case_id) && isText(item?.title));
}

/** A 200 body without a text title, an items list and a facts object is a load failure. */
export function isJourney(body: unknown): body is Journey {
  const value = body as Partial<Journey> | null;
  const facts: unknown = value?.facts;
  return (
    isText(value?.title) &&
    Array.isArray(value?.items) &&
    Array.isArray(value?.tabs) &&
    typeof facts === 'object' &&
    facts !== null &&
    value.items.every((item) => Number.isInteger(item?.id) && isText(item?.line))
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
