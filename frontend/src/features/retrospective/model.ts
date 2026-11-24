// Project retrospective (SCR-33): view state, the save and action bodies, and the checklist words. Pure functions only.
// A value the API returns as null reads "Not recorded" or the specific wording below, never 0 or blank.
import type { ActionCreateBody, ClosureChecklist, MeetingDetail, MeetingList, MeetingOptions, MeetingSaveBody } from '@/api/types';

import { hasHeadingLine, HEADING_MESSAGE, SUMMARY_LIMIT, writeSummary, BOX_KEYS, type Boxes } from './summary';

export type { ClosureChecklist, MeetingDetail, MeetingList, MeetingOptions };
export type MeetingRow = MeetingList['items'][number];
export type MeetingAction = MeetingDetail['actions'][number];
export type Check = ClosureChecklist['checks'][number];

/** A whole-number id from text; null when there is none. Ids are never amounts, and a missing one is never 0. */
export function idOf(value: string): number | null {
  const id = /^\d+$/.test(value) ? Number.parseInt(value, 10) : Number.NaN;
  return Number.isSafeInteger(id) ? id : null;
}

/** An id the form has already checked is chosen; reaching here with none is a bug, never a 0 on the wire. */
function chosen(value: string): number {
  const id = idOf(value);
  if (id === null) throw new Error('A required id is missing.');
  return id;
}

export const PURPOSE = 'Project retrospective';
export const NOT_RECORDED = 'Not recorded';
export const NO_DEADLINE = 'No deadline set';
export const NO_OWNER = 'No owner';
export const DECISIONS_MAX = 50;
export const DECISION_TEXT_MAX = 2000;
export const ACTION_DESCRIPTION_MAX = 1000;
export const ACTION_REASON_MAX = 4000;
export const ACTION_REFERENCE_MAX = 160;
export const REFERENCE_MAX = 160;
export const NO_PROOFS = 'No supporting file is recorded for this project yet. Add the notes file to the project first.';

/** The six checks this screen's strip draws; the API's `context` and `report` checks belong to the closure screen. */
const STRIP_KEYS = ['go_live', 'hypercare', 'archive', 'handover', 'retrospective', 'finance'];

export const STATUS_WORDS: Record<Check['status'], string> = {
  current: 'Current',
  recorded: 'Recorded',
  closed: 'Closed',
  held: 'Not yet',
  unknown: 'Unknown',
  unavailable: 'Unavailable',
};

export const stripChecks = (checks: readonly Check[]) => checks.filter((check) => STRIP_KEYS.includes(check.key));

