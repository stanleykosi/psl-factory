// @vitest-environment jsdom
import { fireEvent, render, screen } from '@testing-library/react';
import { useState } from 'react';
import { describe, expect, it } from 'vitest';

import { TextArea, TextField } from '@/components';

import { violations } from './a11y';

describe('TextField', () => {
  it('label above, hint below, optional marked; an error replaces the hint and marks the field', async () => {
    const { rerender } = render(<TextField label="PO number" optional hint="From the client’s order." defaultValue="" />);
    const input = screen.getByRole('textbox', { name: 'PO number (optional)' });
    expect(input.className).toBe('psl-input');
    expect(document.getElementById(input.getAttribute('aria-describedby') ?? '')?.textContent).toBe('From the client’s order.');
    rerender(<TextField label="PO number" optional hint="From the client’s order." error="Add the PO number." defaultValue="" />);
    expect(input.className).toBe('psl-input is-error');
    expect(input.getAttribute('aria-invalid')).toBe('true');
    const message = document.getElementById(input.getAttribute('aria-describedby') ?? '');
    expect(message?.className).toBe('psl-error');
    expect(message?.textContent).toBe('Add the PO number.');
    expect(screen.queryByText('From the client’s order.')).toBeNull();
    expect(await violations()).toEqual([]);
  });

  it('phone, disabled and read-only states', () => {
    render(
      <>
        <TextField label="A" phone />
        <TextField label="B" disabled defaultValue="x" />
        <TextField label="C" readOnly defaultValue="y" />
      </>,
    );
    expect(screen.getByRole('textbox', { name: 'A' }).className).toBe('psl-input psl-input--phone');
    expect((screen.getByRole('textbox', { name: 'B' }) as HTMLInputElement).disabled).toBe(true);
    expect((screen.getByRole('textbox', { name: 'C' }) as HTMLInputElement).readOnly).toBe(true);
  });
});

function Note({ limit }: { limit?: number }) {
  const [value, setValue] = useState('');
  return <TextArea label="Reason for returning" value={value} limit={limit} onChange={(e) => setValue(e.target.value)} />;
}

describe('TextArea', () => {
  it('counts against a limit and turns over-limit text into an error without cutting it', async () => {
    render(<Note limit={5} />);
    const area = screen.getByRole('textbox', { name: 'Reason for returning' });
    expect(area.className).toBe('psl-input psl-input--area');
    fireEvent.change(area, { target: { value: 'abc' } });
    expect(screen.getByText('3 / 5').className).toBe('psl-count');
    fireEvent.change(area, { target: { value: 'abcdefg' } });
    expect(screen.getByText('7 / 5').className).toBe('psl-count is-over');
    expect(area.className).toBe('psl-input psl-input--area is-error');
    expect((area as HTMLTextAreaElement).value).toBe('abcdefg');
    expect(area.getAttribute('aria-describedby')).toContain('-count');
    expect(await violations()).toEqual([]);
  });
});
