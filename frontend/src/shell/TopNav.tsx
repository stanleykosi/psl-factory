'use client';

import Link from 'next/link';

import type { Me } from '@/api/types';

import type { DestinationInfo } from './destinations';
import { SampleLabel } from './SampleLabel';

type Props = { me: Me | null; destinations: DestinationInfo[]; current: DestinationInfo | undefined };

/** CMP-01 top bar (desktop, 720px and wider). No Start work, bell or account menu in this release. */
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
        <span style={{ marginLeft: 'auto', flex: 'none' }}>
          <SampleLabel />
        </span>
        {me && (
          <span className="psl-nav__who">
            {me.name} · {me.roles.join(', ')}
          </span>
        )}
      </div>
    </nav>
  );
}
