'use client';

import Link from 'next/link';

import type { Me } from '@/api/types';
import { AlertsBell, type BellProps } from '@/features/alerts/AlertsBell';
import { StartWorkButton } from '@/features/start-work/StartWorkButton';

import type { DestinationInfo } from './destinations';
import { SampleLabel } from './SampleLabel';

type Props = { me: Me | null; roleWords: string | null; destinations: DestinationInfo[]; current: DestinationInfo | undefined; bell?: BellProps };

/**
 * CMP-01 top bar (desktop, 720px and wider): brand, links, then at the right the alert bell (F-15, when the shell
 * passes one), the name and Start work (CMP-23) last, as concept 3 of the alerts-bell concepts orders them. Start work
 * shows only when /me startable_lines is not empty. No account menu or sign-out in this release (D-SIGNIN is open).
 * The role words come from role-dashboard and show only when that read gave some. Below 1080px the role is visually hidden (name only) but stays in the accessible name.
 */
export function TopNav({ me, roleWords, destinations, current, bell }: Props) {
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
        {bell && <AlertsBell {...bell} />}
        {me && (
          <span className="psl-nav__who">
            <span className="shell-who-name">{me.name}</span>
            {roleWords && <span className="shell-who-role"> · {roleWords}</span>}
          </span>
        )}
        <span className="shell-navend">
          {me && me.startable_lines.length > 0 && <StartWorkButton variant="bar" />}
          <SampleLabel />
        </span>
      </div>
    </nav>
  );
}
