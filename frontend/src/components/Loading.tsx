// Loading, empty and error (design/system/project/components/Loading): three squares and a sentence on what is
// loading (old figures are never shown as current meanwhile); placeholder bars that hold a list's layout; an empty
// state with a heading, one sentence and the action that fills it; a problem callout with Retry, never a raw error
// code first; a progress bar with mono figures for uploads and imports. Reduced motion stops the squares; the
// words carry the state.
import type { ReactNode } from 'react';

import { BusySquares, Button } from './Button';
import { Callout } from './Callout';
import { cx } from './internal';

export function Loading({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <span className={cx('psl-loading', className)} role="status">
      <BusySquares />
      {children}
    </span>
  );
}

/** Placeholder bars, as wide as the given percentages. Hidden from screen readers: pair with Loading. */
export function Skeleton({ widths = [70, 45, 60], className }: { widths?: number[]; className?: string }) {
  return (
    <div className={cx('psl-panel cmp-skeleton', className)} aria-hidden="true">
      {widths.map((w, i) => (
        <span key={i} className="psl-skel" style={{ width: `${w}%` }} />
      ))}
    </div>
  );
}

/** `level`: the heading level that fits the page outline (2 straight under the page title, 3 inside a section). */
export function EmptyState({ title, children, action, level = 3, className }: { title: string; children: ReactNode; action?: ReactNode; level?: 2 | 3; className?: string }) {
  const Heading = level === 2 ? 'h2' : 'h3';
  return (
    <div className={cx('psl-empty', className)}>
      <Heading>{title}</Heading>
      <p>{children}</p>
      {action}
    </div>
  );
}

/** What failed, in words, and Retry. The callout is announced: it appears because loading failed. */
export function ErrorState({ title, children, onRetry, retryLabel = 'Retry', busy = false }: { title: string; children?: ReactNode; onRetry: () => void; retryLabel?: string; busy?: boolean }) {
  return (
    <div className="cmp-stack">
      <Callout kind="problem">
        <strong>{title}</strong>
        {children && <> {children}</>}
      </Callout>
      <span>
        <Button kind="secondary" busy={busy} busyLabel="Retrying…" onClick={onRetry}>
          {retryLabel}
        </Button>
      </span>
    </div>
  );
}

export function Progress({ value, max, label, text }: { value: number; max: number; label: string; text: string }) {
  const percent = max > 0 ? Math.round((value / max) * 100) : 0;
  return (
    <div>
      <div className="psl-progress" role="progressbar" aria-label={label} aria-valuenow={value} aria-valuemin={0} aria-valuemax={max} aria-valuetext={text}>
        <i style={{ width: `${percent}%` }} />
      </div>
      <span className="psl-mono cmp-progresstext">{text}</span>
    </div>
  );
}
