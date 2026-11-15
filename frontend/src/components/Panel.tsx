// Panel (design/system/project/components/Panel): surface with a 2px ink border and square corners. Decision
// (orange) only where a person decides; agent (blue edge) only for agent work; read-only for context that cannot
// be acted on. The head names the region; `headingLevel` makes it a heading (h2, h3) where the page outline needs
// one; `as="aside"` makes a side panel a complementary landmark where a board draws it beside the main content.
// Other section attributes (data-*, id) and a ref pass through.
import { useId, type ComponentPropsWithRef, type ReactNode } from 'react';

import { cx } from './internal';

export type PanelKind = 'default' | 'decide' | 'agent' | 'readonly';

export function Panel({ kind = 'default', head, darkHead = false, headingLevel, as: Box = 'section', children, className, bodyClassName, headClassName, ...rest }: Omit<ComponentPropsWithRef<'section'>, 'children'> & {
  kind?: PanelKind;
  head?: ReactNode;
  /** An ink header for a summary the content explains (totals, the record). */
  darkHead?: boolean;
  /** The head as a heading of this level. */
  headingLevel?: 2 | 3 | 4;
  /** aside: a side panel (complementary landmark). */
  as?: 'section' | 'aside';
  children: ReactNode;
  className?: string;
  bodyClassName?: string;
  headClassName?: string;
}) {
  const headId = useId();
  const Heading = headingLevel ? (`h${headingLevel}` as const) : 'div';
  return (
    <Box {...rest} className={cx('psl-panel cmp-panelbox', kind !== 'default' && `psl-panel--${kind}`, className)} aria-labelledby={rest['aria-labelledby'] ?? (head && !rest['aria-label'] ? headId : undefined)}>
      {head && (
        <Heading id={headId} className={cx('psl-panel__head', kind === 'decide' && 'psl-panel__head--decide', darkHead && 'psl-panel__head--dark', headClassName)}>
          {head}
        </Heading>
      )}
      <div className={cx('psl-panel__body', bodyClassName)}>{children}</div>
    </Box>
  );
}
