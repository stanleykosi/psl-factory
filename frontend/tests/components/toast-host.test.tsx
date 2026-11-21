// @vitest-environment jsdom
import { act, fireEvent, render, screen } from '@testing-library/react';
import { useState } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { MAX_TOASTS, ToastProvider, useToast, useToastWhen } from '@/components';

import { violations } from './a11y';

beforeEach(() => vi.useFakeTimers());
afterEach(() => vi.useRealTimers());

function Buttons() {
  const toast = useToast();
  const [n, setN] = useState(0);
  return (
    <>
      <button onClick={() => { setN(n + 1); toast.show(`Saved ${n + 1}`); }}>save</button>
      <button onClick={() => toast.show('Moved', { action: { label: 'Undo', onClick: () => toast.show('Undone') } })}>undoable</button>
      <button onClick={() => toast.show('Import stopped', { kind: 'problem', action: { label: 'See', href: '/x' } })}>problem</button>
    </>
  );
}

const setup = () =>
  render(
    <ToastProvider>
      <Buttons />
    </ToastProvider>,
  );
const press = (name: string) => act(() => void fireEvent.click(screen.getByRole('button', { name })));
const flush = () => act(() => void vi.advanceTimersByTime(0));

describe('toast host', () => {
  it('stacks newest at the bottom and keeps at most three', () => {
    setup();
    for (let i = 0; i < 4; i += 1) press('save');
    flush();
    const shown = screen.getAllByRole('status').map((s) => s.textContent);
    expect(MAX_TOASTS).toBe(3);
    expect(shown).toEqual(['Saved 2', 'Saved 3', 'Saved 4']);
  });

  it('dismisses each toast after 6 seconds, longer while hovered or focused', () => {
    setup();
    press('save');
    flush();
    const toast = screen.getByRole('status');
    fireEvent.mouseEnter(toast);
    act(() => void vi.advanceTimersByTime(20000));
    expect(screen.queryByRole('status')).not.toBeNull();
    fireEvent.mouseLeave(toast);
    act(() => void vi.advanceTimersByTime(5999));
    expect(screen.queryByRole('status')).not.toBeNull();
    act(() => void vi.advanceTimersByTime(1));
    expect(screen.queryByRole('status')).toBeNull();

    press('undoable');
    flush();
    fireEvent.focus(screen.getByRole('button', { name: 'Undo' }));
    act(() => void vi.advanceTimersByTime(20000));
    expect(screen.queryByRole('status')).not.toBeNull();
  });

  it('writes the words into a live region that is already drawn, so they are announced', () => {
    setup();
    press('save');
    const toast = screen.getByRole('status');
    expect(toast.textContent).toBe('');
    flush();
    expect(toast.textContent).toBe('Saved 1');
    press('problem');
    expect(screen.getByRole('alert')).not.toBeNull();
  });

  it('never takes focus', () => {
    setup();
    const button = screen.getByRole('button', { name: 'save' });
    button.focus();
    press('save');
    flush();
    expect(document.activeElement).toBe(button);
  });

  it('survives a client-side route change', () => {
    const { rerender } = setup();
    press('save');
    flush();
    rerender(
      <ToastProvider>
        <p>second page</p>
      </ToastProvider>,
    );
    expect(screen.getByText('second page')).not.toBeNull();
    expect(screen.getByRole('status').textContent).toBe('Saved 1');
  });

  it('Undo runs its action and closes the toast', () => {
    setup();
    press('undoable');
    flush();
    press('Undo');
    flush();
    expect(screen.getAllByRole('status').map((s) => s.textContent)).toEqual(['Undone']);
  });

  it('useToastWhen shows a new text once and again after it has cleared', () => {
    function Page({ text }: { text: string | null }) {
      useToastWhen(text);
      return null;
    }
    const view = (text: string | null) => (
      <ToastProvider>
        <Page text={text} />
      </ToastProvider>
    );
    const { rerender } = render(view(null));
    rerender(view('Done once'));
    rerender(view('Done once'));
    flush();
    expect(screen.getAllByRole('status')).toHaveLength(1);
    rerender(view(null));
    rerender(view('Done once'));
    flush();
    expect(screen.getAllByRole('status')).toHaveLength(2);
  });

  describe('on a phone', () => {
    const size = { w: window.innerWidth, h: window.innerHeight };
    beforeEach(() => Object.assign(window, { innerWidth: 390, innerHeight: 844 }));
    afterEach(() => Object.assign(window, { innerWidth: size.w, innerHeight: size.h }));
    const rect = (top: number, bottom: number) => ({ top, bottom, left: 16, right: 374, width: 358, height: bottom - top, x: 16, y: top, toJSON: () => ({}) });
    const lift = () => document.querySelector<HTMLElement>('.cmp-toasts')?.style.getPropertyValue('--toast-lift');

    it('lifts above a fixed bar on the page', () => {
      render(
        <ToastProvider>
          <main>
            <Buttons />
            <div data-testid="bar" style={{ position: 'fixed' }} />
          </main>
        </ToastProvider>,
      );
      vi.spyOn(screen.getByTestId('bar'), 'getBoundingClientRect').mockReturnValue(rect(747, 844) as DOMRect);
      press('save');
      expect(lift()).toBe('97px');
    });

    it("lifts above an open drawer's sticky action bar, not the page's bar behind it (the bar may end above the edge)", () => {
      render(
        <ToastProvider>
          <main>
            <Buttons />
            <div data-testid="page-bar" style={{ position: 'fixed' }} />
          </main>
          <div style={{ position: 'fixed' }}>
            <aside role="dialog" aria-modal="true" aria-label="Register engagement">
              <div data-testid="actions" style={{ position: 'sticky' }} />
            </aside>
          </div>
        </ToastProvider>,
      );
      vi.spyOn(screen.getByTestId('page-bar'), 'getBoundingClientRect').mockReturnValue(rect(747, 844) as DOMRect);
      vi.spyOn(screen.getByTestId('actions'), 'getBoundingClientRect').mockReturnValue(rect(724, 830) as DOMRect);
      press('save');
      expect(lift()).toBe('120px');
    });
  });

  it('has no accessibility violations', async () => {
    vi.useRealTimers();
    setup();
    press('undoable');
    await act(async () => void (await new Promise((r) => setTimeout(r, 5))));
    expect(await violations()).toEqual([]);
  });
});
