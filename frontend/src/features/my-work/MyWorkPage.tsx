'use client';

import { Suspense } from 'react';

import { useMe } from '@/shell/AppShell';
import { visibleDestinations } from '@/shell/destinations';
import { NotOpenState } from '@/shell/FrameStates';

import { MyWork } from './MyWork';
import './my-work.css';

/** /my-work: the person's queues, for anyone whose /me lists My work. */
export function MyWorkPage() {
  const me = useMe();
  if (!me.destinations.includes('my_work')) {
    return <NotOpenState first={visibleDestinations(me.destinations)[0]} />;
  }
  // useSearchParams needs a Suspense boundary so `next build` can prerender the route.
  return (
    <Suspense fallback={null}>
      <MyWork />
    </Suspense>
  );
}
