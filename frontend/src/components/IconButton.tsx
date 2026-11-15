'use client';

// IconButton (design/system/project/components/IconButton): a 44px square with an icon and no visible label, so it
// always names its action with aria-label. A count (filters on) uses the orange count badge inside the button, as
// psl-bundle.css places it; the label carries the count for screen readers.
import type { ComponentPropsWithRef } from 'react';

import { Icon, type IconName } from './Icon';
import { cx } from './internal';

export type IconButtonProps = Omit<ComponentPropsWithRef<'button'>, 'type' | 'aria-label' | 'children'> & {
  icon: IconName;
  /** The action in words ("Close", "Filter", "More actions"). */
  label: string;
  /** No outline: close and clear inside a drawer head, toast or field. */
  bare?: boolean;
  /** How many filters are on; the label says it too ("Filter, 2 on"). */
  count?: number;
};

export function IconButton({ icon, label, bare = false, count, className, ...rest }: IconButtonProps) {
  return (
    <button {...rest} type="button" className={cx('psl-iconbtn', bare && 'psl-iconbtn--bare', className)} aria-label={count !== undefined ? `${label}, ${count} on` : label}>
      <Icon name={icon} />
      {count !== undefined && (
        <span className="psl-badge psl-badge--signal" aria-hidden="true">
          {count}
        </span>
      )}
    </button>
  );
}
