// @vitest-environment jsdom
import { fireEvent, render, screen } from '@testing-library/react';
import { useState } from 'react';
import { describe, expect, it } from 'vitest';

import { formatAmount, Money, MoneyField } from '@/components';

import { violations } from './a11y';

function Amount({ start = '' as string | null, allowUnknown = false }) {
  const [value, setValue] = useState<string | null>(start);
  return (
    <>
      <MoneyField label="Amount" hint="Before tax." value={value} onChange={setValue} allowUnknown={allowUnknown} />
      <output>{value === null ? 'null' : `[${value}]`}</output>
    </>
  );
}

describe('formatAmount and Money', () => {
  it('two decimals with ₦, never rounded; missing is Unknown, never 0', () => {
    expect(formatAmount('4250000')).toBe('₦4,250,000.00');
    expect(formatAmount('4250000.5')).toBe('₦4,250,000.50');
    expect(formatAmount('0.125')).toBe('₦0.125');
    expect(formatAmount(1500000)).toBe('₦1,500,000.00');
    expect(formatAmount('0')).toBe('₦0.00');
    expect(formatAmount(null)).toBe('Unknown');
    expect(formatAmount(undefined)).toBe('Unknown');
    expect(formatAmount('')).toBe('Unknown');
    expect(formatAmount('abc')).toBe('Unknown');
    expect(formatAmount('2100000', { sign: false })).toBe('2,100,000.00');
  });

  it('Money draws Unknown as the amber tag', () => {
    const { container } = render(
      <>
        <Money value={null} />
        <Money value="10" />
      </>,
    );
    expect(container.querySelector('.psl-unknown')?.textContent).toBe('Unknown');
    expect(container.querySelector('.psl-mono')?.textContent).toBe('₦10.00');
  });
});

describe('MoneyField', () => {
  it('₦ fixed in front, separators as typed, the exact digits kept', async () => {
    render(<Amount />);
    const input = screen.getByRole('textbox', { name: 'Amount' });
    expect(input.closest('.psl-input')?.className).toBe('psl-input psl-input--money cmp-wrapped');
    expect(input.closest('.psl-input')?.querySelector('.psl-affix')?.textContent).toBe('₦');
    expect((input as HTMLInputElement).value).toBe('');
    fireEvent.change(input, { target: { value: '4250000.509' } });
    expect((input as HTMLInputElement).value).toBe('4,250,000.50');
    expect(screen.getByText('[4250000.50]')).toBeTruthy();
    fireEvent.change(input, { target: { value: '12a3' } });
    expect(screen.getByText('[123]')).toBeTruthy();
    expect(await violations()).toEqual([]);
  });

  it('empty is empty, not 0; Unknown is the amber tag and can be undone where allowed', async () => {
    render(<Amount allowUnknown />);
    expect(screen.getByText('[]')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Mark as unknown' }));
    expect(screen.getByText('null')).toBeTruthy();
    const group = screen.getByRole('group', { name: 'Amount' });
    expect(group.querySelector('.psl-unknown')?.textContent).toBe('Unknown');
    expect(screen.queryByText(/0\.00/)).toBeNull();
    expect(await violations()).toEqual([]);
    fireEvent.click(screen.getByRole('button', { name: 'Enter the amount' }));
    expect(screen.getByText('[]')).toBeTruthy();
  });

  it('no Mark as unknown where Unknown is not allowed; read-only contract amounts', () => {
    render(<MoneyField label="Contract amount" hint="From SOW-0031." value="4250000.00" readOnly onChange={() => {}} />);
    expect(screen.queryByRole('button', { name: 'Mark as unknown' })).toBeNull();
    const input = screen.getByRole('textbox', { name: 'Contract amount' }) as HTMLInputElement;
    expect(input.readOnly).toBe(true);
    expect(input.value).toBe('4,250,000.00');
    expect(input.closest('.psl-input')?.classList.contains('is-readonly')).toBe(true);
  });
});
