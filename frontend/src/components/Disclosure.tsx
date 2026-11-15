// Disclosure (design/system/project/components/Disclosure): hides detail most people do not need (an agent's
// suggestion that was not used, an earlier version). A native details/summary: Enter and Space toggle it, and
// the triangle turns when open.
import type { ReactNode } from 'react';

import { cx } from './internal';

export function Disclosure({ summary, children, defaultOpen = false, className }: { summary: ReactNode; children: ReactNode; defaultOpen?: boolean; className?: string }) {
  return (
    <details className={cx('psl-disclosure', className)} open={defaultOpen || undefined}>
      <summary>{summary}</summary>
      <div>{children}</div>
    </details>
  );
}
