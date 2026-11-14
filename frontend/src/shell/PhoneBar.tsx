'use client';

import Link from 'next/link';
import { useEffect, useRef, useState } from 'react';

import type { Me } from '@/api/types';

import type { DestinationInfo } from './destinations';
import { MenuIcon } from './icons';
import { SampleLabel } from './SampleLabel';

type Props = { me: Me | null; destinations: DestinationInfo[]; current: DestinationInfo | undefined };

/** CMP-01 phone bar (below 720px): a menu-button disclosure, PSL FACTORY and the sample label. */
export function PhoneBar({ me, destinations, current }: Props) {
  const [open, setOpen] = useState(false);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const hasMenu = me !== null;

  useEffect(() => {
    if (!open) return undefined;
    function onKeyDown(event: KeyboardEvent) {
      if (event.key !== 'Escape') return;
      setOpen(false);
      buttonRef.current?.focus();
    }
    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [open]);

  return (
    <>
      <header className="psl-phonebar psl-on-dark">
        {hasMenu && (
          <button
            ref={buttonRef}
            type="button"
            className="shell-menubutton"
            aria-label="Menu"
            aria-expanded={open}
            aria-controls="phone-menu"
            onClick={() => setOpen((value) => !value)}
          >
            <MenuIcon />
          </button>
        )}
        <span className="psl-brand">PSL FACTORY</span>
        <SampleLabel />
      </header>
      {hasMenu && open && (
        <nav id="phone-menu" aria-label="Main" className="psl-pop psl-menu">
          <p className="shell-menuwho">
            <strong>{me.name}</strong>
            <small>{me.roles.join(', ')}</small>
          </p>
          <div className="psl-sep" aria-hidden="true" />
          {destinations.map((d) => (
            <Link
              key={d.key}
              href={d.href}
              className="psl-menuitem"
              aria-current={d.key === current?.key ? 'page' : undefined}
              onClick={() => setOpen(false)}
            >
              <strong>{d.label}</strong>
            </Link>
          ))}
        </nav>
      )}
    </>
  );
}
