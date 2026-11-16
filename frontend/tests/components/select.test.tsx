// @vitest-environment jsdom
import { fireEvent, render, screen } from '@testing-library/react';
import { useState } from 'react';
import { describe, expect, it } from 'vitest';

import { Select, type SelectOption } from '@/components';

import { violations } from './a11y';

const PEOPLE: SelectOption[] = [
  { value: 'ada', label: 'Ada Okafor', hint: 'Finance Lead', group: 'Finance' },
  { value: 'bisi', label: 'Bisi Adeyemi', hint: 'Finance', group: 'Finance' },
  { value: 'chuka', label: 'Chuka Eze', hint: 'Finance', group: 'Finance' },
  { value: 'dayo', label: 'Dayo Bankole', disabledReason: 'Finance · away until 20 Nov', group: 'Finance' },
];

function Reviewer({ error }: { error?: string }) {
  const [value, setValue] = useState<string | undefined>(undefined);
  return (
    <>
      <Select label="Reviewer" placeholder="Choose a reviewer" options={PEOPLE} value={value} onChange={setValue} error={error} />
      <output>{value ?? 'none'}</output>
    </>
  );
}

const box = () => screen.getByRole('combobox', { name: 'Reviewer' });
const active = () => document.getElementById(box().getAttribute('aria-activedescendant') ?? '');

describe('Select', () => {
  it('closed: placeholder, chevron, error wiring', async () => {
    render(<Reviewer error="Choose who reviews this invoice." />);
    expect(box().className).toBe('psl-input psl-select is-placeholder is-error');
    expect(box().textContent).toBe('Choose a reviewer');
    expect(box().querySelector('.psl-chev')).not.toBeNull();
    expect(box().getAttribute('aria-expanded')).toBe('false');
    expect(await violations()).toEqual([]);
  });

  it('keyboard: arrows, Home/End, typeahead, Enter chooses; Esc closes and keeps focus', async () => {
    render(<Reviewer />);
    box().focus();
    fireEvent.keyDown(box(), { key: 'ArrowDown' });
    expect(box().getAttribute('aria-expanded')).toBe('true');
    expect(screen.getByRole('listbox').className).toContain('psl-pop psl-listbox');
    expect(screen.getByText('FINANCE').className).toBe('psl-optgroup');
    expect(active()?.textContent).toBe('Ada OkaforFinance Lead');
    expect(active()?.className).toBe('psl-option is-active');
    expect(await violations()).toEqual([]);
    fireEvent.keyDown(box(), { key: 'End' });
    expect(active()?.getAttribute('aria-disabled')).toBe('true');
    fireEvent.keyDown(box(), { key: 'Enter' });
    expect(screen.getByText('none')).toBeTruthy();
    fireEvent.keyDown(box(), { key: 'Home' });
    fireEvent.keyDown(box(), { key: 'c' });
    expect(active()?.textContent).toContain('Chuka Eze');
    fireEvent.keyDown(box(), { key: 'Enter' });
    expect(screen.getByText('chuka')).toBeTruthy();
    expect(box().getAttribute('aria-expanded')).toBe('false');
    expect(box().textContent).toBe('Chuka Eze');
    fireEvent.keyDown(box(), { key: 'ArrowDown' });
    expect(screen.getByRole('option', { name: /Chuka Eze/ }).getAttribute('aria-selected')).toBe('true');
    fireEvent.keyDown(box(), { key: 'Escape' });
    expect(screen.queryByRole('listbox')).toBeNull();
    expect(document.activeElement).toBe(box());
  });

  it('the pointer chooses an option; a disabled one stays unchosen', () => {
    render(<Reviewer />);
    fireEvent.click(box());
    fireEvent.click(screen.getByRole('option', { name: /Dayo/ }));
    expect(screen.getByText('none')).toBeTruthy();
    fireEvent.click(screen.getByRole('option', { name: /Bisi/ }));
    expect(screen.getByText('bisi')).toBeTruthy();
  });
});
