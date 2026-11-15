'use client';

import { usePathname } from 'next/navigation';
import { createContext, useCallback, useContext, useEffect, useLayoutEffect, useRef, useState, type ReactNode } from 'react';

import { api, call, setCsrfToken } from '@/api/client';
import { ApiError, networkError } from '@/api/errors';
import type { Me } from '@/api/types';
import { AlertsDrawer } from '@/features/alerts/AlertsDrawer';
import type { BellProps } from '@/features/alerts/AlertsBell';
import { needsYou, needsYouKnown } from '@/features/alerts/model';
import { useAlertsFeed } from '@/features/alerts/useAlertsFeed';
import { useIsPhone } from '@/features/alerts/useIsPhone';

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
export function usePhoneBack({ label, href, note }: PhoneBack) {
  const setBack = useContext(PhoneBackContext);
  if (!setBack) throw new Error('usePhoneBack is only available inside AppShell');
  // Layout effect: the link is set and cleared before paint, so no frame shows the previous page's bar.
  useLayoutEffect(() => {
    const back = { label, href, note };
    setBack(back);
    return () => setBack(null);
  }, [setBack, label, href, note]);
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

  // The alert bell (F-15): one feed and one drawer for both bars. The drawer is open on the path it was opened on,
  // so any route change closes it; on every close focus goes back to the bell that opened it.
  const ready = destinations.length > 0;
  const feed = useAlertsFeed(ready);
  const phone = useIsPhone();
  const [alertsAt, setAlertsAt] = useState<string | null>(null);
  const alertsOpen = ready && alertsAt === pathname;
  // Which bar's bell opened it: the phone bar remounts on a route change, so the bell is looked up again on close.
  const opener = useRef('.shell-topbar .shell-bell');
  const wasOpen = useRef(false);
  const leaving = useRef(false);
  const closeAlerts = useCallback(() => setAlertsAt(null), []);
  // Open and the footer links close the drawer and then change the page; the bar there is the one to take focus.
  // A link to the page already shown never changes the path, so it leaves the flag off and the close effect returns focus to the bell.
  const leaveAlerts = useCallback(
    (href: string) => {
      leaving.current = href.split(/[?#]/)[0] !== pathname;
      setAlertsAt(null);
    },
    [pathname],
  );
  useEffect(() => {
    if (!leaving.current) return;
    leaving.current = false;
    document.querySelector<HTMLElement>(opener.current)?.focus();
  }, [pathname]);
  useEffect(() => {
    if (alertsOpen) wasOpen.current = true;
    else if (wasOpen.current) {
      wasOpen.current = false;
      document.querySelector<HTMLElement>(opener.current)?.focus();
    }
  }, [alertsOpen]);

  let bell: BellProps | undefined;
  if (ready) {
    const ok = feed.data && !feed.error;
    const items = ok ? feed.data!.items : [];
    bell = {
      unread: ok ? feed.data!.unreadCount : undefined,
      need: needsYouKnown(items) ? items.filter((alert) => needsYou(alert) && alert.read === false).length : 0,
      open: alertsOpen,
      onOpen: (button) => {
        if (alertsOpen) return closeAlerts();
        leaving.current = false;
        opener.current = button.closest('.shell-phone') ? '.shell-phone .shell-bell' : '.shell-topbar .shell-bell';
        setAlertsAt(pathname);
        void feed.refresh();
      },
    };
  }

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
      <a className="shell-skip" href="#main" inert={alertsOpen}>
        Skip to main content
      </a>
      <div className="shell-topbar">
        <TopNav me={me} destinations={destinations} current={current} bell={bell} />
      </div>
      <div className="shell-phone" inert={alertsOpen}>
        <PhoneBar key={pathname} me={me} destinations={destinations} current={current} back={phoneBack} bell={bell} />
      </div>
      <main id="main" tabIndex={-1} className="shell-main" inert={alertsOpen}>
        {main}
      </main>
      {alertsOpen && <AlertsDrawer feed={feed} phone={phone} pathname={pathname} onClose={closeAlerts} onLeave={leaveAlerts} />}
    </>
  );
}
