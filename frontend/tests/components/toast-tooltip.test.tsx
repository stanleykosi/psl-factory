// @vitest-environment jsdom
import { act, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { IconButton, Toast, Tooltip } from '@/components';

import { violations } from './a11y';

beforeEach(() => vi.useFakeTimers());
afterEach(() => vi.useRealTimers());

describe('Toast', () => {
  it('success is a status with Undo; stays 6 seconds, longer while hovered', () => {
    const onDismiss = vi.fn();
    const onUndo = vi.fn();
    render(
      <Toast onDismiss={onDismiss} action={{ label: 'Undo', onClick: onUndo }}>
        R-07 accepted with your edit · next: R-08
      </Toast>,
    );
    const toast = screen.getByRole('status');
    expect(toast.className).toBe('psl-toast psl-on-dark');
    expect(toast.querySelector('.psl-tick svg')).not.toBeNull();
    fireEvent.mouseEnter(toast);
    act(() => vi.advanceTimersByTime(10000));
    expect(onDismiss).not.toHaveBeenCalled();
    fireEvent.mouseLeave(toast);
    act(() => vi.advanceTimersByTime(5999));
    expect(onDismiss).not.toHaveBeenCalled();
    act(() => vi.advanceTimersByTime(1));
    expect(onDismiss).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByRole('button', { name: 'Undo' }));
    expect(onUndo).toHaveBeenCalled();
  });

  it('the problem toast is an alert with a link to the fix; dismissible', async () => {
    vi.useRealTimers();
    const onDismiss = vi.fn();
    render(
      <Toast kind="problem" onDismiss={onDismiss} dismissible action={{ label: 'See what happened', href: '/imports/1' }}>
        The bank import stopped at row 214.
      </Toast>,
    );
    expect(screen.getByRole('alert').className).toBe('psl-toast psl-on-dark psl-toast--problem');
    expect(screen.getByRole('link', { name: 'See what happened' }).getAttribute('href')).toBe('/imports/1');
    expect(await violations()).toEqual([]);
    fireEvent.click(screen.getByRole('button', { name: 'Dismiss' }));
    expect(onDismiss).toHaveBeenCalled();
  });
});

describe('Tooltip', () => {
  it('shows after 300ms on focus or hover, describes the trigger, hides on Esc', async () => {
    render(
      <Tooltip text="Filters on: Line, State">
        <IconButton icon="filter" label="Filter" />
      </Tooltip>,
    );
    const button = screen.getByRole('button', { name: 'Filter' });
    const tip = document.getElementById(button.getAttribute('aria-describedby') ?? '') as HTMLElement;
    expect(tip.getAttribute('role')).toBe('tooltip');
    expect(tip.hidden).toBe(true);
    fireEvent.focus(button);
    act(() => vi.advanceTimersByTime(299));
    expect(tip.hidden).toBe(true);
    act(() => vi.advanceTimersByTime(1));
    expect(tip.hidden).toBe(false);
    expect(tip.className).toBe('psl-tip cmp-tip');
    fireEvent.keyDown(button, { key: 'Escape' });
    expect(tip.hidden).toBe(true);
    fireEvent.mouseEnter(button.parentElement as Element);
    act(() => vi.advanceTimersByTime(300));
    expect(tip.hidden).toBe(false);
    vi.useRealTimers();
    expect(await violations()).toEqual([]);
  });
});
