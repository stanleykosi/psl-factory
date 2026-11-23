// F-85: the live work item (GET /work/{id}) and its history, as the page draws them. Presentation only: nothing here
// decides access or business state. A null revision stays null (unknown, never 0).
import type { LiveHistoryRow, LiveWorkItem, LiveWorkTask } from '@/api/types';

export const HISTORY_KINDS = ['worker', 'decision', 'evidence'] as const;
export type LiveHistoryKind = (typeof HISTORY_KINDS)[number] | 'all';

/** Live work ids are integers; any other id ("W-1003") is a v7 item that still has its own page. */
export const isLiveWorkId = (id: string) => /^\d+$/.test(id);

export const HISTORY_FILTERS: readonly { kind: LiveHistoryKind; label: string }[] = [
  { kind: 'all', label: 'All' },
  { kind: 'decision', label: 'Decisions' },
  { kind: 'worker', label: 'Agent work' },
  { kind: 'evidence', label: 'Evidence' },
];

/** The item is re-read while an agent is at work on it (current_activity.watching) or it is processing. */
export const needsPolling = (item: LiveWorkItem) => item.current_activity?.watching === true || item.state === 'processing';

/** The activity line: the agent's own label, else the progress status with its time. Nothing when the item carries neither. */
export function activityOf(item: LiveWorkItem): { text: string; updatedAt?: string } | null {
  if (item.current_activity?.label) return { text: item.current_activity.label };
  if (item.progress) return { text: item.progress.status, updatedAt: item.progress.updated_at };
  return null;
}

/** The page of a task's decision, only for a task this person can claim or decide; otherwise the row is read only. */
export function decisionHref(workId: number, task: LiveWorkTask): string | null {
  return task.can_decide || task.can_claim ? `/work/${workId}/decide?task=${task.id}` : null;
}

/** Station and status words come from the API as they are, with the first letter raised and underscores read as spaces. */
export function words(raw: string): string {
  const text = raw.replace(/_/g, ' ').trim();
  return text.charAt(0).toUpperCase() + text.slice(1);
}

export type HistoryLine = { at: string; station: string; status: string; actor: string | null; reason: string | null; evidenceId: number | null };

/** One history row: unknown stations and statuses stay as text, a missing actor or reason is null, a null evidence id gives no link. */
export function historyLine(row: LiveHistoryRow): HistoryLine {
  return {
    at: row.at,
    station: words(row.station),
    status: words(row.status),
    actor: row.actor ? row.actor : null,
    reason: row.reason ? row.reason : null,
    evidenceId: row.evidence_id ?? null,
  };
}

export const HISTORY_LIMIT = 30;

/** "Showing the latest 30 changes." only when exactly 30 rows came back; else everything the API has. */
export const historyCaption = (count: number) => (count === HISTORY_LIMIT ? `Showing the latest ${HISTORY_LIMIT} changes.` : 'Showing all changes.');

/** A link target the page may draw: an http(s) address or a path on this site. Anything else (javascript:, data:, //host) gets no link. */
export function safeHref(url: string | null | undefined): string | null {
  if (!url) return null;
  if (/^\/(?![/\\])/.test(url)) return url;
  try {
    const parsed = new URL(url);
    return parsed.protocol === 'https:' || parsed.protocol === 'http:' ? url : null;
  } catch {
    return null;
  }
}
