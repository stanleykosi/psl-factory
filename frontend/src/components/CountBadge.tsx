// CountBadge (design/system/project/components/CountBadge): a count in a small mono square. Zero shows "0", never
// hidden, so "none" reads differently from "not loaded". Orange only for things that need the person.
import { cx } from './internal';

export function CountBadge({ count, tone = 'default', className }: { count: number; tone?: 'default' | 'onDark' | 'signal'; className?: string }) {
  return <span className={cx('psl-badge', tone === 'onDark' && 'psl-badge--on-dark', tone === 'signal' && 'psl-badge--signal', className)}>{count}</span>;
}
