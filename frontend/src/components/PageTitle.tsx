// PageTitle: the page title as the boards draw it (D-93): display at 112% stretch, line height 1.08, 40px on
// desktop and 26px on phones by default. Record and form pages whose boards draw a smaller title pass the board's
// size (`size` from 720px, `phoneSize` below). An optional mono eyebrow or breadcrumb sits above it.
import type { ReactNode, Ref } from 'react';

import { cx } from './internal';

export type PageTitleSize = 40 | 36 | 34 | 32 | 30 | 28;
export type PageTitlePhoneSize = 26 | 24 | 22 | 20;

export function PageTitle({ children, above, size = 40, phoneSize = 26, className, titleClassName, id, tabIndex, ref }: {
  children: ReactNode;
  above?: ReactNode;
  /** The board's desktop title size. */
  size?: PageTitleSize;
  /** The phone board's title size. */
  phoneSize?: PageTitlePhoneSize;
  className?: string;
  titleClassName?: string;
  id?: string;
  /** -1 where the page moves focus to its title. */
  tabIndex?: number;
  ref?: Ref<HTMLHeadingElement>;
}) {
  return (
    <header className={cx('cmp-pagehead', className)}>
      {above}
      <h1 ref={ref} id={id} tabIndex={tabIndex} className={cx('cmp-page-title', size !== 40 && `cmp-page-title--${size}`, phoneSize !== 26 && `cmp-page-title--p${phoneSize}`, titleClassName)}>
        {children}
      </h1>
    </header>
  );
}
