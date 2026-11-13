import type { Destination } from '@/api/types';

export type DestinationInfo = { key: Destination; label: string; href: string };

// Display order and labels from the site map (SITEMAP-desktop) and CMP-01.
export const DESTINATIONS: readonly DestinationInfo[] = [
  { key: 'my_work', label: 'My work', href: '/my-work' },
  { key: 'projects', label: 'Projects', href: '/projects' },
  { key: 'overview', label: 'Overview', href: '/overview' },
  { key: 'assistant', label: 'Assistant', href: '/assistant' },
  { key: 'setup', label: 'Setup', href: '/setup' },
];

/** The destinations /me lists, in display order. Presentation only; the API enforces access. */
export function visibleDestinations(allowed: readonly Destination[]): DestinationInfo[] {
  return DESTINATIONS.filter((d) => allowed.includes(d.key));
}

export function destinationForPath(pathname: string): DestinationInfo | undefined {
  return DESTINATIONS.find((d) => pathname === d.href || pathname.startsWith(`${d.href}/`));
}
