'use client';

import Link from 'next/link';

import type { Destination } from '@/api/types';
import { EmptyState, PageTitle } from '@/components';

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
      <PageTitle>{info.label}</PageTitle>
      <EmptyState title={info.label}>This page is not built yet. It arrives in a later release.</EmptyState>
    </>
  );
}

/** An address that is not a destination: the shared empty pattern with a way back. */
export function UnknownPage() {
  const first = visibleDestinations(useMe().destinations)[0];
  return (
    <EmptyState title="This page doesn&rsquo;t exist.">
      <Link href={first.href}>Go to {first.label}</Link>
    </EmptyState>
  );
}
