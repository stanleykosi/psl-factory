'use client';

import { Button } from '@/components';

/** The footer under a cursor- or page-read list: what is shown, a failure line when the last read failed, and Show more. */
export function MoreFooter({ text, hasMore, busy, failed, onMore, className }: { text?: string; hasMore: boolean; busy: boolean; failed: boolean; onMore: () => void; className?: string }) {
  return (
    <div className={className ? `projects__more ${className}` : 'projects__more'}>
      {text && (
        <span className="projects__morecount" aria-live="polite">
          {text}
        </span>
      )}
      {failed && (
        <p className="projects__morefail" role="alert">
          We couldn’t load more. Your rows are safe; try again.
        </p>
      )}
      {hasMore && (
        <Button kind="secondary" busy={busy} busyLabel="Loading…" onClick={onMore} data-more="">
          {failed ? 'Retry' : 'Show more'}
        </Button>
      )}
    </div>
  );
}
