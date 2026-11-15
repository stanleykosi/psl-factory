'use client';

// Disclosure (design/system/project/components/Disclosure): hides detail most people do not need (an agent's
// suggestion that was not used, an earlier version, an agent's steps). Two looks, as the boards draw them (D-93):
// `box`, a native details/summary with a triangle that turns when open; `link`, a summary that reads as a link
// ("Preview the invoice") with no box. Where the trigger sits inside a sentence and the detail shows below the
// block ("…from 3 sources. See his steps"), use DisclosureLink with the detail in an element of its own.
import { useState, type ReactNode } from 'react';

import { cx } from './internal';

export function Disclosure({ summary, openSummary, children, defaultOpen = false, look = 'box', className }: {
  summary: ReactNode;
  /** The summary while open ("Hide the invoice"); the same as `summary` when not given. */
  openSummary?: ReactNode;
  children: ReactNode;
  defaultOpen?: boolean;
  look?: 'box' | 'link';
  className?: string;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <details className={cx(look === 'box' ? 'psl-disclosure' : 'cmp-disclosure--link', className)} open={defaultOpen || undefined} onToggle={(event) => setOpen(event.currentTarget.open)}>
      <summary className={look === 'link' ? 'psl-link' : undefined}>{open && openSummary !== undefined ? openSummary : summary}</summary>
      <div>{children}</div>
    </details>
  );
}

/** A link-look button that shows and hides the element named by `controls` (which the caller renders with `hidden`). */
export function DisclosureLink({ open, onToggle, controls, children, openLabel, className }: {
  open: boolean;
  onToggle: () => void;
  /** The id of the detail it shows. */
  controls: string;
  /** The words while closed ("See his steps"). */
  children: ReactNode;
  /** The words while open ("Hide his steps"). */
  openLabel?: ReactNode;
  className?: string;
}) {
  return (
    <button type="button" className={cx('psl-link cmp-disclosurelink', className)} aria-expanded={open} aria-controls={controls} onClick={onToggle}>
      {open && openLabel !== undefined ? openLabel : children}
    </button>
  );
}
