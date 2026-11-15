// Breadcrumb (design/system/project/components/Breadcrumb): a one-line trail above a page title, two levels at
// most (PROJECTS / LAGOON HEALTH). The current page is the title, so it is not a link; give it as `current` only
// where a board draws it. On phones the Back link replaces the trail (the shell's phone bar).
import NextLink from 'next/link';
import { Fragment } from 'react';

export function Breadcrumb({ items, current }: { items: { label: string; href: string }[]; current?: string }) {
  return (
    <nav aria-label="Breadcrumb">
      <p className="psl-crumb">
        {items.map((item, i) => (
          <Fragment key={item.href}>
            {i > 0 && <span aria-hidden="true"> / </span>}
            <NextLink href={item.href}>{item.label}</NextLink>
          </Fragment>
        ))}
        {current && (
          <>
            <span aria-hidden="true"> / </span>
            <span aria-current="page">{current}</span>
          </>
        )}
      </p>
    </nav>
  );
}
