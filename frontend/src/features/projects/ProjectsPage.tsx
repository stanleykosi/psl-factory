'use client';

import { Suspense } from 'react';

import { useMe } from '@/shell/AppShell';
import { visibleDestinations } from '@/shell/destinations';
import { NotOpenState } from '@/shell/FrameStates';

import { ProjectsList } from './ProjectsList';
import './projects.css';

/** /projects: the projects list, for anyone whose /me lists Projects. Without it no request is made. */
export function ProjectsPage() {
  const me = useMe();
  if (!me.destinations.includes('projects')) {
    return <NotOpenState first={visibleDestinations(me.destinations)[0]} />;
  }
  // useSearchParams needs a Suspense boundary so `next build` can prerender the route.
  return (
    <Suspense fallback={null}>
      <ProjectsList />
    </Suspense>
  );
}
