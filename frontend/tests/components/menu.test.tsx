// @vitest-environment jsdom
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { MenuButton, SplitButton, type MenuItem } from '@/components';

import { violations } from './a11y';

const onCopy = vi.fn();
const ITEMS: MenuItem[] = [
  { key: 'cancel', label: 'Request cancellation', detail: 'A Finance Lead decides', danger: true, onSelect: vi.fn() },
  { key: 'copy', label: 'Copy reference', onSelect: onCopy },
  { key: 'open', label: 'Open in Projects', href: '/projects/1' },
  { key: 'role', label: 'Switch role', disabledReason: 'You have one role' },
  { key: 'ask', label: 'Ask Chidi about this', onSelect: vi.fn() },
];

const trigger = () => screen.getByRole('button', { name: 'More actions' });
const focused = () => document.activeElement as HTMLElement;

describe('Menu', () => {
  it('opens on the first item; arrows wrap, Home/End, typeahead; the danger item is last after a separator', async () => {
    render(<MenuButton label="More actions" icon="more" iconOnly items={ITEMS} />);
    expect(trigger().getAttribute('aria-haspopup')).toBe('menu');
    fireEvent.keyDown(trigger(), { key: 'ArrowDown' });
    const menu = screen.getByRole('menu', { name: 'More actions' });
    expect(trigger().getAttribute('aria-expanded')).toBe('true');
    expect(trigger().getAttribute('aria-controls')).toBe(menu.id);
    const items = screen.getAllByRole('menuitem');
    expect(items.map((i) => i.querySelector('strong')?.textContent)).toEqual(['Copy reference', 'Open in Projects', 'Switch role', 'Ask Chidi about this', 'Request cancellation']);
    expect(items[4].previousElementSibling?.getAttribute('role')).toBe('separator');
    expect(items[4].className).toContain('psl-menuitem--danger');
    expect(focused()).toBe(items[0]);
    expect(items[0].className).toContain('is-active');
    expect(await violations()).toEqual([]);
    fireEvent.keyDown(focused(), { key: 'ArrowUp' });
    expect(focused()).toBe(items[4]);
    fireEvent.keyDown(focused(), { key: 'ArrowDown' });
    expect(focused()).toBe(items[0]);
    fireEvent.keyDown(focused(), { key: 'End' });
    expect(focused()).toBe(items[4]);
    fireEvent.keyDown(focused(), { key: 'Home' });
    expect(focused()).toBe(items[0]);
    fireEvent.keyDown(focused(), { key: 'a' });
    expect(focused()).toBe(items[3]);
    expect(items[2].getAttribute('aria-disabled')).toBe('true');
    expect(items[1].getAttribute('href')).toBe('/projects/1');
  });

  it('Esc closes and returns focus to the button; Enter runs an item and closes', () => {
    render(<MenuButton label="More actions" icon="more" iconOnly items={ITEMS} />);
    fireEvent.click(trigger());
    fireEvent.keyDown(focused(), { key: 'Escape' });
    expect(screen.queryByRole('menu')).toBeNull();
    expect(focused()).toBe(trigger());
    fireEvent.keyDown(trigger(), { key: 'ArrowUp' });
    expect(focused().textContent).toContain('Request cancellation');
    fireEvent.keyDown(focused(), { key: 'Home' });
    fireEvent.click(focused());
    expect(onCopy).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole('menu')).toBeNull();
    expect(focused()).toBe(trigger());
  });

  it('a disabled item does nothing; a press outside closes', () => {
    render(<MenuButton label="More actions" icon="more" iconOnly items={ITEMS} />);
    fireEvent.click(trigger());
    fireEvent.click(screen.getByRole('menuitem', { name: /Switch role/ }));
    expect(screen.getByRole('menu')).toBeTruthy();
    fireEvent.mouseDown(document.body);
    expect(screen.queryByRole('menu')).toBeNull();
  });
});

describe('SplitButton', () => {
  it('main part starts; the arrow opens the line menu and stays pressed; hidden with nothing to start', async () => {
    const onMain = vi.fn();
    const { rerender } = render(<SplitButton onMain={onMain} items={[{ key: 'inv', label: 'Invoice preparation and delivery', detail: 'From a completed milestone', group: 'Lines you can start · most used', onSelect: vi.fn() }]} />);
    fireEvent.click(screen.getByRole('button', { name: 'Start work' }));
    expect(onMain).toHaveBeenCalled();
    const more = screen.getByRole('button', { name: 'More ways to start' });
    expect(more.className).toBe('psl-btn psl-btn--start psl-btn--sm psl-split__more');
    fireEvent.click(more);
    expect(more.className).toContain('is-open');
    expect(screen.getByText('LINES YOU CAN START · MOST USED').className).toBe('psl-optgroup');
    expect(await violations()).toEqual([]);
    rerender(<SplitButton onMain={onMain} items={[]} />);
    expect(screen.queryByRole('button', { name: 'Start work' })).toBeNull();
  });
});
