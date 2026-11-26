// F-116: the archive page (SCR-47) on the live work item. Turns GET /work/{id}/archive-files into the Section objects the workspace renderer
// draws, and describes the writes (reserve, look up, copy again). Presentation only: which files exist, their groups, their states and the
// actions on each come from the read; "archived and verified" is said only from `verified`. A value the read does not give reads Unknown or
// is left out, never 0.
import type { paths } from '@/api/live-schema';
import { formatDayTime } from '@/components';
import { makeCommand, type CommandDescriptor, type LineContext } from '@/features/workspace/adapter';
import type { Item, Section } from '@/features/workspace/labels';

type Get<P extends keyof paths> = paths[P] extends { get: { responses: { 200: { content: { 'application/json': infer B } } } } } ? B : never;
export type Archive = Get<'/api/v1/work/{work_id}/archive-files'>;
export type ArchiveFile = Archive['files'][number];
export type JobState = NonNullable<ArchiveFile['job']>['state'];

export const TEXT = {
  nothing: 'Nothing is waiting to be archived.',
  verifiedNext: 'Handover can start now that the archive is verified.',
  checkIntro: 'Look each file up first. Only files the archive confirms missing can be copied again.',
  review: 'Review the list, then start the archive.',
  noToken: 'We don’t have this item’s current version yet. Reload and try again.',
  noSource: 'Choose at least one source.',
  queued: 'Queued. The archive has been asked to start copying.',
  locked: 'Check the page before trying again.',
} as const;

/** The word for one file's job state; a file with no job has not started. */
export const STATE_WORDS: Record<JobState | 'none', string> = {
  confirmed: 'Archived',
  pending: 'Copying',
  leased: 'Copying',
  unknown: 'Not confirmed',
  missing: 'Missing',
  held: 'On hold',
  none: 'Not started',
};
export const stateOf = (f: ArchiveFile): JobState | 'none' => (f.job === null ? 'none' : f.job.state);

/** Worst first: a group is headlined by its worst state, so an uncertain file is never hidden behind a good one. */
const ORDER = ['unknown', 'missing', 'held', 'copying', 'archived', 'none'] as const;
type Bucket = (typeof ORDER)[number];
const bucketOf = (f: ArchiveFile): Bucket => {
  const s = stateOf(f);
  return s === 'pending' || s === 'leased' ? 'copying' : s === 'confirmed' ? 'archived' : s;
};
const BUCKET_WORDS: Record<Bucket, string> = { unknown: 'Not confirmed', missing: 'Missing', held: 'On hold', copying: 'Copying', archived: 'Archived', none: 'Not started' };
const COUNTED = new Set<Bucket>(['unknown', 'missing', 'held']);

export type Group = { name: string; files: ArchiveFile[]; state: string };

/** The group's state words: one state alone reads "Archived", "Copying", "Not started" or "Not confirmed · N"; a mix lists the worst first, each with its count. */
export function groupState(files: ArchiveFile[]): string {
  const counts = new Map<Bucket, number>();
  for (const f of files) counts.set(bucketOf(f), (counts.get(bucketOf(f)) ?? 0) + 1);
  const present = ORDER.filter((b) => counts.has(b));
  if (present.length === 1 && !COUNTED.has(present[0])) return BUCKET_WORDS[present[0]];
  return present.map((b) => `${BUCKET_WORDS[b]} · ${counts.get(b)}`).join(', ');
}

/** One group per distinct `group` text as served, in the order first seen. */
export function groupsOf(a: Archive): Group[] {
  const by = new Map<string, ArchiveFile[]>();
  for (const f of a.files) by.set(f.group, [...(by.get(f.group) ?? []), f]);
  return [...by.entries()].map(([name, files]) => ({ name, files, state: groupState(files) }));
}

const count = (a: Archive, s: JobState) => a.files.filter((f) => stateOf(f) === s).length;

/** Whether the archive is being copied: a file is waiting or leased, or the work item is processing. */
export const isWorking = (a: Archive, state: string | undefined) => state === 'processing' || a.files.some((f) => f.job?.state === 'pending' || f.job?.state === 'leased');

/** The status sentence, or null when there is nothing to say (no files, and a reservation may start). */
export function statusSentence(a: Archive, state: string | undefined): string | null {
  const total = a.files.length;
  if (a.verified) return `Archived and verified: ${total} files, each matched in the archive index.`;
  if (total === 0) return a.can_reserve ? null : TEXT.nothing;
  const unknown = count(a, 'unknown');
  const held = count(a, 'held');
  const heldNote = held > 0 ? ` ${held} ${held === 1 ? 'file is' : 'files are'} on hold.` : '';
  if (unknown > 0) return `The archive store didn’t confirm ${unknown} of ${total} files. They won’t be copied again until someone checks what arrived.${heldNote}`;
  if (state === 'effect_uncertain' || state === 'awaiting_reconciliation') return `The archive result is not confirmed.${heldNote}`;
  if (isWorking(a, state)) return `Archiving in progress. ${count(a, 'confirmed')} of ${total} files copied.${heldNote}`;
  const finding = a.finding.trim();
  return `${finding === '' ? TEXT.nothing : finding}${heldNote}`.trim();
}

