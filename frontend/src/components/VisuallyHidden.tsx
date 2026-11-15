// VisuallyHidden: text for screen readers only (one class instead of the fourteen feature copies the audit found).
import type { ReactNode } from 'react';

import './components.css';

export function VisuallyHidden({ children, id }: { children: ReactNode; id?: string }) {
  return (
    <span className="cmp-sr" id={id}>
      {children}
    </span>
  );
}
