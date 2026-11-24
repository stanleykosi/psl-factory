// F-85: the weekly report panel, read only (GET /work/{id}/weekly-report), as the reference line adapter.
// Every write on this panel (review, correct) is F-87; `commands()` only describes `correct`.
import type { LiveWeeklyReport } from '@/api/types';
import { formatDayTime } from '@/components';

import { makeCommand, readPanel, type LineAdapter } from './adapter';
import type { Item, Section } from './labels';

export const NOT_RECORDED = 'Not recorded';

const PARTS = [
  ['status', 'Status'],
  ['risks', 'Risks'],
  ['timeline', 'Timeline'],
  ['next_steps', 'Next steps'],
] as const;

type Parts = NonNullable<LiveWeeklyReport['editable_parts']>;

const citeText = (n: number) => `${n} ${n === 1 ? 'record' : 'records'} cited`;
const when = (value: string | null | undefined) => (value ? formatDayTime(value) : NOT_RECORDED);

/** The parts to show: the editable parts, else the draft's parts (same shape), else none. */
function partsOf(report: LiveWeeklyReport): Parts | null {
  return report.editable_parts ?? report.draft?.values.parts ?? null;
}

function sections(report: LiveWeeklyReport): Section[] {
  const out: Section[] = [
    {
      key: 'period',
      kind: 'facts',
      title: 'Period',
      items: [
        { id: 'from', label: 'From', value: when(report.selection.start_at) },
        { id: 'to', label: 'To', value: when(report.selection.end_at) },
      ],
    },
  ];
  const parts = partsOf(report);
  if (parts) {
    out.push({
      key: 'parts',
      kind: 'text',
      title: report.editable_parts ? 'Report parts' : 'Draft',
      items: PARTS.map(([key, label]): Item => ({ id: key, text: `${label}: ${parts[key].text || NOT_RECORDED}`, detail: citeText(parts[key].evidence_ids.length) })),
    });
  }
  if (report.return_review_id !== null) {
    out.push({ key: 'returned', kind: 'text', title: 'Review', items: [{ id: 'returned', text: 'Returned to you' }] });
  }
  out.push({
    key: 'recipients',
    kind: 'recipients',
    title: 'Recipients',
    items: report.recipients.map(
      (r, i): Item => ({
        id: String(i),
        text: r.name,
        tag: r.receipt_id === null ? { label: 'No receipt yet', tone: 'neutral' } : { label: 'Receipt recorded', tone: 'verified' },
        ...(r.recorded_at ? { at: r.recorded_at } : {}),
      }),
    ),
  });
  if (report.next_action) out.push({ key: 'next', kind: 'text', title: 'Next', items: [{ id: 'next', text: report.next_action }] });
  return out;
}

export const weeklyReportAdapter: LineAdapter<LiveWeeklyReport> = {
  key: 'weekly-report',
  read: (ref) => readPanel<LiveWeeklyReport>(ref),
  sections: (report) => sections(report),
  commands: (report, ctx) => [
    makeCommand({
      id: 'weekly-report.correct',
      label: 'Correct the report',
      url: `/api/v1/work/${ctx.workId}/weekly-report`,
      tokens: { expected_revision: report.expected_revision, case_revision: report.case_revision },
      ...(report.can_correct ? {} : { disabledReason: 'This report can’t be corrected now.' }),
      successStatuses: [201],
    }),
  ],
};
