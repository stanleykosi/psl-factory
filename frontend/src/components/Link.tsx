// Link (design/system/project/components/Link): links go somewhere; buttons do something. Quiet links underline on
// hover only, for rows that already read as links. A record the person cannot open is shown, never hidden, as
// restricted text with a lock.
import NextLink from 'next/link';
import type { ComponentPropsWithRef, ReactNode } from 'react';

import { Icon } from './Icon';
import { cx } from './internal';

export type LinkProps = Omit<ComponentPropsWithRef<typeof NextLink>, 'href'> & {
  href: string;
  quiet?: boolean;
  children: ReactNode;
};

export function Link({ href, quiet = false, className, children, ...rest }: LinkProps) {
  return (
    <NextLink {...rest} href={href} className={cx('psl-link', quiet && 'psl-link--quiet', className)}>
      {children}
    </NextLink>
  );
}

/** The record named, with a lock, where the person may know it exists but not open it. */
export function RestrictedLink({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <span className={cx('psl-link is-restricted cmp-restricted', className)}>
      <Icon name="lock" />
      {children}
    </span>
  );
}
