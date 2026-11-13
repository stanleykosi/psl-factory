'use client';

import type { Destination } from '@/api/types';

import { useMe } from './AppShell';
import { DESTINATIONS, visibleDestinations } from './destinations';
import { NotOpenState } from './FrameStates';

/** A destination whose screen arrives in a later task: page title plus the shared empty pattern. */
export function DestinationPage({ destination }: { destination: Destination }) {
  const me = useMe();
  const info = DESTINATIONS.find((d) => d.key === destination)!;
  if (!me.destinations.includes(destination)) {
    return <NotOpenState first={visibleDestinations(me.destinations)[0]} />;
  }
  return (
    <>
      <h1 className="shell-title">{info.label}</h1>
      <div className="psl-empty">
        <h3>{info.label}</h3>
        <p>This page is not built yet. It arrives in a later release.</p>
      </div>
    </>
  );
}
