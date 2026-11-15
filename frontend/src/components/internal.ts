'use client';

// Helpers shared by the components in this folder; not exported from the library.
import { useEffect, useLayoutEffect, useRef, useSyncExternalStore, type KeyboardEvent, type Ref, type RefObject } from 'react';

import './components.css';

/** Sets a ref the caller passed, whether a callback or an object. */
export function assignRef<T>(ref: Ref<T> | undefined, value: T | null) {
  if (typeof ref === 'function') ref(value);
  else if (ref) (ref as { current: T | null }).current = value;
}

/** Joins class names, dropping empty ones. */
export function cx(...names: unknown[]): string {
  return names.filter((n): n is string => typeof n === 'string' && n !== '').join(' ');
}

const PHONE = '(max-width: 719.98px)';

function subscribePhone(onChange: () => void) {
  if (typeof window.matchMedia !== 'function') return () => {};
  const query = window.matchMedia(PHONE);
  query.addEventListener('change', onChange);
  return () => query.removeEventListener('change', onChange);
}

/** True below bp-phone (720px); false where matchMedia is missing (tests) and on the server. */
export function usePhone(): boolean {
  return useSyncExternalStore(
    subscribePhone,
    () => (typeof window.matchMedia === 'function' ? window.matchMedia(PHONE).matches : false),
    () => false,
  );
}

const useIsoLayoutEffect = typeof window === 'undefined' ? useEffect : useLayoutEffect;

const FOCUSABLE =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

/**
 * A modal surface (drawer, sheet, dialog): focus moves in on open (to `initial`, else the first field, else the
 * panel), Tab stays inside, Esc closes, and focus returns to whatever had it before the surface opened.
 * Returns the keydown handler for the panel.
 */
export function useModal(panel: RefObject<HTMLElement | null>, onClose: () => void, initial?: RefObject<HTMLElement | null>) {
  const close = useRef(onClose);
  useIsoLayoutEffect(() => {
    close.current = onClose;
  });

  useEffect(() => {
    const opener = document.activeElement as HTMLElement | null;
    const root = panel.current;
    if (root) {
      const field = root.querySelector<HTMLElement>('input:not([disabled]), select:not([disabled]), textarea:not([disabled])');
      (initial?.current ?? field ?? root).focus();
    }
    return () => {
      if (opener && document.contains(opener)) opener.focus();
    };
    // Runs once per opening; the refs are stable.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (event: KeyboardEvent<HTMLElement>) => {
    if (event.key === 'Escape') {
      event.preventDefault();
      event.stopPropagation();
      close.current();
      return;
    }
    if (event.key !== 'Tab' || !panel.current) return;
    const items = [...panel.current.querySelectorAll<HTMLElement>(FOCUSABLE)];
    if (items.length === 0) {
      event.preventDefault();
      return;
    }
    const first = items[0];
    const last = items[items.length - 1];
    const active = document.activeElement;
    if (event.shiftKey && (active === first || active === panel.current)) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && active === last) {
      event.preventDefault();
      first.focus();
    }
  };
}

/** Calls `onOutside` on a pointer press outside every element in `refs` while `active`. */
export function useOutsidePress(refs: RefObject<HTMLElement | null>[], active: boolean, onOutside: () => void) {
  const handler = useRef(onOutside);
  useIsoLayoutEffect(() => {
    handler.current = onOutside;
  });
  useEffect(() => {
    if (!active) return undefined;
    function onDown(event: PointerEvent | MouseEvent) {
      const target = event.target as Node;
      if (refs.some((r) => r.current?.contains(target))) return;
      handler.current();
    }
    document.addEventListener('mousedown', onDown);
    return () => document.removeEventListener('mousedown', onDown);
    // The refs are stable objects.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active]);
}

/**
 * Typeahead: collects keys typed within 500ms and returns the index of the first item, from `from` onwards and
 * wrapping, whose text starts with them; -1 when none does.
 */
export function useTypeahead() {
  const typed = useRef({ text: '', at: 0 });
  return (key: string, texts: string[], from: number): number => {
    const now = Date.now();
    typed.current = { text: (now - typed.current.at > 500 ? '' : typed.current.text) + key.toLowerCase(), at: now };
    const query = typed.current.text;
    for (let step = 0; step < texts.length; step += 1) {
      const at = (from + step) % texts.length;
      if (texts[at].trim().toLowerCase().startsWith(query)) return at;
    }
    return -1;
  };
}

/** True for a key that should feed typeahead: one printable character with no modifier. */
export function isTypeaheadKey(event: KeyboardEvent): boolean {
  return event.key.length === 1 && event.key !== ' ' && !event.ctrlKey && !event.metaKey && !event.altKey;
}
