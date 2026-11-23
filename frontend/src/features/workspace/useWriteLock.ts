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
  const unlock = useCallback(
    (key: string) =>
      setLocked((current) => {
        if (!current.has(key)) return current;
        const next = new Set(current);
        next.delete(key);
        return next;
      }),
    [],
  );

  return { pending, locked, writing, begin, end, lock, unlock };
}
