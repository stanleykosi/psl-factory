// F-85: the weekly report panel, read only (GET /work/{id}/weekly-report), as the reference line adapter.
// Review and correct are described here (commands) and drawn by WeeklyReportActions (F-89); sent by useWorkCommand.
import type { LiveWeeklyReport } from '@/api/types';
import { formatDayTime } from '@/components';

import { makeCommand, readPanel, type LineAdapter } from './adapter';
import type { Item, Section } from './labels';
import { WeeklyReportActions } from './WeeklyReportActions';

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
    out.push({
      key: 'returned',
      kind: 'text',
      title: 'Review',
      items: [{ id: 'returned', text: 'Returned to you' }, ...(report.return_note ? [{ id: 'returned-note', text: `“${report.return_note}”` }] : [])],
    });
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

const NO_TOKEN = 'We don’t have this report’s current version yet. Reload and try again.';
const VERDICTS = [
  ['approve', 'Approve and send'],
  ['return', 'Return with a note'],
  ['reject', 'Refuse'],
] as const;

/** True when the report text on the page is the version a review would act on. */
export const reportTextShown = (r: LiveWeeklyReport) => r.preview !== null && r.preview.sections.length > 0 && r.preview.id === r.document_version_id;

function commands(report: LiveWeeklyReport, ctx: { workId: number }) {
  const tokens = { expected_revision: report.expected_revision, case_revision: report.case_revision };
  const missing = tokens.expected_revision == null || tokens.case_revision == null;
  const out = [
    makeCommand({
      id: 'weekly-report.correct',
      label: 'Send for review',
      url: `/api/v1/work/${ctx.workId}/weekly-report`,
      tokens,
      ...(!report.can_correct ? { disabledReason: 'This report can’t be corrected now.' } : report.editable_parts === null ? { disabledReason: 'The report parts aren’t available to edit here.' } : missing ? { disabledReason: NO_TOKEN } : {}),
      successStatuses: [201],
    }),
  ];
  if (report.document_version_id === null) return out;
  for (const [verdict, label] of VERDICTS) {
    if (!report.review_verdicts.includes(verdict)) continue;
    if (verdict === 'approve' && !reportTextShown(report)) continue;
    out.push(
      makeCommand({
        id: `weekly-report.${verdict}`,
        label,
        url: `/api/v1/work/${ctx.workId}/reviews`,
        tokens,
        action: null,
        fixed: { kind: 'document', version_id: report.document_version_id, verdict },
        ...(missing ? { disabledReason: NO_TOKEN } : {}),
        successStatuses: [200],
      }),
    );
  }
  return out;
}

export const weeklyReportAdapter: LineAdapter<LiveWeeklyReport> = {
  key: 'weekly-report',
  read: (ref) => readPanel<LiveWeeklyReport>(ref),
  sections: (report) => sections(report),
  commands: (report, ctx) => commands(report, ctx),
  Actions: WeeklyReportActions,
};
