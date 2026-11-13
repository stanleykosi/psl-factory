'use client';

import { useRouter } from 'next/navigation';
import { useEffect } from 'react';

import { useMe } from './AppShell';
import { visibleDestinations } from './destinations';

/** `/` sends the person to their first destination, in display order. */
export function HomeRedirect() {
  const me = useMe();
  const router = useRouter();
  const first = visibleDestinations(me.destinations)[0];
  useEffect(() => {
    if (first) router.replace(first.href);
  }, [first, router]);
  return null;
}
