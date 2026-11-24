// Types of the live work list, derived from the generated live contract (no hand copies, no edit to src/api).
import type { operations } from '@/api/live-schema';

type ListOperation = operations['work_queue'];
type ListQuery = NonNullable<ListOperation['parameters']['query']>;

/** One page of GET /api/v1/work. */
export type WorkListPage = ListOperation['responses'][200]['content']['application/json'];
/** One row: `id` is the integer the work item route takes (`/work/{id}`). */
export type WorkListRow = WorkListPage['items'][number];
export type WorkQueue = NonNullable<ListQuery['queue']>;
export type LineKey = NonNullable<ListQuery['line']>;
/** Every state a row can carry; labels.ts must name each one. */
export type WorkState = WorkListRow['state'];
export type WorkLine = WorkListPage['lines'][number];

/** Rows per page the server accepts; no `limit` means the server's own default. */
export type WorkLimit = NonNullable<ListQuery['limit']>;

/** What narrows a queue; any change restarts the list from page 1. */
export type WorkListFilters = { line?: LineKey; q?: string; project?: string; state?: WorkState; limit?: WorkLimit };

/** GET /api/v1/work/counts: the person's whole queues and per-line summaries. */
export type WorkCounts = operations['work_counts']['responses'][200]['content']['application/json'];
export type QueueCount = WorkCounts['queues'][number];

/** `evaluated` is the count of work items the server looked at, never a total of rows. */
export type WorkCoverage = { limited: boolean; evaluated: number; deferredCount: number };

/** idle: nothing more to ask for here; keep-looking: ten empty pages in a row, more may follow; done: the list is complete. */
export type MoreState = 'idle' | 'loading' | 'failed' | 'keep-looking' | 'done';
