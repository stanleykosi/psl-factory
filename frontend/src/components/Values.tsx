// Money and When: amounts and times in mono as the README writes them; the amber Unknown tag when a value is not
// known. Used in tables (Money with `sign` off where the header says ₦), facts and summaries.
import { formatAmount, formatClock, formatDate, formatDateTime, formatDayMonth, formatDayTime, formatTime, formatWeekdayDayTime, UNKNOWN } from './format';
import { cx } from './internal';

export function Unknown({ className }: { className?: string }) {
  return <span className={cx('psl-unknown', className)}>{UNKNOWN}</span>;
}

export function Money({ value, sign = true, className }: { value: string | null | undefined; sign?: boolean; className?: string }) {
  const text = formatAmount(value, { sign });
  if (text === UNKNOWN) return <Unknown className={className} />;
  return <span className={cx('psl-mono', className)}>{text}</span>;
}

const SHOW = {
  date: formatDate,
  time: formatTime,
  datetime: formatDateTime,
  daytime: formatDayTime,
  weekdaytime: formatWeekdayDayTime,
  clock: formatClock,
  daymonth: formatDayMonth,
};

/**
 * A date or time in a <time> element, in the format named by `show` (see format.ts: the board's own format where a
 * board draws one); Unknown when missing.
 */
export function When({ value, show = 'date', className }: { value: string | Date | null | undefined; show?: keyof typeof SHOW; className?: string }) {
  const text = SHOW[show](value);
  if (text === UNKNOWN || value === null || value === undefined) return <Unknown className={className} />;
  const iso = value instanceof Date ? value.toISOString() : value;
  return (
    <time dateTime={iso} className={cx(show !== 'date' && show !== 'daymonth' && 'psl-mono', className)}>
      {text}
    </time>
  );
}
