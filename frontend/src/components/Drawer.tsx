'use client';

// Drawer (design/system/project/components/Drawer): opens from the right over the page (500px), so people never
// lose the queue. Head: mono eyebrow, display title, one line of context, close button; the body scrolls and the
// footer stays. Modal: focus moves in and stays in, Esc, the close button and the scrim close it, and focus
// returns to the opener. Below 720px it is a full-height sheet with an 18px title; `keepTop` leaves the top of the
// page in view, as SCR-04-mobile draws the Start work sheet (D-93). "Needs fixing" puts a ValidationSummary first in the body; "submitting" is a busy
// Button in the footer; "done" closes and shows a Toast (the consumer's).
import { useId, useRef, type ReactNode, type RefObject } from 'react';

import { IconButton } from './IconButton';
import { cx, useModal, usePhone } from './internal';
import { Layer } from './Overlay';

export function Drawer({ title, eyebrow, subline, onClose, footer, children, initialFocus, keepTop = false, className }: {
  title: string;
  /** START WORK; desktop only, as the phone sheet head has none. */
  eyebrow?: string;
  subline?: ReactNode;
  onClose: () => void;
  footer?: ReactNode;
  children: ReactNode;
  /** What takes focus on opening; the first field otherwise. */
  initialFocus?: RefObject<HTMLElement | null>;
  /** On phones, the sheet stops 70px under the phone bar so the page's top stays in view. */
  keepTop?: boolean;
  className?: string;
}) {
  const phone = usePhone();
  const panel = useRef<HTMLElement>(null);
  const titleId = useId();
  const onKeyDown = useModal(panel, onClose, initialFocus);
  const kind = phone ? 'psl-sheet' : 'psl-drawer';
  return (
    <Layer kind={phone ? 'sheet' : 'drawer'} onScrim={onClose}>
      {/* Esc and the Tab loop are handled for the whole surface. */}
      {/* eslint-disable-next-line jsx-a11y/no-noninteractive-element-interactions */}
      <aside
        ref={panel}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
        className={cx(kind, 'cmp-panel', phone && 'cmp-panel--full', phone && keepTop && 'cmp-panel--keeptop', className)}
        onKeyDown={onKeyDown}
      >
        {phone && <span className="psl-sheet__grab" aria-hidden="true" />}
        <div className={`${kind}__head`}>
          <span className="cmp-headtext">
            {eyebrow && !phone && <span className="psl-drawer__eyebrow">{eyebrow}</span>}
            <span className="psl-drawer__title" id={titleId}>
              {title}
            </span>
            {subline && <span className="psl-hint">{subline}</span>}
          </span>
          <IconButton bare icon="close" label="Close" onClick={onClose} />
        </div>
        <div className={cx(`${kind}__body`, 'cmp-scroll')}>{children}</div>
        {footer && <div className={`${kind}__foot`}>{footer}</div>}
      </aside>
    </Layer>
  );
}
