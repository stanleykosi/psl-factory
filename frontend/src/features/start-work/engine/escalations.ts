// F-92: the escalation requests a project offers to start from: its `workflow_intake_url` (the escalation register), `requests`,
// paged with `?page=` while `next_page` is set. Rows are worded from the served direction and target.
import { call, liveApi } from '@/api/client';

import type { OptionSource } from '../RecordPicker';
import type { LineOption } from '../types';

const capital = (word: string) => word.charAt(0).toUpperCase() + word.slice(1);

/** "Escalate to PMO · #12": the served direction (its underscore read as a hyphen) and target, and the request's id. */
export const requestLabel = (request: { id: number; direction: string; target: string }) =>
  `${capital(request.direction.replace(/_/g, '-'))} to ${request.target} · #${request.id}`;

/** A project with no `workflow_intake_url` has no register to read: an empty list. */
export function escalationSource(caseId: string, hasRegister: boolean): OptionSource {
  return async (q, cursor) => {
    if (!hasRegister) return { items: [] };
    const page = await call(liveApi.GET('/api/v1/projects/{case_id}/escalation-register', { params: { path: { case_id: caseId }, query: { page: cursor ? Number.parseInt(cursor, 10) : undefined } } }));
    const needle = q.trim().toLowerCase();
    const items = page.requests
      .map((request) => ({ value: String(request.id), label: requestLabel(request) }) as LineOption)
      .filter((option) => option.label.toLowerCase().includes(needle));
    return { items, next_cursor: page.next_page === null ? undefined : String(page.next_page) };
  };
}
