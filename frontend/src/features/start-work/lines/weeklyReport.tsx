'use client';

// SCR-04-*-weekly: Project (the shell's), Week and Reference. The week is the date range control's days;
// period is sent as offset datetimes (localMidnight); the template and content ids are always null (no name or list is served, backend question LC-6). `background` is not sent.
import { IntakeField } from '../IntakeField';
import type { RangeValue } from '../intake';
import type { Field, WeeklyBody } from '../types';
import type { LineForm, LineFormProps } from './index';

export const WEEKLY_KEY = 'pmo-weekly-report/v1';

const WEEK = { name: 'week', label: 'Week', type: 'date_range', required: true } as Field;
const REFERENCE = { name: 'reference', label: 'Reference', type: 'text', required: true } as Field;

/** The server wants each end of the period with an explicit offset (apps/workflows/factory_reporting.py). The contract names no
 *  timezone, so the week is read as the browser's local days: it starts at local midnight of the first day and ends at local
 *  midnight after the last day (the last day is included). An engineering reading, not a business rule. */
export function localMidnight(day: string, plusDays = 0): string {
  const [y, m, d] = day.split('-').map((part) => Number.parseInt(part, 10));
  const at = new Date(y, m - 1, d + plusDays);
  const two = (n: number) => String(Math.abs(n)).padStart(2, '0');
  const offset = -at.getTimezoneOffset();
  return `${at.getFullYear()}-${two(at.getMonth() + 1)}-${two(at.getDate())}T00:00:00${offset < 0 ? '-' : '+'}${two(Math.trunc(offset / 60))}:${two(offset % 60)}`;
}

const rangeOf = (value: unknown): RangeValue => (value && typeof value === 'object' && 'from' in value ? (value as RangeValue) : { from: '', to: '' });
const textOf = (value: unknown) => (typeof value === 'string' ? value : '');

function WeeklyFields({ values, setValue, errors, readOnly }: LineFormProps) {
  return (
    <>
      <IntakeField lineKey={WEEKLY_KEY} field={WEEK} value={rangeOf(values.week)} onChange={(v) => setValue('week', v)} parent={undefined} parentLabel={undefined} readOnly={readOnly} error={errors.week} note={undefined} />
      <IntakeField lineKey={WEEKLY_KEY} field={REFERENCE} value={textOf(values.reference)} onChange={(v) => setValue('reference', v)} parent={undefined} parentLabel={undefined} readOnly={readOnly} error={errors.reference} note={undefined} />
    </>
  );
}

/** The server's field names for this line's body, by control (the spec's table); a name not here is drawn as its own box. */
const TARGETS: Record<string, string> = {
  case_id: 'project',
  case_revision: 'project',
  line: 'general',
  idempotency_key: 'general',
  reference: 'reference',
  'intake.inputs.start_at': 'week',
  'intake.inputs.end_at': 'week',
  'intake.inputs': 'week',
  start_at: 'week',
  end_at: 'week',
  template_id: 'general',
  content_id: 'general',
};

export const weeklyReport: LineForm = {
  key: WEEKLY_KEY,
  startLabel: 'Start report',
  drawerTitle: 'Weekly client report',
  Form: WeeklyFields,
  missing(values) {
    const week = rangeOf(values.week);
    return [
      ...(week.from && week.to ? [] : [{ name: 'week', label: 'Week' }]),
      ...(textOf(values.reference).trim() ? [] : [{ name: 'reference', label: 'Reference' }]),
    ];
  },
  buildBody(values, ctx): WeeklyBody {
    const week = rangeOf(values.week);
    return {
      line: WEEKLY_KEY,
      case_id: ctx.caseId,
      case_revision: ctx.caseRevision,
      idempotency_key: ctx.idempotencyKey,
      intake: { inputs: { template_id: null, content_id: null, start_at: localMidnight(week.from), end_at: localMidnight(week.to, 1) } },
      reference: textOf(values.reference).trim(),
    };
  },
  target: (name) => TARGETS[name],
};