const text = (id: string, value: string): Item => ({ id, text: value });

function indexSection(a: Archive): Section {
  return {
    key: 'archive-index',
    kind: 'table',
    title: 'Archive index',
    columns: [
      { key: 'group', label: 'Group', kind: 'text' },
      { key: 'files', label: 'Files', kind: 'integer' },
      { key: 'state', label: 'State', kind: 'text' },
    ],
    items: groupsOf(a).map((g): Item => ({
      id: g.name,
      cells: [
        { column: 'group', text: g.name },
        { column: 'files', text: String(g.files.length) },
        { column: 'state', text: g.state },
      ],
    })),
  };
}

export function archiveSections(a: Archive, ctx: Pick<LineContext, 'state'>): Section[] {
  const out: Section[] = [];
  const sentence = statusSentence(a, ctx.state);
  if (sentence) out.push({ key: 'status', kind: 'text', items: [text('status', sentence)] });
  if (a.files.length > 0) out.push(indexSection(a));
  const store: Item[] = [...(a.store !== null ? [text('store', `Store: ${a.store}`)] : []), ...(a.limited ? [text('limited', 'Copy limit reached')] : [])];
  if (store.length > 0) out.push({ key: 'store', kind: 'text', title: 'Archive store', items: store });
  if (a.verified) out.push({ key: 'next', kind: 'text', title: 'Next', items: [text('handover', TEXT.verifiedNext)] });
  return out;
}

// ---- what a file may be asked ----

/** "Look up" for a file the store did not confirm (or confirmed missing), only when the read lists it. A held or waiting file has none. */
export const canLookup = (f: ArchiveFile) => f.job !== null && (f.job.state === 'unknown' || f.job.state === 'missing') && f.actions.includes('lookup');
/** "Copy again" only when the read lists `retry` for that file. */
export const canRetry = (f: ArchiveFile) => f.job !== null && f.actions.includes('retry');
export const filesToCheck = (a: Archive) => a.files.filter((f) => f.job?.state === 'unknown');

export const sourceLabel = (f: ArchiveFile) => {
  if (f.source_kind === null) return null;
  const kind = f.source_kind.replaceAll('_', ' ');
  return `${kind.charAt(0).toUpperCase()}${kind.slice(1)}${f.source_id === null ? '' : ` · #${f.source_id}`}`;
};
export const receiptLabel = (f: ArchiveFile) => (f.receipt === null ? null : `Receipt ${formatDayTime(f.receipt.at)}`);

// ---- the start ----

/** The sources checked at first: the read's required ones that it also lists; nothing outside `sources` is ever sent. */
export const defaultSources = (a: Archive): number[] => a.sources.filter((s) => a.required_source_ids.includes(s.id)).map((s) => s.id);
export const chosenSources = (a: Archive, picked: number[]): number[] => a.sources.filter((s) => picked.includes(s.id)).map((s) => s.id);
export const startHeld = (a: Archive, picked: number[]): string | null => (chosenSources(a, picked).length === 0 ? TEXT.noSource : null);

// ---- the descriptors ----

export const START_ID = 'archive.reserve';
export const lookupId = (jobId: number) => `archive.lookup.${jobId}`;
export const retryId = (jobId: number) => `archive.retry.${jobId}`;
export const isArchiveId = (id: string) => id.startsWith('archive.');

/** The write descriptors, from the read. A null token is unknown: the write is disabled, never sent as 0. Bodies carry the action and the
 *  tokens and no key field. */
export function archiveCommands(a: Archive, ctx: Pick<LineContext, 'workId' | 'revision'>): CommandDescriptor[] {
  const route = `/api/v1/work/${ctx.workId}/archive-files`;
  const known = (...tokens: (number | null | undefined)[]) => (tokens.every((t) => t != null) && ctx.revision !== null ? undefined : TEXT.noToken);
  const out: CommandDescriptor[] = [];
  const hold = known(a.expected_revision, a.case_revision);
  out.push(
    makeCommand({ id: START_ID, label: 'Start archive', url: route, tokens: { expected_revision: a.expected_revision, case_revision: a.case_revision }, action: null, successStatuses: [202], ...(hold ? { disabledReason: hold } : {}) }),
  );
  for (const f of a.files) {
    if (f.job === null) continue;
    const reason = known(f.job.revision);
    const base = { url: `${route}/${f.job.id}/recovery`, tokens: { revision: f.job.revision }, successStatuses: [200 as const], ...(reason ? { disabledReason: reason } : {}) };
    if (canLookup(f)) out.push(makeCommand({ id: lookupId(f.job.id), label: 'Look up', action: 'lookup', ...base }));
    if (canRetry(f)) out.push(makeCommand({ id: retryId(f.job.id), label: 'Copy again', action: 'retry', ...base }));
  }
  return out;
}
