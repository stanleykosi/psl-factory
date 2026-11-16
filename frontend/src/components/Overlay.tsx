'use client';

// The layer every modal surface sits in: rendered into document.body over the scrim, which closes it on a pointer
// press (Esc and the close button are the keyboard ways). Not a design-system component of its own.
import type { ReactNode } from 'react';
import { createPortal } from 'react-dom';

import { cx } from './internal';

export function Layer({ kind, onScrim, children }: { kind: 'drawer' | 'sheet' | 'center'; onScrim?: () => void; children: ReactNode }) {
  return createPortal(
    <div className={cx('cmp-layer', `cmp-layer--${kind}`)}>
      <div className="psl-scrim" aria-hidden="true" onClick={onScrim} />
      {children}
    </div>,
    document.body,
  );
}
