// Money and When: amounts and times in mono as the README writes them; the amber Unknown tag when a value is not
// known. Used in tables (Money with `sign` off where the header says ₦), facts and summaries.
import { formatAmount, formatDate, formatDateTime, formatTime, UNKNOWN } from './format';
import { cx } from './internal';

export function Unknown({ className }: { className?: string }) {
  return <span className={cx('psl-unknown', className)}>{UNKNOWN}</span>;
}

export function Money({ value, sign = true, className }: { value: string | number | null | undefined; sign?: boolean; className?: string }) {
  const text = formatAmount(value, { sign });
  if (text === UNKNOWN) return <Unknown className={className} />;
  return <span className={cx('psl-mono', className)}>{text}</span>;
}

/** A date ("17 Nov 2026"), time ("14:30 WAT") or both, in a <time> element; Unknown when missing. */
export function When({ value, show = 'date', className }: { value: string | Date | null | undefined; show?: 'date' | 'time' | 'datetime'; className?: string }) {
  const text = show === 'time' ? formatTime(value) : show === 'datetime' ? formatDateTime(value) : formatDate(value);
  if (text === UNKNOWN || value === null || value === undefined) return <Unknown className={className} />;
  const iso = value instanceof Date ? value.toISOString() : value;
  return (
    <time dateTime={iso} className={cx(show !== 'date' && 'psl-mono', className)}>
      {text}
    </time>
  );
}
