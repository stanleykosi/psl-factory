// Breadcrumb (design/system/project/components/Breadcrumb): a one-line trail above a page title, two levels at
// most (PROJECTS / LAGOON HEALTH). The trail reads as one line of text, as the boards write it (D-93): the " / "
// separators are plain visible text between the links, so assistive technology reads the same line. A level with
// no page of its own (the line a work item is on) is text, not a link. The current page is the title, so it is not
// a link; give it as `current` only where a board draws it. On phones the Back link replaces the trail (the shell's
// phone bar).
import NextLink from 'next/link';
import { Fragment, type ReactNode } from 'react';

import { cx } from './internal';

export function Breadcrumb({ items, current, className }: { items: { label: string; href?: string }[]; current?: ReactNode; className?: string }) {
  return (
    <nav aria-label="Breadcrumb">
      <p className={cx('psl-crumb', className)}>
        {items.map((item, i) => (
          <Fragment key={i}>
            {i > 0 && ' / '}
            {item.href ? <NextLink href={item.href}>{item.label}</NextLink> : item.label}
          </Fragment>
        ))}
        {current && (
          <>
            {' / '}
            <span aria-current="page">{current}</span>
          </>
        )}
      </p>
    </nav>
  );
}
