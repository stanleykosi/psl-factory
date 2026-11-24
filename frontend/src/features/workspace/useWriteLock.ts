'use client';

// The locking both write hooks share (useWorkspaceStep for the v7 item, useWorkCommand for the live item):
// one write at a time, guarded synchronously by a ref so a double click sends once, a `pending` token for the
// press that is running, and a set of keys that stay locked after an outcome that may or may not have happened.
import { useCallback, useRef, useState } from 'react';

export function useWriteLock() {
  const [pending, setPending] = useState<string | null>(null);
  const [locked, setLocked] = useState<ReadonlySet<string>>(() => new Set());
  const writing = useRef(false);

  /** Takes the write slot; false when a write is already running (nothing may be sent). */
  const begin = useCallback((token: string) => {
    if (writing.current) return false;
    writing.current = true;
    setPending(token);
    return true;
  }, []);
  const end = useCallback(() => {
    writing.current = false;
    setPending(null);
  }, []);
  const lock = useCallback((key: string) => setLocked((current) => new Set(current).add(key)), []);

  return { pending, locked, writing, begin, end, lock };
}

// ---- The same lock, kept per scope above the components (F-87, TECH-2-1) ----
// The live item's controls and every line form can be unmounted without a new read (History and back, a failed panel
// re-read). A lock held in component state would be lost with them, and a write that may have happened could be sent
// again. This store lives in the module, keyed by scope (the work id), so it outlives them; only a full page load clears it.
import { useSyncExternalStore } from 'react';

type Shared = { pending: string | null; locked: ReadonlySet<string>; unread: object | null };
const EMPTY: Shared = { pending: null, locked: new Set(), unread: null };
const states = new Map<string, Shared>();
const writing = new Map<string, boolean>();
const listeners = new Set<() => void>();

const read = (scope: string): Shared => states.get(scope) ?? EMPTY;
function change(scope: string, patch: Partial<Shared>) {
  states.set(scope, { ...read(scope), ...patch });
  listeners.forEach((listener) => listener());
}
const subscribe = (listener: () => void) => {
  listeners.add(listener);
  return () => void listeners.delete(listener);
};

/** `useWriteLock`'s shape, backed by the scope's store. `unread` is the item a failed re-read left unread (null: none). */
export function useScopedWriteLock(scope: string) {
  const { pending, locked, unread } = useSyncExternalStore(subscribe, () => read(scope), () => EMPTY);
  const begin = useCallback(
    (token: string) => {
      if (writing.get(scope)) return false;
      writing.set(scope, true);
      change(scope, { pending: token });
      return true;
    },
    [scope],
  );
  const end = useCallback(() => {
    writing.set(scope, false);
    change(scope, { pending: null });
  }, [scope]);
  const lock = useCallback((key: string) => change(scope, { locked: new Set(read(scope).locked).add(key) }), [scope]);
  const setUnread = useCallback((item: object | null) => change(scope, { unread: item }), [scope]);
  return { pending, locked, unread, begin, end, lock, setUnread };
}

/** Test seam: forget every scope (a full page load does this in the browser). */
export function resetScopedWriteLocks() {
  states.clear();
  writing.clear();
  listeners.forEach((listener) => listener());
}
