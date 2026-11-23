'use client';

import { useRouter } from 'next/navigation';
import { useCallback, useRef, useState } from 'react';

import { call, csrfHeader, liveApi, setCsrfToken } from '@/api/client';
import { ApiError } from '@/api/errors';
import { useToast } from '@/components';

/**
 * Ends the session (POST /api/v1/session/logout), keeps the new token and goes to /sign-in, which leaves the old frame
 * behind (or, on the sign-in page itself, runs `onSignedOut`). A failure keeps the person where they are with a toast; the request is never repeated by the app.
 */
export function useSignOut(onSignedOut?: () => void) {
  const router = useRouter();
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const running = useRef(false);
  const signOut = useCallback(async () => {
    if (running.current) return;
    running.current = true;
    setBusy(true);
    try {
      const session = await call(liveApi.POST('/api/v1/session/logout', { params: csrfHeader, body: {} }));
      setCsrfToken(session.csrf_token);
      router.replace('/sign-in');
      // Already on /sign-in (the not-admitted notice): the page stays mounted, so it starts over itself.
      onSignedOut?.();
    } catch (error) {
      // call() has already re-read the token after a csrf_failed.
      const stale = error instanceof ApiError && error.kind === 'csrf';
      toast.show(stale ? 'Your session was refreshed. Press Sign out again. Nothing was changed.' : 'We couldn’t sign you out. Try again.', { kind: 'problem' });
    } finally {
      running.current = false;
      setBusy(false);
    }
  }, [router, toast, onSignedOut]);
  return { signOut, busy };
}
