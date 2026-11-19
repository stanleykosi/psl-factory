// @vitest-environment jsdom
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { useState } from 'react';
import { describe, expect, it, vi } from 'vitest';

import { BottomSheet, Button, Dialog, Drawer, TextField } from '@/components';

import { violations } from './a11y';

function WithDrawer() {
  const [open, setOpen] = useState(false);
  return (
    <>
      <Button onClick={() => setOpen(true)}>Log change</Button>
      {open && (
        <Drawer
          eyebrow="START WORK"
          title="Scope or timeline change"
          subline="Line chosen from the Start work menu"
          onClose={() => setOpen(false)}
          footer={
            <>
              <Button kind="secondary" size="lg" onClick={() => setOpen(false)}>
                Cancel
              </Button>
              <Button kind="start" size="lg">
                Log change
              </Button>
            </>
          }
        >
          <TextField label="What changes" />
        </Drawer>
      )}
    </>
  );
}

describe('Drawer', () => {
  it('modal from the right: focus moves to the first field and stays in; Esc closes and returns focus', async () => {
    render(<WithDrawer />);
    const opener = screen.getByRole('button', { name: 'Log change' });
    opener.focus();
    fireEvent.click(opener);
    const dialog = screen.getByRole('dialog', { name: 'Scope or timeline change' });
    expect(dialog.className).toBe('psl-drawer cmp-panel');
    expect(dialog.getAttribute('aria-modal')).toBe('true');
    expect(screen.getByText('START WORK').className).toBe('psl-drawer__eyebrow');
    await waitFor(() => expect(document.activeElement).toBe(screen.getByRole('textbox', { name: 'What changes' })));
    expect(await violations()).toEqual([]);
    const buttons = [...dialog.querySelectorAll('button')];
    buttons[buttons.length - 1].focus();
    fireEvent.keyDown(buttons[buttons.length - 1], { key: 'Tab' });
    await waitFor(() => expect(document.activeElement).toBe(buttons[0]));
    fireEvent.keyDown(dialog, { key: 'Escape' });
    expect(screen.queryByRole('dialog')).toBeNull();
    await waitFor(() => expect(document.activeElement).toBe(opener));
  });

  it('the close button and the scrim close it', () => {
    render(<WithDrawer />);
    fireEvent.click(screen.getByRole('button', { name: 'Log change' }));
    fireEvent.click(screen.getByRole('button', { name: 'Close' }));
    expect(screen.queryByRole('dialog')).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: 'Log change' }));
    fireEvent.click(document.querySelector('.psl-scrim') as Element);
    expect(screen.queryByRole('dialog')).toBeNull();
  });

  it('is a full-height sheet below 720px', () => {
    vi.stubGlobal('matchMedia', (q: string) => ({ matches: q.includes('max-width'), media: q, addEventListener() {}, removeEventListener() {} }));
    render(<WithDrawer />);
    fireEvent.click(screen.getByRole('button', { name: 'Log change' }));
    const dialog = screen.getByRole('dialog');
    expect(dialog.className).toBe('psl-sheet cmp-panel cmp-panel--full');
    expect(screen.queryByText('START WORK')).toBeNull();
    expect(dialog.querySelector('.psl-sheet__grab')).not.toBeNull();
    vi.unstubAllGlobals();
  });
});

describe('BottomSheet', () => {
  it('grab handle, title, close; swipe down dismisses', async () => {
    const onClose = vi.fn();
    render(
      <BottomSheet title="Filter" onClose={onClose} footer={<Button size="xl" block>Show 4 results</Button>}>
        <p>Lines</p>
      </BottomSheet>,
    );
    const sheet = screen.getByRole('dialog', { name: 'Filter' });
    expect(sheet.className).toBe('psl-sheet cmp-panel');
    expect(sheet.querySelector('.psl-sheet__grab')).not.toBeNull();
    expect(await violations()).toEqual([]);
    const head = sheet.querySelector('.cmp-swipe') as Element;
    fireEvent.pointerDown(head, { clientY: 100 });
    fireEvent.pointerUp(head, { clientY: 130 });
    expect(onClose).not.toHaveBeenCalled();
    fireEvent.pointerDown(head, { clientY: 100 });
    fireEvent.pointerUp(head, { clientY: 200 });
    expect(onClose).toHaveBeenCalledTimes(1);
    fireEvent.keyDown(sheet, { key: 'Escape' });
    expect(onClose).toHaveBeenCalledTimes(2);
  });
});

describe('Dialog', () => {
  it('an alert dialog; focus starts on Cancel; the destructive action uses the Reject button', async () => {
    const onCancel = vi.fn();
    render(
      <Dialog title="Deactivate Kunle Ade?" actionLabel="Deactivate account" destructive onAction={() => {}} onCancel={onCancel}>
        Kunle can no longer sign in.
      </Dialog>,
    );
    const dialog = screen.getByRole('alertdialog', { name: 'Deactivate Kunle Ade?' });
    expect(dialog.getAttribute('aria-describedby')).toBeTruthy();
    await waitFor(() => expect(document.activeElement).toBe(screen.getByRole('button', { name: 'Cancel' })));
    expect(screen.getByRole('button', { name: 'Deactivate account' }).className).toBe('psl-btn psl-btn--reject');
    expect(await violations()).toEqual([]);
    fireEvent.keyDown(dialog, { key: 'Escape' });
    expect(onCancel).toHaveBeenCalled();
  });
});
