'use client';

// Menu (design/system/project/components/Menu): a list of actions that opens from a button. Same surface as the
// select list. Keyboard (the menu-button pattern): Enter, Space or Down on the button opens on the first item, Up
// on the last; in the menu, arrows move and wrap, Home and End jump, typing jumps to the first item that starts
// with the letters typed, Enter or Space runs the item, Esc closes and returns focus to the button, Tab closes.
// The keyboard-active item has the blue left edge. A disabled item stays readable with its reason; a destructive
// item is always last, after a separator.
import NextLink from 'next/link';
import { useEffect, useId, useRef, useState, type KeyboardEvent, type ReactNode, type RefObject } from 'react';

import { Button, type ButtonKind, type ButtonSize } from './Button';
import type { IconName } from './Icon';
import { IconButton } from './IconButton';
import { cx, isTypeaheadKey, useOutsidePress, useTypeahead } from './internal';

export type MenuItem = {
  key: string;
  label: string;
  /** The second line ("From a completed milestone"). */
  detail?: ReactNode;
  /** Navigation items are links. */
  href?: string;
  onSelect?: () => void;
  /** Why it cannot be used now; shown as its second line. */
  disabledReason?: string;
  /** Destructive (signal-ink); placed last, after a separator. */
  danger?: boolean;
  /** A mono caps group label drawn above this item. */
  group?: string;
  /** A separator above this item. */
  separatorBefore?: boolean;
  /** Leading avatar ("Describe it to Tola"). */
  leading?: ReactNode;
};

/** Destructive items move to the end, after a separator. */
function ordered(items: MenuItem[]): MenuItem[] {
  const safe = items.filter((i) => !i.danger);
  const danger = items.filter((i) => i.danger).map((i, n) => (n === 0 && safe.length > 0 ? { ...i, separatorBefore: true } : i));
  return [...safe, ...danger];
}

export type MenuProps = {
  id: string;
  label: string;
  items: MenuItem[];
  /** Which item takes focus on opening. */
  initial: 'first' | 'last';
  /** Called when the menu should close; `refocus` is true when focus should go back to the button. */
  onClose: (refocus: boolean) => void;
  triggerRef: RefObject<HTMLElement | null>;
  /** A non-interactive head (the account menu's name and role). */
  header?: ReactNode;
  align?: 'start' | 'end';
  className?: string;
};

export function Menu({ id, label, items, initial, onClose, triggerRef, header, align = 'start', className }: MenuProps) {
  const list = ordered(items);
  const [active, setActive] = useState(initial === 'first' ? 0 : list.length - 1);
  const refs = useRef<(HTMLElement | null)[]>([]);
  const menuRef = useRef<HTMLDivElement>(null);
  const typeahead = useTypeahead();

  useOutsidePress([menuRef, triggerRef], true, () => onClose(false));

  useEffect(() => {
    refs.current[active]?.focus();
  }, [active]);

  function run(item: MenuItem) {
    if (item.disabledReason) return;
    item.onSelect?.();
    onClose(!item.href);
  }

  function keys(event: KeyboardEvent<HTMLDivElement>) {
    const last = list.length - 1;
    if (event.key === 'ArrowDown') setActive((at) => (at >= last ? 0 : at + 1));
    else if (event.key === 'ArrowUp') setActive((at) => (at <= 0 ? last : at - 1));
    else if (event.key === 'Home') setActive(0);
    else if (event.key === 'End') setActive(last);
    else if (event.key === 'Escape') {
      event.stopPropagation();
      onClose(true);
    } else if (event.key === 'Tab') {
      onClose(false);
      return;
    } else if (isTypeaheadKey(event)) {
      const at = typeahead(event.key, list.map((i) => i.label), active + 1);
      if (at >= 0) setActive(at);
      return;
    } else return;
    event.preventDefault();
  }

  return (
    // Keys are handled once for the whole menu; each item is focusable.
    // eslint-disable-next-line jsx-a11y/no-static-element-interactions
    <div ref={menuRef} className={cx('psl-pop cmp-pop', align === 'end' && 'cmp-pop--end', className)} onKeyDown={keys}>
      {header && <div className="cmp-menuhead">{header}</div>}
      <div id={id} role="menu" aria-label={label} className="psl-menu cmp-menu">
        {list.map((item, at) => {
          const common = {
            role: 'menuitem',
            className: cx('psl-menuitem', item.danger && 'psl-menuitem--danger', item.leading !== undefined && 'psl-menuitem--agent', at === active && 'is-active'),
            tabIndex: at === active ? 0 : -1,
            'aria-disabled': item.disabledReason ? true : undefined,
            onFocus: () => setActive(at),
          } as const;
          const setRef = (el: HTMLElement | null) => {
            refs.current[at] = el;
          };
          const body = (
            <>
              {item.leading}
              <strong>{item.label}</strong>
              {(item.disabledReason ?? item.detail) && <small>{item.disabledReason ?? item.detail}</small>}
            </>
          );
          return (
            <MenuRow key={item.key} item={item} at={at} list={list}>
              {item.href && !item.disabledReason ? (
                <NextLink {...common} ref={setRef} href={item.href} onClick={() => run(item)}>
                  {body}
                </NextLink>
              ) : (
                <button {...common} ref={setRef} type="button" className={cx(common.className, 'cmp-menubutton')} onClick={() => run(item)}>
                  {body}
                </button>
              )}
            </MenuRow>
          );
        })}
      </div>
    </div>
  );
}

