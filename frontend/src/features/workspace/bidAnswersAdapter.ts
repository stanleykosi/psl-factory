// F-96: the RFP response panel on the live work item (GET /work/{id}/bid-answers), through the shared line adapter. This file
// reads (summary sections) and DESCRIBES the writes; BidAnswersActions draws the requirement rows and sends through useWorkCommand.
// Not served by the live API, so not drawn: the filters, the progress bar and the "before review" checklist.
import type { LiveBidAnswerRow, LiveBidAnswers } from '@/api/types';
import { formatDayTime } from '@/components';

import { BidAnswersActions } from './BidAnswersActions';
import { makeCommand, readPanel, type CommandDescriptor, type LineAdapter } from './adapter';
import type { Section } from './labels';

export const NO_TOKEN = 'We don’t have this response’s current version yet. Reload and try again.';
export const READ_ONLY = 'You can’t change these answers.';
export const SEND_HELD = 'Sending the response for review needs the bid pack, which this page doesn’t read yet.';

export const DISPOSITIONS = [
  ['addressed', 'Addressed'],
  ['clarification', 'Needs clarification'],
  ['out_of_scope', 'Out of scope'],
] as const;
export const dispositionWords = (d: LiveBidAnswerRow['disposition']) => DISPOSITIONS.find(([k]) => k === d)?.[1] ?? d;

const STATUS_WORDS: Record<LiveBidAnswerRow['status'], string> = {
  current: 'Current',
  queued: 'Queued',
  running: 'Tola is working',
  held: 'On hold',
  suggested: 'Suggestion ready',
  reviewed: 'Reviewed',
  stale: 'Out of date',
};
export const statusWords = (s: LiveBidAnswerRow['status']) => STATUS_WORDS[s] ?? s;

const VERDICT_WORDS: Record<string, string> = { approve: 'Approved', return: 'Returned', reject: 'Refused' };

function sections(readback: LiveBidAnswers): Section[] {
  const { counts, response_review: review, rows } = readback;
  const out: Section[] = [
    {
      key: 'counts',
      kind: 'facts',
      title: 'Requirements',
      items: [
        { id: 'total', label: 'Requirements', value: String(counts.total) },
        { id: 'answered', label: 'With an answer', value: String(counts.answered) },
        { id: 'clarification', label: 'Needing clarification', value: String(counts.clarification) },
        { id: 'reviewed', label: 'Reviewed', value: String(counts.reviewed) },
        ...(counts.visible < counts.total ? [{ id: 'hidden', label: 'Not shown to you', value: String(counts.total - counts.visible) }] : []),
        ...(rows.length < counts.total ? [{ id: 'shown', label: 'Listed below', value: String(rows.length) }] : []),
      ],
    },
  ];
  if (review) {
    out.push({
      key: 'engineering',
      kind: 'text',
      title: 'Engineering review',
      items: [
        { id: 'verdict', text: `${review.role}: ${(VERDICT_WORDS[review.verdict] ?? review.verdict).toLowerCase()}`, detail: formatDayTime(review.reviewed_at) },
        ...(review.reason ? [{ id: 'reason', text: `“${review.reason}”` }] : []),
      ],
    });
  }
  return out;
}

function commands(readback: LiveBidAnswers, ctx: { workId: number }): CommandDescriptor[] {
  const tokens = { expected_revision: readback.expected_revision, case_revision: readback.case_revision };
  const url = `/api/v1/work/${ctx.workId}/bid-answers`;
  const hold = !readback.can_write ? READ_ONLY : tokens.expected_revision == null || tokens.case_revision == null ? NO_TOKEN : undefined;
  const spec = { url, tokens, ...(hold ? { disabledReason: hold } : {}) };
  return [
    makeCommand({ ...spec, id: 'bid-answers.review', label: 'Save answer', successStatuses: [201] }),
    makeCommand({ ...spec, id: 'bid-answers.undo', label: 'Undo', successStatuses: [201] }),
    // one descriptor per requirement: each carries its own operation key, so asking for another is never the same request
    ...readback.rows.map((row) => makeCommand({ ...spec, id: `bid-answers.suggest.${row.key}`, action: 'suggest', keyField: 'operation_key', fixed: { key: row.key }, label: 'Ask Tola', successStatuses: [201] })),
  ];
}

export const bidAnswersAdapter: LineAdapter<LiveBidAnswers> = {
  key: 'bid-answers',
  read: (ref) => readPanel<LiveBidAnswers>(ref),
  sections: (readback) => sections(readback),
  commands: (readback, ctx) => commands(readback, ctx),
  Actions: BidAnswersActions,
};
