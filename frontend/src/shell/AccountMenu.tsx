'use client';

import { Menu, useMenuButton } from '@/components';
import { useSignOut } from '@/features/sign-in/useSignOut';

/**
 * SCR-15-desktop-account: the name and role words in the top bar open a menu with the name and "Sign out" (the other
 * account items come with FE-ALERTS-MENU). The button keeps the who-line's class, so the bar lays it out as before;
 * the menu is a sibling, drawn under the bar's right edge. The accessible name starts "Account menu: " and then holds the
 * visible words, so it contains the label a sighted person reads.
 */
export function AccountMenu({ name, roleWords }: { name: string; roleWords: string | null }) {
  const { open, close, id, triggerRef, triggerProps } = useMenuButton();
  const { signOut } = useSignOut();
  return (
    <>
      <button {...triggerProps} type="button" className="psl-nav__who" aria-label={`Account menu: ${name}${roleWords ? ` · ${roleWords}` : ''}`} title={roleWords ? `${name} · ${roleWords}` : undefined}>
        <span className="shell-who-name">{name}</span>
        {roleWords && <span className="shell-who-role"> · {roleWords}</span>}
      </button>
      {open && (
        <div className="shell-accountpop">
          <Menu
            id={id}
            label="Account"
            initial={open}
            onClose={close}
            triggerRef={triggerRef}
            header={
              <>
                <strong>{name}</strong>
                {roleWords && <small>{roleWords}</small>}
              </>
            }
            items={[{ key: 'sign-out', label: 'Sign out', detail: 'Signs you out on this device', onSelect: () => void signOut() }]}
          />
        </div>
      )}
    </>
  );
}
