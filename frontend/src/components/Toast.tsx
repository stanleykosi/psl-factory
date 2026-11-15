'use client';

// Toast (design/system/project/components/Toast): a dark bar at the bottom centre after an action that changed
// something, saying what happened and what is next, with Undo when it can be undone. It stays 6 seconds, and
// longer while hovered or focused, or until dismissed. Success is a polite status; the problem toast (orange top
// edge) is an alert, only for a failure that happened in the background, with a link to the fix. Never for an
// error that needs action now (that is a Callout). The live region is drawn first and the message written into
// it a moment later, so screen readers announce it (a region that appears already filled is often not read).
import NextLink from 'next/link';
import { useEffect, useRef, useState, type ReactNode } from 'react';

import { Icon } from './Icon';
import { IconButton } from './IconButton';
import { cx } from './internal';

export const TOAST_MS = 6000;

export type ToastAction = { label: string; onClick: () => void } | { label: string; href: string };

export function Toast({ kind = 'success', children, action, dismissible = false, onDismiss }: {
  kind?: 'success' | 'problem';
  children: ReactNode;
  /** Undo, or the link to the fix on a problem toast. */
  action?: ToastAction;
  /** Shows the close button. */
  dismissible?: boolean;
  /** Called after 6 seconds (unless hovered or focused) and on dismiss. */
  onDismiss: () => void;
}) {
  const [held, setHeld] = useState(false);
  const [written, setWritten] = useState(false);
  useEffect(() => {
    const timer = setTimeout(() => setWritten(true), 0);
    return () => clearTimeout(timer);
  }, []);
  const dismiss = useRef(onDismiss);
  useEffect(() => {
    dismiss.current = onDismiss;
  });
  useEffect(() => {
    if (held) return undefined;
    const timer = setTimeout(() => dismiss.current(), TOAST_MS);
    return () => clearTimeout(timer);
  }, [held]);

  return (
    <div className="cmp-toasts">
      <div
        className={cx('psl-toast psl-on-dark', kind === 'problem' && 'psl-toast--problem')}
        role={kind === 'problem' ? 'alert' : 'status'}
        onMouseEnter={() => setHeld(true)}
        onMouseLeave={() => setHeld(false)}
        onFocus={() => setHeld(true)}
        onBlur={(event) => {
          if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setHeld(false);
        }}
      >
        {kind === 'success' && (
          <span className="psl-tick">
            <Icon name="check" />
          </span>
        )}
        <span>{written ? children : null}</span>
        {action &&
          ('href' in action ? (
            <NextLink href={action.href}>{action.label}</NextLink>
          ) : (
            <button type="button" className="cmp-toast__action" onClick={action.onClick}>
              {action.label}
            </button>
          ))}
        {dismissible && <IconButton bare icon="close" label="Dismiss" onClick={() => onDismiss()} />}
      </div>
    </div>
  );
}
