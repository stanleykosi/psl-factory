// F-101: the income schedule panel (key 'finance-schedule', GET /work/{id}/finance-schedule) on the live work item: stage, finding,
// income rows, the result, held duplicates, returned rows and why a review has not started. The review decision is described here
// and drawn by IncomeScheduleReview; sent by useWorkCommand. Presentation only: which verdicts are offered is the read's
// `review_verdicts`, and whether a review can start is its `review_hold_code`. A null amount reads Unknown, never 0; amounts are the
// server's strings, shown as given with their unit, and nothing is added, subtracted or counted. Not drawn: "posted to the
// ledger" (no field), exports, correct and resubmit, settling a duplicate (F-101B).
import type { LiveSchedule } from '@/api/types';
import { formatAmount } from '@/components';

import { makeCommand, readPanel, registerLineAdapter, type CommandDescriptor, type LineAdapter } from './adapter';
import { IncomeScheduleReview } from './IncomeScheduleReview';
import type { Item, Section } from './labels';

export const UNKNOWN = 'Unknown';
export const NO_TOKEN = 'We don’t have this schedule’s current version yet. Reload and try again.';
export const NO_SCHEDULE = 'There is no schedule to review yet.';
export const HOLD_TEXT = {
  reviewer_missing: 'Nobody is set to review schedules yet. The review starts when an admin sets who reviews schedules.',
  review_rule_missing: 'The schedule review rule isn’t set up yet. The review starts when an admin sets it up.',
} as const;

export const VERDICTS = [
  ['approve', 'Approve'],
  ['return', 'Return'],
  ['reject', 'Reject'],
  ['revoke', 'Withdraw approval'],
] as const;
export type Verdict = (typeof VERDICTS)[number][0];

const RELATIONSHIP: Record<string, string> = { disaggregation: 'Disaggregation', reclassification: 'Reclassification', additive: 'Additive' };
const DUPLICATE: Record<string, string> = { not_assessed: 'Not checked', already_represented: 'Already included', separately_justified: 'Justified separately' };

/** A code as the server sent it, lightly capitalised; text we do not know is kept as given. */
export const codeText = (code: string) => {
  const text = code.replaceAll('_', ' ').trim();
  return text ? text.charAt(0).toUpperCase() + text.slice(1) : UNKNOWN;
};
const word = (table: Record<string, string>, value: string) => table[value] ?? codeText(value);

/** An amount as given, with its unit; null (or a string we cannot read) is unknown, never 0. */
export function amountText(value: string | null | undefined, unit: string | null | undefined): string {
  if (value === null || value === undefined || value === '') return UNKNOWN;
  const shown = formatAmount(value, { sign: false });
  const text = shown === UNKNOWN ? value : shown;
  return unit ? `${text} ${unit}` : text;
}

/** The decide panel is drawn only when nothing holds the review and the read offers at least one known verdict (the list is the server's answer; `review_id` is not a gate, a verified schedule offers Withdraw approval without one). */
export const offeredVerdicts = (s: LiveSchedule): Verdict[] =>
  s.review_hold_code === null && s.schedule_id !== null ? VERDICTS.map(([v]) => v).filter((v) => s.review_verdicts.includes(v)) : [];

const lines = (id: string, texts: string[]): Item[] => texts.map((text, i) => ({ id: `${id}-${i}`, text }));

