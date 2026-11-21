'use client';

// Toast (design/system/project/components/Toast): a dark bar at the bottom centre after an action that changed
// something, saying what happened and what is next, with Undo when it can be undone. It stays 6 seconds, and
// longer while hovered or focused, or until dismissed. Success is a polite status; the problem toast (orange top
// edge) is an alert, only for a failure that happened in the background, with a link to the fix. Never for an
// error that needs action now (that is a Callout). The live region is drawn first and the message written into
// it a moment later, so screen readers announce it (a region that appears already filled is often not read).
// ToastProvider (below) is the one host: see design/system/project/components/Toast/README.md.
import NextLink from 'next/link';
import { createContext, useCallback, useContext, useEffect, useLayoutEffect, useMemo, useRef, useState, type ReactNode } from 'react';

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
  );
}

/** Undo runs, then the toast closes; a link to a fix is left as it is. */
function undoThenClose(action: ToastAction | undefined, close: () => void): ToastAction | undefined {
  if (!action || 'href' in action) return action;
  return {
    label: action.label,
    onClick: () => {
      action.onClick();
      close();
    },
  };
}

type ToastOptions = { kind?: 'success' | 'problem'; action?: ToastAction; dismissible?: boolean };
type ToastItem = ToastOptions & { id: number; message: ReactNode };
type ToastApi = { show: (message: ReactNode, options?: ToastOptions) => void };

const ToastContext = createContext<ToastApi | null>(null);

/** Shows a toast in the app-wide host: `const toast = useToast(); toast.show('Billing contact saved.')`. */
export function useToast(): ToastApi {
  const api = useContext(ToastContext);
  if (!api) throw new Error('useToast is only available inside ToastProvider');
  return api;
}

/**
 * Shows a toast once each time `text` becomes a new non-empty string, for a page that keeps the result of an action in
 * state (and clears it when the next action starts). `label` is a bold lead-in.
 */
export function useToastWhen(text: string | null | undefined, label?: string) {
  const toast = useToast();
  const shown = useRef<string | null>(null);
  useEffect(() => {
    if (!text) {
      shown.current = null;
      return;
    }
    if (shown.current === text) return;
    shown.current = text;
    toast.show(
      label ? (
        <>
          <strong>{label}</strong> {text}
        </>
      ) : (
        text
      ),
    );
    // The label is part of the same message as the text.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [text, toast]);
}

export const MAX_TOASTS = 3;

/**
 * The one toast host, mounted in the app shell so it outlives a client-side route change. Newest at the bottom,
 * at most MAX_TOASTS (older ones drop). It never moves focus. On phones it is full width inside the gutters and
 * lifts above any sticky or fixed bar at the bottom of the screen (the assistant composer, a decide bar).
 */
export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);
  const next = useRef(0);
  const host = useRef<HTMLDivElement>(null);
  const api = useMemo<ToastApi>(
    () => ({
      show: (message, options) => {
        next.current += 1;
        setItems((all) => [...all, { ...options, id: next.current, message }].slice(-MAX_TOASTS));
      },
    }),
    [],
  );
  const remove = useCallback((id: number) => setItems((all) => all.filter((item) => item.id !== id)), []);

  // Phones: measure the bars pinned to the bottom edge and sit above the tallest one.
  useLayoutEffect(() => {
    const node = host.current;
    if (!node) return undefined;
    const lift = () => {
      let top = window.innerHeight;
      if (items.length > 0 && window.innerWidth < 720) {
        for (const el of document.body.querySelectorAll<HTMLElement>('main *, body > *')) {
          if (node.contains(el)) continue;
          const rect = el.getBoundingClientRect();
          if (rect.width < window.innerWidth * 0.9 || rect.height === 0 || rect.bottom < window.innerHeight - 1 || rect.top < window.innerHeight * 0.3) continue;
          const position = getComputedStyle(el).position;
          if (position === 'fixed' || position === 'sticky') top = Math.min(top, rect.top);
        }
      }
      node.style.setProperty('--toast-lift', `${window.innerHeight - top}px`);
    };
    lift();
    // A bar can arrive after the toast does (the next page of an action that navigates), so the phone measures again while one shows.
    const timer = items.length > 0 && window.innerWidth < 720 ? setInterval(lift, 400) : undefined;
    window.addEventListener('resize', lift);
    return () => {
      clearInterval(timer);
      window.removeEventListener('resize', lift);
    };
  }, [items]);

  return (
    <ToastContext.Provider value={api}>
      {children}
      {items.length > 0 && (
        <div ref={host} className="cmp-toasts">
          {items.map((item) => (
            <Toast
              key={item.id}
              kind={item.kind}
              dismissible={item.dismissible}
              action={undoThenClose(item.action, () => remove(item.id))}
              onDismiss={() => remove(item.id)}
            >
              {item.message}
            </Toast>
          ))}
        </div>
      )}
    </ToastContext.Provider>
  );
}
