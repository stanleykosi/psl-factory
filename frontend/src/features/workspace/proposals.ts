// PROPOSAL (D-LINE-WORKSPACE, contract mock only): two fields the frame reads ahead of the contract. They live in the
// mock fixtures and in this one typed reader; the generated types and openapi.json do not carry them, and the backend
// developer may change or refuse either (G-SCR28-1, G-SCR28-3). An absent or malformed value reads as "not supplied".
import type { Verdict } from '@/features/decide/format';
import { PROJECT_TABS } from '@/features/projects/model';

import { RECORD_ID } from './labels';
import type { Step, Workspace } from './labels';

/** G-SCR28-1 `steps[].items_default: "checked"`: the target items of an `items` step start ticked. Absent means unticked. */
export const itemsDefaultChecked = (step: Step): boolean => (step as { items_default?: unknown }).items_default === 'checked';

/** X-LINKS (G-SCR28-3) `workspace.links[]`: only the kinds the frame draws; any other kind is not drawn. `project_tab` (F-28) is a
 *  link to one of the project's tabs, drawn only for a known tab and a valid case id. */
export type WorkspaceLink =
  | { key: string; label: string; kind: 'assistant' }
  | { key: string; label: string; kind: 'project_tab'; href: string }
  | { key: string; label: string; kind: 'document'; documentId: string; version: string };

const text = (value: unknown): value is string => typeof value === 'string' && value.trim() !== '';

export function workspaceLinks(workspace: Workspace): WorkspaceLink[] {
  const list = (workspace as { links?: unknown }).links;
  if (!Array.isArray(list)) return [];
  const links: WorkspaceLink[] = [];
  for (const entry of list as { key?: unknown; label?: unknown; target?: { kind?: unknown; document_id?: unknown; version?: unknown; tab?: unknown; case_id?: unknown } }[]) {
    if (!text(entry?.key) || !text(entry.label) || typeof entry.target !== 'object' || entry.target === null) continue;
    const { key, label } = entry;
    const { kind, document_id: documentId, version, tab, case_id: caseId } = entry.target;
    if (kind === 'assistant') links.push({ key, label, kind });
    else if (kind === 'project_tab') {
      const found = PROJECT_TABS.find((t) => t.key === tab);
      if (found && text(caseId) && RECORD_ID.test(caseId)) links.push({ key, label, kind, href: `/projects/${caseId}${found.path}` });
    } else if (kind === 'document' && text(documentId) && (text(version) || typeof version === 'number')) links.push({ key, label, kind, documentId, version: String(version) });
  }
  return links;
}

/** PROPOSAL (item-level `values`, F-23 UX-1-1): the current value of each field an item-scope step edits, keyed by field name
 *  (text a string, a record field {value, label}, a date "YYYY-MM-DD"). The edit form opens with them; the frame never derives them. */
export function itemValues(item: object): Record<string, unknown> {
  const values = (item as { values?: unknown }).values;
  return typeof values === 'object' && values !== null && !Array.isArray(values) ? (values as Record<string, unknown>) : {};
}

/** PROPOSAL (column `date_format: "day_month"`, F-23 UI-2-1): a date column the board writes without the year ("13 Nov"). The cells stay dates. */
export const columnDayMonth = (column: object): boolean => (column as { date_format?: unknown }).date_format === 'day_month';

/** PROPOSAL (`agent_note.warn_lines`, F-23 sign-off): the indexes of note lines the board draws as an amber warning (a line that asks the person to act). Tone comes from data, never from the words. */
export function warnLines(note: object): Set<number> {
  const list = (note as { warn_lines?: unknown }).warn_lines;
  return new Set(Array.isArray(list) ? list.filter((n): n is number => Number.isInteger(n)) : []);
}

/** PROPOSAL (`steps[].starts_line: {line_key, prefill}`, F-30 G-SCR30-1): the step opens Start work on that line, filled for the person to check. Absent or malformed reads as not supplied. */
export function startsLine(step: Step): { line_key: string; intake: Record<string, unknown> } | undefined {
  const value = (step as { starts_line?: { line_key?: unknown; prefill?: unknown } }).starts_line;
  if (typeof value !== 'object' || value === null || !text(value.line_key)) return undefined;
  const { prefill } = value;
  if (typeof prefill !== 'object' || prefill === null || Array.isArray(prefill)) return undefined;
  return { line_key: value.line_key, intake: prefill as Record<string, unknown> };
}

/** PROPOSAL (`assign.candidates[].kind`, F-30 G-SCR30-3): a candidate who is a team or an outside party, worded as the backend words it. Absent reads as a plain name. */
export const assignCandidateKind = (candidate: object): 'person' | 'team' | 'outside_party' | undefined => {
  const kind = (candidate as { kind?: unknown }).kind;
  return kind === 'person' || kind === 'team' || kind === 'outside_party' ? kind : undefined;
};

/** PROPOSAL (`steps[].verdict`, F-33 G-C-1): a decision step's verdict, decided in place through E-TASK-CLAIM and E-TASK-DECIDE.
 *  Read only on a step with `task_id`. `undefined`: no proposal (the existing decision-page link); `null`: a value the
 *  page does not offer (e.g. `revoke`), so the step is not drawn. */
export function stepVerdict(step: Step): Verdict | null | undefined {
  if (!step.task_id || !Object.hasOwn(step, 'verdict')) return undefined;
  const value = (step as { verdict?: unknown }).verdict;
  return value === 'approve' || value === 'return' || value === 'reject' ? value : null;
}
