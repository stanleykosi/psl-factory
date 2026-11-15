'use client';

// CMP-23 Start work. In the top bar ('bar'): the "+ Start work" main part and the "More ways to start" chevron;
// in the phone bar ('phone'): "+ Start", which opens the chooser. The shell mounts it only when /me
// startable_lines is not empty; which lines appear, and whether the main part opens one directly, come from E-LINES.
import { useCallback, useEffect, useRef, useState } from 'react';

import { buttonClass, Icon } from '@/components';

import { StartWorkDrawer, type StartEntry } from './StartWorkDrawer';

export function StartWorkButton({ variant }: { variant: 'bar' | 'phone' }) {
  const [entry, setEntry] = useState<StartEntry | null>(null);
  const opener = useRef<HTMLButtonElement | null>(null);
  // Set on close; focus goes back to the opener once the drawer has gone, so nothing inside it takes focus after.
  const restore = useRef(false);

  const open = (how: StartEntry, button: HTMLButtonElement) => {
    opener.current = button;
    setEntry(how);
  };
  const close = useCallback(() => {
    restore.current = true;
    setEntry(null);
  }, []);

  useEffect(() => {
    if (entry !== null || !restore.current) return;
    restore.current = false;
    opener.current?.focus();
  }, [entry]);

  return (
    <>
      {variant === 'bar' ? (
        <span className="psl-split sw-split">
          <button type="button" className={buttonClass('start', 'sm')} onClick={(e) => open('default', e.currentTarget)}>
            <Icon name="plus" />
            <span>
              Start <span className="sw-word">work</span>
            </span>
          </button>
          <button
            type="button"
            className={`${buttonClass('start', 'sm')} psl-split__more${entry === 'chooser' ? ' is-open' : ''}`}
            aria-label="More ways to start"
            aria-haspopup="dialog"
            aria-expanded={entry === 'chooser'}
            onClick={(e) => open('chooser', e.currentTarget)}
          >
            <Icon name="chev" />
          </button>
        </span>
      ) : (
        <button
          type="button"
          className={`${buttonClass('start', 'sm')} sw-phonestart`}
          aria-label="Start work"
          aria-haspopup="dialog"
          onClick={(e) => open('chooser', e.currentTarget)}
        >
          <Icon name="plus" />
          Start
        </button>
      )}
      {entry && <StartWorkDrawer entry={entry} onClose={close} />}
    </>
  );
}
