// SCR-38 Milestones tab: the contract stages of GET /projects/{case_id}/money, the recorded completions of
// GET /projects/{case_id}/milestones and the one-completion read, with their guards and the words shown. Pure functions
// only. A table row is joined to a completion only through `milestone_id` (never by name or date); nothing is totalled or
// inferred from another fact (INV-UNKNOWN, INV-FACTS).
import type { operations } from '@/api/live-schema';
import { formatDayMonth, UNKNOWN } from '@/components';

import { amountText, isObject, type MoneyChange, type MoneyItem } from './moneyModel';

export type Completions = operations['workspaces_project_tab']['responses'][200]['content']['application/json'];
export type CompletionSection = Completions['sections'][number];
export type CompletionRow = CompletionSection['items'][number];
export type Completion = operations['project_operations_milestone']['responses'][200]['content']['application/json'];

const textOrNull = (value: unknown) => value === null || typeof value === 'string';

function isRow(value: unknown): value is CompletionRow {
  return isObject(value) && typeof value.title === 'string' && typeof value.state === 'string' && textOrNull(value.detail) && textOrNull(value.at) && Number.isInteger(value.record_id);
}

/** The tab's single section of recorded completions (found by being the only one, never by its title); no section is none recorded yet. */
export function isCompletions(body: unknown): body is Completions {
  if (!isObject(body) || typeof body.as_of !== 'string' || !Array.isArray(body.sections) || body.sections.length > 1) return false;
  if (body.sections.length === 0) return true;
  const section: unknown = body.sections[0];
  return isObject(section) && Array.isArray(section.items) && section.items.every(isRow) && Number.isInteger(section.page) && typeof section.has_more === 'boolean';
}

/** The one recorded completion read for a proof button. */
export function isCompletion(body: unknown): body is Completion {
  return isObject(body) && Number.isInteger(body.id) && typeof body.name === 'string' && typeof body.completed_at === 'string' && Number.isInteger(body.proof_version);
}

/** The contract stages of a money body, in the order sent; invoices outside any stage are not milestones. */
export const contractStages = (items: MoneyItem[]) => items.filter((item) => item.contract_stage);

/** "Done 27 Oct" from `completed_at`, "Not completed" when it is null; never worked out from a due date. */
export function completionText(item: Pick<MoneyItem, 'completed_at'>): string {
  if (item.completed_at === null) return 'Not completed';
  const day = formatDayMonth(item.completed_at);
  return day === UNKNOWN ? 'Done' : `Done ${day}`;
}

/** "Due 30 Oct"; undefined without a due date. Never compared with today. */
export function dueText(item: Pick<MoneyItem, 'due_date'>): string | undefined {
  if (item.due_date === null) return undefined;
  const day = formatDayMonth(item.due_date);
  return day === UNKNOWN ? undefined : `Due ${day}`;
}

/** The recorded completion a stage points to through `milestone_id`, when the loaded page holds it. */
export function completionFor(item: Pick<MoneyItem, 'milestone_id'>, rows: CompletionRow[]): CompletionRow | undefined {
  return item.milestone_id === null ? undefined : rows.find((row) => row.record_id === item.milestone_id);
}

/** "Recorded by Tunde Bello"; undefined when the row does not say who. */
export const recordedByText = (row: Pick<CompletionRow, 'detail'>): string | undefined => (row.detail === null ? undefined : `Recorded by ${row.detail}`);

/** "Done 27 Oct" / "Completed 27 Oct" for a recorded completion read. */
export function completedText(completion: Pick<Completion, 'completed_at'>): string {
  const day = formatDayMonth(completion.completed_at);
  return day === UNKNOWN ? 'Completed' : `Completed ${day}`;
}

/** The change as text: its reference and note as sent. */
export const changeText = (change: Pick<MoneyChange, 'reference' | 'note'>): string => [change.reference, change.note].filter(Boolean).join(' · ');

/** The contract amount as text, or undefined (drawn Unknown). */
export const contractAmount = (item: Pick<MoneyItem, 'amount' | 'currency'>) => amountText(item.amount, item.currency);

/** The CHANGES column shows only when some stage has a change. */
export const hasChanges = (items: MoneyItem[]) => items.some((item) => item.changes.length > 0);

// SCR-19 Mark a milestone complete: the options read, the 201 of the write, and the words shown.
export type CompletionOptions = operations['project_operations_milestone_options']['responses'][200]['content']['application/json'];
export type RecordedCompletion = operations['project_operations_record_milestone']['responses'][201]['content']['application/json'];
export type Hold = NonNullable<CompletionOptions['hold']>;
export type ProofChoice = CompletionOptions['proofs'][number];

const HOLDS: readonly unknown[] = ['baseline_required', 'proof_required', 'name_in_use'];

/** The options read; a body missing a field is not drawn (no partial data). */
export function isCompletionOptions(body: unknown): body is CompletionOptions {
  if (!isObject(body) || !Number.isInteger(body.revision) || !Array.isArray(body.proofs)) return false;
  const proofs = body.proofs.every((p: unknown) => isObject(p) && Number.isInteger(p.id) && typeof p.label === 'string');
  const next = body.next_page === null || Number.isInteger(body.next_page);
  return proofs && next && typeof body.can_complete === 'boolean' && typeof body.can_attach_pdf === 'boolean' && (body.hold === null || HOLDS.includes(body.hold));
}

/** The 201 of the write. It is not shown as "recorded"; it only names the completion to re-read. */
export function isRecordedCompletion(body: unknown): body is RecordedCompletion {
  return isObject(body) && Number.isInteger(body.id) && Number.isInteger(body.revision) && typeof body.name === 'string' && Number.isInteger(body.evidence_id);
}

/** Plain words for each hold; the server's own message and the raw code are never shown. */
export const HOLD_WORDS: Record<Hold, string> = {
  baseline_required: 'This project has no signed baseline yet. A milestone can be completed once the SOW baseline is signed.',
  proof_required: 'There is no proof on record for this milestone yet.',
  name_in_use: 'A completion with this name is already recorded.',
};
export const NO_AUTHORITY = 'You can’t mark this milestone complete.';

/** The reason shown instead of the control: the hold's words, or the no-authority line when the server says no without a hold. */
export const holdText = (options: Pick<CompletionOptions, 'can_complete' | 'hold'>): string | undefined =>
  options.hold !== null ? HOLD_WORDS[options.hold] : options.can_complete ? undefined : NO_AUTHORITY;

/** The milestone name is 1 to 200 characters once trimmed; anything else is not a milestone to complete. */
export const usableName = (name: string | null | undefined): name is string => typeof name === 'string' && name.trim().length > 0 && name.length <= 200;

/** The link from a Milestones-tab row to the page; the name is the stage label exactly as /money gives it. */
export const completeHref = (caseId: string, name: string) => `/projects/${encodeURIComponent(caseId)}/milestones/complete?name=${encodeURIComponent(name)}`;
