'use client';

// The alert bell (F-15, concept 3 of design/concepts/alerts-bell-concepts.html) in the top bar and the phone bar:
// a button that opens the one alerts drawer, the unread badge, and from 1080px the red "N need you" chip.
import { badgeText, bellName } from './model';

export const ALERTS_DRAWER_ID = 'alerts-drawer';

/** What the bars need to draw the bell; the counts are already the ones to show (none when unknown). */
export type BellProps = {
  unread: number | undefined;
  need: number;
  open: boolean;
  onOpen: (button: HTMLButtonElement) => void;
};

function BellIcon() {
  return (
    <svg aria-hidden="true" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M6 9a6 6 0 0 1 12 0c0 6 2 7 2 7H4s2-1 2-7z" />
      <path d="M10 20a2 2 0 0 0 4 0" />
    </svg>
  );
}

export function AlertsBell({ unread, need, open, onOpen, phone = false }: BellProps & { phone?: boolean }) {
  const badge = badgeText(unread);
  return (
    <span className="shell-bellwrap">
      <button
        type="button"
        className={`shell-bell${open ? ' is-open' : ''}`}
        aria-label={bellName(unread, need)}
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-controls={ALERTS_DRAWER_ID}
        onClick={(event) => onOpen(event.currentTarget)}
      >
        <BellIcon />
        {badge && (
          <span className="shell-bellbadge" aria-hidden="true">
            {badge}
          </span>
        )}
      </button>
      {/* In the bell's name already; the phone bar has no chip (the Needs you tab carries the count). */}
      {!phone && need > 0 && (
        <span className="shell-bellchip" aria-hidden="true">
          {need} need you
        </span>
      )}
    </span>
  );
}
