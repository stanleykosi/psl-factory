// Panel (design/system/project/components/Panel): surface with a 2px ink border and square corners. Decision
// (orange) only where a person decides; agent (blue edge) only for agent work; read-only for context that cannot
// be acted on. The head names the region.
import { useId, type ReactNode } from 'react';

import { cx } from './internal';

export type PanelKind = 'default' | 'decide' | 'agent' | 'readonly';

export function Panel({ kind = 'default', head, darkHead = false, children, className, bodyClassName }: {
  kind?: PanelKind;
  head?: ReactNode;
  /** An ink header for a summary the content explains (totals, the record). */
  darkHead?: boolean;
  children: ReactNode;
  className?: string;
  bodyClassName?: string;
}) {
  const headId = useId();
  return (
    <section className={cx('psl-panel cmp-panelbox', kind !== 'default' && `psl-panel--${kind}`, className)} aria-labelledby={head ? headId : undefined}>
      {head && (
        <div id={headId} className={cx('psl-panel__head', kind === 'decide' && 'psl-panel__head--decide', darkHead && 'psl-panel__head--dark')}>
          {head}
        </div>
      )}
      <div className={cx('psl-panel__body', bodyClassName)}>{children}</div>
    </section>
  );
}
