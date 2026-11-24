'use client';

import { useRouter } from 'next/navigation';
import { useCallback, useEffect, useRef } from 'react';

import { call, liveApi } from '@/api/client';
import { Button, Callout } from '@/components';

import { useSignOut } from './useSignOut';

/**
 * What happens once a person is signed in: a person with no open work stays on the page (`onNotAdmitted`); everyone
 * else goes on to `destination`, or the home page. An onboarding read that fails leaves the frame to show its own states.
 */
export function useAfterSignIn(onNotAdmitted: () => void) {
  const router = useRouter();
  // The router object may change between renders; the follow-up must use the current one without restarting.
  const routerRef = useRef(router);
  useEffect(() => {
    routerRef.current = router;
  });
  return useCallback(
    async (destination: string | null) => {
      try {
        const onboarding = await call(liveApi.GET('/api/v1/me/onboarding'));
        if (!onboarding.admitted) return onNotAdmitted();
      } catch {
        // The frame shows its own states.
      }
      routerRef.current.replace(destination ?? '/');
    },
    [onNotAdmitted],
  );
}

/** The body of a signed-in person who has no work yet: the notice and Sign out. `onSignedOut` runs on a page that stays mounted. */
export function NotAdmittedBody({ title = 'Sign in', onSignedOut }: { title?: string; onSignedOut?: () => void }) {
  const { signOut, busy } = useSignOut(onSignedOut);
  return (
    <div className="signin-form">
      <h1 className="signin-title">{title}</h1>
      <Callout kind="info">You’re signed in, but no work is open to you yet. Ask your administrator.</Callout>
      <Button kind="secondary" size="lg" busy={busy} busyLabel="Signing out…" onClick={() => void signOut()}>
        Sign out
      </Button>
    </div>
  );
}
