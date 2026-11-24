// CountBadge (design/system/project/components/CountBadge): a count in a small mono square. Zero shows "0", never
// hidden, so "none" reads differently from "not loaded". Ink where the boards draw a count of filters on (D-93);
// orange only for things that need the person.
import { cx } from './internal';

export function CountBadge({ count, atLeast = false, tone = 'default', className }: { count: number; /** The server counted some but not all: "12+", named "at least 12". */ atLeast?: boolean; tone?: 'default' | 'onDark' | 'signal' | 'ink'; className?: string }) {
  return (
    <span className={cx('psl-badge', tone === 'onDark' && 'psl-badge--on-dark', tone === 'signal' && 'psl-badge--signal', tone === 'ink' && 'cmp-badge--ink', className)} {...(atLeast ? { role: 'img', 'aria-label': `at least ${count}` } : {})}>
      {atLeast ? `${count}+` : count}
    </span>
  );
}
