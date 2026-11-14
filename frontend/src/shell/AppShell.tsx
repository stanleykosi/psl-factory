'use client';

import { usePathname } from 'next/navigation';
import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react';

import { api, call, setCsrfToken } from '@/api/client';
import { ApiError, networkError } from '@/api/errors';
import type { Me } from '@/api/types';

import { destinationForPath, visibleDestinations } from './destinations';
import { ForbiddenState, LoadErrorState, LoadingState, NoSectionsState, SignedOutState } from './FrameStates';
import { PhoneBar, type PhoneBack } from './PhoneBar';
import { TopNav } from './TopNav';

type MeState = { status: 'loading' } | { status: 'ready'; me: Me } | { status: 'error'; error: ApiError };

const MeContext = createContext<Me | null>(null);
const PhoneBackContext = createContext<((back: PhoneBack | null) => void) | null>(null);

/** The signed-in person from GET /api/v1/me, for pages inside the frame. */
export function useMe(): Me {
  const me = useContext(MeContext);
  if (!me) throw new Error('useMe is only available inside a loaded AppShell');
  return me;
}

/**
 * A sub-page's back link for the phone bar ("← Queue" on SCR-10-mobile): while the page is mounted the bar
 * shows this link in place of Menu and PSL FACTORY, as the phone boards draw it. Pages that never call it keep
 * the menu bar.
 */
export function usePhoneBack({ label, href }: PhoneBack) {
  const setBack = useContext(PhoneBackContext);
  if (!setBack) throw new Error('usePhoneBack is only available inside AppShell');
  useEffect(() => {
    const back = { label, href };
    setBack(back);
    return () => setBack(null);
  }, [setBack, label, href]);
}

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname() ?? '/';
  const [state, setState] = useState<MeState>({ status: 'loading' });
  const [phoneBack, setPhoneBack] = useState<PhoneBack | null>(null);

  const load = useCallback(async () => {
    setState({ status: 'loading' });
    try {
      const me = await call(api.GET('/api/v1/me'));
      setCsrfToken(me.csrf_token);
      setState({ status: 'ready', me });
    } catch (error) {
      setCsrfToken(null);
      setState({ status: 'error', error: error instanceof ApiError ? error : networkError() });
    }
  }, []);

  useEffect(() => {
    // One /me call per page load; the effect only starts the request.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, [load]);

  const me = state.status === 'ready' ? state.me : null;
  const destinations = me ? visibleDestinations(me.destinations) : [];
  const current = destinations.find((d) => d.key === destinationForPath(pathname)?.key);

  let main: ReactNode;
  if (state.status === 'loading') main = <LoadingState />;
  else if (state.status === 'error') {
    const { error } = state;
    if (error.kind === 'unauthenticated') main = <SignedOutState pathname={pathname} />;
    else if (error.kind === 'forbidden') main = <ForbiddenState error={error} />;
    else main = <LoadErrorState error={error} onRetry={() => void load()} />;
  } else if (destinations.length === 0) main = <NoSectionsState />;
  else
    main = (
      <MeContext.Provider value={state.me}>
        <PhoneBackContext.Provider value={setPhoneBack}>{children}</PhoneBackContext.Provider>
      </MeContext.Provider>
    );

  return (
    <>
      <a className="shell-skip" href="#main">
        Skip to main content
      </a>
      <div className="shell-topbar">
        <TopNav me={me} destinations={destinations} current={current} />
      </div>
      <div className="shell-phone">
        <PhoneBar key={pathname} me={me} destinations={destinations} current={current} back={phoneBack} />
      </div>
      <main id="main" tabIndex={-1} className="shell-main">
        {main}
      </main>
    </>
  );
}
