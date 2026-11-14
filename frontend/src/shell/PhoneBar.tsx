'use client';

import Link from 'next/link';
import { useEffect, useRef, useState } from 'react';

import type { Me } from '@/api/types';

import type { DestinationInfo } from './destinations';
import { MenuIcon } from './icons';
import { SampleLabel } from './SampleLabel';

/** A sub-page's way back, drawn in the phone bar as "← label". */
export type PhoneBack = { label: string; href: string };

type Props = {
  me: Me | null;
  destinations: DestinationInfo[];
  current: DestinationInfo | undefined;
  back?: PhoneBack | null;
};

/**
 * CMP-01 phone bar (below 720px): a menu-button disclosure, PSL FACTORY and the sample label. On a sub-page
 * that sets a back link the bar shows "← label" instead of Menu and PSL FACTORY (SCR-10-mobile, SCR-22-mobile).
 */
export function PhoneBar({ me, destinations, current, back = null }: Props) {
  const [open, setOpen] = useState(false);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const hasMenu = me !== null && back === null;

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
        {back ? (
          <Link href={back.href} aria-label={`Back to ${back.label}`}>
            {`← ${back.label}`}
          </Link>
        ) : (
          <span className="psl-brand">PSL FACTORY</span>
        )}
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
