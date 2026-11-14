'use client';

import Link from 'next/link';

import type { Me } from '@/api/types';
import { StartWorkButton } from '@/features/start-work/StartWorkButton';

import type { DestinationInfo } from './destinations';
import { SampleLabel } from './SampleLabel';

type Props = { me: Me | null; destinations: DestinationInfo[]; current: DestinationInfo | undefined };

/**
 * CMP-01 top bar (desktop, 720px and wider). Start work (CMP-23) shows only when /me startable_lines is not empty;
 * no bell or account menu in this release.
 * Below 1080px the role is visually hidden (name only) but stays in the accessible name.
 */
export function TopNav({ me, destinations, current }: Props) {
  return (
    <nav className="psl-nav psl-on-dark" aria-label="Main">
      <div className="psl-nav__in">
        <span className="psl-brand">PSL FACTORY</span>
        {destinations.length > 0 && (
          <div className="psl-nav__links">
            {destinations.map((d) => (
              <Link key={d.key} href={d.href} className="psl-navlink" aria-current={d.key === current?.key ? 'page' : undefined}>
                {d.label}
              </Link>
            ))}
          </div>
        )}
        <span className="shell-navend">
          {me && me.startable_lines.length > 0 && <StartWorkButton variant="bar" />}
          <SampleLabel />
        </span>
        {me && (
          <span className="psl-nav__who">
            <span className="shell-who-name">{me.name}</span>
            <span className="shell-who-role"> · {me.roles.join(', ')}</span>
          </span>
        )}
      </div>
    </nav>
  );
}
