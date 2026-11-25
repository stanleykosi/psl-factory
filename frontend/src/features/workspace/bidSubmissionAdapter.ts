// F-98: the RFP submission panel on the live work item (panel key `bid-submission`, GET /work/{id}/bid-submission), read together
// with the bid pack (GET /work/{id}/bid-pack) and the item's own review tasks. This file reads (summary sections) and DESCRIBES
// the writes; BidSubmissionActions draws the controls and sends through useWorkCommand.
//   Send for review   POST /bid-pack/review-request {pack_id, version_id}
//   Approve, Return, Refuse  POST /reviews kind bid, subject document (the live API's route for an RFP pack; `kind: document` answers
//                     404 for this line) on the exact document version; the role is the open review's own
//   Send to the client  POST /bid-submission {version_id} (202)
// Not served by the live API, so not drawn: the per-part pack checklist and its sizes, the history timeline, the agent note, and the
// way a person edits the pack. HELD: recording a portal receipt (needs a proof picked from a list and an attestation the contract does
// not word).
import type { LiveBidSubmission } from '@/api/types';
import { formatDayTime } from '@/components';
import { words } from '@/features/work-item/live/model';

import { BidSubmissionActions } from './BidSubmissionActions';
import { makeCommand, readPanel, type CommandDescriptor, type LineAdapter } from './adapter';
import { NO_PACK, PACK_UNREAD, myReview, openReviews, readPackContext, sendForReviewCommand, type PackContext } from './bidPack';
import type { Section } from './labels';

export type BidSubmissionReadback = LiveBidSubmission & { context: PackContext };

export const NO_TOKEN = 'We don’t have this pack’s current version yet. Reload and try again.';
export const VERDICTS = [
  ['approve', 'Approve'],
  ['return', 'Return with a note'],
  ['reject', 'Refuse'],
] as const;
const NOT_RECORDED = 'Not recorded';

export const sizeWords = (bytes: number) => (bytes >= 1_000_000 ? `${(bytes / 1_000_000).toFixed(1)} MB` : `${Math.max(1, Math.round(bytes / 1000))} KB`);

/** Where the pack stands for the person reading: what the read says, in words. */
export function reviewState(readback: BidSubmissionReadback): string {
  const { pack } = readback.context;
  if (!pack) return NOT_RECORDED;
  if (pack.decision) return `${pack.decision.label} on ${formatDayTime(pack.decision.created_at)}`;
  if (openReviews(readback.context.tasks).length > 0) return 'With the reviewer';
  return pack.document_version_id === null ? 'Not prepared for review yet' : 'Not sent for review yet';
}

function sections(readback: BidSubmissionReadback): Section[] {
  const { pack } = readback.context;
  const out: Section[] = [];
  if (pack) {
    out.push({
      key: 'pack',
      kind: 'facts',
      title: 'Bid pack',
      items: [
        { id: 'version', label: 'Pack version', value: String(pack.number) },
        { id: 'review', label: 'Review', value: reviewState(readback) },
        ...(readback.sample ? [{ id: 'sample', label: 'Kind', value: 'A test pack, not a real bid' }] : []),
      ],
    });
    out.push({ key: 'cover', kind: 'text', title: 'Cover note', items: [{ id: 'cover', text: pack.cover_note || NOT_RECORDED }] });
    if (pack.decision?.note) out.push({ key: 'decision-note', kind: 'text', title: `${pack.decision.label}: the reviewer’s note`, items: [{ id: 'note', text: `“${pack.decision.note}”` }] });
  } else {
    out.push({ key: 'pack', kind: 'text', title: 'Bid pack', items: [{ id: 'none', text: readback.context.read === 'failed' ? PACK_UNREAD : NO_PACK }] });
  }
  const { file } = readback;
  const parts = readback.sections.map((s) => words(s.name)).join(', ');
  out.push({
    key: 'contents',
    kind: 'facts',
    title: 'What will be sent',
    items: [
      { id: 'route', label: 'Sent to', value: words(readback.route) },
      { id: 'parts', label: 'Parts', value: parts || NOT_RECORDED },
      { id: 'file', label: 'File', value: file ? sizeWords(file.size) : 'Not ready yet' },
      ...(file ? [{ id: 'checks', label: 'File checks', value: file.checks.length === 0 && file.findings.length === 0 ? 'Format, count and size are as the client asks' : 'Problems found' }] : []),
    ],
  });
  if (file && file.checks.length > 0) {
    out.push({ key: 'findings', kind: 'text', title: 'File problems', items: file.checks.map((c, i) => ({ id: String(i), text: c.message })) });
  }
  const sent = readback.submission;
  out.push({
    key: 'sending',
    kind: 'facts',
    title: 'Sending',
    items: [
      { id: 'approval', label: 'Approval recorded', value: readback.approval_recorded ? 'Yes' : 'Not yet' },
      { id: 'job', label: 'Delivery', value: readback.job_status ? words(readback.job_status) : 'Not started' },
      ...(sent
        ? [
            { id: 'at', label: 'Sent', value: formatDayTime(sent.submitted_at) },
            { id: 'late', label: 'On time', value: sent.late ? 'No, after the deadline' : 'Yes' },
            { id: 'receipts', label: 'Receipts', value: String(sent.receipt_ids.length) },
          ]
        : []),
    ],
  });
  return out;
}

