// Projects (SCR-22 list, SCR-07 journey): view state, the E-PROJECTS query and response checks. Pure functions only.
import type { operations } from '@/api/schema';

type ListOperation = operations['E-PROJECTS'];
export type ProjectsQuery = NonNullable<ListOperation['parameters']['query']>;
export type ProjectList = ListOperation['responses'][200]['content']['application/json'];
export type ProjectRow = ProjectList['items'][number];
export type Limit = NonNullable<ProjectsQuery['limit']>;
export type Journey = operations['E-PROJECT']['responses'][200]['content']['application/json'];
export type JourneyLine = Journey['lines'][number];

export const LIMITS: Limit[] = [10, 20, 50];
const DEFAULT_LIMIT: Limit = 20;

export type ProjectsView = { q?: string; limit: Limit };

/** Reads the view from the URL; an empty q or an invalid limit falls back to the default. */
export function parseProjectsView(params: URLSearchParams): ProjectsView {
  const q = params.get('q')?.trim() || undefined;
  const limit = LIMITS.find((n) => String(n) === params.get('limit')) ?? DEFAULT_LIMIT;
  return { q, limit };
}

/** The URL search for a view; q is left out when empty and limit when 20. Cursors are never written. */
export function projectsSearch(view: ProjectsView): string {
  const params = new URLSearchParams();
  if (view.q) params.set('q', view.q);
  if (view.limit !== DEFAULT_LIMIT) params.set('limit', String(view.limit));
  const search = params.toString();
  return search ? `?${search}` : '';
}

/** limit is always sent; q only when it has text, so the request never carries an empty q. */
export function buildProjectsQuery(view: ProjectsView, cursor?: string): ProjectsQuery {
  const query: ProjectsQuery = { limit: view.limit };
  const q = view.q?.trim();
  if (q) query.q = q;
  if (cursor) query.cursor = cursor;
  return query;
}

/** Footer text once the last page is loaded; there is no total, so only loaded rows are counted. */
export const allShowingText = (loaded: number) => `All ${loaded} showing`;
export const shownText = (loaded: number) => `${loaded} shown`;

const isText = (value: unknown) => typeof value === 'string' && value !== '';

/** A 200 body that is not a project list (for example a misrouted response) is treated as a load failure. */
export function isProjectList(body: unknown): body is ProjectList {
  const items = (body as { items?: unknown } | null)?.items;
  return Array.isArray(items) && items.every((item) => isText(item?.case_id) && isText(item?.title));
}

export function isJourney(body: unknown): body is Journey {
  const value = body as Partial<Journey> | null;
  return (
    isText(value?.title) &&
    isText(value?.next) &&
    Array.isArray(value?.lines) &&
    value.lines.every((line) => isText(line?.line) && isText(line?.work_id))
  );
}