/** The pieces of a closure checklist's retrospective link: the meeting id, when the API named it. */
export function meetingIdFromUrl(url: string | null): number | null {
  const match = /\/meetings\/(\d+)(?:[/?#]|$)/.exec(url ?? '');
  return match ? idOf(match[1]) : null;
}

/** The query of the page: positive integers or nothing. */
export function positiveInt(value: string | null | undefined): number | null {
  return value && /^[1-9]\d{0,9}$/.test(value) ? idOf(value) : null;
}

const pad = (n: number) => String(n).padStart(2, '0');
/** "2026-11-23T10:00" in the device's time zone, the value the date-time field holds. */
export function localStamp(at: Date): string {
  return `${at.getFullYear()}-${pad(at.getMonth() + 1)}-${pad(at.getDate())}T${pad(at.getHours())}:${pad(at.getMinutes())}`;
}
export const defaultReference = (at: Date) => `Retrospective ${at.getFullYear()}-${pad(at.getMonth() + 1)}-${pad(at.getDate())}`;
export const defaultActionReference = (count: number) => `Retro action ${count + 1}`;

/** The instant the field means, as the API takes it; null for a value that is not a full date and time. */
export function occurredIso(stamp: string): string | null {
  if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/.test(stamp)) return null;
  const at = new Date(stamp);
  return Number.isNaN(at.getTime()) ? null : at.toISOString();
}

export type DecisionRow = { key: number; text: string; evidenceId: string; changeEvidenceId: number | null };

/** The previous version's decisions as editable rows; change_evidence_id rides along untouched. */
export function carriedDecisions(decisions: MeetingDetail['decisions']): DecisionRow[] {
  return decisions.map((d, key) => ({ key, text: d.text, evidenceId: String(d.evidence_id), changeEvidenceId: d.change_evidence_id ?? null }));
}

export type SaveDraft = {
  reference: string;
  occurredAt: string;
  /** The whole summary as one block (a saved summary with no headings), else null and the boxes are written. */
  whole: string | null;
  boxes: Boxes;
  other: string;
  participantIds: number[];
  decisions: DecisionRow[];
  evidenceId: string;
  meetingId: number | null;
};

export const draftSummary = (draft: Pick<SaveDraft, 'whole' | 'boxes' | 'other'>) => (draft.whole !== null ? draft.whole : writeSummary(draft.boxes, draft.other));

export type SaveProblems = { reference?: string; occurredAt?: string; boxes?: string; boxLines: Partial<Record<keyof Boxes, string>>; evidence?: string; decisions: Record<number, string>; any: boolean };

/** What stops Save, per field. `now` is passed so the future-time rule is testable. */
export function saveProblems(draft: SaveDraft, proofs: number, now: Date): SaveProblems {
  const out: SaveProblems = { boxLines: {}, decisions: {}, any: false };
  const reference = draft.reference.trim();
  if (reference === '') out.reference = 'Give the retrospective a reference.';
  else if (reference.length > REFERENCE_MAX) out.reference = `Use ${REFERENCE_MAX} characters or fewer.`;
  const at = occurredIso(draft.occurredAt);
  if (at === null) out.occurredAt = 'Choose when it was held.';
  else if (new Date(at).getTime() > now.getTime()) out.occurredAt = "That time hasn't happened yet.";
  const summary = draftSummary(draft);
  if (summary.trim() === '') out.boxes = 'Write in at least one box.';
  else if (summary.length > SUMMARY_LIMIT) out.boxes = `The retrospective is ${summary.length - SUMMARY_LIMIT} characters over the ${SUMMARY_LIMIT} limit.`;
  if (draft.whole === null) for (const key of BOX_KEYS) if (hasHeadingLine(draft.boxes[key])) out.boxLines[key] = HEADING_MESSAGE;
  if (proofs === 0) out.evidence = NO_PROOFS;
  else if (draft.evidenceId === '') out.evidence = 'Choose the notes file.';
  for (const row of draft.decisions) {
    if (row.text.trim() === '') out.decisions[row.key] = 'Write the decision, or remove this row.';
    else if (row.text.length > DECISION_TEXT_MAX) out.decisions[row.key] = `Use ${DECISION_TEXT_MAX} characters or fewer.`;
    else if (row.evidenceId === '') out.decisions[row.key] = 'Choose its supporting file.';
  }
  out.any = Boolean(out.reference || out.occurredAt || out.boxes || out.evidence || Object.keys(out.boxLines).length || Object.keys(out.decisions).length);
  return out;
}

/** The one POST body of a save; `revision` is the latest meetings read's. */
export function saveBody(draft: SaveDraft, revision: number): MeetingSaveBody {
  return {
    revision,
    reference: draft.reference.trim(),
    kind: 'retrospective',
    occurred_at: occurredIso(draft.occurredAt) ?? '',
    purpose: PURPOSE,
    summary: draftSummary(draft),
    participant_ids: draft.participantIds,
    decisions: draft.decisions.map((row) => {
      const base = { text: row.text, evidence_id: chosen(row.evidenceId) };
      return row.changeEvidenceId === null ? base : { ...base, change_evidence_id: row.changeEvidenceId };
    }),
    evidence_id: chosen(draft.evidenceId),
    meeting_id: draft.meetingId,
  };
}

export type ActionDraft = { description: string; ownerId: string; dueAt: string; reason: string; evidenceId: string; reference: string };

export function actionProblems(draft: ActionDraft, taken: readonly string[]): Partial<Record<keyof ActionDraft, string>> {
  const out: Partial<Record<keyof ActionDraft, string>> = {};
  if (draft.description.trim() === '') out.description = 'Describe the action.';
  else if (draft.description.length > ACTION_DESCRIPTION_MAX) out.description = `Use ${ACTION_DESCRIPTION_MAX} characters or fewer.`;
  if (draft.reason.trim() === '') out.reason = 'Say why it is needed.';
  else if (draft.reason.length > ACTION_REASON_MAX) out.reason = `Use ${ACTION_REASON_MAX} characters or fewer.`;
  if (draft.evidenceId === '') out.evidenceId = 'Choose its supporting file.';
  const reference = draft.reference.trim();
  if (reference === '') out.reference = 'Give the action a reference.';
  else if (reference.length > ACTION_REFERENCE_MAX) out.reference = `Use ${ACTION_REFERENCE_MAX} characters or fewer.`;
  else if (taken.includes(reference)) out.reference = 'Action reference already exists.';
  if (draft.dueAt !== '' && occurredIso(draft.dueAt) === null) out.dueAt = 'Choose a date and time, or leave it empty.';
  return out;
}

/** An empty deadline sends null, never a made-up date; an empty owner sends null. */
export function actionBody(draft: ActionDraft, revision: number, meetingId: number): ActionCreateBody {
  return {
    revision,
    reference: draft.reference.trim(),
    description: draft.description,
    owner_id: idOf(draft.ownerId),
    due_at: draft.dueAt === '' ? null : occurredIso(draft.dueAt),
    evidence_id: chosen(draft.evidenceId),
    reason: draft.reason,
    meeting_id: meetingId,
  };
}

export const ownerText = (action: MeetingAction) => action.current.owner?.label ?? NO_OWNER;
export const deadlineText = (action: MeetingAction, format: (value: string) => string) => (action.current.deadline ? format(action.current.deadline) : NO_DEADLINE);

export const TIMING_WORDS: Record<MeetingAction['current']['timing'], string> = { CLOSED: 'Closed', UNKNOWN: 'Timing unknown', PAUSED: 'Paused', OVERDUE: 'Overdue', NOT_DUE: 'Not due yet' };
export const STATUS_ACTION_WORDS: Record<MeetingAction['current']['status'], string> = { open: 'Open', in_progress: 'In progress', paused: 'Paused', completed: 'Completed', cancelled: 'Cancelled' };

export const moreThanShown = (options: MeetingOptions) => options.more_participants || options.more_owners || options.more_proofs;
