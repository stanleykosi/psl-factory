'use client';

// BottomSheet (design/system/project/components/BottomSheet): on phones, filters, short choices and confirmations
// open from the bottom with a grab handle and full-width actions in thumb reach (the main one at control-xl).
// Modal like the Drawer; swiping down on the handle or head, the close button, Esc or the scrim dismiss it.
import { useId, useRef, type PointerEvent, type ReactNode, type RefObject } from 'react';

import { IconButton } from './IconButton';
import { cx, useModal } from './internal';
import { Layer } from './Overlay';

// How far a swipe down must travel to dismiss.
const SWIPE_PX = 60;

export function BottomSheet({ title, onClose, footer, children, initialFocus, className }: {
  title: string;
  onClose: () => void;
  footer?: ReactNode;
  children: ReactNode;
  initialFocus?: RefObject<HTMLElement | null>;
  className?: string;
}) {
  const panel = useRef<HTMLDivElement>(null);
  const start = useRef<number | null>(null);
  const titleId = useId();
  const onKeyDown = useModal(panel, onClose, initialFocus);
  const swipe = {
    onPointerDown: (event: PointerEvent) => {
      start.current = event.clientY;
    },
    onPointerUp: (event: PointerEvent) => {
      if (start.current !== null && event.clientY - start.current > SWIPE_PX) onClose();
      start.current = null;
    },
  };
  return (
    <Layer kind="sheet" onScrim={onClose}>
      {/* Esc and the Tab loop are handled for the whole surface. */}
      {/* eslint-disable-next-line jsx-a11y/no-noninteractive-element-interactions */}
      <div ref={panel} role="dialog" aria-modal="true" aria-labelledby={titleId} tabIndex={-1} className={cx('psl-sheet cmp-panel', className)} onKeyDown={onKeyDown}>
        {/* Pointer-only swipe; the close button is the keyboard way. */}
        <div className="cmp-swipe" {...swipe}>
          <span className="psl-sheet__grab" aria-hidden="true" />
          <div className="psl-sheet__head">
            <strong className="cmp-sheet-title" id={titleId}>
              {title}
            </strong>
            <IconButton bare icon="close" label="Close" onClick={onClose} />
          </div>
        </div>
        <div className="psl-sheet__body cmp-scroll">{children}</div>
        {footer && <div className="psl-sheet__foot">{footer}</div>}
      </div>
    </Layer>
  );
}
