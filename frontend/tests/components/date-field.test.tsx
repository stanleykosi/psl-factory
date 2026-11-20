// @vitest-environment jsdom
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { useState } from 'react';
import { describe, expect, it } from 'vitest';

import { DateField, formatDate, formatTime, parseDate } from '@/components';

import { violations } from './a11y';

function Payment({ unavailable }: { unavailable?: (iso: string) => string | undefined }) {
  const [value, setValue] = useState('');
  return (
    <>
      <DateField label="Payment date" value={value} onChange={setValue} today="2026-11-13" unavailable={unavailable} />
      <output>{value || 'empty'}</output>
    </>
  );
}

const input = () => screen.getByRole('textbox', { name: 'Payment date' });

describe('dates', () => {
  it('reads 17/11/2026 and 17 Nov 2026, and says what is wrong', () => {
    expect(parseDate('17/11/2026')).toEqual({ iso: '2026-11-17' });
    expect(parseDate('17 Nov 2026')).toEqual({ iso: '2026-11-17' });
    expect(parseDate('17 november 2026')).toEqual({ iso: '2026-11-17' });
    expect(parseDate('31 Nov 2026')).toEqual({ error: 'November has 30 days.' });
    expect(parseDate('soon')).toEqual({ error: 'Write the date as 17 Nov 2026.' });
    expect(formatDate('2026-11-17')).toBe('17 Nov 2026');
    expect(formatDate(null)).toBe('Unknown');
    expect(formatTime('2026-11-17T13:30:00Z')).toBe('14:30 WAT');
  });
});

describe('DateField', () => {
  it('typing a date writes it the README way; a wrong one shows its error', async () => {
    render(<Payment />);
    fireEvent.change(input(), { target: { value: '17/11/2026' } });
    fireEvent.blur(input());
    expect((input() as HTMLInputElement).value).toBe('17 Nov 2026');
    expect(screen.getByText('2026-11-17')).toBeTruthy();
    fireEvent.change(input(), { target: { value: '31 Nov 2026' } });
    fireEvent.blur(input());
    expect(screen.getByText('November has 30 days.')).toBeTruthy();
    expect(input().getAttribute('aria-invalid')).toBe('true');
    expect(screen.getByText('empty')).toBeTruthy();
    expect(await violations()).toEqual([]);
  });

  it('the calendar: today outlined, chosen filled, not-allowed struck through; keys move and choose; Esc returns focus', async () => {
    const weekend = (iso: string) => ([0, 6].includes(new Date(`${iso}T12:00:00Z`).getUTCDay()) ? 'No meetings at weekends' : undefined);
    render(<Payment unavailable={weekend} />);
    const opener = screen.getByRole('button', { name: 'Choose a date' });
    fireEvent.click(opener);
    const dialog = screen.getByRole('dialog', { name: 'Choose a date' });
    expect(dialog.className).toContain('psl-pop psl-cal');
    const today = screen.getByRole('gridcell', { name: '13 November 2026, today' });
    expect(today.className).toBe('psl-day is-today');
    await waitFor(() => expect(document.activeElement).toBe(today));
    expect(screen.getByRole('gridcell', { name: '14 November 2026, No meetings at weekends' }).getAttribute('aria-disabled')).toBe('true');
    expect(await violations()).toEqual([]);
    fireEvent.keyDown(today, { key: 'ArrowRight' });
    fireEvent.keyDown(document.activeElement as Element, { key: 'Enter' });
    expect(screen.getByText('empty')).toBeTruthy();
    fireEvent.keyDown(document.activeElement as Element, { key: 'ArrowDown' });
    await waitFor(() => expect((document.activeElement as HTMLElement).getAttribute('aria-label')).toBe('21 November 2026, No meetings at weekends'));
    fireEvent.keyDown(document.activeElement as Element, { key: 'Home' });
    await waitFor(() => expect((document.activeElement as HTMLElement).getAttribute('aria-label')).toBe('16 November 2026'));
    fireEvent.keyDown(document.activeElement as Element, { key: 'Enter' });
    expect(screen.getByText('2026-11-16')).toBeTruthy();
    expect((input() as HTMLInputElement).value).toBe('16 Nov 2026');
    await waitFor(() => expect(document.activeElement).toBe(opener));
    fireEvent.click(opener);
    expect(screen.getByRole('gridcell', { name: '16 November 2026' }).getAttribute('aria-selected')).toBe('true');
    fireEvent.keyDown(document.activeElement as Element, { key: 'PageDown' });
    expect(screen.getByRole('grid', { name: 'December 2026' })).toBeTruthy();
    fireEvent.keyDown(document.activeElement as Element, { key: 'Escape' });
    expect(screen.queryByRole('dialog')).toBeNull();
    await waitFor(() => expect(document.activeElement).toBe(opener));
  });

  it('a typed day that is not allowed shows the reason', () => {
    render(<Payment unavailable={(iso) => (iso < '2026-11-10' ? 'Receipts can’t be before the milestone.' : undefined)} />);
    fireEvent.change(input(), { target: { value: '1 Nov 2026' } });
    fireEvent.blur(input());
    expect(screen.getByText('Receipts can’t be before the milestone.')).toBeTruthy();
  });
});
