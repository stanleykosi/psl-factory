// Project tabs (the Documents list that opens SCR-08): the E-PROJECT-TAB query, response checks and row text. Pure functions
// only. Registers and Actions read the live sections (sectionsModel); Milestones and Money have their own reads.
import type { operations } from '@/api/schema';

import type { ProjectTab } from './model';

type TabOperation = operations['E-PROJECT-TAB'];
export type TabQuery = NonNullable<TabOperation['parameters']['query']>;
export type TabResponse = TabOperation['responses'][200]['content']['application/json'];
export type DocumentRow = NonNullable<TabResponse['documents']>[number];
export type ListTab = 'milestones' | 'documents' | 'registers' | 'actions';
/** The tabs read through E-PROJECT-TAB (v7); the others have their own live reads. */
export type ReadTab = Extract<ListTab, 'documents'>;
export type TabRows = { documents: DocumentRow[] };

/** The tabs this model reads; Money keeps its own panel. */
export const hasTabContent = (tab: ProjectTab): tab is ListTab => tab === 'milestones' || tab === 'documents' || tab === 'registers' || tab === 'actions';

export type TabView = { q?: string };

/** The request: limit always, q only when settled, cursor for "Show more". */
export function buildTabQuery(view: TabView, cursor?: string, limit: TabQuery['limit'] = 10): TabQuery {
  const query: TabQuery = { limit };
  if (view.q) query.q = view.q;
  if (cursor) query.cursor = cursor;
  return query;
}

const isObject = (value: unknown): value is Record<string, unknown> => typeof value === 'object' && value !== null && !Array.isArray(value);
const isText = (value: unknown) => typeof value === 'string' && value !== '';

const ROW_CHECKS: Record<ReadTab, (row: Record<string, unknown>) => boolean> = {
  documents: (row) => isText(row.document_id) && isText(row.title) && isText(row.version) && isText(row.status),
};

/** A 200 body without the tab's typed array of well-formed rows (a misrouted response) is a load failure. */
export function isTabResponse(body: unknown, tab: ReadTab): body is TabResponse {
  if (!isObject(body)) return false;
  const rows = body[tab];
  return Array.isArray(rows) && rows.every((row) => isObject(row) && ROW_CHECKS[tab](row));
}

export const rowsOf = <T extends ReadTab>(data: TabResponse, tab: T): TabRows[T] => (data[tab] ?? []) as TabRows[T];
