'use client';

// CMP-23 drawer frame: a right-hand psl-drawer over a psl-scrim from 720px, a full-width bottom psl-sheet below
// (every line on the phone, as the design engineer chose on 14 Nov 2026; long forms scroll inside the sheet).
// A modal dialog labelled by its title: focus moves in and stays in, Esc and the scrim close it, and the opener
// gets focus back (StartWorkButton). Rendered into document.body so it sits over the page, not inside the bar.
import { useEffect, useId, useRef, useSyncExternalStore, type KeyboardEvent, type ReactNode } from 'react';
import { createPortal } from 'react-dom';

const WIDE = '(min-width: 720px)';
const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';
const FIRST_FIELD =
  'input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [role="combobox"]:not([disabled]), [role="radio"][tabindex="0"]';

function subscribe(onChange: () => void) {
  if (typeof window.matchMedia !== 'function') return () => {};
  const query = window.matchMedia(WIDE);
  query.addEventListener('change', onChange);
  return () => query.removeEventListener('change', onChange);
}

/** True from 720px; true where matchMedia is missing (tests), so the drawer is the default. */
export function useWide(): boolean {
  return useSyncExternalStore(
    subscribe,
    () => (typeof window.matchMedia === 'function' ? window.matchMedia(WIDE).matches : true),
    () => true,
  );
}

type Props = {
  /** The mono line above the title, from 720px only: the phone sheet head has none (SCR-04-mobile). */
  eyebrow?: string;
  title: string;
  subline?: ReactNode;
  onClose: () => void;
  footer?: ReactNode;
  children: ReactNode;
  /** 480px from 720px instead of the bundle's 500px, where the board draws it so. */
  narrow?: boolean;
  /** Changes when the content is replaced (loading to chooser, chooser to line), so focus moves to it again. */
  focusKey: string;
};

export function DrawerFrame({ eyebrow, title, subline, onClose, footer, children, focusKey, narrow = false }: Props) {
  const wide = useWide();
  const panelRef = useRef<HTMLDivElement>(null);
  const titleId = useId();
  const kind = wide ? 'psl-drawer' : 'psl-sheet';

  useEffect(() => {
    const panel = panelRef.current;
    if (!panel) return;
    const first = panel.querySelector<HTMLElement>(`.sw-body ${FIRST_FIELD.split(', ').join(', .sw-body ')}`);
    (first ?? panel).focus();
  }, [focusKey]);

  function onKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key === 'Escape') {
      event.preventDefault();
      onClose();
      return;
    }
    if (event.key !== 'Tab' || !panelRef.current) return;
    const items = [...panelRef.current.querySelectorAll<HTMLElement>(FOCUSABLE)];
    if (items.length === 0) {
      event.preventDefault();
      return;
    }
    const first = items[0];
    const last = items[items.length - 1];
    const active = document.activeElement;
    if (event.shiftKey && (active === first || active === panelRef.current)) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && active === last) {
      event.preventDefault();
      first.focus();
    }
  }

  return createPortal(
    <div className={`sw-layer sw-layer--${wide ? 'drawer' : 'sheet'}`}>
      {/* Pointer-only dismissal; Esc and the Close button are the keyboard equivalents. */}
      <div className="psl-scrim sw-scrim" aria-hidden="true" onClick={onClose} />
      {/* eslint-disable-next-line jsx-a11y/no-noninteractive-element-interactions */}
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
        className={`${kind} sw-panel${narrow ? ' sw-panel--narrow' : ''}`}
        onKeyDown={onKeyDown}
      >
        {!wide && <div className="psl-sheet__grab" aria-hidden="true" />}
        <div className={`${kind}__head sw-head`}>
          <span className="sw-headtext">
            {eyebrow && wide && <span className="psl-drawer__eyebrow">{eyebrow}</span>}
            <strong className="psl-drawer__title" id={titleId}>
              {title}
            </strong>
            {subline && <span className="psl-hint">{subline}</span>}
          </span>
          <button type="button" className="psl-iconbtn psl-iconbtn--bare sw-close" aria-label="Close" onClick={onClose}>
            <span aria-hidden="true">×</span>
          </button>
        </div>
        <div className={`${kind}__body sw-body`}>{children}</div>
        {footer && <div className={`${kind}__foot sw-foot`}>{footer}</div>}
      </div>
    </div>,
    document.body,
  );
}