function MenuRow({ item, at, list, children }: { item: MenuItem; at: number; list: MenuItem[]; children: ReactNode }) {
  const groupStart = item.group !== undefined && item.group !== list[at - 1]?.group;
  return (
    <>
      {item.separatorBefore && at > 0 && <div className="psl-sep" role="separator" />}
      {groupStart && (
        <div className="psl-optgroup" role="presentation">
          {item.group?.toUpperCase()}
        </div>
      )}
      {children}
    </>
  );
}

/** Opening state and keys shared by every button that opens a menu (MenuButton, SplitButton). */
export function useMenuButton() {
  const [open, setOpen] = useState<false | 'first' | 'last'>(false);
  const triggerRef = useRef<HTMLButtonElement | null>(null);
  const id = useId();
  const close = (refocus: boolean) => {
    setOpen(false);
    if (refocus) triggerRef.current?.focus();
  };
  const triggerProps = {
    ref: triggerRef,
    'aria-haspopup': 'menu' as const,
    'aria-expanded': open !== false,
    'aria-controls': open ? id : undefined,
    onClick: () => setOpen((o) => (o ? false : 'first')),
    onKeyDown: (event: KeyboardEvent<HTMLButtonElement>) => {
      if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
        event.preventDefault();
        setOpen(event.key === 'ArrowDown' ? 'first' : 'last');
      }
    },
  };
  return { open, close, id, triggerRef, triggerProps };
}

/** A button that opens a menu: a labelled button, or an icon button when `icon` is given without `kind`. */
export function MenuButton({ label, items, menuLabel, icon, iconOnly = false, kind = 'secondary', size = 'md', header, align = 'start', className }: {
  label: string;
  items: MenuItem[];
  /** The menu's name; the button's label by default. */
  menuLabel?: string;
  icon?: IconName;
  /** An icon button ("More actions"); needs `icon`. */
  iconOnly?: boolean;
  kind?: ButtonKind;
  size?: ButtonSize;
  header?: ReactNode;
  align?: 'start' | 'end';
  className?: string;
}) {
  const { open, close, id, triggerRef, triggerProps } = useMenuButton();
  return (
    <span className={cx('cmp-anchor cmp-anchor--inline', className)}>
      {iconOnly && icon ? (
        <IconButton {...triggerProps} icon={icon} label={label} />
      ) : (
        <Button {...triggerProps} kind={kind} size={size} icon={icon}>
          {label}
        </Button>
      )}
      {open && <Menu id={id} label={menuLabel ?? label} items={items} initial={open} onClose={close} triggerRef={triggerRef} header={header} align={align} />}
    </span>
  );
}
