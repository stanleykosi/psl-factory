'use client';

// ShowMore (design/system/project/components/ShowMore): lists show 50 rows, then a footer with how many are
// showing and "Show 50 more" (or however many are left). No numbered pages. When everything shows: "All 74
// showing". Where the total is not known (a cursor list), "50 showing" and "Show more".
import { Button } from './Button';
import { cx } from './internal';

export const PAGE_SIZE = 50;

export function ShowMore({ shown, total, onMore, step = PAGE_SIZE, busy = false, hasMore, className }: {
  shown: number;
  /** undefined where the list only knows whether there is more. */
  total?: number;
  onMore: () => void;
  step?: number;
  busy?: boolean;
  /** For a list without a total: whether there is more to load. */
  hasMore?: boolean;
  className?: string;
}) {
  const more = total !== undefined ? total > shown : Boolean(hasMore);
  const text = total === undefined ? `${shown} showing` : more ? `${shown} of ${total} showing` : `All ${total} showing`;
  const label = total === undefined ? 'Show more' : `Show ${Math.min(step, total - shown)} more`;
  return (
    <div className={cx('psl-showmore', className)}>
      <span role="status">{text}</span>
      {more && (
        <Button kind="secondary" size="sm" busy={busy} busyLabel="Loading…" onClick={onMore}>
          {label}
        </Button>
      )}
    </div>
  );
}