/** Why the send to the client can't be pressed, or null. The server still decides who may send. */
function queueHeld(readback: BidSubmissionReadback): string | null {
  if (!readback.file) return 'The PDF for this pack isn’t ready to check yet.';
  if (readback.file.findings.length > 0 || readback.file.checks.length > 0) return 'The file checks found problems. Fix them before sending.';
  if (readback.job_id !== null) return 'This pack is already being sent.';
  return null;
}

function commands(readback: BidSubmissionReadback, ctx: { workId: number }): CommandDescriptor[] {
  const tokens = { expected_revision: readback.expected_revision, case_revision: readback.case_revision };
  const missing = tokens.expected_revision == null || tokens.case_revision == null;
  const url = (path: string) => `/api/v1/work/${ctx.workId}${path}`;
  const { pack, tasks } = readback.context;
  const out: CommandDescriptor[] = [sendForReviewCommand('bid-submission.send', ctx.workId, readback.context, tokens, null)];
  const review = myReview(tasks);
  if (review && pack && pack.document_version_id !== null && !pack.decision) {
    for (const [verdict, label] of VERDICTS) {
      if (!review.verdicts.includes(verdict)) continue;
      out.push(
        makeCommand({
          id: `bid-submission.${verdict}`,
          label,
          url: url('/reviews'),
          tokens,
          action: null,
          fixed: { kind: 'bid', subject: 'document', target_id: pack.document_version_id, role: review.role, verdict, evidence_id: null },
          ...(missing ? { disabledReason: NO_TOKEN } : {}),
          successStatuses: [200],
        }),
      );
    }
  }
  if (readback.approval_recorded && !readback.submission) {
    const held = queueHeld(readback) ?? (missing ? NO_TOKEN : null);
    out.push(
      makeCommand({
        id: 'bid-submission.queue',
        label: 'Send to the client',
        url: url('/bid-submission'),
        tokens,
        action: null,
        fixed: { version_id: readback.version_id },
        ...(held ? { disabledReason: held } : {}),
        successStatuses: [202],
      }),
    );
  }
  return out;
}

export const bidSubmissionAdapter: LineAdapter<BidSubmissionReadback> = {
  key: 'bid-submission',
  read: async (ref, ctx) => {
    const submission = await readPanel<LiveBidSubmission>(ref);
    const workId = ctx?.workId ?? Number(/\/work\/(\d+)\//.exec(ref.url)?.[1]);
    return { ...submission, context: await readPackContext(workId) };
  },
  sections: (readback) => sections(readback),
  commands: (readback, ctx) => commands(readback, ctx),
  Actions: BidSubmissionActions,
};
