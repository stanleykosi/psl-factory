'use client';

// SplitButton (design/system/project/components/SplitButton, CMP-23): Start work in the top bar. The main part
// starts the person's most-used line; the arrow opens the Menu of every line they may start. Shown only when the
// person may start something: with no items it renders nothing (hidden, not disabled). The arrow half stays
// pressed while its menu is open. On a phone the shell draws "+ Start" instead.
import { Icon } from './Icon';
import { buttonClass } from './Button';
import { cx } from './internal';
import { Menu, useMenuButton, type MenuItem } from './Menu';

export function SplitButton({ label = 'Start work', onMain, items, moreLabel = 'More ways to start', menuLabel = 'Lines you can start', className }: {
  label?: string;
  onMain: () => void;
  items: MenuItem[];
  moreLabel?: string;
  menuLabel?: string;
  className?: string;
}) {
  const { open, close, id, triggerRef, triggerProps } = useMenuButton();
  if (items.length === 0) return null;
  const main = buttonClass('start', 'sm');
  return (
    <span className={cx('cmp-anchor cmp-anchor--inline', className)}>
      <span className="psl-split">
        <button type="button" className={main} onClick={onMain}>
          <Icon name="plus" />
          {label}
        </button>
        <button {...triggerProps} type="button" className={cx(main, 'psl-split__more', open && 'is-open')} aria-label={moreLabel}>
          <Icon name="chev" />
        </button>
      </span>
      {open && <Menu id={id} label={menuLabel} items={items} initial={open} onClose={close} triggerRef={triggerRef} align="end" />}
    </span>
  );
}