export function scheduleSections(s: LiveSchedule): Section[] {
  const out: Section[] = [];
  const found = [s.stage, s.finding].filter((t) => t.trim() !== '');
  if (found.length > 0) out.push({ key: 'found', kind: 'text', title: 'What was found', items: lines('found', found) });
  if (s.review_hold_code && HOLD_TEXT[s.review_hold_code]) out.push({ key: 'hold', kind: 'text', title: 'Review', items: lines('hold', [HOLD_TEXT[s.review_hold_code]]) });

  const inc = s.income;
  if (s.kind === 'income' && inc) {
    out.push({
      key: 'schedule',
      kind: 'facts',
      title: 'The schedule',
      items: [
        { id: 'entity', label: 'Entity', value: inc.entity },
        { id: 'period', label: 'Period', value: inc.period },
        { id: 'currency', label: 'Currency', value: inc.currency },
        { id: 'line', label: 'Report line', value: inc.report_line },
        { id: 'units', label: 'Units', value: `${inc.source_unit} to ${inc.target_unit}` },
      ],
    });
    out.push({
      key: 'rows',
      kind: 'table',
      title: 'Income rows',
      columns: [
        { key: 'row', label: 'Row', kind: 'text' },
        { key: 'relationship', label: 'Relationship', kind: 'text' },
        { key: 'amount', label: 'Amount', kind: 'text' },
        { key: 'accounts', label: 'Source accounts', kind: 'text' },
        { key: 'duplicate', label: 'Duplicate check', kind: 'text' },
      ],
      items: inc.rows.map(
        (r): Item => ({
          id: r.key,
          cells: [
            { column: 'row', text: r.key },
            { column: 'relationship', text: word(RELATIONSHIP, r.relationship) },
            { column: 'amount', text: amountText(r.amount, r.unit) },
            { column: 'accounts', text: r.source_accounts.join(', ') || UNKNOWN },
            { column: 'duplicate', text: word(DUPLICATE, r.duplicate_state) },
          ],
        }),
      ),
    });
  }

  const res = s.result;
  if (res) {
    const unit = res.target_unit;
    out.push({
      key: 'result',
      kind: 'facts',
      title: 'The result',
      items: [
        { id: 'status', label: 'Result', value: res.status === 'ready' ? 'Ready' : res.status === 'held' ? 'Held' : codeText(res.status), tag: res.status === 'ready' ? { label: 'Ready', tone: 'verified' } : { label: res.status === 'held' ? 'Held' : codeText(res.status), tone: 'uncertain' } },
        { id: 'adjusted', label: 'Adjusted total', value: amountText(res.adjusted_total, unit) },
        { id: 'parent', label: 'Parent amount', value: amountText(res.parent_amount, unit) },
        { id: 'additive', label: 'Additive total', value: amountText(res.additive_total, unit) },
        { id: 'reclass', label: 'Reclassification total', value: amountText(res.reclassification_total, unit) },
      ],
    });
    if (res.findings.length > 0) out.push({ key: 'findings', kind: 'text', title: 'Findings', items: lines('findings', res.findings.map(codeText)) });
    if (res.missing_required.length > 0) out.push({ key: 'missing', kind: 'text', title: 'Still needed', items: lines('missing', res.missing_required.map(codeText)) });
  }

  if (s.duplicates.length > 0) out.push({ key: 'duplicates', kind: 'text', title: 'Possible duplicates', items: lines('dup', s.duplicates) });

  if (s.returned) {
    out.push({
      key: 'returned',
      kind: 'text',
      title: 'Returned for correction',
      items: s.returned.rows.length > 0 ? s.returned.rows.map((r, i): Item => ({ id: `ret-${i}`, text: `${r.key}: ${word(RELATIONSHIP, r.relationship)}` })) : [{ id: 'ret', text: 'This schedule was returned for correction.' }],
    });
  }

  const inv = s.inventory;
  if (s.kind === 'inventory' && inv) {
    out.push({ key: 'coverage', kind: 'facts', title: 'Coverage', items: [{ id: 'coverage', label: 'Coverage', value: inv.coverage === 'partial' ? 'Partial' : inv.coverage === 'declared_complete' ? 'Declared complete' : codeText(inv.coverage) }] });
    out.push({
      key: 'inventory',
      kind: 'table',
      title: 'Schedules in the workbook',
      columns: [
        { key: 'schedule', label: 'Schedule', kind: 'text' },
        { key: 'purpose', label: 'Purpose', kind: 'text' },
        { key: 'gaps', label: 'Gaps', kind: 'text' },
      ],
      items: inv.schedules.map(
        (x, i): Item =>
          x.restricted
            ? { id: `inv-${i}`, cells: [{ column: 'schedule', text: x.key }] }
            : { id: `inv-${i}`, cells: [{ column: 'schedule', text: x.key }, { column: 'purpose', text: x.purpose }, { column: 'gaps', text: x.gaps.join('; ') || 'None listed' }] },
      ),
    });
  }
  return out;
}

export function scheduleCommands(s: LiveSchedule, ctx: { workId: number }): CommandDescriptor[] {
  const tokens = { expected_revision: s.expected_revision, case_revision: s.case_revision };
  const disabledReason = tokens.expected_revision == null || tokens.case_revision == null ? NO_TOKEN : s.schedule_id === null ? NO_SCHEDULE : undefined;
  return [
    makeCommand({
      id: 'income-schedules.review',
      label: 'Record a decision',
      url: `/api/v1/work/${ctx.workId}/reviews`,
      tokens,
      // the body has no `action`: verdict, evidence_id and note come from the press; kind and target are fixed here
      action: null,
      fixed: { kind: 'schedule', target_id: s.schedule_id },
      ...(disabledReason ? { disabledReason } : {}),
      successStatuses: [200],
    }),
  ];
}

export const incomeSchedulesAdapter: LineAdapter<LiveSchedule> = {
  key: 'finance-schedule',
  read: (ref) => readPanel<LiveSchedule>(ref),
  sections: (s) => scheduleSections(s),
  commands: (s, ctx) => scheduleCommands(s, ctx),
  Actions: IncomeScheduleReview,
};

registerLineAdapter(incomeSchedulesAdapter as LineAdapter);
