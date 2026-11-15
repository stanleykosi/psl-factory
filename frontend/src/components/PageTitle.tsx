// PageTitle: the README's `page-title` text style (display, 34/37px at 112% stretch, 26px on phones), with an
// optional mono eyebrow or breadcrumb above it.
import type { ReactNode } from 'react';

import { cx } from './internal';

export function PageTitle({ children, above, className }: { children: ReactNode; above?: ReactNode; className?: string }) {
  return (
    <header className={cx('cmp-pagehead', className)}>
      {above}
      <h1 className="cmp-page-title">{children}</h1>
    </header>
  );
}
