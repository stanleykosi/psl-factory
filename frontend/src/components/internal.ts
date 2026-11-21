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
 * panel), Tab stays inside, Esc closes, and focus returns to `returnTo` when given (the button that opened it, where
 * a press may not focus it, as on touch), else to whatever had it before the surface opened.
 * Returns the keydown handler for the panel.
 */
export function useModal(panel: RefObject<HTMLElement | null>, onClose: () => void, initial?: RefObject<HTMLElement | null>, returnTo?: RefObject<HTMLElement | null>) {
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
      // Read on closing, on purpose: the opener named by the caller is the one on the page now.
      // eslint-disable-next-line react-hooks/exhaustive-deps
      const back = returnTo?.current ?? opener;
      if (back && document.contains(back)) back.focus();
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

/** The part of the screen a popover may use: the window, cut down by every ancestor that clips or scrolls (a drawer body). */
function clipBounds(el: HTMLElement) {
  let top = 0;
  let left = 0;
  let right = window.innerWidth;
  let bottom = window.innerHeight;
  for (let p = el.parentElement; p && p !== document.body; p = p.parentElement) {
    const style = getComputedStyle(p);
    if (!/(auto|scroll|hidden|clip)/.test(`${style.overflowX} ${style.overflowY}`)) continue;
    const r = p.getBoundingClientRect();
    top = Math.max(top, r.top);
    left = Math.max(left, r.left);
    right = Math.min(right, r.left + p.clientWidth);
    bottom = Math.min(bottom, r.top + p.clientHeight);
  }
  return { top, left, right, bottom };
}

const EDGE = 8;

/**
 * D-167: a popover (calendar, menu, filter, list) always stays in view and never adds space to the page. Once it is drawn it
 * is measured against the window and any scrolling box it sits in (a drawer): too far right or left, it slides back inside;
 * no room below but more above, it opens upward (and the other way). Only inline left/right/top/bottom are set, so the
 * component's own classes are untouched. Placed again when the window is resized.
 */
export function useKeepInView(ref: RefObject<HTMLElement | null>, open: boolean) {
  useIsoLayoutEffect(() => {
    const el = ref.current;
    if (!open || !el) return undefined;
    const place = () => {
      el.style.left = '';
      el.style.right = '';
      el.style.top = '';
      el.style.bottom = '';
      const b = clipBounds(el);
      const r = el.getBoundingClientRect();
      let shift = 0;
      if (r.right > b.right - EDGE) shift = b.right - EDGE - r.right;
      if (r.left + shift < b.left + EDGE) shift = b.left + EDGE - r.left;
      if (shift !== 0) {
        el.style.left = `${el.offsetLeft + shift}px`;
        el.style.right = 'auto';
      }
      const anchor = (el.offsetParent as HTMLElement | null)?.getBoundingClientRect();
      if (!anchor) return;
      const below = b.bottom - anchor.bottom;
      const above = anchor.top - b.top;
      const need = r.height + EDGE;
      const up = r.bottom <= anchor.top + 1;
      if (!up && need > below && above > below) {
        el.style.top = 'auto';
        el.style.bottom = 'calc(100% + var(--space-1))';
      } else if (up && need > above && below > above) {
        el.style.bottom = 'auto';
        el.style.top = 'calc(100% + var(--space-1))';
      }
    };
    place();
    window.addEventListener('resize', place);
    return () => window.removeEventListener('resize', place);
  }, [open, ref]);
}
