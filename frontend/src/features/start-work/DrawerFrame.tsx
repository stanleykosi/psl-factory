'use client';

// CMP-23 drawer frame: the shared Drawer (a right-hand 500px drawer from 720px, a full-width bottom sheet below;
// every line on the phone, as the design engineer chose on 14 Nov 2026; long forms scroll inside the sheet).
// A modal dialog labelled by its title: focus moves in and stays in, Esc and the scrim close it, and the opener
// gets focus back. Rendered into document.body so it sits over the page, not inside the bar.
import { useEffect, useRef, type ReactNode } from 'react';

import { Drawer, useIsPhone } from '@/components';

/** True from 720px; true where matchMedia is missing (tests), so the drawer is the default. */
export function useWide(): boolean {
  return !useIsPhone();
}

// A combobox button or a radio group is a first field too; focus moves to it again when the content is replaced.
const FIRST_FIELD =
  'input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [role="combobox"]:not([disabled]), [role="radio"][tabindex="0"]';

type Props = {
  /** The mono line above the title, from 720px only: the phone sheet head has none (SCR-04-mobile). */
  eyebrow?: string;
  title: string;
  subline?: ReactNode;
  onClose: () => void;
  footer?: ReactNode;
  children: ReactNode;
  /** Changes when the content is replaced (loading to chooser, chooser to line), so focus moves to it again. */
  focusKey: string;
};

export function DrawerFrame({ eyebrow, title, subline, onClose, footer, children, focusKey }: Props) {
  const body = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const panel = body.current?.closest<HTMLElement>('[role="dialog"]');
    (body.current?.querySelector<HTMLElement>(FIRST_FIELD) ?? panel)?.focus();
  }, [focusKey]);
  return (
    <Drawer eyebrow={eyebrow} title={title} subline={subline} onClose={onClose} footer={footer} className="sw-panel">
      <div ref={body} className="sw-body">
        {children}
      </div>
    </Drawer>
  );
}
