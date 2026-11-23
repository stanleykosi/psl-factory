import type { DestinationKey, Me } from '@/api/types';

export type DestinationInfo = { key: DestinationKey; label: string; href: string };

// Display order and labels from the site map (SITEMAP-desktop) and CMP-01.
export const DESTINATIONS: readonly DestinationInfo[] = [
  { key: 'my_work', label: 'My work', href: '/my-work' },
  { key: 'projects', label: 'Projects', href: '/projects' },
  { key: 'overview', label: 'Overview', href: '/overview' },
  { key: 'assistant', label: 'Assistant', href: '/assistant' },
  { key: 'setup', label: 'Setup', href: '/setup' },
];

/** The destinations /me lists, matched by key, in display order. Keys the frame has no link for (clients) draw none. Presentation only; the API enforces access. */
export function visibleDestinations(listed: Me['destinations']): DestinationInfo[] {
  return DESTINATIONS.filter((d) => listed.some((l) => l.key === d.key));
}

/** Whether /me lists this destination (clients included, which has no link of its own). */
export function hasDestination(me: Me, key: DestinationKey): boolean {
  return me.destinations.some((d) => d.key === key);
}

export function destinationForPath(pathname: string): DestinationInfo | undefined {
  // Clients sit under Projects (SCR-35 draws Projects current).
  if (pathname === '/clients' || pathname.startsWith('/clients/')) return DESTINATIONS.find((d) => d.key === 'projects');
  return DESTINATIONS.find((d) => pathname === d.href || pathname.startsWith(`${d.href}/`));
}
